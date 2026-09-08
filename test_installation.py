import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent


def git(repo, *args, check=True):
    return subprocess.run(['git', '-C', str(repo), *args], text=True,
                          encoding='utf-8', capture_output=True, check=check)


class InstallationIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.powershell = shutil.which('pwsh') or shutil.which('powershell')
        if sys.platform == 'win32':
            cls.python_exe = Path(sys.executable)
        else:
            cls.python_exe = None

    def require_powershell_fixture(self):
        if not self.powershell or not self.python_exe or self.python_exe.suffix.lower() != '.exe':
            self.skipTest('Windows PowerShell and python.exe are required for setup fixtures')

    def make_host(self, root):
        host = root / 'host'
        host.mkdir()
        git(host, 'init', '-b', 'main')
        git(host, 'config', 'user.name', 'fixture')
        git(host, 'config', 'user.email', 'fixture@example.invalid')
        (host / 'README.md').write_text('fixture\n', encoding='utf-8')
        git(host, 'add', 'README.md')
        git(host, 'commit', '-m', 'fixture')
        git(host, 'remote', 'add', 'origin', 'https://github.com/fixture/host.git')
        return host

    def clone_dispatcher(self, root, name='dispatcher'):
        clone = root / name
        subprocess.run(['git', 'clone', '--quiet', str(ROOT), str(clone)],
                       check=True, capture_output=True, text=True)
        return clone

    def run_ps(self, script, *args):
        return subprocess.run(
            [self.powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(script), *map(str, args)],
            text=True, encoding='utf-8', errors='replace', capture_output=True)

    def run_setup(self, source, host, install_root):
        return self.run_ps(
            source / 'setup.ps1', '-HostRepo', host, '-RunnerLabel', 'fixture-dispatch',
            '-InstallRoot', install_root, '-Codex', self.python_exe,
            '-Python', self.python_exe)

    def test_clean_reviewed_source_records_provenance_and_hash_validation(self):
        self.require_powershell_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.clone_dispatcher(root)
            (source / 'harmless-local-note.txt').write_text('unrelated\n', encoding='utf-8')
            host = self.make_host(root)
            install_root = root / 'install'
            result = self.run_setup(source, host, install_root)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            install = install_root / 'fixture-host'
            manifest = json.loads((install / 'install-manifest.json').read_text(encoding='utf-8-sig'))
            revision = git(source, 'rev-parse', 'HEAD').stdout.strip()
            self.assertEqual(manifest['version'], revision)
            self.assertEqual(manifest['source_provenance']['git_revision'], revision)
            self.assertEqual(
                set(manifest['source_provenance']['files']),
                {'setup.ps1', 'bridge.py', 'invoke-dispatch.ps1',
                 'templates/ready-dispatch.yml.template'})

            validated = self.run_ps(install / 'invoke-dispatch.ps1',
                                    '-Config', install / 'config.json', '-ValidateOnly')
            self.assertEqual(validated.returncode, 0, validated.stderr + validated.stdout)
            (install / 'bridge.py').write_text('tampered\n', encoding='utf-8')
            rejected = self.run_ps(install / 'invoke-dispatch.ps1',
                                   '-Config', install / 'config.json', '-ValidateOnly')
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('Installed dispatcher changed', rejected.stderr + rejected.stdout)

    def test_dirty_material_source_is_rejected_before_host_mutation(self):
        self.require_powershell_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.clone_dispatcher(root)
            (source / 'bridge.py').write_text(
                (source / 'bridge.py').read_text(encoding='utf-8') + '# dirty fixture\n',
                encoding='utf-8')
            host = self.make_host(root)
            install_root = root / 'install'
            result = self.run_setup(source, host, install_root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('local changes in material files', result.stderr + result.stdout)
            self.assertFalse(install_root.exists())
            self.assertEqual(git(host, 'status', '--porcelain').stdout, '')
            self.assertFalse((host / '.github' / 'workflows').exists())

    def test_clean_pinned_checkout_can_validate_and_unrelated_file_is_allowed(self):
        self.require_powershell_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.clone_dispatcher(root)
            (source / 'unrelated-local-file.txt').write_text('ignored by executable check\n', encoding='utf-8')
            config = root / 'config.json'
            config.write_text(json.dumps({'codex': str(self.python_exe)}), encoding='utf-8')
            result = self.run_ps(source / 'invoke-dispatch.ps1',
                                 '-Config', config, '-ValidateOnly')
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
