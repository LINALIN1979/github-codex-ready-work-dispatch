# WI-004 — Independent GitHub-hosted CI

Status: Done
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's dispatcher hardening request dated 2026-09-09.
References: `AGENTS.md`, `SECURITY.md`, `templates/ready-dispatch.yml.template`,
`docs/validation.md` and the existing Python/PowerShell/workflow checks.

## Goal

Provide independent, GitHub-hosted CI that verifies this reusable dispatcher
without using a privileged desktop runner or live Codex/provider behavior.

## Scope

Add a repository CI workflow and deterministic validation for the full Python
suite, Python 3.10 compatibility where claimed, PowerShell parsing, YAML/template
validation, actionlint where practical, `git diff --check` and existing static /
security checks; document tested versus simulated behavior.

## Out of scope

No self-hosted runner targeting, Codex execution, host mutation, SSH keys,
coordination commands, secrets, repository settings, branch protection or ruleset
changes.

## Acceptance criteria

1. CI runs only on GitHub-hosted runners and requires no secrets or repository writes.
2. The complete existing test suite and stated compatibility/static checks run in CI.
3. Third-party actions use immutable commit pins where practical.
4. Documentation distinguishes real tests, disposable local Git behavior, simulated
   GitHub/Codex/provider behavior and unproven live-host behavior.
5. CI configuration and checks are reviewable offline without starting a runner.

## Dependencies and Ready gate

WI-003 must be internally validated first because CI will exercise its installation
and provenance checks. No live host or provider dependency is required. WI-003 is
internally validated and suitable for independent review on Draft PR #5; the
dependency gate is satisfied for this focused branch.

## Validation / evidence

`python -m unittest discover -s . -p 'test_*.py' -v`: 37 tests passed in 94.815
seconds before the hosted-run compatibility fixes; the corrected branch also passes the
same suite in 102.987 seconds. Python 3.10 AST, PowerShell AST, `git diff --check` and
credential-pattern checks passed. With isolated PyYAML 6.0.3, `python ci/validate_yaml.py`
passed for the CI workflow and rendered dispatcher template. Hosted run `34253865489`
passed workflow/template validation, actionlint and both Ubuntu jobs, while revealing
Windows path-normalization and scanner self-match issues. The fixes are on this branch;
corrected hosted run `34295193351` passed all six jobs, including both Windows Python
matrix jobs and PowerShell/static checks. The review revisions then produced head
`3a020d2e7beb797946b852207e37fa220b64d572`; hosted run `34298388997` for that head
also passed all six jobs. The dedicated credential scanner and the isolated YAML
validator also pass locally. No host
repository, runner, provider or secret was used.

## Results / evidence links

`.github/workflows/ci.yml` uses only GitHub-hosted `ubuntu-latest` and `windows-latest`
runners with `contents: read`. It runs the complete Python suite on 3.10/3.14,
PowerShell and static checks, PyYAML workflow/template validation and actionlint from
the pinned v1.7.7 module. `docs/ci.md` records what is real, disposable, simulated or
unproven. Review revisions restore canonical resume checkout handling, use a redacting
credential scanner with regression coverage, and validate complete event-specific diff
ranges with full history and fixed subprocess arguments. Third-party actions are pinned to immutable commit SHAs; no Codex execution,
coordination command, SSH key, secret or repository write is configured.

Out-of-scope changes: None. Independent review approved the implementation and PR #6
was merged to `main` with merge commit `ecb00317cdad331c729da7b43a8ac85d386630d6`
on 2026-09-09. The lifecycle record is therefore Done.
