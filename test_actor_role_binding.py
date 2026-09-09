import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

from bridge import process_coordination, validate_coordination_command


ROOT = Path(__file__).resolve().parent


class ActorRoleBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.powershell = shutil.which('pwsh') or shutil.which('powershell')
        cls.python_exe = Path(__import__('sys').executable)

    def require_operator_fixture(self):
        if not self.powershell or self.python_exe.suffix.lower() != '.exe':
            self.skipTest('Windows PowerShell and python.exe are required for setup integration')

    def run_ps(self, script, *args):
        return subprocess.run(
            [self.powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(script), *map(str, args)],
            text=True, encoding='utf-8', errors='replace', capture_output=True)

    def run_setup_with_array_arguments(self, root, source, host, install, workflow,
                                       parameter, values, extra):
        runner = root / f'run-{workflow}.ps1'
        quoted_values = ', '.join("'" + str(value).replace("'", "''") + "'" for value in values)
        arguments = [
            f"-HostRepo '{str(host).replace("'", "''")}'",
            "-RunnerLabel 'fixture-dispatch'",
            f"-InstallRoot '{str(install).replace("'", "''")}'",
            f"-Codex '{str(self.python_exe).replace("'", "''")}'",
            f"-Python '{str(self.python_exe).replace("'", "''")}'",
            f"-{parameter} @({quoted_values})",
            f"-WorkflowPath '.github/workflows/{workflow}.yml'",
        ] + extra
        runner.write_text(
            f"& '{str(source / 'setup.ps1').replace("'", "''")}' " + ' '.join(arguments) + '\n',
            encoding='utf-8')
        return self.run_ps(runner)

    def make_host(self, root):
        host = root / 'host'
        host.mkdir()
        subprocess.run(['git', '-C', str(host), 'init', '-b', 'main'], check=True,
                       capture_output=True, text=True)
        subprocess.run(['git', '-C', str(host), 'config', 'user.name', 'fixture'], check=True)
        subprocess.run(['git', '-C', str(host), 'config', 'user.email', 'fixture@example.invalid'], check=True)
        (host / 'README.md').write_text('fixture\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(host), 'add', 'README.md'], check=True)
        subprocess.run(['git', '-C', str(host), 'commit', '-m', 'fixture'], check=True,
                       capture_output=True, text=True)
        subprocess.run(['git', '-C', str(host), 'remote', 'add', 'origin',
                        'https://github.com/fixture/host.git'], check=True)
        return host

    def test_setup_validateonly_and_installed_bridge_use_explicit_principal_pairs(self):
        self.require_operator_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'dispatcher'
            subprocess.run(['git', 'clone', '--quiet', str(ROOT), str(source)], check=True,
                           capture_output=True, text=True)
            host = self.make_host(root)
            install = root / 'install'
            setup = self.run_setup_with_array_arguments(
                root, source, host, install, 'explicit', 'TrustedCoordinatorBinding',
                ['alice=Technical Planner', 'bob=Reviewer'], [
                    "-CoordinationRef 'refs/heads/codex/review-commands'",
                    "-CoordinationAuthorityRef 'ADR-007'",
                ])
            self.assertEqual(setup.returncode, 0, setup.stderr + setup.stdout)
            install_dir = install / 'fixture-host'
            config_path = install_dir / 'config.json'
            config = json.loads(config_path.read_text(encoding='utf-8-sig'))
            self.assertEqual(config['trusted_coordination_principals'], [
                {'actor': 'alice', 'roles': ['Technical Planner']},
                {'actor': 'bob', 'roles': ['Reviewer']},
            ])
            validate = self.run_ps(install_dir / 'invoke-dispatch.ps1',
                                   '-Config', config_path, '-ValidateOnly')
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

            probe = (
                'import json,sys; from bridge import coordination_principal_pairs; '
                'c=json.load(open(sys.argv[1], encoding="utf-8")); '
                'pairs=coordination_principal_pairs(c); '
                'raise SystemExit(0 if tuple(sys.argv[2:4]) in pairs else 1)'
            )
            env = os.environ.copy()
            env['PYTHONPATH'] = str(install_dir)
            for actor, role in [('alice', 'Technical Planner'), ('bob', 'Reviewer')]:
                result = subprocess.run([self.python_exe, '-c', probe, config_path, actor, role],
                                        env=env, text=True, capture_output=True)
                with self.subTest(actor=actor, role=role):
                    self.assertEqual(result.returncode, 0, result.stderr)
            for actor, role in [('alice', 'Reviewer'), ('bob', 'Technical Planner')]:
                result = subprocess.run([self.python_exe, '-c', probe, config_path, actor, role],
                                        env=env, text=True, capture_output=True)
                with self.subTest(actor=actor, role=role):
                    self.assertEqual(result.returncode, 1)

    def test_setup_preserves_legacy_single_support_and_rejects_unsafe_bindings(self):
        self.require_operator_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'dispatcher'
            subprocess.run(['git', 'clone', '--quiet', str(ROOT), str(source)], check=True,
                           capture_output=True, text=True)
            host = self.make_host(root)

            legacy = self.run_ps(
                source / 'setup.ps1', '-HostRepo', host, '-RunnerLabel', 'fixture-dispatch',
                '-InstallRoot', root / 'legacy-install', '-Codex', self.python_exe,
                '-Python', self.python_exe, '-CoordinationRef', 'refs/heads/codex/legacy',
                '-TrustedCoordinatorActor', 'alice', '-TrustedCoordinatorRole', 'Technical Planner',
                '-CoordinationAuthorityRef', 'ADR-007', '-WorkflowPath',
                '.github/workflows/legacy.yml')
            self.assertEqual(legacy.returncode, 0, legacy.stderr + legacy.stdout)
            ambiguous = self.run_setup_with_array_arguments(
                root, source, host, root / 'ambiguous-install', 'ambiguous',
                'TrustedCoordinatorActor', ['alice', 'bob'], [
                    "-CoordinationRef 'refs/heads/codex/ambiguous'",
                    "-TrustedCoordinatorRole @('Technical Planner', 'Reviewer')",
                    "-CoordinationAuthorityRef 'ADR-007'",
                ])
            self.assertNotEqual(ambiguous.returncode, 0)
            whitespace = self.run_ps(
                source / 'setup.ps1', '-HostRepo', host, '-RunnerLabel', 'fixture-dispatch',
                '-InstallRoot', root / 'whitespace-install', '-Codex', self.python_exe,
                '-Python', self.python_exe, '-CoordinationRef', 'refs/heads/codex/whitespace',
                '-TrustedCoordinatorBinding', 'alice=   ', '-CoordinationAuthorityRef', 'ADR-007',
                '-WorkflowPath', '.github/workflows/whitespace.yml')
            self.assertNotEqual(whitespace.returncode, 0)

    def test_setup_without_coordination_remains_backward_compatible(self):
        self.require_operator_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'dispatcher'
            subprocess.run(['git', 'clone', '--quiet', str(ROOT), str(source)], check=True,
                           capture_output=True, text=True)
            host = self.make_host(root)
            result = self.run_ps(
                source / 'setup.ps1', '-HostRepo', host, '-RunnerLabel', 'fixture-dispatch',
                '-InstallRoot', root / 'disabled-install', '-Codex', self.python_exe,
                '-Python', self.python_exe, '-WorkflowPath', '.github/workflows/disabled.yml')
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            install_dir = root / 'disabled-install' / 'fixture-host'
            config_path = install_dir / 'config.json'
            config = json.loads(config_path.read_text(encoding='utf-8-sig'))
            self.assertEqual(config['coordination_ref'], '')
            validate = self.run_ps(install_dir / 'invoke-dispatch.ps1',
                                   '-Config', config_path, '-ValidateOnly')
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

    def setUp(self):
        self.config = {
            'repository': 'fixture/repo',
            'trusted_coordination_principals': [
                {'actor': 'alice', 'roles': ['Technical Planner']},
                {'actor': 'bob', 'roles': ['Reviewer']},
            ],
            'trusted_coordination_actors': [],
            'trusted_coordination_roles': [],
            'coordination_authority_ref': 'ADR-007',
        }
        self.command = {
            'schema_version': 1, 'command_id': 'cmd-001', 'action': 'revise',
            'repository': 'fixture/repo', 'wi_path': 'docs/work-items/WI-001-test.md',
            'wi_blob': '2' * 40, 'base_sha': '3' * 40, 'attempt_id': '4' * 32,
            'task_id': '11111111-1111-4111-8111-111111111111', 'checkout': 'unused',
            'work_branch': 'codex/test', 'pr_number': 7, 'expected_pr_head': '3' * 40,
            'feedback_ref': 'https://github.com/fixture/repo/pull/7#pullrequestreview-101',
            'feedback_sha256': '0' * 64, 'feedback': 'bounded feedback', 'issuer_actor': 'alice',
            'active_role': 'Technical Planner', 'authority_ref': 'ADR-007',
            'created_at': '2026-09-08T01:00:00+00:00',
        }

    def test_authorized_pair_succeeds_but_cross_pair_and_forged_role_fail(self):
        self.command['feedback_sha256'] = hashlib.sha256(b'bounded feedback').hexdigest()
        self.assertIs(validate_coordination_command(self.config, 'cmd-001', self.command), self.command)
        for actor, role in [('alice', 'Reviewer'), ('bob', 'Technical Planner'), ('alice', 'Product Owner')]:
            changed = dict(self.command, issuer_actor=actor, active_role=role)
            with self.subTest(actor=actor, role=role), self.assertRaisesRegex(RuntimeError, 'actor-role pair'):
                validate_coordination_command(self.config, 'cmd-001', changed)

    def test_legacy_single_principal_migrates_and_legacy_ambiguous_config_fails(self):
        self.command['feedback_sha256'] = hashlib.sha256(b'bounded feedback').hexdigest()
        legacy = dict(self.config, trusted_coordination_principals=None,
                      trusted_coordination_actors=['alice'],
                      trusted_coordination_roles=['Technical Planner'])
        self.assertIs(validate_coordination_command(legacy, 'cmd-001', self.command), self.command)
        ambiguous = dict(legacy, trusted_coordination_actors=['alice', 'bob'],
                         trusted_coordination_roles=['Technical Planner', 'Reviewer'])
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'):
            validate_coordination_command(ambiguous, 'cmd-001', self.command)

    def test_disabled_coordination_remains_compatible(self):
        with self.assertRaisesRegex(RuntimeError, 'disabled'):
            process_coordination(dict(self.config, coordination_ref=''), Path('.'), None, 'cmd-001')


if __name__ == '__main__':
    unittest.main()
