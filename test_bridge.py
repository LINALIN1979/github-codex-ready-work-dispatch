import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from bridge import Store, acquire, classify, parse_wi, validate_result, host_lock, child_environment, execute, SCHEMA, run_one, git


class Gates(unittest.TestCase):
    def setUp(self):
        self.item = {'wi': 'WI-005', 'wi_blob': 'abc', 'path': 'docs/work-items/WI-005-test.md'}
        self.state = {'schema_version': 1, 'paused': None, 'claims': {}}

    def test_ready_role_and_closed_state(self):
        text = 'Status: Ready\n## Goal\nDo it\n## Acceptance criteria\n- It works\n'
        item = parse_wi(self.item['path'], text)
        self.assertEqual(item['role'], 'Implementer')
        self.assertEqual(item['tier'], 'T2 Standard')
        self.assertEqual(parse_wi('work/WI-005-test.md', text, 'work')['wi'], 'WI-005')
        for changed in [text.replace('Ready', 'Review'), text + 'Owner Role: Art Designer\n',
                        text + 'Capability Tier: T3 Deep\n', text + 'Status: Ready\n',
                        text.replace('## Goal', '## Intent')]:
            self.assertIsNone(parse_wi(self.item['path'], changed))

    def test_duplicate_and_crashed_claim_never_replayed(self):
        claimed = acquire(self.state, self.item, 'test-run')
        self.assertIsNone(acquire(claimed, self.item, 'duplicate'))
        other = dict(self.item, wi='WI-006')
        self.assertIsNone(acquire(claimed, other, 'other'))
        claimed['claims']['WI-005']['status'] = 'review'
        self.assertIsNone(acquire(claimed, self.item, 'duplicate-after-finish'))

    def test_quota_pause_and_explicit_retry(self):
        claimed = acquire(self.state, self.item, 'run')
        claimed['claims']['WI-005'].update(status='quota', branch='codex/test', checkout='saved', thread_id='saved-task')
        claimed['paused'] = {'wi': 'WI-005', 'reason': 'quota'}
        self.assertIsNone(acquire(claimed, dict(self.item, wi='WI-006'), 'next'))
        retried = acquire(claimed, self.item, 'retry', retry=True)
        self.assertEqual(retried['claims']['WI-005']['thread_id'], 'saved-task')
        self.assertIsNone(retried['paused'])
        with self.assertRaises(RuntimeError):
            acquire(claimed, dict(self.item, wi_blob='changed'), 'stale', retry=True)

    def test_failure_classification_does_not_parse_normal_agent_text(self):
        self.assertEqual(classify(1, [{'type': 'error', 'message': 'usage limit reached'}]), 'quota')
        self.assertEqual(classify(1, [], 'HTTP 429'), 'quota')
        self.assertEqual(classify(0, []), 'execution_error')
        self.assertEqual(classify(0, [{'type': 'turn.completed'}], timed_out=True), 'timeout')
        self.assertEqual(classify(0, [{'type': 'item.completed', 'text': 'quota'}, {'type': 'turn.completed'}]), 'completed')

    def test_result_validation(self):
        valid = dict.fromkeys(SCHEMA['required'], '')
        valid.update(outcome='Review', summary='Verified')
        self.assertEqual(validate_result(valid), valid)
        for changed in [dict(valid, outcome='Done'), dict(valid, outcome='Blocked'), {}, dict(valid, summary=3)]:
            with self.assertRaises(ValueError):
                validate_result(changed)

    def test_child_does_not_inherit_actions_tokens(self):
        with patch.dict(os.environ, {'BRIDGE_TOKEN': 'secret', 'ACTIONS_RUNTIME_TOKEN': 'secret', 'GITHUB_TOKEN': 'secret'}):
            self.assertFalse({'BRIDGE_TOKEN', 'ACTIONS_RUNTIME_TOKEN', 'GITHUB_TOKEN'} & child_environment().keys())

    def test_host_lock_excludes_a_second_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            with host_lock(Path(tmp)):
                child = subprocess.run([sys.executable, '-c',
                    'from pathlib import Path; from bridge import host_lock; '
                    'ctx=host_lock(Path(' + repr(tmp) + ')); ctx.__enter__()'],
                    cwd=Path(__file__).parent, capture_output=True)
                self.assertNotEqual(child.returncode, 0)
            with host_lock(Path(tmp)):
                pass

    def test_real_process_quota_and_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fake = folder / 'fake.py'
            fake.write_text('import sys,json\nsys.stdin.read()\nprint(json.dumps({"type":"error","message":"usage limit reached"}))\nsys.exit(1)\n')
            status, _ = execute([sys.executable, str(fake)], 'test', folder, folder, 10, lambda e: None, lambda: None)
            self.assertEqual(status, 'quota')
            fake.write_text('import sys,time\nsys.stdin.read()\ntime.sleep(30)\n')
            status, _ = execute([sys.executable, str(fake)], 'test', folder, folder, .1, lambda e: None, lambda: None)
            self.assertEqual(status, 'timeout')


