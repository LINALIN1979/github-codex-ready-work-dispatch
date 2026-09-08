# WI-003 — Source and installation integrity

Status: Ready
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
no live dependency is required. Ready is intentionally withheld until the
implementation baseline is checked and the dependency review is complete.
