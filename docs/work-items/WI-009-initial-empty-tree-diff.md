# WI-009 — Initial-repository empty-tree diff validation

Status: Planned
Work Type: Design
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Low-priority follow-up finding from WI-004's complete-range CI review on 2026-09-09.
References: `ci/check_diff_range.py`, `.github/workflows/ci.yml` and `docs/ci.md`.
This follow-up is not a blocker for PR #6 and is not part of PRs #5–#9's current
integration sequence.

## Goal

Ensure the initial/zero-before push fallback checks the root commit itself by
diffing Git's empty tree against the head, rather than starting at the root commit
and potentially omitting its changes.

## Scope

Design and implement a bounded, deterministic empty-tree fallback for the initial
repository case. Preserve pull-request base→head and ordinary push before→head
behavior, full-SHA validation, argument-list subprocess calls and no shell evaluation.
Add focused tests for a clean root commit and a root commit containing a whitespace
defect.

## Out of scope

No changes to PR #6's current implementation, PR #5–#9 bases or merge sequence;
no historical rewrite, force-push, provider/host execution or unrelated CI changes.

## Acceptance criteria

- The zero-before/initial fallback uses Git's empty-tree object as the diff base.
- A whitespace defect introduced in the root commit is detected deterministically.
- A clean root commit passes, and ordinary push plus pull-request ranges are unchanged.
- Subprocess execution remains argument-based without evaluating untrusted shell text.
- The work remains independently reviewable and does not alter historical commits.

## Dependencies and Ready gate

This is a low-priority Planned follow-up. It may be promoted independently after a
focused scope review; it must not be added as an implementation dependency to PR #6
or the current PR #5–#9 integration sequence.

## Validation / evidence

The current validator safely falls back to the first commit when the push `before`
SHA is all zero. That fallback is bounded but omits the root commit from the checked
range; this work item records the gap without changing current Review behavior.

## Results / evidence links

Finding recorded for future implementation. No current PR or historical Git state is
changed. Out-of-scope changes: None.
