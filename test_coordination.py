import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from bridge import (CoordinationStore, claim_coordination_execution, run_one, run_revision,
                    coordination_observations, process_coordination,
                    validate_coordination_command, validate_coordination_context,
                    validate_receipt, verify_coordination_actor, verify_feedback)


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


def full_observations(command, revision=HEAD, **overrides):
    verified = {
        'verified_actor': 'owner', 'feedback_kind': 'pullrequestreview',
        'feedback_id': '101', 'claim_status': 'review',
        'observed_base_sha': BASE, 'observed_wi_blob': BLOB,
        'observed_checkout_head': HEAD, 'observed_remote_head': HEAD,
        'observed_pr_head': HEAD,
    }
    verified.update(overrides)
    return coordination_observations(revision, command, **verified)


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
            'feedback_ref': 'https://github.com/fixture/repo/pull/7#pullrequestreview-101',
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

    def test_technical_retry_without_pr_allows_empty_feedback_identity(self):
        retry = dict(self.command, action='technical_retry', pr_number=0,
                     expected_pr_head='', feedback_ref='', feedback='',
                     feedback_sha256=hashlib.sha256(b'').hexdigest())
        self.assertIs(validate_coordination_command(self.config, 'cmd-001', retry), retry)
        self.assertEqual(verify_feedback(self.config, retry),
                         {'feedback_kind': None, 'feedback_id': None})

    def test_technical_retry_with_pr_requires_refetched_feedback(self):
        empty = dict(self.command, action='technical_retry', feedback_ref='', feedback='',
                     feedback_sha256=hashlib.sha256(b'').hexdigest())
        with self.assertRaises(RuntimeError):
            validate_coordination_command(self.config, 'cmd-001', empty)
        with self.assertRaises(RuntimeError):
            verify_feedback(self.config, empty)

        review = {'id': 101, 'html_url': self.command['feedback_ref'],
                  'body': self.feedback, 'user': {'login': 'owner'}}
        retry = dict(self.command, action='technical_retry')
        with patch('bridge.github_api', return_value=review) as api:
            self.assertEqual(verify_feedback(self.config, retry),
                             {'feedback_kind': 'pullrequestreview', 'feedback_id': '101'})
        api.assert_called_once_with(self.config, 'GET', 'pulls/7/reviews/101')

    def test_commit_actor_must_match_allowlisted_issuer(self):
        verified = {'sha': HEAD, 'author': {'login': 'owner'},
                    'committer': {'login': 'owner'},
                    'commit': {'verification': {'verified': True}}}
        with patch('bridge.github_api', return_value=verified):
            verify_coordination_actor(self.config, HEAD, self.command)
        for payload in (
                dict(verified, author={'login': 'attacker'}),
                dict(verified, committer={'login': 'attacker'}),
                dict(verified, committer=None),
                dict(verified, commit={'verification': {'verified': False}}),
                dict(verified, sha='9' * 40)):
            with self.subTest(payload=payload), patch('bridge.github_api', return_value=payload), \
                    self.assertRaises(RuntimeError):
                verify_coordination_actor(self.config, HEAD, self.command)

    def test_technical_retry_with_pr_processes_verified_feedback_once(self):
        command = dict(self.command, action='technical_retry')
        config = dict(self.config, coordination_ref='refs/heads/codex/coordination')
        old = {'wi': 'WI-001', 'path': command['wi_path'], 'attempt_id': ATTEMPT,
               'thread_id': TASK, 'branch': 'codex/test', 'checkout': 'saved',
               'pr_number': 7, 'result_commit': HEAD, 'status': 'timeout'}
        state = {'schema_version': 1, 'paused': {'wi': 'WI-001'},
                 'claims': {'WI-001': old}}
        store = FakeStateStore(state)

        class FakeCoordination:
            def __init__(self):
                self.status = None

            def read(self):
                receipts = {} if self.status is None else {'cmd-001': {'status': self.status}}
                return HEAD, {'schema_version': 1, 'commands': {'cmd-001': command},
                              'receipts': receipts}

            def command_origin(self, *args):
                return HEAD

            def accept(self, *args):
                self.status = 'accepted'
                return {'status': 'accepted'}

            def reject(self, *args):
                raise AssertionError('valid retry must not reject')

            def finish(self, command_id, status, **evidence):
                self.status = status

        coordination = FakeCoordination()
        claimed = dict(old, attempt_id='6' * 32, status='running')
        final = dict(claimed, result_commit='7' * 40, pr_number=7, pr_status='published')
        final_state = {'schema_version': 1, 'paused': None, 'claims': {'WI-001': final}}
        review = {'id': 101, 'html_url': command['feedback_ref'],
                  'body': self.feedback, 'user': {'login': 'owner'}}
        with patch('bridge.CoordinationStore', return_value=coordination), \
                patch('bridge.verify_coordination_actor', return_value='owner'), \
                patch('bridge.github_api', return_value=review) as api, \
                patch('bridge.validate_coordination_context', return_value=(HEAD, state, old)), \
                patch('bridge.claim_coordination_execution', return_value=claimed), \
                patch('bridge.run_one') as retry:
            store.read = lambda: (HEAD, copy.deepcopy(final_state))
            process_coordination(config, Path('root'), store, 'cmd-001')
        api.assert_called_once_with(config, 'GET', 'pulls/7/reviews/101')
        retry.assert_called_once_with(config, Path('root'), store, claimed, True)
        self.assertEqual(coordination.status, 'completed')

    def test_feedback_reference_is_canonical_and_api_content_is_exact(self):
        review = {'id': 101, 'html_url': self.command['feedback_ref'],
                  'body': self.feedback, 'user': {'login': 'owner'}}
        with patch('bridge.github_api', return_value=review):
            self.assertEqual(verify_feedback(self.config, self.command),
                             {'feedback_kind': 'pullrequestreview', 'feedback_id': '101'})
        comment_command = dict(
            self.command,
            feedback_ref='https://github.com/fixture/repo/pull/7#issuecomment-202')
        comment = {'id': 202, 'html_url': comment_command['feedback_ref'],
                   'issue_url': 'https://api.github.com/repos/fixture/repo/issues/7',
                   'body': self.feedback, 'user': {'login': 'owner'}}
        with patch('bridge.github_api', return_value=comment):
            self.assertEqual(verify_feedback(self.config, comment_command),
                             {'feedback_kind': 'issuecomment', 'feedback_id': '202'})
        malformed = dict(self.command,
                         feedback_ref='https://github.com/fixture/repo/issues/7')
        with self.assertRaises(RuntimeError):
            validate_coordination_command(self.config, 'cmd-001', malformed)
        for changed in (
                dict(self.command, feedback_ref='https://github.com/fixture/repo/pull/8#pullrequestreview-101'),
                dict(self.command, feedback_ref='https://github.com/fixture/repo/pull/7#issuecomment-101')):
            with self.subTest(ref=changed['feedback_ref']), \
                    patch('bridge.github_api', return_value=review), self.assertRaises(RuntimeError):
                verify_feedback(self.config, changed)
        for payload in (dict(review, body='different'),
                        dict(review, user={'login': 'attacker'}),
                        dict(review, id=999)):
            with self.subTest(payload=payload), patch('bridge.github_api', return_value=payload), \
                    self.assertRaises(RuntimeError):
                verify_feedback(self.config, self.command)

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

    def test_technical_retry_rejects_mismatched_resumed_task_without_persisting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / 'work' / 'saved'
            wi = checkout / 'docs' / 'work-items' / 'WI-001-test.md'
            wi.parent.mkdir(parents=True)
            wi.write_text('# WI-001\n\nStatus: Blocked\n', encoding='utf-8')
            record = {
                'wi': 'WI-001', 'path': 'docs/work-items/WI-001-test.md',
                'attempt_id': ATTEMPT, 'thread_id': TASK, 'checkout': str(checkout),
                'branch': 'codex/test', 'base_sha': BASE, 'role': 'Implementer',
                'tier': 'T2 Standard', 'run_url': 'coordination:cmd-001',
            }
            store = FakeStateStore({'schema_version': 1, 'paused': None,
                                    'claims': {'WI-001': dict(record)}})
            mismatched = '22222222-2222-4222-8222-222222222222'

            def fake_git(repo, *args, **kwargs):
                if args == ('rev-parse', 'FETCH_HEAD'):
                    return completed(BASE)
                return completed('')

            def fake_execute(command, prompt, folder, log_dir, timeout, on_event, heartbeat):
                self.assertIn('resume', command)
                self.assertIn(TASK, command)
                on_event({'type': 'thread.started', 'thread_id': mismatched})
                raise AssertionError('mismatched event must stop execution immediately')

            config = {'remote': 'fixture.git', 'repository': 'fixture/repo',
                      'codex': 'codex.exe', 'base_branch': 'main'}
            with patch('bridge.git', side_effect=fake_git), \
                    patch('bridge.checkpoint', return_value=HEAD), \
                    patch('bridge.execute', side_effect=fake_execute), \
                    self.assertRaisesRegex(RuntimeError, 'different Developer task'):
                run_one(config, root, store, record, True)
            self.assertEqual(store.state['claims']['WI-001']['thread_id'], TASK)
            self.assertFalse(any('thread_id' in fields for _, _, fields in store.patches))
            self.assertTrue((root / 'logs' / ATTEMPT / 'recovery.txt').exists())

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
                if observed is None:
                    raise RuntimeError('missing command')
                return HEAD

            def accept(self, command_id, observed, origin, evidence):
                if self.status is not None:
                    return None
                self.status = 'accepted'
                return {'status': 'accepted'}

            def reject(self, command_id, observed, origin, evidence, error_code):
                self.status = 'rejected'

            def finish(self, command_id, status, **evidence):
                self.status = status

        coordination = FakeCoordination()
        claimed = dict(old, attempt_id='6' * 32, status='running')
        with patch('bridge.CoordinationStore', return_value=coordination), \
                patch('bridge.verify_coordination_actor'), \
                patch('bridge.verify_feedback', return_value={
                    'feedback_kind': 'pullrequestreview', 'feedback_id': '101'}), \
                patch('bridge.validate_coordination_context', return_value=(HEAD, state, old)), \
                patch('bridge.claim_coordination_execution', return_value=claimed), \
                patch('bridge.run_revision', side_effect=RuntimeError('interrupted')) as resume:
            with self.assertRaises(RuntimeError):
                process_coordination(config, Path('root'), store, 'cmd-001')
            self.assertEqual(coordination.status, 'failed_uncertain')
            process_coordination(config, Path('root'), store, 'cmd-001')
            self.assertEqual(resume.call_count, 1)

    def test_rejections_are_durable_closed_sanitized_receipts(self):
        config = dict(self.config, coordination_ref='refs/heads/codex/coordination')

        class FakeCoordination:
            def __init__(self, command):
                self.command = command
                self.receipt = None

            def read(self):
                receipts = {} if self.receipt is None else {'cmd-001': self.receipt}
                return HEAD, {'schema_version': 1,
                              'commands': {'cmd-001': self.command}, 'receipts': receipts}

            def command_origin(self, revision, command_id, observed):
                if observed is None:
                    raise RuntimeError('missing command')
                return HEAD

            def reject(self, command_id, command, origin, observed, error_code):
                self.receipt = CoordinationStore._receipt(
                    command_id, 'rejected', origin, observed, False, error_code)
                validate_receipt(command_id, self.receipt)

            def accept(self, *args):
                raise AssertionError('rejected command must not be accepted')

        cases = [
            ('missing', None, None),
            ('malformed', dict(self.command, extra='no'), None),
            ('wrong_actor', dict(self.command, issuer_actor='attacker'), None),
            ('forged_role', dict(self.command, active_role='Product Owner'), None),
            ('unsigned', self.command, 'actor'),
            ('bad_feedback', self.command, 'feedback'),
            ('stale_head', self.command, 'context'),
            ('changed_wi', self.command, 'context'),
            ('dirty_checkout', self.command, 'context'),
        ]
        for name, command, failing_phase in cases:
            coordination = FakeCoordination(command)
            actor_error = RuntimeError('unsigned') if failing_phase == 'actor' else None
            feedback_error = RuntimeError('bad feedback') if failing_phase == 'feedback' else None
            context_error = RuntimeError(name) if failing_phase == 'context' else None
            with self.subTest(name=name), \
                    patch('bridge.CoordinationStore', return_value=coordination), \
                    patch('bridge.verify_coordination_actor', return_value='owner',
                          side_effect=actor_error), \
                    patch('bridge.verify_feedback', return_value={
                        'feedback_kind': 'pullrequestreview', 'feedback_id': '101'},
                          side_effect=feedback_error), \
                    patch('bridge.validate_coordination_context', return_value=(HEAD, {}, {}),
                          side_effect=context_error), \
                    self.assertRaises(RuntimeError):
                process_coordination(config, Path('root'), FakeStateStore({}), 'cmd-001')
            self.assertEqual(coordination.receipt['status'], 'rejected')
            self.assertFalse(coordination.receipt['execution_may_have_started'])
            serialized = json.dumps(coordination.receipt)
            if command is not None:
                self.assertNotIn(command.get('checkout', ''), serialized)
                self.assertRegex(coordination.receipt['observed']['checkout_sha256'],
                                 r'^[0-9a-f]{64}$')
            else:
                self.assertIsNone(coordination.receipt['command_commit'])


