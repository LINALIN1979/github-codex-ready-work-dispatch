import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from bridge import (CoordinationStore, claim_coordination_execution, run_revision,
                    process_coordination,
                    validate_coordination_command, validate_coordination_context,
                    verify_coordination_actor)


BASE = '1' * 40
BLOB = '2' * 40
HEAD = '3' * 40
ATTEMPT = '4' * 32
TASK = '11111111-1111-4111-8111-111111111111'


def completed(value='', returncode=0):
    class Result:
        stdout = value
        stderr = ''
    result = Result()
    result.returncode = returncode
    return result


class FakeStateStore:
    def __init__(self, state, path='store'):
        self.state = state
        self.path = Path(path)
        self.writes = []
        self.patches = []

    def read(self):
        return 'a' * 40, copy.deepcopy(self.state)

    def write(self, revision, state, message):
        self.state = copy.deepcopy(state)
        self.writes.append((revision, message))

    def patch(self, wi, attempt, **fields):
        self.state['claims'][wi].update(fields)
        self.patches.append((wi, attempt, fields))


class CoordinationCommandTests(unittest.TestCase):
    def setUp(self):
        self.feedback = 'Please tighten the existing validation; do not change scope.'
        self.config = {
            'repository': 'fixture/repo', 'remote': 'fixture.git', 'base_branch': 'main',
            'codex': 'codex.exe',
            'trusted_coordination_actors': ['owner'],
            'trusted_coordination_roles': ['Technical Planner'],
            'coordination_authority_ref': 'ADR-007',
        }
        self.command = {
            'schema_version': 1, 'command_id': 'cmd-001', 'action': 'revise',
            'repository': 'fixture/repo', 'wi_path': 'docs/work-items/WI-001-test.md',
            'wi_blob': BLOB, 'base_sha': BASE, 'attempt_id': ATTEMPT,
            'task_id': TASK, 'checkout': 'unused', 'work_branch': 'codex/test',
            'pr_number': 7, 'expected_pr_head': HEAD,
            'feedback_ref': 'https://github.com/fixture/repo/pull/7#review-1',
            'feedback_sha256': hashlib.sha256(self.feedback.encode()).hexdigest(),
            'feedback': self.feedback, 'issuer_actor': 'owner',
            'active_role': 'Technical Planner', 'authority_ref': 'ADR-007',
            'created_at': '2026-09-08T01:00:00+00:00',
        }

    def test_closed_schema_actor_role_digest_and_action(self):
        self.assertIs(validate_coordination_command(self.config, 'cmd-001', self.command), self.command)
        for key, value in (
                ('issuer_actor', 'attacker'), ('active_role', 'Product Owner'),
                ('authority_ref', 'chat-comment'), ('feedback_sha256', '0' * 64),
                ('repository', 'other/repo'), ('action', 'merge')):
            changed = dict(self.command, **{key: value})
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                validate_coordination_command(self.config, 'cmd-001', changed)
        changed = dict(self.command)
        changed['extra'] = 'not allowed'
        with self.assertRaises(RuntimeError):
            validate_coordination_command(self.config, 'cmd-001', changed)

    def test_commit_actor_must_match_allowlisted_issuer(self):
        with patch('bridge.github_api', return_value={'author': {'login': 'owner'}}):
            verify_coordination_actor(self.config, HEAD, self.command)
        with patch('bridge.github_api', return_value={'author': {'login': 'attacker'}}), \
                self.assertRaises(RuntimeError):
            verify_coordination_actor(self.config, HEAD, self.command)

    def test_exact_context_accepts_valid_and_rejects_stale_or_dirty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / 'work' / 'saved'
            checkout.mkdir(parents=True)
            command = dict(self.command, checkout=str(checkout))
            record = {
                'wi': 'WI-001', 'path': command['wi_path'], 'wi_blob': BLOB,
                'base_sha': BASE, 'attempt_id': ATTEMPT, 'thread_id': TASK,
                'checkout': str(checkout), 'branch': 'codex/test', 'status': 'review',
                'pr_number': 7, 'result_commit': HEAD,
            }
            store = FakeStateStore({'schema_version': 1, 'paused': None,
                                    'claims': {'WI-001': record}})
            dirty = {'value': False}

            def fake_git(repo, *args, **kwargs):
                joined = ' '.join(args)
                if joined == 'rev-parse FETCH_HEAD':
                    return completed(BASE)
                if joined == f'rev-parse {BASE}:{command["wi_path"]}':
                    return completed(BLOB)
                if joined == 'status --porcelain':
                    return completed(' M local-change\n' if dirty['value'] else '')
                if joined == 'remote get-url origin':
                    return completed('fixture.git')
                if joined == 'branch --show-current':
                    return completed('codex/test')
                if joined == 'rev-parse HEAD':
                    return completed(HEAD)
                if joined == 'ls-remote origin refs/heads/codex/test':
                    return completed(HEAD + '\trefs/heads/codex/test\n')
                return completed('')

            pr = {'number': 7, 'html_url': 'https://github.com/fixture/repo/pull/7',
                  'head': {'repo': {'full_name': 'fixture/repo'}, 'ref': 'codex/test', 'sha': HEAD},
                  'base': {'repo': {'full_name': 'fixture/repo'}, 'ref': 'main'},
                  'state': 'open', 'draft': True, 'merged_at': None}
            with patch('bridge.git', side_effect=fake_git), patch('bridge.github_api', return_value=pr):
                _, _, observed = validate_coordination_context(self.config, root, store, command)
                self.assertEqual(observed['thread_id'], TASK)
                with self.assertRaises(RuntimeError):
                    validate_coordination_context(self.config, root, store,
                                                  dict(command, expected_pr_head='5' * 40))
                dirty['value'] = True
                with self.assertRaises(RuntimeError):
                    validate_coordination_context(self.config, root, store, command)

    def test_claim_preserves_same_task_branch_pr_and_creates_new_attempt(self):
        old = {'wi': 'WI-001', 'path': 'docs/work-items/WI-001-test.md',
               'attempt_id': ATTEMPT, 'thread_id': TASK, 'branch': 'codex/test',
               'checkout': 'saved', 'pr_number': 7, 'status': 'review', 'history': []}
        state = {'schema_version': 1, 'paused': None, 'claims': {'WI-001': old}}
        store = FakeStateStore(state)
        command = dict(self.command)
        record = claim_coordination_execution(store, 'a' * 40, state, old, command)
        self.assertNotEqual(record['attempt_id'], ATTEMPT)
        self.assertEqual((record['thread_id'], record['branch'], record['pr_number']),
                         (TASK, 'codex/test', 7))
        self.assertEqual(record['status'], 'running')

    def test_revision_resumes_exact_task_once_and_keeps_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / 'work' / 'saved'
            wi = checkout / 'docs' / 'work-items' / 'WI-001-test.md'
            wi.parent.mkdir(parents=True)
            wi.write_text('# WI-001\n\nStatus: Review\n', encoding='utf-8')
            command = dict(self.command, checkout=str(checkout))
            record = {'wi': 'WI-001', 'path': 'docs/work-items/WI-001-test.md',
                      'attempt_id': '6' * 32, 'thread_id': TASK, 'checkout': str(checkout),
                      'branch': 'codex/test', 'base_sha': BASE, 'pr_number': 7}
            store = FakeStateStore({'schema_version': 1, 'paused': None,
                                    'claims': {'WI-001': dict(record)}})
            calls = []

            def fake_execute(cmd, prompt, folder, log_dir, timeout, on_event, heartbeat):
                calls.append((cmd, prompt, folder))
                on_event({'type': 'thread.started', 'thread_id': TASK})
                (log_dir / 'answer.json').write_text(json.dumps({
                    'outcome': 'Review', 'summary': 'Revised', 'validation': 'Passed',
                    'decision_owner': '', 'question': '', 'options_and_tradeoffs': '',
                    'recommendation': ''}), encoding='utf-8')
                return 'completed', 0

            def fake_git(repo, *args, **kwargs):
                if args == ('rev-parse', 'FETCH_HEAD'):
                    return completed(BASE)
                return completed('')

            with patch('bridge.execute', side_effect=fake_execute), \
                    patch('bridge.checkpoint', return_value='7' * 40), \
                    patch('bridge.publish_result'), patch('bridge.git', side_effect=fake_git):
                run_revision(self.config, root, store, record, command)
            self.assertEqual(len(calls), 1)
            self.assertIn('resume', calls[0][0])
            self.assertIn(TASK, calls[0][0])
            self.assertIn(self.feedback, calls[0][1])
            self.assertEqual(calls[0][2], checkout)
            self.assertIn('Status: Review', wi.read_text(encoding='utf-8'))

    def test_interrupted_command_receipt_prevents_replay(self):
        command = dict(self.command)
        config = dict(self.config, coordination_ref='refs/heads/codex/coordination')
        old = {'wi': 'WI-001', 'path': command['wi_path'], 'attempt_id': ATTEMPT,
               'thread_id': TASK, 'branch': 'codex/test', 'checkout': 'saved',
               'pr_number': 7, 'status': 'review'}
        state = {'schema_version': 1, 'paused': None, 'claims': {'WI-001': old}}
        store = FakeStateStore(state)

        class FakeCoordination:
            status = None

            def read(self):
                return HEAD, {'schema_version': 1, 'commands': {'cmd-001': command},
                              'receipts': {} if self.status is None else {'cmd-001': {'status': self.status}}}

            def command_origin(self, revision, command_id, observed):
                return HEAD

            def accept(self, command_id, observed, origin):
                if self.status is not None:
                    return None
                self.status = 'accepted'
                return {'status': 'accepted'}

            def finish(self, command_id, status, **evidence):
                self.status = status

        coordination = FakeCoordination()
        claimed = dict(old, attempt_id='6' * 32, status='running')
        with patch('bridge.CoordinationStore', return_value=coordination), \
                patch('bridge.verify_coordination_actor'), \
                patch('bridge.validate_coordination_context', return_value=(HEAD, state, old)), \
                patch('bridge.claim_coordination_execution', return_value=claimed), \
                patch('bridge.run_revision', side_effect=RuntimeError('interrupted')) as resume:
            with self.assertRaises(RuntimeError):
                process_coordination(config, Path('root'), store, 'cmd-001')
            self.assertEqual(coordination.status, 'failed_uncertain')
            process_coordination(config, Path('root'), store, 'cmd-001')
            self.assertEqual(resume.call_count, 1)


