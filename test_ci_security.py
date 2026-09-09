import subprocess
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
DIFF_RANGE_SPEC = spec_from_file_location('check_diff_range', ROOT / 'ci' / 'check_diff_range.py')
DIFF_RANGE = module_from_spec(DIFF_RANGE_SPEC)
DIFF_RANGE_SPEC.loader.exec_module(DIFF_RANGE)


class CISecurityTests(unittest.TestCase):
    def test_credential_scan_reports_location_without_secret_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_secret = 'ghp_' + 'A' * 40
            fixture = Path(directory) / 'fixture.txt'
            fixture.write_text(f'token = {fake_secret}\n', encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(ROOT / 'ci' / 'check_credentials.py'), '--root', directory],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn('fixture.txt:1:github-token', result.stdout)
            self.assertNotIn(fake_secret, result.stdout + result.stderr)
            self.assertNotIn('token =', result.stdout + result.stderr)

    def test_diff_range_uses_pull_request_base_push_before_and_safe_initial_fallback(self):
        base = '1' * 40
        before = '2' * 40
        head = '3' * 40
        self.assertEqual(
            DIFF_RANGE.choose_range('pull_request', '', base, head), (base, head)
        )
        self.assertEqual(
            DIFF_RANGE.choose_range('push', before, '', head), (before, head)
        )
        with patch.object(DIFF_RANGE.subprocess, 'run') as run:
            run.return_value.stdout = base + '\n'
            self.assertEqual(
                DIFF_RANGE.choose_range('push', '0' * 40, '', head), (base, head)
            )



if __name__ == '__main__':
    unittest.main()
