# WI-001 — Reliable Draft PR and coordinator handoff

Status: Ready
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

2026-09-08: repository Owner directly authorized planning and implementing reliable,
idempotent Review/Blocked Draft PR publication and a generic event-driven coordinator
contract, tests, review branches, push and PR creation; no merge or live deployment.
Source task: 01a06817-c097-7f92-acf7-0a323783f344.
References: AGENTS.md, docs/work-items/README.md, docs/internals.md,
docs/recovery.md, SECURITY.md. Host governance was read from Home Rolls On remote main.

## Goal

Make every Developer result discoverable through a verified Draft PR, or leave an
explicit fail-closed publication failure with a publication-only recovery path.

## Scope

PR lookup/create/update, durable PR identity/status and result evidence, safe recovery,
generic coordinator contract, offline unit/integration tests and operator documentation.

## Out of scope

No host-specific data, live runner/config changes, historical WI execution, merge,
force push, product/art/game architecture decisions or coordinator Owner authority.

## Acceptance criteria

1. Review and Blocked publish one Draft PR per repository/base/head; retries and duplicate
   events recover/update it without creating another or replacing reviewer-owned text.
2. Durable claim and committed result evidence retain verified PR URL, number, state,
   draft flag and handoff status. Closed/merged/non-draft conflicts fail closed.
3. Token/permission/network/ambiguous API failure explicitly pauses dispatch; the branch,
   result and local recovery data survive. Compare links never count as PR success.
4. Explicit publication-only recovery updates the same result/claim without starting
   Codex, changing lifecycle authority or clearing unrelated pauses.
5. Tests cover Review, Blocked, duplicate, technical retry, token/permission failure,
   uncertain create and existing PR recovery, durable failure/recovery and Git CAS.
6. Document a generic GitHub PR event contract, idempotency, trust checks and authority
   boundaries; provider configuration remains host-owned.

## Dependencies and Ready gate

Remote main verified at 8f3ff77a61009a7e5651208c7b4b8a2257230dae; no state branch exists
in this reusable repository. Explicit Owner scope resolves bounded tooling decisions.
All required references, testable criteria and role are present; no live dependency is
needed for offline implementation. Ready gate satisfied before implementation.

## Validation / evidence

Full unittest suite, temporary Git remotes and fake API/Codex, duplicate/race tests,
PowerShell AST parse, workflow YAML/actionlint and scope/security/diff checks.

## Results / evidence links

Not started. Ready checkpoint precedes implementation.