class CoordinationStoreTests(unittest.TestCase):
    def test_command_receipt_is_at_most_once_and_command_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / 'remote.git'
            seed = root / 'seed'
            from bridge import run, git
            run(['git', 'init', '--bare', str(remote)])
            run(['git', 'init', str(seed)])
            git(seed, 'config', 'user.name', 'Test')
            git(seed, 'config', 'user.email', 'test@example.invalid')
            command = {'schema_version': 1, 'command_id': 'cmd-1'}
            document = {'schema_version': 1, 'commands': {'cmd-1': command}, 'receipts': {}}
            (seed / 'coordination.json').write_text(json.dumps(document), encoding='utf-8')
            git(seed, 'add', 'coordination.json')
            git(seed, 'commit', '-m', 'command')
            origin = git(seed, 'rev-parse', 'HEAD').stdout.strip()
            git(seed, 'branch', '-M', 'codex/coordination')
            git(seed, 'remote', 'add', 'origin', str(remote))
            git(seed, 'push', 'origin', 'codex/coordination')
            first = CoordinationStore(root / 'one.git', str(remote), 'refs/heads/codex/coordination')
            second = CoordinationStore(root / 'two.git', str(remote), 'refs/heads/codex/coordination')
            revision, observed = first.read()
            self.assertEqual(first.command_origin(revision, 'cmd-1', command), origin)
            stale_revision, stale_document = second.read()
            competing = copy.deepcopy(stale_document)
            competing['receipts']['other'] = {'schema_version': 1, 'status': 'accepted'}
            self.assertIsNotNone(first.accept('cmd-1', command, origin))
            with self.assertRaises(RuntimeError):
                second.write(stale_revision, competing, 'competing stale receipt')
            self.assertIsNone(second.accept('cmd-1', command, origin))
            first.finish('cmd-1', 'completed', result_commit=HEAD)
            _, final = second.read()
            self.assertEqual(final['receipts']['cmd-1']['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