class CoordinationStoreTests(unittest.TestCase):
    @staticmethod
    def command(command_id='cmd-1'):
        feedback = 'Reviewed immutable feedback.'
        return {
            'schema_version': 1, 'command_id': command_id, 'action': 'revise',
            'repository': 'fixture/repo', 'wi_path': 'docs/work-items/WI-001-test.md',
            'wi_blob': BLOB, 'base_sha': BASE, 'attempt_id': ATTEMPT,
            'task_id': TASK, 'checkout': 'C:/safe/checkout', 'work_branch': 'codex/test',
            'pr_number': 7, 'expected_pr_head': HEAD,
            'feedback_ref': 'https://github.com/fixture/repo/pull/7#pullrequestreview-101',
            'feedback_sha256': hashlib.sha256(feedback.encode()).hexdigest(),
            'feedback': feedback, 'issuer_actor': 'owner',
            'active_role': 'Technical Planner', 'authority_ref': 'ADR-007',
            'created_at': '2026-09-08T01:00:00+00:00',
        }

    def test_receipt_schema_rejects_unknown_and_malformed_fields(self):
        observed = coordination_observations(HEAD, {'repository': 'fixture/repo'})
        receipt = CoordinationStore._receipt(
            'cmd-1', 'rejected', HEAD, observed, False, 'command_schema_invalid')
        self.assertIs(validate_receipt('cmd-1', receipt), receipt)
        for changed in (
                dict(receipt, extra='forbidden'),
                dict(receipt, schema_version=2),
                dict(receipt, command_commit='not-a-sha'),
                dict(receipt, command_commit=None),
                dict(receipt, execution_may_have_started=True),
                dict(receipt, observed=dict(observed, extra='forbidden'))):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                validate_receipt('cmd-1', changed)
        missing = CoordinationStore._receipt(
            'cmd-1', 'rejected', None, coordination_observations(HEAD, None),
            False, 'command_origin_invalid')
        self.assertIs(validate_receipt('cmd-1', missing), missing)
        with self.assertRaises(RuntimeError):
            validate_receipt('cmd-1', dict(missing, command_commit=HEAD))
        forged_missing = copy.deepcopy(missing)
        forged_missing['observed']['repository'] = 'fixture/repo'
        with self.assertRaises(RuntimeError):
            validate_receipt('cmd-1', forged_missing)

    def test_receipt_schema_validates_identities_timestamps_and_state_requirements(self):
        command = self.command()
        observed = full_observations(command)
        accepted = CoordinationStore._receipt('cmd-1', 'accepted', HEAD, observed, True)
        self.assertIs(validate_receipt('cmd-1', accepted), accepted)

        malformed = [
            ('command_id', dict(accepted, command_id='../unsafe')),
            ('recorded_at', dict(accepted, recorded_at='not-a-time')),
            ('repository', dict(accepted, observed=dict(observed, repository='bad\nrepo'))),
            ('feedback_digest', dict(accepted, observed=dict(observed, feedback_sha256='x' * 64))),
            ('task', dict(accepted, observed=dict(observed, task_id='not-a-uuid'))),
            ('actor', dict(accepted, observed=dict(observed, verified_actor='attacker'))),
            ('claim', dict(accepted, observed=dict(observed, claim_status='running'))),
            ('head', dict(accepted, observed=dict(observed, observed_pr_head='9' * 40))),
            ('feedback_identity', dict(accepted, observed=dict(observed, feedback_id='999'))),
            ('missing_wi', dict(accepted, observed=dict(observed, wi_blob=None))),
        ]
        for name, changed in malformed:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                validate_receipt('cmd-1', changed)

        completed = copy.deepcopy(accepted)
        completed.update(status='completed', finished_at=completed['recorded_at'])
        completed['observed'].update(result_attempt_id='6' * 32,
                                     result_commit='7' * 40,
                                     result_pr_number=7,
                                     result_pr_status='published')
        self.assertIs(validate_receipt('cmd-1', completed), completed)
        for name, value in (('result_commit', None), ('result_pr_number', 0),
                            ('result_pr_status', 'failed')):
            changed = copy.deepcopy(completed)
            changed['observed'][name] = value
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                validate_receipt('cmd-1', changed)

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
            command = self.command()
            rejected_command = {
                'schema_version': 99, 'checkout': 'secret-local-path',
                'repository': 'attacker\n/repository', 'wi_path': '../secret',
                'work_branch': 'bad branch', 'issuer_actor': 'attacker!',
                'feedback_ref': 'javascript:alert(1)', 'created_at': 'not-a-time',
            }
            document = {'schema_version': 1,
                        'commands': {'cmd-1': command, 'cmd-2': rejected_command},
                        'receipts': {}}
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
            observations = full_observations(command, revision)
            competing['receipts']['other'] = first._receipt(
                'other', 'accepted', origin,
                full_observations(dict(command, command_id='other'), revision), True)
            self.assertIsNotNone(first.accept('cmd-1', command, origin, observations))
            with self.assertRaises(RuntimeError):
                second.write(stale_revision, competing, 'competing stale receipt')
            self.assertIsNone(second.accept('cmd-1', command, origin, observations))
            first.finish('cmd-1', 'completed', result_attempt_id='6' * 32,
                         result_commit='7' * 40, result_pr_number=7,
                         result_pr_status='published')
            _, final = second.read()
            self.assertEqual(final['receipts']['cmd-1']['status'], 'completed')
            validate_receipt('cmd-1', final['receipts']['cmd-1'])
            current_revision, _ = first.read()
            rejected_observations = coordination_observations(
                current_revision, rejected_command)
            first.reject('cmd-2', rejected_command, origin, rejected_observations,
                         'command_schema_invalid')
            _, rejected = second.read()
            self.assertEqual(rejected['receipts']['cmd-2']['status'], 'rejected')
            self.assertNotIn('secret-local-path',
                             json.dumps(rejected['receipts']['cmd-2']))
            serialized = json.dumps(rejected['receipts']['cmd-2'])
            for attacker_value in ('attacker\\n/repository', '../secret', 'bad branch',
                                   'attacker!', 'javascript:alert(1)', 'not-a-time'):
                self.assertNotIn(attacker_value, serialized)


if __name__ == '__main__':
    unittest.main()
