# Coordinator revision commands

WI-002 implements this adapter as an optional, disabled-by-default path. It does not grant
approval, lifecycle, merge or scope authority. A host must separately review and configure
the integration before any command can run.

## Host configuration

Run `setup.ps1` with all four coordination options or none of them:

```powershell
.\setup.ps1 `
  -HostRepo D:\repos\my-project `
  -RunnerLabel my-project-codex-dispatch `
  -CoordinationRef refs/heads/codex/coordination `
  -TrustedCoordinatorBinding 'OWNER_LOGIN=Technical Planner' `
  -CoordinationAuthorityRef docs/decisions/ADR-NNN.md
```

The coordination ref must already exist and contain only `coordination.json`. Keep tokens and
machine configuration outside Git. Each `TrustedCoordinatorBinding` is one explicit
`actor=role` pair; the dispatcher never treats the actor list and role list as a Cartesian
product. Leaving `coordination_ref` empty disables command handling; merely pushing or
commenting on a PR never invokes it.

Legacy enabled configurations with only `trusted_coordination_actors` and
`trusted_coordination_roles` remain supported only when each contains exactly one value,
which is interpreted as one pair. Multi-actor or multi-role legacy configurations fail
closed rather than being silently reinterpreted. Rerun setup with explicit bindings to
migrate, or author `trusted_coordination_principals` as a closed list of objects such as:

```json
"trusted_coordination_principals": [
  {"actor": "alice", "roles": ["Technical Planner"]},
  {"actor": "bob", "roles": ["Reviewer"]}
]
```

## Document and command schema

The branch document is a closed schema-v1 object:

```json
{
  "schema_version": 1,
  "commands": {
    "review-0001": {
      "schema_version": 1,
      "command_id": "review-0001",
      "action": "revise",
      "repository": "OWNER/HOST_PROJECT",
      "wi_path": "docs/work-items/WI-012-example.md",
      "wi_blob": "40-lowercase-hex-Git-blob",
      "base_sha": "40-lowercase-hex-commit",
      "attempt_id": "32-lowercase-hex-attempt",
      "task_id": "saved-Codex-task-UUID",
      "checkout": "C:/absolute/preserved/checkout",
      "work_branch": "codex/auto-wi-012-example",
      "pr_number": 12,
      "expected_pr_head": "40-lowercase-hex-result-commit",
      "feedback_ref": "https://github.com/OWNER/HOST_PROJECT/pull/12#pullrequestreview-123",
      "feedback_sha256": "sha256-of-exact-feedback-UTF8",
      "feedback": "Bounded review feedback text",
      "issuer_actor": "OWNER_LOGIN",
      "active_role": "Technical Planner",
      "authority_ref": "docs/decisions/ADR-NNN.md",
      "created_at": "2026-09-08T01:00:00+00:00"
    }
  },
  "receipts": {}
}
```

Every field is required. `revise` requires the existing open Draft PR and exact head.
`technical_retry` maps to the existing stopped quota/error/timeout recovery and must use the
claim's current PR/result identity, or zero/empty when none exists. A technical retry without a PR
uses empty feedback and reference fields plus the SHA-256 of the empty string. Otherwise feedback
is untrusted data and its immutable GitHub reference, digest and actor are all checked.

Commands are append-only. Mutating or removing a published command fails closed. The dispatcher
locates the commit that first introduced the command and requires GitHub REST to report the exact
allowlisted issuer as both the commit author and signer-associated committer, with a verified
commit signature. A self-declared `issuer_actor`, unsigned author-email attribution, or a verified
signature associated with a different committer is insufficient. `feedback_ref` accepts only the exact canonical
`pullrequestreview-ID` or `issuecomment-ID` URL for the stated PR. The adapter fetches that object
from GitHub and requires its immutable ID, URL, body and actor to match the command.

Receipts are also schema version 1 closed objects. Every receipt has exactly these top-level
fields: `schema_version`, `command_id`, `status`, `command_commit`, `recorded_at`, `finished_at`,
`execution_may_have_started`, `error_code` and `observed`. `observed` has a fixed schema containing
the command/document, repository, action, WI/base/claim/task/branch/PR/head, feedback, actor/role,
authority and result identities. The local checkout is represented only by its SHA-256 digest so
machine paths or credentials cannot enter coordination history. Unknown, missing or mistyped
receipt fields reject the whole document. Command IDs, timestamps, hashes/digests, repository,
PR/result identities and status-dependent observations are validated on every read and write.
Malformed untrusted strings are recorded only as null or a one-way checkout digest; accepted and
completed receipts require the verified actor plus exact WI, claim, task, branch, PR and head
evidence. `command_commit` is null only for a `command_origin_invalid` rejection before a command
origin can be established. Schema-invalid and every later rejection requires the valid origin
commit SHA; `observed.document_revision` still records the exact
coordination document that was inspected.

## Invoke and recovery

Invoke exactly one explicit command ID:

```powershell
.\invoke-dispatch.ps1 -Config <external-host-config> -CoordinationCommand review-0001
```

The generated workflow exposes the same `coordination_command` manual input. It is mutually
exclusive with `retry_wi` and `publish_wi`. No PR event automatically fills or executes it.

Every syntactically addressable rejected command is first published as a `rejected` receipt with
a bounded error code and `execution_may_have_started: false`. This includes malformed commands,
wrong actors or roles, unverifiable feedback, stale base/PR heads, changed work items and dirty or
mismatched checkouts. Publication is reconciled on CAS conflicts, and no Developer invocation is
possible on the rejection path.

Before Codex starts, the dispatcher publishes an `accepted` receipt by non-force CAS. Therefore
duplicate, reordered and competing invocations cannot run the same command twice. A crash after
acceptance leaves an accepted or `failed_uncertain` receipt and is never replayed automatically,
even if Codex may not have started. Reconcile the saved task, checkout, claim and logs, then issue
a newly authorized command ID only when governance permits it.

A successful revision resumes the recorded task ID, checkpoints the same branch, updates the
same Draft PR handoff block and finishes the receipt with result evidence. Missing tasks, dirty
checkouts, stale main/WI/PR heads, mismatched roles/actors or ambiguous claims stop without a
replacement task, force push, fence clearing, merge or lifecycle approval.
The same task-identity check applies to `technical_retry`: if Codex reports a different
`thread.started` ID while resuming a saved task, execution stops and the replacement ID is never
written to claim state.
