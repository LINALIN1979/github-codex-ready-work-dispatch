# WI-005 — Safe work-item creation and explicit Ready authorization

Status: Planned
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
minimum eligibility contract are known; no live dependency is required. Ready is
intentionally withheld until the independent CI work is suitable for review.

