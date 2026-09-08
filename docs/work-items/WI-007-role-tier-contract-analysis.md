# WI-007 — Dispatcher role/tier contract analysis

Status: Ready
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
live dependency. WI-006 is internally validated and suitable for independent review on
Draft PR #8; the dependency gate is satisfied for this focused branch.

## Validation / evidence

Analysis is based on `bridge.py`, `README.md`, `SECURITY.md`, `docs/integration.md`,
`docs/coordination.md` and `docs/MODEL_TIERS.md` from the current dispatcher baseline.
No live host, runner, provider or Codex fixture is required.

## Results / evidence links

The dispatcher is intentionally Developer-oriented, not completely host-neutral. The
closed execution-role vocabulary is `Implementer`, `Tester / Playtester` and
`Docs / Traceability`; unknown Owner Role values are not eligible. Capability tiers
default to `T2 Standard` and accept only `T1` or `T2` prefixes. These fields select the
Developer task contract and never grant Product, Art, Architecture, lifecycle, merge,
scope or acceptance authority. Coordinator roles in WI-006 are a separate trust-policy
concept and must not be confused with Developer execution roles.

No code change is required. A future host-neutral dispatcher, if ever desired, would
need a separately authorized implementation WI with machine-readable host policy; this
WI does not expand the current authority boundary or invent that work item.

Out-of-scope changes: None. This work item is Review and is not Done.
