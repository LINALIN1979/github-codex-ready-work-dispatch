from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from bridge import parse_wi


ROOT = Path(__file__).resolve().parent


class WorkItemAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.powershell = shutil.which('pwsh') or shutil.which('powershell')

    def require_powershell(self):
        if not self.powershell:
            self.skipTest('PowerShell is required for work-item helper tests')

    def run_ps(self, script, *args):
        return subprocess.run(
            [self.powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(script), *map(str, args)],
            text=True, encoding='utf-8', errors='replace', capture_output=True)

    def test_creation_is_planned_and_explicit_valid_promotion_succeeds(self):
        self.require_powershell()
        with tempfile.TemporaryDirectory() as temporary:
            host = Path(temporary)
            created = self.run_ps(ROOT / 'new-work-item.ps1', '-HostRepo', host,
                                  '-Title', 'Add export command', '-Goal', 'Add the approved export command',
                                  '-Acceptance', '- Export produces the expected file.')
            self.assertEqual(created.returncode, 0, created.stderr + created.stdout)
            path = next((host / 'docs' / 'work-items').glob('WI-*.md'))
            text = path.read_text(encoding='utf-8')
            self.assertIn('Status: Planned', text)
            self.assertIsNone(parse_wi('docs/work-items/' + path.name, text))
            promoted = self.run_ps(ROOT / 'mark-ready.ps1', '-HostRepo', host,
                                   '-WorkItem', path.name)
            self.assertEqual(promoted.returncode, 0, promoted.stderr + promoted.stdout)
            ready = path.read_text(encoding='utf-8')
            self.assertIn('Status: Ready', ready)
            self.assertIsNotNone(parse_wi('docs/work-items/' + path.name, ready))

    def test_incomplete_or_malformed_work_item_is_not_promoted(self):
        self.require_powershell()
        with tempfile.TemporaryDirectory() as temporary:
            host = Path(temporary)
            directory = host / 'docs' / 'work-items'
            directory.mkdir(parents=True)
            cases = {
                'WI-001-empty-goal.md': 'Status: Planned\nOwner Role: Implementer\n## Goal\n\n## Acceptance criteria\n- Works\n',
                'WI-002-bad-role.md': 'Status: Planned\nOwner Role: Product Owner\n## Goal\nDo it\n## Acceptance criteria\n- Works\n',
                'WI-003-bad-tier.md': 'Status: Planned\nCapability Tier: T3 Deep\n## Goal\nDo it\n## Acceptance criteria\n- Works\n',
                'WI-004-no-criteria-list.md': 'Status: Planned\n## Goal\nDo it\n## Acceptance criteria\nPending\n',
            }
            for name, text in cases.items():
                path = directory / name
                path.write_text(text, encoding='utf-8')
                result = self.run_ps(ROOT / 'mark-ready.ps1', '-HostRepo', host,
                                     '-WorkItem', name)
                with self.subTest(name=name):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(path.read_text(encoding='utf-8'), text)

    def test_existing_valid_manually_authored_ready_item_remains_supported(self):
        text = 'Status: Ready\nOwner Role: Docs / Traceability\nCapability Tier: T1\n## Goal\nDocument it\n## Acceptance criteria\n- Link the evidence\n'
        self.assertIsNotNone(parse_wi('docs/work-items/WI-009-manual.md', text))


if __name__ == '__main__':
    unittest.main()
