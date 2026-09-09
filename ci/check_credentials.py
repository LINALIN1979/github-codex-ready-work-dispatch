"""Fail if tracked-text candidates contain common credential formats."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {Path('docs/validation.md'), Path('.github/workflows/ci.yml')}
SECRET_PATTERN = re.compile(
    r'(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|'
    r'AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)'
)


def main() -> int:
    findings = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or '.git' in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if relative in EXCLUDED:
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError as error:
            print(f'Cannot read {relative}: {error}', file=sys.stderr)
            return 2
        for line_number, line in enumerate(text.splitlines(), 1):
            if SECRET_PATTERN.search(line):
                findings.append(f'{relative}:{line_number}:{line}')
    if findings:
        print('\n'.join(findings))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
