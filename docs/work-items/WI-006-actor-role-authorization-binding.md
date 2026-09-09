# WI-006 — Coordinator actor-role authorization binding

Status: Planned
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's dispatcher hardening request dated 2026-09-09.
References: WI-002, `docs/coordination.md`, `docs/decisions/ADR-001-coordinator-revision-commands.md`,
`setup.ps1`, `invoke-dispatch.ps1`, `bridge.py`, `SECURITY.md` and `docs/recovery.md`.

## Goal

Bind authenticated coordinator actors to explicitly authorized roles without
implicitly authorizing the Cartesian product of trusted actors and trusted roles.

## Scope

Review and, if confirmed, implement a small closed actor-to-role configuration
binding; preserve disabled-by-default behavior, command-origin/signature checks,
exact identity checks, durable CAS receipts and the same original Developer task.
Add migration-safe validation, tests and documentation.

## Out of scope

No general RBAC system, direct PR-comment execution, merge/lifecycle/Product/Art/
Architecture authority, host activation, live provider fixtures, force push or
reinterpretation of an existing enabled configuration.

## Acceptance criteria

1. Two actors/two roles exercise an authorized pair successfully.
2. A trusted actor using another trusted role and a forged role fail closed without
   Developer execution.
3. Disabled coordination remains backward compatible.
4. A legitimate single-principal configuration has a documented migration path.
5. Existing WI-002 trust, identity, CAS, receipt and replay invariants remain covered.

## Dependencies and Ready gate

WI-005 must be internally validated first. WI-002's accepted schema and disabled
default are fixed inputs; any enabled configuration format change requires deliberate
version/documentation. Ready is intentionally withheld until dependency review passes.
