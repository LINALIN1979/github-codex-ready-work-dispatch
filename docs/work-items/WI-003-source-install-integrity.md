# WI-003 — Source and installation integrity

Status: Review
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's dispatcher hardening request dated 2026-09-09.
References: `AGENTS.md`, `SECURITY.md`, `setup.ps1`, `invoke-dispatch.ps1`,
`bridge.py`, `templates/ready-dispatch.yml.template`, `docs/recovery.md` and
`docs/validation.md`.

## Goal

Ensure an installation never claims a Git revision that does not represent the
source actually copied into the installed runtime.

## Scope

Fail-closed source provenance checks in `setup.ps1` and related invocation/hash
validation; explicit behavior for non-Git source; focused regression tests and
validation evidence. Preserve pinned-submodule execution and all host data,
claims, logs, recovery checkouts and configuration.

## Out of scope

No dispatcher behavior redesign, host repository changes, live runner/provider
execution, workflow activation, reset/stash/discard/history rewrite or changes
to coordination authority.

## Acceptance criteria

1. Clean reviewed source installs successfully and records provenance for every
   materially installed runtime source file.
2. Dirty relevant tracked or untracked source is rejected or explicitly marked
   unverified; no false Git revision is recorded.
3. Harmless unrelated local files do not incorrectly block installation.
4. Installed hash validation and pinned-submodule invocation remain working.
5. Validation does not mutate host execution state.
6. Focused and complete offline tests cover the above and the security invariants
   remain unchanged.

## Dependencies and Ready gate

WI-002 is Done and its accepted coordination boundary is unchanged. The source
files, provenance policy, tests and offline disposable-host evidence are defined;
no live dependency is required. The Ready gate was satisfied before implementation
on this focused branch.

## Validation / evidence

Focused installation tests and the complete offline suite passed on Windows / Python
3.14.6: `python -m unittest test_installation -v` (3 tests) and
`python -m unittest discover -s . -p 'test_*.py' -v` (37 tests). Python 3.10 AST
parsing and PowerShell AST parsing passed. `git diff --check` and credential-pattern
scan passed. The disposable setup fixture verified clean provenance, harmless unrelated
untracked files, dirty material-source rejection before host writes, installed hash
validation and clean pinned-checkout invocation. YAML/actionlint tools were unavailable
in this local environment; the template was unchanged and these checks are recorded
for independent CI review in WI-004.

## Results / evidence links

The original provenance issue was confirmed. `setup.ps1` now requires a Git repository
root with a verified 40-hex `HEAD`, all four material source paths tracked and no
tracked, staged or untracked changes in those paths before creating install/data
directories. Non-Git source fails closed. The manifest records the Git revision and
SHA-256 hashes for `setup.ps1`, `bridge.py`, `invoke-dispatch.ps1` and
`templates/ready-dispatch.yml.template`, plus installed executable hashes. The
installed invocation validates the manifest revision relationship and existing hashes.
Pinned-submodule execution remains a clean executable-checkout path without a manifest.

Out-of-scope changes: None. No host repository, live runner/provider, claims, logs,
recovery checkout, configuration, force push or history rewrite was touched.

## Completion notes

Implementation and internal validation are complete. This work item is intentionally
left at Review for independent review; it is not Done and no PR was merged.