class RemoteCAS(unittest.TestCase):
    def test_result_and_quota_are_published_without_second_agent(self):
        for outcome, base_branch in [('completed', 'main'), ('quota', 'main'), ('completed', 'develop')]:
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                remote, seed = root / 'remote.git', root / 'seed'
                subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
                subprocess.run(['git', 'init', '-b', base_branch, str(seed)], check=True, capture_output=True)
                git(seed, 'config', 'user.name', 'Test')
                git(seed, 'config', 'user.email', 'test@example.invalid')
                dependency = root / 'dependency'
                subprocess.run(['git', 'init', str(dependency)], check=True, capture_output=True)
                git(dependency, 'config', 'user.name', 'Test')
                git(dependency, 'config', 'user.email', 'test@example.invalid')
                (dependency / 'sentinel.txt').write_text('pinned dependency')
                git(dependency, 'add', '.')
                git(dependency, 'commit', '-m', 'dependency fixture')
                git(seed, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(dependency), 'tools/dependency')
                path = 'docs/work-items/WI-005-fixture.md'
                (seed / path).parent.mkdir(parents=True)
                (seed / path).write_text('Status: Ready\n')
                git(seed, 'add', '.')
                git(seed, 'commit', '-m', 'fixture')
                git(seed, 'remote', 'add', 'origin', str(remote))
                git(seed, 'push', '-u', 'origin', base_branch)
                store = Store(root / 'data' / 'store.git', str(remote))
                revision, state = store.read()
                item = {'wi': 'WI-005', 'path': path, 'wi_blob': git(seed, 'rev-parse', 'HEAD:' + path).stdout.strip(),
                        'base_sha': git(seed, 'rev-parse', 'HEAD').stdout.strip(), 'role': 'Tester / Playtester', 'tier': 'T1'}
                claimed = acquire(state, item, 'fixture-run')
                record = claimed['claims']['WI-005']
                record.update(branch='codex/test', checkout=str(root / 'data' / 'work' / 'fixture'))
                store.write(revision, claimed, 'claim')
                def fake_execute(command, prompt, folder, log_dir, timeout, on_event, heartbeat):
                    self.assertEqual((folder / 'tools/dependency/sentinel.txt').read_text(), 'pinned dependency')
                    self.assertIn('windows.sandbox="elevated"', command)
                    self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', command)
                    on_event({'type': 'thread.started', 'thread_id': '11111111-1111-4111-8111-111111111111'})
                    (folder / 'partial.txt').write_text('preserved work')
                    answer = dict.fromkeys(SCHEMA['required'], '')
                    answer.update(outcome='Review', summary='fixture verified')
                    (log_dir / 'answer.json').write_text(json.dumps(answer))
                    return outcome, 0 if outcome == 'completed' else 1
                config = {'remote': str(remote), 'repository': 'fixture/repo', 'codex': 'unused', 'base_branch': base_branch}
                with patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'always'}), patch('bridge.execute', side_effect=fake_execute), patch('bridge.create_pr', return_value={}):
                    run_one(config, root / 'data', store, record, False)
                _, final = store.read()
                self.assertEqual(final['claims']['WI-005']['status'], 'review' if outcome == 'completed' else 'quota')
                self.assertIn('/compare/' + base_branch + '...', final['claims']['WI-005']['review_url'])
                self.assertEqual(final['claims']['WI-005']['thread_id'], '11111111-1111-4111-8111-111111111111')
                self.assertIsNone(acquire(final, item, 'duplicate'))
                self.assertIn('preserved work', git(seed, '--git-dir=' + str(remote), 'show', 'codex/test:partial.txt').stdout)
                if outcome == 'quota':
                    self.assertEqual(final['paused']['reason'], 'quota')

    def test_same_wi_is_independent_across_host_remotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ['host-a', 'host-b']:
                remote = root / (name + '.git')
                subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
                store = Store(root / (name + '-store.git'), str(remote))
                revision, state = store.read()
                state = acquire(state, {'wi': 'WI-001', 'wi_blob': 'same'}, name)
                store.write(revision, state, 'independent host claim')
                self.assertEqual(store.read()[1]['claims']['WI-001']['run_url'], name)
            with self.assertRaises(RuntimeError):
                Store(root / 'host-a-store.git', str(root / 'host-b.git'))

    def test_conflicting_claims_only_one_push_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / 'remote.git'
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            first, second = Store(root / 'one.git', str(remote)), Store(root / 'two.git', str(remote))
            rev1, state1 = first.read()
            rev2, state2 = second.read()
            item = {'wi': 'WI-005', 'wi_blob': 'a'}
            first.write(rev1, acquire(state1, item, 'first'), 'claim')
            with self.assertRaises(RuntimeError):
                second.write(rev2, acquire(state2, item, 'second'), 'claim')
            _, observed = second.read()
            self.assertEqual(observed['claims']['WI-005']['run_url'], 'first')
            self.assertIsNone(acquire(observed, item, 'duplicate'))
            oldrev, state = first.read()
            otherrev, otherstate = second.read()
            state['claims']['WI-005']['status'] = 'quota'
            first.write(oldrev, state, 'quota')
            with self.assertRaises(RuntimeError):
                second.write(otherrev, otherstate, 'stale writer')


if __name__ == '__main__':
    unittest.main()
