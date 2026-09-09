import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import bridge
from bridge import CoordinationStore, Store, run_one, verify_coordination_actor


ROOT = Path(__file__).resolve().parent
OLD_EMAIL = 'bridge@users.noreply.github.com'
EXPECTED_NAME = 'github-codex-ready-work-dispatch'
EXPECTED_EMAIL = 'github-codex-ready-work-dispatch@invalid'


def git_config(repo, key):
    result = subprocess.run(['git', '-C', str(repo), 'config', '--get', key],
                            check=True, capture_output=True, text=True)
    return result.stdout.strip()


def completed(stdout=''):
    return subprocess.CompletedProcess(['git'], 0, stdout=stdout, stderr='')


def make_host_remote(root):
    remote = root / 'host.git'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True,
                   capture_output=True, text=True)
    seed = root / 'seed'
    subprocess.run(['git', 'clone', '--quiet', str(remote), str(seed)], check=True,
                   capture_output=True, text=True)
    subprocess.run(['git', '-C', str(seed), 'config', 'user.name', 'fixture'], check=True)
    subprocess.run(['git', '-C', str(seed), 'config', 'user.email', 'fixture@example.invalid'],
                   check=True)
    item = seed / 'docs' / 'work-items' / 'WI-008-automated-git-identity-provenance.md'
    item.parent.mkdir(parents=True)
    item.write_text('# WI-008\n\nStatus: Ready\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(seed), 'add', str(item.relative_to(seed))], check=True)
    subprocess.run(['git', '-C', str(seed), 'commit', '-m', 'fixture'], check=True,
                   capture_output=True, text=True)
    subprocess.run(['git', '-C', str(seed), 'branch', '-M', 'main'], check=True)
    subprocess.run(['git', '-C', str(seed), 'push', '--quiet', 'origin', 'main'], check=True,
                   capture_output=True, text=True)
    base = subprocess.run(['git', '-C', str(seed), 'rev-parse', 'HEAD'], check=True,
                          capture_output=True, text=True).stdout.strip()
    return remote, base


class GitIdentityTests(unittest.TestCase):
    def assert_identity(self, repo):
        self.assertEqual(git_config(repo, 'user.name'), EXPECTED_NAME)
        self.assertEqual(git_config(repo, 'user.email'), EXPECTED_EMAIL)

    def test_dispatch_and_coordination_stores_use_approved_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / 'remote.git'
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True,
                           capture_output=True, text=True)
            Store(root / 'dispatch-state.git', str(remote))
            CoordinationStore(root / 'coordination.git', str(remote),
                              'refs/heads/codex/coordination')
            self.assert_identity(root / 'dispatch-state.git')
            self.assert_identity(root / 'coordination.git')

    def test_fresh_developer_checkout_uses_approved_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, base = make_host_remote(root)
            (root / 'work').mkdir()
            store = type('FakeStore', (), {
                'path': root / 'store.git',
                'patch': lambda self, wi, attempt, **fields: None,
            })()
            record = {
                'wi': 'WI-008',
                'path': 'docs/work-items/WI-008-automated-git-identity-provenance.md',
                'attempt_id': 'a' * 32,
                'thread_id': '',
                'checkout': str(root / 'work' / 'attempt'),
                'branch': 'codex/wi-008-test',
                'base_sha': base,
                'role': 'Implementer',
                'tier': 'T2 Standard',
                'run_url': 'fixture:run',
            }
            config = {'remote': str(remote), 'repository': 'fixture/repo',
                      'codex': 'codex.exe', 'base_branch': 'main'}
            real_git = bridge.git

            def fake_git(repo, *args, **kwargs):
                if Path(repo) == store.path:
                    if args == ('rev-parse', 'FETCH_HEAD'):
                        return completed(base + '\n')
                    return completed()
                if args[:1] == ('submodule',):
                    return completed()
                return real_git(repo, *args, **kwargs)

            def fake_execute(command, prompt, folder, log_dir, timeout, on_event, heartbeat):
                (log_dir / 'answer.json').write_text(json.dumps({
                    'outcome': 'Review', 'summary': 'fixture', 'validation': 'passed',
                    'decision_owner': '', 'question': '', 'options_and_tradeoffs': '',
                    'recommendation': '',
                }), encoding='utf-8')
                return 'completed', 0

            with patch('bridge.git', side_effect=fake_git), \
                    patch('bridge.execute', side_effect=fake_execute), \
                    patch('bridge.checkpoint', return_value='c' * 40), \
                    patch('bridge.publish_result'), patch('bridge.set_status'):
                run_one(config, root, store, record, False)
            self.assert_identity(Path(record['checkout']))

    def test_runtime_code_contains_no_old_identity(self):
        runtime_files = [ROOT / 'bridge.py', ROOT / 'setup.ps1',
                         ROOT / 'invoke-dispatch.ps1', ROOT / 'config.example.json']
        for path in runtime_files:
            with self.subTest(path=path.name):
                self.assertNotIn(OLD_EMAIL, path.read_text(encoding='utf-8'))

    def test_verified_coordination_actor_is_independent_of_local_git_identity(self):
        config = {
            'repository': 'fixture/repo',
            'trusted_coordination_principals': [
                {'actor': 'owner', 'roles': ['Technical Planner']},
            ],
            'trusted_coordination_actors': [],
            'trusted_coordination_roles': [],
        }
        command = {
            'issuer_actor': 'owner', 'active_role': 'Technical Planner',
        }
        revision = '1' * 40
        verified = {
            'sha': revision,
            'author': {'login': 'owner'},
            'committer': {'login': 'owner'},
            'commit': {'verification': {'verified': True}},
        }
        with patch.dict(os.environ, {
            'GIT_AUTHOR_NAME': 'personal-account',
            'GIT_AUTHOR_EMAIL': 'personal@example.invalid',
            'GIT_COMMITTER_NAME': 'personal-account',
            'GIT_COMMITTER_EMAIL': 'personal@example.invalid',
        }), patch('bridge.github_api', return_value=verified) as api:
            self.assertEqual(verify_coordination_actor(config, revision, command), 'owner')
        api.assert_called_once_with(config, 'GET', 'commits/' + revision)


if __name__ == '__main__':
    unittest.main()
