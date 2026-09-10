# WI-010 — Design safe Developer-session recovery from GitHub checkpoints

Status: Planned
Work Type: Design
Owner Role: Technical Planner
Capability Tier: T2 Standard

## Authorization and linked source of truth

Created at the Project Owner's request on 2026-09-10 as a design-only follow-up.
References: `AGENTS.md`, `SECURITY.md`, `docs/recovery.md`,
`docs/coordination.md`, `docs/coordinator-handoff.md` and
WI-002 — Resume original task for authorized review revisions (Done).

This item is not Ready. Creating it does not authorize any host activation, runner start,
checkpoint migration, GitHub configuration change, live recovery, replacement Developer
task or implementation.

## Goal

Design a host-neutral, fail-closed recovery protocol for the case where the saved Codex
Developer session/task is demonstrably unavailable after work has been checkpointed to
GitHub. The protocol must let an authorized operator determine whether a new Developer
session may safely continue from verified GitHub evidence without duplicate execution,
lost provenance, changed requirements or implicit lifecycle approval.

## Scope

- Define the precise distinction among session lookup failure, local checkout loss,
  dispatcher/process crash, uncertain running claim and provider-side history loss.
- Inventory the GitHub checkpoints that can be trusted for recovery: immutable WI blob and
  base SHA, claim/attempt state, committed result or checkpoint SHA, work branch, Draft PR,
  coordination command/receipt and verified feedback identity where applicable.
- Specify a closed recovery-request and recovery-receipt schema, separate from
  `codex/dispatch-state`, with source identity, observed evidence, decision, operator,
  timestamp and at-most-once fencing.
- Specify preconditions for an explicitly authorized replacement Developer session, including
  stopped-process proof, clean recreated checkout, exact branch/PR/head reconciliation,
  unchanged WI/base verification, no ambiguous/running claim and a bounded recovery prompt.
- Define failure modes, user-visible Blocked evidence, audit data minimization and rollback/
  abort behavior.
- Provide a disposable-remotes and fake-Codex validation plan for a later implementation.

## Risks and non-negotiable boundaries

- GitHub evidence can be incomplete or ordered differently from a local crash; a missing
  receipt, unreadable claim, unknown process state or divergent branch/PR head must block
  recovery.
- A new session does not prove continuity with the lost session. It must never inherit an
  unverified task identity, claim authority, approval, lifecycle state or unstaged local work.
- PR text, review text, webhook payloads and model summaries are untrusted input. They cannot
  create a recovery request or change requirements.
- Recovery must not clear, replace or weaken a running/uncertain claim; must not force-push,
  rewrite history, delete checkpoints, retry blindly or create a second active Developer.
- Git metadata is provenance only, not authorization. Credentials, raw model logs and local
  absolute paths must not be written to GitHub evidence.
- This design must remain compatible with WI-002's rule that its `revise` command never
  creates a replacement task. Any future session-loss recovery is a distinct, explicit action
  with its own authorization and receipt fence.

## Out of scope

- Implementing recovery code, schemas, workflows, host configuration, provider APIs or
  GitHub App credentials.
- Automatically detecting or repairing a lost session in production.
- Live runner/cutover changes, host work-item lifecycle changes, merge automation, game or
  host-project changes.
- Replaying an uncertain execution, restoring secrets or local uncommitted files, or treating
  any checkpoint as permission to continue changed requirements.

## Acceptance criteria

1. The design defines a closed vocabulary and decision table for all loss/recovery states,
   including cases that must remain permanently Blocked.
2. It lists every required GitHub checkpoint and its exact provenance checks, and identifies
   evidence that is insufficient by itself.
3. It defines a versioned recovery-request/receipt model with independent durable
   at-most-once fencing; it does not reuse `codex/dispatch-state` as lifecycle or command
   authority.
4. A replacement session is permitted only after an explicit authorized recovery request
   references immutable WI/base/claim/attempt/branch/PR/head identities and proves the old
   process is stopped. The recovery prompt is bounded to verified checkpoints.
5. The design specifies rejection, crash and partial-publication handling that preserves all
   existing evidence and never performs force update, automatic retry or implicit task
   replacement.
6. It documents the security, privacy and provider limitations plus a test matrix using
   disposable remotes/checkouts and fake Codex/provider endpoints.
7. An independent review accepts the design before any implementation work item is created.
   No existing WI becomes Ready or Done as a consequence of this design.

## Dependencies and decision gate

The existing WI-002 adapter and recovery documentation are accepted reusable foundations, but
they do not authorize replacement-task recovery. Before implementation, the Owner must approve
the selected recovery semantics, authority surface, acceptable continuity claim and host
integration boundary. A host must separately authorize any isolated fixture; WI-007 live
cutover remains outside this item.

## Validation / evidence

Design review only. Proposed later validation must cover: unavailable task with clean GitHub
checkpoint; stopped task after partial branch push; missing/ambiguous claim; stale or changed WI;
divergent PR head; duplicate/reordered recovery requests; forged feedback; crash after receipt;
and successful bounded continuation on the same recovered work branch/Draft PR.

## Results / evidence links

Not started. No implementation or live recovery is authorized.
