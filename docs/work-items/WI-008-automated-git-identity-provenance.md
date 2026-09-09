# WI-008 — Automated Git identity provenance

Status: Planned
Work Type: Design
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Raised from the independent security review of the existing dispatcher baseline on
2026-09-09. References: `bridge.py`, `setup.ps1`, `docs/coordination.md`, `SECURITY.md`
and the GitHub attribution model. This is a separate finding and is not part of
WI-003–WI-007.

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

## Out of scope

No historical commit rewrite, force-push, state/history replacement, host activation,
live provider/Codex execution, weakening of WI-002 signature/actor/feedback/CAS/replay
checks, or implementation in WI-003–WI-007.

## Acceptance criteria

1. All automated Git identity configuration paths are identified with current behavior.
2. The design compares the preferred reserved `.invalid` default with an explicitly
   reviewed dedicated bot/App identity, including operational tradeoffs.
3. The selected policy, if any, applies consistently to work, dispatch-state and
   coordination commits as appropriate, with clear host opt-in rules.
4. Documentation distinguishes Git author metadata from authenticated coordination
   authority and states that old attribution cannot be retroactively corrected here.
5. The design is independently reviewable and contains no implementation or history
   rewrite.

## Dependencies and decision gate

This work item is intentionally **Planned**, not Ready. The Owner must choose between:

- **Preferred default:** retain the clear automation name and use a reserved
  `github-codex-ready-work-dispatch@invalid`-style address; or
- **Dedicated identity:** require each host to configure a separately reviewed bot/App
  identity, with no accidental fallback to a personal account.

The Owner must also confirm whether the default is to be applied uniformly to work,
dispatch-state and coordination stores, or whether a documented exception is needed.
Until those decisions are recorded, promoting this item to Ready would assume an
identity policy outside the current implementation authority.

## Validation / evidence

The baseline finding is the observed configuration of automated repositories/checkouts:
`user.name = github-codex-ready-work-dispatch` and
`user.email = bridge@users.noreply.github.com`. No historical attribution is changed
by this work item, and no live host or GitHub account operation is required for design.

## Results / evidence links

Pending the Owner decision above. No implementation is authorized while this item is
Planned. Out-of-scope changes: None.
