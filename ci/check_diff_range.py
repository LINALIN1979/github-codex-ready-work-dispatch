"""Run git diff --check over the complete event-specific reviewed range."""

import os
from pathlib import Path
import re
import subprocess
import sys


SHA = re.compile(r'^[0-9a-fA-F]{40}$')


def _require_sha(name, value):
    if not value or not SHA.fullmatch(value):
        raise RuntimeError(f'{name} is not a full commit SHA')
    return value


def choose_range(event_name, before, pull_request_base, head, repository=Path('.')):
    head = _require_sha('head', head)
    if event_name == 'pull_request':
        base = _require_sha('pull request base', pull_request_base)
    elif event_name == 'push' and before and set(before) != {'0'}:
        base = _require_sha('push before', before)
    else:
        roots = subprocess.run(
            ['git', 'rev-list', '--max-parents=0', head],
            cwd=repository, check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        if not roots:
            raise RuntimeError('cannot determine an initial commit fallback')
        base = _require_sha('initial commit fallback', roots[0])
    return base, head


def main():
    try:
        base, head = choose_range(
            os.environ.get('CI_EVENT_NAME', ''),
            os.environ.get('CI_BEFORE_SHA', ''),
            os.environ.get('CI_PR_BASE_SHA', ''),
            os.environ.get('CI_HEAD_SHA', ''),
        )
        completed = subprocess.run(['git', 'diff', '--check', base, head])
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Unable to validate complete diff range: {error}', file=sys.stderr)
        return 2
    if completed.returncode:
        return completed.returncode
    print(f'git diff --check range: {base}..{head}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
