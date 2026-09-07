import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import bridge


class FakeGitHub:
    """API fixture with server-side creation even when its response is lost."""
    def __init__(self):
        self.prs = []
        self.calls = []
        self.lose_create_response = False
        self.deny = False

    def __call__(self, config, method, path, data=None):
        self.calls.append((method, path, data))
        if self.deny:
            raise bridge.PublicationError('http_403')
        if method == 'GET' and path.startswith('pulls?'):
            return copy.deepcopy(self.prs)
        if method == 'POST':
            pr = dict(data, number=1, html_url='https://github.com/fixture/repo/pull/1',
                      state='open', merged_at=None,
                      head={'ref': data['head'], 'repo': {'full_name': config['repository']}},
                      base={'ref': data['base'], 'repo': {'full_name': config['repository']}})
            self.prs.append(pr)
            if self.lose_create_response:
                raise bridge.PublicationError('transport_or_response_error')
            return copy.deepcopy(pr)
        if method == 'PATCH':
            self.prs[0].update(data)
        return copy.deepcopy(self.prs[0])


class PRPublication(unittest.TestCase):
    def setUp(self):
        self.config = {'repository': 'fixture/repo'}
        self.record = {'wi': 'WI-001', 'branch': 'codex/auto-wi-001-test',
                       'path': 'docs/work-items/WI-001-test.md', 'attempt_id': 'first',
                       'run_url': 'fixture-run', 'result_path': 'docs/automation/results/test.md'}
        self.result = dict.fromkeys(bridge.SCHEMA['required'], '')
        self.result.update(outcome='Review', summary='Verified', validation='offline checks')
        self.api = FakeGitHub()

    def publish(self, folder):
        with patch('bridge.github_api', side_effect=self.api):
            return bridge.create_pr(self.config, folder, self.record, self.result)

    def test_review_blocked_duplicate_and_technical_retry_reuse_one_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / '.github').mkdir()
            template = '## Validation\n\n- [ ] Independent review\n'
            (folder / '.github/pull_request_template.md').write_text(template)
            for outcome in ['Review', 'Blocked', 'Review']:
                self.result.update(outcome=outcome, decision_owner='Owner', question='Check result')
                self.record['attempt_id'] = outcome
                fields = self.publish(folder)
                self.assertTrue(fields['pr_draft'])
                self.assertEqual(fields['pr_status'], 'published')
                self.assertIn('Outcome: ' + outcome, self.api.prs[0]['body'])
                self.assertTrue(self.api.prs[0]['body'].startswith(template.rstrip()))
            self.api.prs[0]['body'] += '\nHuman review note.\n'
            self.api.prs[0]['title'] = 'Reviewer title'
            self.publish(folder)
            previous = len(self.api.calls)
            self.publish(folder)
            self.assertFalse(any(c[0] in {'POST', 'PATCH'} for c in self.api.calls[previous:]))
            self.assertTrue(self.api.prs[0]['body'].endswith('Human review note.\n'))
            self.assertEqual(self.api.prs[0]['title'], 'Reviewer title')
            self.assertEqual(sum(c[0] == 'POST' for c in self.api.calls), 1)

    def test_lost_creation_response_recovers_existing_pr(self):
        self.api.lose_create_response = True
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.publish(Path(tmp))['pr_number'], 1)
            self.publish(Path(tmp))
        self.assertEqual(len(self.api.prs), 1)
        self.assertEqual(sum(c[0] == 'POST' for c in self.api.calls), 1)

    def test_known_pr_survives_temporarily_empty_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.record.update(self.publish(folder))
            api = self.api
            def delayed(config, method, path, data=None):
                return [] if path.startswith('pulls?') else api(config, method, path, data)
            with patch('bridge.github_api', side_effect=delayed):
                self.assertEqual(bridge.create_pr(self.config, folder, self.record, self.result)['pr_number'], 1)
        self.assertEqual(sum(c[0] == 'POST' for c in self.api.calls), 1)

    def test_closed_merged_nondraft_foreign_and_ambiguous_pr_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.publish(folder)
            good = copy.deepcopy(self.api.prs[0])
            for delta in [{'state': 'closed'}, {'merged_at': 'today'}, {'draft': False},
                          {'base': {'ref': 'retargeted', 'repo': {'full_name': 'fixture/repo'}}},
                          {'head': {'ref': 'different', 'repo': {'full_name': 'other/repo'}}},
                          {'html_url': 'https://example.invalid/steal'}]:
                self.api.prs = [dict(good, **delta)]
                with self.assertRaises(bridge.PublicationError):
                    self.publish(folder)
            self.api.prs = [good, good]
            with self.assertRaises(bridge.PublicationError):
                self.publish(folder)
        self.assertEqual(sum(c[0] == 'POST' for c in self.api.calls), 1)

    def test_missing_token_and_http_errors_are_sanitized(self):
        with patch.dict(os.environ, {}, clear=True), patch('bridge.urllib.request.urlopen') as request:
            with self.assertRaisesRegex(bridge.PublicationError, '^missing_token$'):
                bridge.github_api(self.config, 'GET', 'pulls')
            request.assert_not_called()
        for code in [401, 403, 422, 429, 500]:
            error = urllib.error.HTTPError('https://api.github.com', code, 'SECRET', {}, io.BytesIO(b'SECRET'))
            with patch.dict(os.environ, {'BRIDGE_TOKEN': 'SECRET'}), \
                    patch('bridge.urllib.request.urlopen', side_effect=error):
                with self.assertRaisesRegex(bridge.PublicationError, '^http_' + str(code) + '$'):
                    bridge.github_api(self.config, 'POST', 'pulls', {})

    def test_permission_denial_never_creates_pr(self):
        self.api.deny = True
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(bridge.PublicationError):
            self.publish(Path(tmp))
        self.assertFalse(any(c[0] == 'POST' for c in self.api.calls))

    def test_failed_or_unverified_update_never_reports_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.publish(folder)
            self.result['summary'] = 'Changed result'
            api = self.api
            def rejected(config, method, path, data=None):
                if method == 'PATCH':
                    raise bridge.PublicationError('http_403')
                return api(config, method, path, data)
            with patch('bridge.github_api', side_effect=rejected), self.assertRaises(bridge.PublicationError):
                bridge.create_pr(self.config, folder, self.record, self.result)
            def ignored(config, method, path, data=None):
                return copy.deepcopy(api.prs[0]) if method == 'PATCH' else api(config, method, path, data)
            with patch('bridge.github_api', side_effect=ignored), \
                    self.assertRaisesRegex(bridge.PublicationError, 'pr_body_verification_failed'):
                bridge.create_pr(self.config, folder, self.record, self.result)
            self.assertEqual(self.publish(folder)['pr_status'], 'published')
            self.assertEqual(sum(c[0] == 'POST' for c in api.calls), 1)


