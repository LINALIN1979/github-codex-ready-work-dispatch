# ADR-001 — Coordinator revision-command boundary

Status: Accepted
Date: 2026-09-08

## Context

The dispatcher creates one saved Codex task, isolated checkout, work branch and Draft PR
for an initial host work item. It can resume stopped quota/error/timeout attempts, but it
does not accept ordinary review feedback or resume a Review result. Hosts that want one
Owner-facing coordinator therefore still require a human to relay review prompts.

PR comments and event payloads are untrusted and cannot safely become local execution
instructions. The host's `codex/dispatch-state` is already limited to execution facts and
must not become coordinator authority or lifecycle state.

## Decision

Add an optional, disabled-by-default revision-command adapter with these boundaries:

- The host supplies a dedicated coordination ref and a configured allowlist of trusted
  GitHub actors. The ref is separate from the base branch and `codex/dispatch-state`.
- Commands and receipts use a versioned closed schema, append-only logical IDs and
  non-force compare-and-swap publication.
- Initial actions are `revise` and `technical_retry`. No command represents merge,
  lifecycle transition, Product/Art/Architecture approval or changed scope.
- A `revise` command must match the host repository, source WI path/blob, base SHA, claim
  attempt/task, recovery checkout, work branch, Draft PR number and expected PR head.
- The dispatcher verifies the configured actor and host governance reference, requires a
  stopped/non-running claim and clean exact checkout, then resumes the saved Codex task on
  the same branch. It never creates a replacement task for a revision command.
- Duplicate/stale/forged/ambiguous commands are durable no-ops or failures. One command ID
  can invoke Codex at most once. A receipt records the observed identities and outcome.
- Feedback content is bounded and referenced by immutable GitHub identity/digest. It is
  still treated as untrusted data inside a governance-framed Developer prompt.
- Command processing is exposed only through an explicit invocation/workflow input. Merely
  receiving a PR event never executes local code.

## Alternatives

1. Dedicated host coordination ref (recommended): auditable CAS fencing and clean state
   separation.
2. Execute PR comments directly: rejected because authorization, replay and injection
   boundaries are insufficient.
3. Put commands on host main: rejected because routine revisions would mutate lifecycle
   source and retrigger Ready scanning.
4. Create a new Codex task per review: rejected because it loses task continuity and makes
   duplicate review events expensive and ambiguous.

## Consequences

Hosts retain provider UX, actor policy, coordination-ref ownership and end-to-end
validation. This reusable repository owns schema validation, exact identity checks,
original-task resume, receipts and offline tests. Existing hosts are unchanged until they
pin a reviewed implementation and explicitly configure/invoke the adapter.

The Technical Owner accepted this decision on 2026-09-08. It grants no host coordinator
write access, approval authority, merge authority or live deployment by itself.
