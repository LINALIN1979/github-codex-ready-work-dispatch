# WI-006 — Coordinator actor-role authorization binding

Status: Done
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
version/documentation. WI-005 is internally validated and suitable for independent
review on Draft PR #7; the dependency gate is satisfied for this focused branch.

## Validation / evidence

Focused `python -m unittest test_actor_role_binding -v`: 6 tests passed. The fixture
executes setup, generated config validation, installed bridge authorization parsing,
explicit valid/cross-pair outcomes, legacy migration, ambiguous legacy rejection,
disabled compatibility and whitespace-only binding rejection. The complete suite and
static checks are recorded in `docs/validation.md`. The operator-path fixture is
also parsed with the Python 3.10 grammar used by hosted CI.

## Results / evidence links

The prior Cartesian-product behavior was confirmed. `trusted_coordination_principals`
now provides a closed actor-to-role mapping. Legacy enabled configurations remain
supported only for exactly one actor and one role; ambiguous multi-actor/multi-role
legacy settings fail closed. Setup accepts repeated `actor=role` bindings, rejects empty
roles and emits the explicit mapping at sufficient JSON depth. Command data still cannot create authority: authentication is
verified separately against the signed GitHub commit actor, then the actor-role pair
is checked before feedback/context validation and durable acceptance.

Out-of-scope changes: None. Disabled coordination, WI-002 schemas, receipts, exact
identity checks, same-task resume and replay fences remain in scope and covered.
Independent review approved the implementation and PR #8 was merged to `main` with
merge commit `096d0fc9bb4d0c6124c74be4744a05fcc8a70527` on 2026-09-09. The lifecycle
record is therefore Done.
