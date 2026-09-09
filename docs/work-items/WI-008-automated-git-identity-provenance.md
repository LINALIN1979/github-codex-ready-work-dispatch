# WI-008 — Automated Git identity provenance

Status: Done
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Raised from the independent security review of the existing dispatcher baseline on
2026-09-09. References: `bridge.py`, `setup.ps1`, `docs/coordination.md`, `SECURITY.md`
and the GitHub attribution model. This is a separate finding and is not part of
WI-003–WI-007.

## Owner decision — 2026-09-09

The Owner approved the preferred default identity policy. Unless a host explicitly
configures a dedicated reviewed bot/App identity, every dispatcher-generated Git
commit uses:

```text
user.name = github-codex-ready-work-dispatch
user.email = github-codex-ready-work-dispatch@invalid
```

The same default applies consistently to Developer/work checkout commits,
`codex/dispatch-state` commits and coordination-store commits. A dedicated identity
override must be explicit and must not silently fall back to a personal account.

Git author/committer metadata is provenance only. It is not authorization evidence;
WI-002 remains separately enforced through command-origin signature, verified GitHub
actor, actor→role authorization, exact feedback/context checks, durable CAS receipts
and replay fencing. Provider-specific App authentication is out of scope unless
explicitly authorized later.

## Goal

Define an intentionally controlled, non-misleading Git author identity for future
dispatcher-generated commits, without rewriting historical commits or confusing Git
metadata with authenticated GitHub coordination authority.

## Scope

Inventory every automated commit path and its current `user.name`/`user.email`
configuration, including work checkouts, the dispatch-state store and the coordination
store where applicable. Design one consistent default policy that retains a clear
automation `user.name` and uses a reserved `.invalid` address unless a host explicitly
configures a dedicated, reviewed bot/App identity. Document opt-in host-specific identity
requirements, propagation points, migration limits, audit evidence and the distinction
between Git author/committer metadata and WI-002 authenticated coordinator authority.

## Baseline inventory

The current implementation configures the same personal-account-mappable identity in
three automated commit paths: `DispatchStore` for `codex/dispatch-state`,
`CoordinationStore` for the coordination store, and fresh Developer/work checkouts.
Each currently sets `user.name` to `github-codex-ready-work-dispatch` but sets
`user.email` to `bridge@users.noreply.github.com`. The approved policy replaces that
email in all three paths with the reserved `.invalid` address; it does not use either
Git field as WI-002 authorization evidence.

## Out of scope

No historical commit rewrite, force-push, state/history replacement, host activation,
live provider/Codex execution, weakening of WI-002 signature/actor/feedback/CAS/replay
checks, or implementation in WI-003–WI-007.

## Acceptance criteria

- All automated Git identity configuration paths are identified with current behavior.
- The design compares the preferred reserved `.invalid` default with an explicitly
  reviewed dedicated bot/App identity, including operational tradeoffs.
- The selected policy, if any, applies consistently to work, dispatch-state and
  coordination commits as appropriate, with clear host opt-in rules.
- Documentation distinguishes Git author metadata from authenticated coordination
  authority and states that old attribution cannot be retroactively corrected here.
- The design is independently reviewable and contains no implementation or history
  rewrite.

## Dependencies and decision gate

The Owner decision above closes the identity-policy decision gate. The design was
implemented only after PRs #5–#9 were integrated. No implementation was added to those
PRs.

## Validation / evidence

The baseline finding was the observed configuration of automated repositories/checkouts:
`user.name = github-codex-ready-work-dispatch` and
`user.email = bridge@users.noreply.github.com`. The implementation now configures the
approved `.invalid` identity in all three runtime paths, including fresh work checkouts
and preserved checkouts resumed through both retry and revision flows. No historical
attribution is changed by this work item, and no live host or GitHub account operation
is required.

Focused `python -B -m unittest test_git_identity -v`: 6 tests passed. The full Python
suite passed 56 tests. GitHub-hosted CI run `34310841865` passed all six jobs for head
`04b746fecda9b88abe81926b11d5c744f2be0adb`, including Ubuntu/Windows Python 3.10/3.14,
PowerShell/static checks, workflow/template validation and actionlint. Retry and revision
fixtures exercised preserved checkouts, real checkpoint commits, migration to the
approved identity before new commits, and preservation of historical commits.

## Results / evidence links

Owner decision recorded and implemented: use the reserved `.invalid` identity by
default, uniformly across work, dispatch-state and coordination commits, with an
explicit reviewed bot/App override only. Runtime code has no old-email reference;
historical evidence remains intentionally documented. Git metadata remains provenance
only and WI-002/WI-006 authentication, actor-role, feedback, context, CAS, same-task and
replay invariants remain unchanged.

Independent review approved the preserved-checkout migration revision. PR #10 was
merged to `main` on 2026-09-09 with merge commit
`f4c1be620b2bd0694a7ca6d89997362c32103043`. Historical commits and attribution were
not rewritten. Out-of-scope changes: None.
