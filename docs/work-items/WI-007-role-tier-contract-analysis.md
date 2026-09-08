# WI-007 — Dispatcher role/tier contract analysis

Status: Planned
Work Type: Documentation
Owner Role: Docs / Traceability
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's dispatcher hardening request dated 2026-09-09.
References: `bridge.py`, `README.md`, `SECURITY.md`, `docs/coordination.md`,
`docs/integration.md`, `docs/MODEL_TIERS.md` where host context is relevant, and
the existing work-item contract.

## Goal

Decide and document whether this reusable dispatcher is intentionally Developer-
oriented with a closed execution-role vocabulary or is meant to be host-neutral.

## Scope

Analyze hard-coded roles and capability-tier behavior, document the resulting
contract and correct misleading integration language. If host-neutral behavior is
required, document the design gap and propose a separate future implementation WI.

## Out of scope

No authority expansion, arbitrary-role support, machine-readable host-policy
implementation, live dispatch, host repository changes or manufactured code change.

## Acceptance criteria

1. The role/tier conclusion is evidence-backed by the current dispatcher code and docs.
2. Developer-oriented behavior retains its closed role/tier contract and docs do not
   imply arbitrary host roles are supported.
3. Any host-neutral gap is recorded as a future separately authorized implementation,
   not silently implemented here.
4. Analysis is independently reviewable with explicit out-of-scope and no live fixtures.

## Dependencies and Ready gate

WI-006 must be internally validated first because its authorization binding affects
the documented role boundary. This is a documentation/decision work item and needs no
live dependency. Ready is intentionally withheld until WI-006 is suitable for review.

