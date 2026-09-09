"""Fail if tracked-text candidates contain common credential formats."""

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {Path('docs/validation.md'), Path('.github/workflows/ci.yml')}
SECRET_PATTERN = re.compile(
    r'(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|'
    r'AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)'
)


def scan(root=ROOT):
    root = Path(root)
    findings = []
    for path in root.rglob('*'):
        if not path.is_file() or '.git' in path.parts:
            continue
        relative = path.relative_to(root)
        if root == ROOT and relative in EXCLUDED:
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError as error:
            raise RuntimeError(f'Cannot read {relative}: {error}') from error
        for line_number, line in enumerate(text.splitlines(), 1):
            match = SECRET_PATTERN.search(line)
            if not match:
                continue
            if match.group(1).startswith(('ghp_', 'github_pat_')):
                kind = 'github-token'
            elif match.group(1).startswith('AKIA'):
                kind = 'aws-access-key'
            else:
                kind = 'private-key-header'
            findings.append(f'{relative}:{line_number}:{kind}')
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        findings = scan(args.root)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 2
    if findings:
        print('\n'.join(findings))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
