"""GitHub Ready work -> local Codex bridge. No third-party Python dependencies."""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

STATE_REF = 'refs/heads/codex/dispatch-state'
ROLES = {'Implementer', 'Tester / Playtester', 'Docs / Traceability'}
RETRYABLE = {'quota', 'execution_error', 'timeout'}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {
    'outcome': {'type': 'string', 'enum': ['Review', 'Blocked']},
    'summary': {'type': 'string'}, 'validation': {'type': 'string'},
    'decision_owner': {'type': 'string'}, 'question': {'type': 'string'},
    'options_and_tradeoffs': {'type': 'string'}, 'recommendation': {'type': 'string'}},
    'required': ['outcome', 'summary', 'validation', 'decision_owner', 'question',
                 'options_and_tradeoffs', 'recommendation']}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run(args, cwd=None, input=None, check=True, env=None):
    p = subprocess.run(args, cwd=cwd, input=input, text=True, encoding='utf-8',
                       errors='replace', capture_output=True, env=env, timeout=120)
    if check and p.returncode:
        raise RuntimeError(f'{args[0]} failed ({p.returncode}): {p.stderr[-1500:]}')
    return p


def git(repo, *args, input=None, check=True):
    return run(['git', '-C', str(repo), *args], input=input, check=check)


@contextlib.contextmanager
def host_lock(root):
    """OS lock releases on parent exit. Durable running claim still prevents crash replay."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'host.lock').open('a+b') as f:
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            f.write(b'0')
            f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == 'nt':
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


class Store:
    """One JSON document in an orphan Git branch; non-force push is compare-and-swap."""
    def __init__(self, path, remote):
        self.path = Path(path)
        if not self.path.exists():
            run(['git', 'init', '--bare', str(self.path)])
            git(self.path, 'remote', 'add', 'origin', remote)
        if git(self.path, 'remote', 'get-url', 'origin').stdout.strip() != remote:
            raise RuntimeError('Unexpected state-store remote')
        git(self.path, 'config', 'user.name', 'github-codex-ready-work-dispatch')
        git(self.path, 'config', 'user.email', 'bridge@users.noreply.github.com')

    def read(self):
        refs = git(self.path, 'ls-remote', '--heads', 'origin', STATE_REF).stdout.strip()
        if not refs:
            return None, {'schema_version': 1, 'paused': None, 'claims': {}}
        git(self.path, 'fetch', '--quiet', 'origin', STATE_REF)
        revision = git(self.path, 'rev-parse', 'FETCH_HEAD').stdout.strip()
        state = json.loads(git(self.path, 'show', f'{revision}:state.json').stdout)
        if state.get('schema_version') != 1:
            raise RuntimeError('Unknown dispatch-state schema')
        return revision, state

    def write(self, revision, state, message):
        blob = git(self.path, 'hash-object', '-w', '--stdin',
                   input=json.dumps(state, ensure_ascii=False, indent=2) + '\n').stdout.strip()
        # NUL delimiter avoids Windows text-pipe CRLF becoming part of the filename.
        tree = git(self.path, 'mktree', '-z', input=f'100644 blob {blob}\tstate.json\0').stdout.strip()
        parents = ['-p', revision] if revision else []
        commit = git(self.path, 'commit-tree', tree, *parents, '-m', message).stdout.strip()
        result = git(self.path, 'push', '--porcelain', 'origin', f'{commit}:{STATE_REF}', check=False)
        if result.returncode:
            # No retry on uncertain writes: refetch/reconcile on a subsequent invocation.
            raise RuntimeError('State publication failed or claim conflict; no agent may start')
        return commit

    def patch(self, wi, attempt, **fields):
        revision, state = self.read()
        record = state['claims'][wi]
        if record['attempt_id'] != attempt:
            raise RuntimeError('Claim ownership changed')
        record.update(fields, updated_at=now())
        self.write(revision, state, f'{wi}: {fields.get("status", "heartbeat")}')


def parse_wi(path, text, work_items_path='docs/work-items'):
    prefix = re.escape(work_items_path.rstrip('/'))
    match = re.fullmatch(prefix + r'/(WI-\d+)-[\w-]+\.md', path)
    if not match:
        return None
    def field(name):
        values = re.findall(rf'^{re.escape(name)}:\s*([^\r\n]+)', text, re.M)
        return values[0].strip() if len(values) == 1 else None
    if field('Status') != 'Ready':
        return None
    role = field('Owner Role') or 'Implementer'
    if role not in ROLES:
        return None
    tier = field('Capability Tier') or 'T2 Standard'
    if not re.match(r'^T[12](?:\b| )', tier):
        return None
    required = ('Goal', 'Acceptance criteria')
    headings = '\n'.join(re.findall(r'^## .+$', text, re.M)).lower()
    if any(word.lower() not in headings for word in required):
        return None
    return {'wi': match[1], 'path': path, 'role': role, 'tier': tier}


def acquire(state, candidate, run_url, retry=False):
    """Pure gate, also exercised under conflicting remote writes in integration tests."""
    state = copy.deepcopy(state)
    records = state['claims']
    old = records.get(candidate['wi'])
    if any(x['status'] == 'running' for x in records.values()):
        return None
    if retry:
        if not old or old['status'] not in RETRYABLE:
            raise RuntimeError('Retry requires a stopped quota/error/timeout claim')
        if old['wi_blob'] != candidate['wi_blob']:
            raise RuntimeError('WI changed since attempt; reconcile scope before retry')
        if old.get('base_sha') != candidate.get('base_sha'):
            raise RuntimeError('Main changed since attempt; reconcile and rebase before retry')
        if state['paused'] and state['paused']['wi'] != candidate['wi']:
            raise RuntimeError('Another work item owns the pause')
    elif state['paused'] or old:
        return None
    record = dict(candidate)
    record.update(attempt_id=uuid.uuid4().hex, status='running', owner='codex-local',
                  run_url=run_url, started_at=now(), updated_at=now(), thread_id=None,
                  history=(old.get('history', []) + [old]) if old else [])
    # Avoid recursively embedding history in retry snapshots.
    for item in record['history']:
        item.pop('history', None)
    if retry:
        record.update(branch=old['branch'], checkout=old['checkout'], thread_id=old.get('thread_id'))
    records[candidate['wi']] = record
    state['paused'] = None
    return state


def classify(exit_code, events, stderr='', timed_out=False):
    if timed_out:
        return 'timeout'
    errors = [x for x in events if x.get('type') in {'error', 'turn.failed'}]
    error_text = json.dumps(errors).lower()
    if exit_code:
        error_text += stderr.lower()
    if re.search(r'usage.limit|quota|insufficient_quota|rate.limit|too many requests|\b429\b', error_text):
        return 'quota'
    if exit_code or errors or not any(x.get('type') == 'turn.completed' for x in events):
        return 'execution_error'
    return 'completed'


def validate_result(result):
    if not isinstance(result, dict) or set(result) != set(SCHEMA['required']):
        raise ValueError('Malformed agent result')
    if any(not isinstance(v, str) for v in result.values()):
        raise ValueError('Non-string result field')
    if result['outcome'] not in {'Review', 'Blocked'} or not result['summary'].strip():
        raise ValueError('Missing supported outcome/summary')
    if result['outcome'] == 'Blocked' and not (result['question'].strip() and result['decision_owner'].strip()):
        raise ValueError('Blocked requires question and decision owner')
    return result


def child_environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('GITHUB_', 'ACTIONS_', 'RUNNER_')) or key in {'GH_TOKEN', 'BRIDGE_TOKEN'}:
            del env[key]
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        result = run(['taskkill', '/PID', str(process.pid), '/T', '/F'], check=False)
        if result.returncode and process.poll() is None:
            process.kill()
    else:
        process.kill()
    process.wait(timeout=30)


def execute(command, prompt, folder, log_dir, timeout, on_event, heartbeat):
    events, timed_out = [], False
    lines = queue.Queue()
    with (log_dir / 'stderr.log').open('w', encoding='utf-8') as err, \
            (log_dir / 'events.jsonl').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=err, text=True, encoding='utf-8', env=child_environment())
        try:
            process.stdin.write(prompt)
            process.stdin.close()
            def reader():
                for line in process.stdout:
                    lines.put(line)
                lines.put(None)
            threading.Thread(target=reader, daemon=True).start()
            start = last_heartbeat = time.monotonic()
            while True:
                if time.monotonic() - start > timeout:
                    timed_out = True
                    stop_process(process)
                    break
                if time.monotonic() - last_heartbeat > 120:
                    heartbeat()
                    last_heartbeat = time.monotonic()
                try:
                    line = lines.get(timeout=1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                log.write(line)
                log.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events.append(event)
                on_event(event)
            code = process.wait(timeout=30)
        finally:
            stop_process(process)
            process.stdout.close()
    stderr = (log_dir / 'stderr.log').read_text(encoding='utf-8')
    return classify(code, events, stderr, timed_out), code


def set_status(path, status):
    text = path.read_text(encoding='utf-8')
    text, count = re.subn(r'^Status: [^\r\n]+', 'Status: ' + status, text, flags=re.M)
    if count != 1:
        raise RuntimeError('Ambiguous work item status')
    path.write_text(text, encoding='utf-8')


def checkpoint(folder, branch, message):
    if git(folder, 'branch', '--show-current').stdout.strip() != branch:
        raise RuntimeError('Agent changed branch; preserve checkout for recovery')
    git(folder, 'add', '--all')
    if git(folder, 'diff', '--cached', '--quiet', check=False).returncode:
        git(folder, 'commit', '-m', message)
    git(folder, 'push', '-u', 'origin', f'HEAD:refs/heads/{branch}')
    return git(folder, 'rev-parse', 'HEAD').stdout.strip()


def create_pr(config, folder, record, result):
    token = os.environ.get('BRIDGE_TOKEN')
    if not token:
        return {'pr_note': 'No PR token; use the published compare link.'}
    template = folder / '.github' / 'pull_request_template.md'
    body = template.read_text(encoding='utf-8') if template.exists() else ''
    body = body.replace('Issue:  ', f'Issue: {record["path"]}  ')
    body = body.replace('## What changed\n\n-', '## What changed\n\n' + result['summary'])
    body = body.replace('## What did NOT change\n\n-', '## What did NOT change\n\nNo approval or automatic merge is granted by this dispatcher.')
    body = body.replace('## Known limitations\n\n-', '## Known limitations\n\nAgent evidence requires independent review.\n\n' + result['validation'])
    body += f'\n\nDispatch evidence: {record["run_url"]}\n'
    data = json.dumps({'title': f'{record["wi"]}: {result["outcome"]} requested',
                       'head': record['branch'], 'base': config.get('base_branch', 'main'), 'body': body, 'draft': True}).encode()
    request = urllib.request.Request(f'https://api.github.com/repos/{config["repository"]}/pulls', data=data,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'github-codex-ready-work-dispatch'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {'pr_url': json.load(response)['html_url']}
    except Exception as error:
        # Work is already durable. Never rerun an agent because PR creation failed.
        return {'pr_note': f'PR creation unavailable ({type(error).__name__}); use compare link.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--retry-wi', default='')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    root = Path(config['root']).resolve()
    if args.retry_wi and not re.fullmatch(r'WI-\d+', args.retry_wi):
        raise ValueError('Invalid retry WI')
    with host_lock(Path(config.get('host_lock_root', str(root))).resolve()):
        store = Store(root / 'store.git', config['remote'])
        version = run([config['codex'], '--version']).stdout.strip()
        if version != config['codex_version']:
            raise RuntimeError('Codex version changed; validate bridge before dispatch')
        run_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com') + '/' + config['repository'] + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', 'local')
        deadline = time.monotonic() + config.get('batch_seconds', 14400)
        for _ in range(config.get('max_items', 10)):
            if time.monotonic() >= deadline:
                break
            git(store.path, 'fetch', '--quiet', 'origin', 'refs/heads/' + config.get('base_branch', 'main'))
            base = git(store.path, 'rev-parse', 'FETCH_HEAD').stdout.strip()
            candidates = []
            work_items_path = config.get('work_items_path', 'docs/work-items').strip('/')
            paths = git(store.path, 'ls-tree', '-r', '--name-only', base, work_items_path).stdout.splitlines()
            for path in paths:
                item = parse_wi(path, git(store.path, 'show', f'{base}:{path}').stdout, work_items_path)
                if item:
                    item.update(base_sha=base, wi_blob=git(store.path, 'rev-parse', f'{base}:{path}').stdout.strip())
                    candidates.append(item)
            revision, state = store.read()
            if state['paused'] and not args.retry_wi:
                print('Dispatch paused: ' + json.dumps(state['paused']))
                return 0
            chosen = None
            for item in sorted(candidates, key=lambda x: x['wi']):
                if args.retry_wi and item['wi'] != args.retry_wi:
                    continue
                claimed = acquire(state, item, run_url, bool(args.retry_wi))
                if claimed:
                    chosen = claimed['claims'][item['wi']]
                    chosen.setdefault('branch', 'codex/auto-' + item['wi'].lower() + '-' + chosen['attempt_id'][:8])
                    chosen.setdefault('checkout', str(root / 'work' / chosen['attempt_id']))
                    store.write(revision, claimed, f'{item["wi"]}: claim before execution')
                    break
            if not chosen:
                print('No eligible unclaimed Ready work; no agent started.')
                return 0
            run_one(config, root, store, chosen, bool(args.retry_wi))
            args.retry_wi = ''
        return 0


def run_one(config, root, store, record, retry):
    wi, attempt = record['wi'], record['attempt_id']
    folder = Path(record['checkout']).resolve()
    if not folder.is_relative_to(root / 'work'):
        raise RuntimeError('Checkout outside bridge work directory')
    log_dir = root / 'logs' / attempt
    log_dir.mkdir(parents=True)
    schema_path = log_dir / 'schema.json'
    schema_path.write_text(json.dumps(SCHEMA), encoding='utf-8')
    answer_path = log_dir / 'answer.json'
    status = 'execution_error'
    result = None
    try:
        git(store.path, 'fetch', '--quiet', 'origin', 'refs/heads/' + config.get('base_branch', 'main'))
        current_main = git(store.path, 'rev-parse', 'FETCH_HEAD').stdout.strip()
        if current_main != record['base_sha']:
            raise RuntimeError('Main changed between selection and launch; reconcile running claim before retry')
        if retry:
            if not folder.exists() or git(folder, 'status', '--porcelain').stdout:
                raise RuntimeError('Retry checkout missing/dirty; preserve and reconcile before retry')
        else:
            run(['git', 'clone', '--quiet', '--no-checkout', config['remote'], str(folder)])
            git(folder, 'checkout', '-b', record['branch'], record['base_sha'])
            git(folder, 'config', 'user.name', 'github-codex-ready-work-dispatch')
            git(folder, 'config', 'user.email', 'bridge@users.noreply.github.com')
        # Populate the host's pinned dependencies for both fresh and resumed work.
        git(folder, 'submodule', 'update', '--init', '--recursive')
        set_status(folder / record['path'], 'In Progress')
        prepared_head = checkpoint(folder, record['branch'], f'{wi}: start authorized implementation')
        store.patch(wi, attempt, prepared_head=prepared_head)
        prompt = f'''Act as {record['role']} at capability tier {record['tier']} for {record['path']} only.
The Product Owner authorized this repository-backed Ready work through the dispatch protocol.
Read the work item and any governance files that exist in the host repository, including AGENTS.md, docs/PROJECT_STATE.md and docs/WORKFLOW.md when present.
The bridge checked out {config.get('base_branch', 'main')} {record['base_sha']}, claimed this WI on codex/dispatch-state, changed its status to In Progress, and pushed a clean work branch with matching upstream at {prepared_head}. These are known bridge changes. Under the automated-entry Safe Sync provision in AGENTS.md, verify local status/HEAD against this supplied prepared_head; the bridge has completed network synchronization. No redundant network pull is needed for this invocation.
Verify semantic Ready gates, dependencies, approval authority and any Issue/Project mirrors before implementation. Do not treat Draft specs as approved. If gates fail, report Blocked with owner/options/tradeoffs.
Do the bounded work, tests and evidence. Preserve acceptance criteria. Do not merge, change branches, start other tasks, modify bridge state, or buy credits/use a reset. Do not push or create PRs: the bridge checkpoints this isolated work and publishes the result for review.
Do not change WI lifecycle status yourself; the bridge applies your Review/Blocked result and evidence. You cannot approve your own work or claim Done. Escalate decisions outside authority in the structured result.
If sandbox permissions prevent a necessary step, report Blocked; do not bypass protections.
Return the required JSON result. Empty decision fields are allowed only for Review.
'''
        # --ignore-user-config also drops windows.sandbox. Select the already provisioned
        # restricted-user backend explicitly; do not fall back to unsandboxed execution.
        command = [config['codex'], 'exec', '--sandbox', 'workspace-write',
                   '-c', 'windows.sandbox="elevated"']
        if retry and record.get('thread_id'):
            command += ['resume']
        command += ['--ignore-user-config', '--json', '--output-schema', str(schema_path),
                    '--output-last-message', str(answer_path)]
        if retry and record.get('thread_id'):
            command += [record['thread_id']]
        command += ['-']
        def event_hook(event):
            if event.get('type') == 'thread.started':
                thread = event.get('thread_id', '')
                uuid.UUID(thread)
                store.patch(wi, attempt, thread_id=thread)
        status, code = execute(command, prompt, folder, log_dir, config.get('task_seconds', 2700),
                               event_hook, lambda: store.patch(wi, attempt, heartbeat_at=now()))
        if status == 'completed':
            result = validate_result(json.loads(answer_path.read_text(encoding='utf-8')))
            status = result['outcome'].lower()
        else:
            result = {'outcome': 'Blocked', 'summary': f'Agent stopped: {status} (exit {code}).',
                      'validation': 'Incomplete; inspect preserved checkout and local logs.',
                      'decision_owner': 'Workflow coordinator', 'question': 'Restore capacity or resolve the execution failure before explicit retry.',
                      'options_and_tradeoffs': 'Wait for quota reset and retry this WI; investigate other failures. No automatic retry or purchase.',
                      'recommendation': 'Preserve this attempt and resume only after the cause is resolved.'}
        set_status(folder / record['path'], result['outcome'])
        report_dir = folder / 'docs' / 'automation' / 'results'
        report_dir.mkdir(parents=True, exist_ok=True)
        report = report_dir / f'{wi}-{attempt[:8]}.md'
        report.write_text(f'# {wi} execution result\n\nRun: {record["run_url"]}\n\n' +
                          '\n\n'.join(f'## {k}\n\n{v}' for k, v in result.items()) + '\n', encoding='utf-8')
        with (folder / record['path']).open('a', encoding='utf-8') as out:
            out.write(f'\n## Automated execution evidence\n\nSee `{report.relative_to(folder).as_posix()}`.\n')
        if result['outcome'] == 'Blocked':
            escalation = folder / 'docs' / 'escalations' / f'ESC-{wi}-{attempt[:8]}.md'
            escalation.parent.mkdir(parents=True, exist_ok=True)
            escalation.write_text(f'# Escalation for {wi}\n\nStatus: Open\nOwner: {result["decision_owner"]}\nWork item: {record["path"]}\n\n' +
                                  '\n\n'.join(f'## {k}\n\n{result[k]}' for k in ['question', 'options_and_tradeoffs', 'recommendation']) + '\n', encoding='utf-8')
        commit = checkpoint(folder, record['branch'], f'{wi}: preserve {status} result')
        git(store.path, 'fetch', '--quiet', 'origin', 'refs/heads/' + config.get('base_branch', 'main'))
        current_main = git(store.path, 'rev-parse', 'FETCH_HEAD').stdout.strip()
        fields = {'status': status, 'result_commit': commit, 'summary': result['summary'],
                  'result_path': report.relative_to(folder).as_posix(),
                  'review_url': f'https://github.com/{config["repository"]}/compare/{config.get('base_branch', 'main')}...{record["branch"]}',
                  'finished_at': now(), 'base_changed_during_work': current_main != record['base_sha']}
        fields.update(create_pr(config, folder, record, result))
        revision, state = store.read()
        if state['claims'][wi]['attempt_id'] != attempt:
            raise RuntimeError('Claim changed before completion publication')
        state['claims'][wi].update(fields, updated_at=now())
        if status in RETRYABLE:
            state['paused'] = {'wi': wi, 'reason': status, 'since': now(), 'retry': 'Explicit workflow_dispatch retry_wi after recovery'}
        store.write(revision, state, f'{wi}: {status}')
        print(f'{wi}: {status}; {fields["review_url"]}')
    except Exception:
        # Fail closed. Do not rewrite an uncertain published claim or delete work/logs.
        # A remaining running claim fences all new work until coordinator reconciliation.
        (log_dir / 'recovery.txt').write_text('Bridge interrupted. Preserve checkout; inspect GitHub claim and logs before manual recovery.\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'Bridge stopped safely: {error}', file=sys.stderr)
        sys.exit(1)