class DurablePublication(unittest.TestCase):
    def test_failed_handoff_pauses_then_recovers_without_codex(self):
        for outcome in ['Review', 'Blocked']:
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                remote, seed = root / 'remote.git', root / 'seed'
                subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
                subprocess.run(['git', 'init', '-b', 'main', str(seed)], check=True, capture_output=True)
                bridge.git(seed, 'config', 'user.name', 'Test')
                bridge.git(seed, 'config', 'user.email', 'test@example.invalid')
                path = 'docs/work-items/WI-001-test.md'
                (seed / path).parent.mkdir(parents=True)
                (seed / path).write_text('Status: Ready\n')
                bridge.git(seed, 'add', '.')
                bridge.git(seed, 'commit', '-m', 'fixture')
                bridge.git(seed, 'remote', 'add', 'origin', str(remote))
                bridge.git(seed, 'push', 'origin', 'main')
                store = bridge.Store(root / 'data/store.git', str(remote))
                rev, state = store.read()
                item = dict(wi='WI-001', path=path, role='Implementer', tier='T2',
                            wi_blob=bridge.git(seed, 'rev-parse', 'HEAD:' + path).stdout.strip(),
                            base_sha=bridge.git(seed, 'rev-parse', 'HEAD').stdout.strip())
                state = bridge.acquire(state, item, 'fixture-run')
                record = state['claims']['WI-001']
                record.update(branch='codex/auto-wi-001-test', checkout=str(root / 'data/work/fixture'))
                store.write(rev, state, 'claim')
                api = FakeGitHub()
                api.deny = True
                def fake_execute(command, prompt, folder, log_dir, *args):
                    result = dict.fromkeys(bridge.SCHEMA['required'], '')
                    result.update(outcome=outcome, summary='Preserved result',
                                  decision_owner='Owner', question='Review evidence')
                    (log_dir / 'answer.json').write_text(json.dumps(result))
                    return 'completed', 0
                config = {'remote': str(remote), 'repository': 'fixture/repo', 'codex': 'unused'}
                with patch('bridge.execute', side_effect=fake_execute) as execute, \
                        patch('bridge.github_api', side_effect=api):
                    with self.assertRaises(bridge.PublicationError):
                        bridge.run_one(config, root / 'data', store, record, False)
                    failed = store.read()[1]
                    saved = failed['claims']['WI-001']
                    self.assertEqual(saved['status'], 'publication_error')
                    self.assertEqual(saved['pr_error'], 'http_403')
                    self.assertEqual(failed['paused']['reason'], 'publication_error')
                    self.assertIsNone(bridge.acquire(failed, dict(item, wi='WI-002'), 'duplicate'))
                    with self.assertRaises(RuntimeError):
                        bridge.acquire(failed, item, 'not-a-code-retry', retry=True)
                    report = bridge.git(seed, '--git-dir=' + str(remote), 'show',
                                        saved['branch'] + ':' + saved['result_path']).stdout
                    self.assertIn('http_403', report)
                    api.deny = False
                    with patch('bridge.checkpoint', side_effect=RuntimeError('injected push failure')):
                        with self.assertRaisesRegex(RuntimeError, 'injected push failure'):
                            bridge.recover_publication(config, root / 'data', store, 'WI-001')
                    interrupted = store.read()[1]
                    self.assertEqual(interrupted['claims']['WI-001']['status'], 'running')
                    self.assertEqual(interrupted['claims']['WI-001']['pr_status'], 'published')
                    self.assertIsNone(bridge.acquire(interrupted, dict(item, wi='WI-002'), 'fenced'))
                    # Dirty publication evidence is preserved; recovery refuses it.
                    with self.assertRaisesRegex(RuntimeError, 'dirty'):
                        bridge.recover_publication(config, root / 'data', store, 'WI-001')
                    # Simulate authorized reconciliation by committing preserved evidence,
                    # then recording its verified remote SHA, without discarding/resetting.
                    checkout = Path(saved['checkout'])
                    repaired = bridge.checkpoint(checkout, saved['branch'], 'preserve interrupted PR evidence')
                    store.patch('WI-001', saved['attempt_id'], result_commit=repaired)
                    bridge.recover_publication(config, root / 'data', store, 'WI-001')
                    bridge.recover_publication(config, root / 'data', store, 'WI-001')
                    self.assertEqual(execute.call_count, 1)
                final = store.read()[1]
                saved = final['claims']['WI-001']
                self.assertEqual(saved['status'], outcome.lower())
                self.assertIsNone(final['paused'])
                self.assertEqual(saved['pr_url'], 'https://github.com/fixture/repo/pull/1')
                self.assertEqual(sum(c[0] == 'POST' for c in api.calls), 1)
                report = bridge.git(seed, '--git-dir=' + str(remote), 'show',
                                    saved['branch'] + ':' + saved['result_path']).stdout
                self.assertIn(saved['pr_url'], report)
                self.assertEqual(report.count('## PR handoff'), 1)
                self.assertIsNone(bridge.acquire(final, item, 'duplicate'))


if __name__ == '__main__':
    unittest.main()
