# WI-005 — Safe work-item creation and explicit Ready authorization

Status: Ready
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's dispatcher hardening request dated 2026-09-09.
References: `AGENTS.md`, `docs/work-items/README.md`, `docs/WORKFLOW.md` as
applicable to host contracts, `new-work-item.ps1`, `bridge.py` and `README.md`.

## Goal

Prevent work-item creation from implicitly granting the `Ready` execution
authorization boundary while preserving support for valid manually authored Ready WIs.

## Scope

Make normal creation produce `Planned`; add a separate explicit promotion operation
that validates the minimum dispatcher eligibility contract and tests/documentation for
creation, validation and promotion.

## Out of scope

No new lifecycle states, weakened Ready parsing, automatic approval inference, host
repository changes beyond the requested helper behavior, live dispatch or changes to
claim/coordination security.

## Acceptance criteria

1. Ordinary creation produces a non-eligible `Planned` WI.
2. Incomplete or malformed WIs cannot be promoted to Ready.
3. A valid explicit promotion succeeds and is auditable in the file.
4. Existing manually authored valid Ready WIs remain supported.
5. Tests prove Ready parsing is not broadened or weakened.

## Dependencies and Ready gate

WI-004 must be internally validated first. The closed lifecycle vocabulary and
minimum eligibility contract are known; no live dependency is required. WI-004 is
internally validated and suitable for independent review on Draft PR #6; the
dependency gate is satisfied for this focused branch.

## Validation / evidence

Focused `python -m unittest test_work_items -v`: 3 tests passed. The complete suite
and static checks are recorded in `docs/validation.md`.

## Results / evidence links

`new-work-item.ps1` now creates `Status: Planned` with the closed default role and
T2 tier. The new `mark-ready.ps1` is a separate explicit operation: it accepts only
one `Status: Planned` field, a valid dispatcher filename, closed role/tier values,
exactly one non-empty Goal and Acceptance criteria heading, and a non-empty criteria
list. It changes only the status after all validation succeeds; failed promotion
leaves the source file unchanged. Existing manually authored valid Ready items still
pass the unchanged `bridge.py` parser.

Out-of-scope changes: None. Ready remains the automatic execution authorization
boundary; this work item is Review and is not Done.
