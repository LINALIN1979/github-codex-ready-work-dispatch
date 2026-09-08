# WI-002 — Resume original task for authorized review revisions

Status: Review
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's 2026-09-08 request for a coordinator-managed review
loop that reuses the original Codex Developer task. The Technical Owner accepted ADR-001
on 2026-09-08. References: ADR-001 (Accepted),
`docs/coordinator-handoff.md`, `docs/internals.md`, `docs/recovery.md` and SECURITY.md.

## Goal

Provide a host-neutral, fail-closed command and receipt adapter that resumes the exact saved
Developer task for review feedback without interpreting PR content as execution authority.

## Scope

Versioned command/receipt schema; configured coordination ref and trusted-actor validation;
exact WI/claim/task/checkout/branch/PR/head checks; `revise` original-task resume; explicit
technical retry mapping; CAS/idempotency; durable failure/recovery evidence; setup/invocation
wiring; offline tests and operator documentation.

## Out of scope

No provider-specific ChatGPT Work API, host governance decision, automatic PR-comment
execution, new task fallback, merge, lifecycle transition, approval inference, active host
upgrade, secret storage or game/project code.

## Acceptance criteria

1. Feature is disabled by default; existing configuration, Ready dispatch, technical retry
   and publication-only recovery remain compatible.
2. A valid `revise` command with exact host/WI/base/claim/task/branch/PR/head identities
   invokes the saved Codex task once and updates the same branch/Draft PR evidence.
3. Duplicate, reordered, stale-head, changed-WI, wrong-repository, wrong-actor, forged-role
   and malformed commands never invoke Codex and produce sanitized durable evidence.
4. Missing task, running/uncertain claim, dirty or mismatched checkout, ambiguous PR or CAS
   conflict fails closed without replacement task, force push, fence clearing or lifecycle
   change.
5. Versioned receipts make one command ID at-most-once across duplicate workflow events,
   process interruption and competing dispatchers; recovery never replays an uncertain run.
6. Developer prompts clearly delimit untrusted feedback from repository governance and do
   not treat review text as Product/Art/Architecture approval.
7. Tests use disposable Git remotes, fake Codex/GitHub endpoints and interruption points;
   PowerShell/YAML/schema/security and backward-compatibility checks pass.

## Dependencies

ADR-001 Accepted and explicit Owner authorization of the command schema/security boundary.
No live host/provider is required for offline implementation.

## Ready gate

Goal, scope, closed acceptance criteria, role, capability and offline evidence are defined.
ADR-001 is Accepted; implementation is disabled by default and requires no live dependency.
No unresolved Owner decision blocks this bounded reusable implementation. Ready gate met.

## Validation / evidence

Full unit/integration suite with real disposable Git remotes and fake model/provider;
duplicate/CAS/crash tests; PowerShell AST, YAML/actionlint, Python 3.10 grammar, setup hash,
credential scan and `git diff --check`. No live runner or host work item execution.

## Results / evidence links

Bounded implementation completed and submitted for independent Review. The adapter is disabled
by default and requires an explicit command ID plus a fully configured dedicated ref, trusted
actor/role and authority reference. It verifies the immutable command-origin GitHub actor,
closed schema/digest, exact base/WI/claim/task/checkout/branch/Draft-PR/head identities and a
clean stopped checkout before publishing an at-most-once CAS receipt and resuming the original
task. Duplicate or interrupted commands do not replay; failures preserve sanitized evidence.

Evidence: `docs/validation.md` (WI-002 section), `test_coordination.py`, rendered setup/workflow
fixture, PowerShell/Python/JSON/actionlint checks and the full offline test suite. No live host,
provider command, runner upgrade, merge, lifecycle approval or project code was exercised.
