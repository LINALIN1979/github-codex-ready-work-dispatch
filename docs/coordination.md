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
  -TrustedCoordinatorActor OWNER_LOGIN `
  -TrustedCoordinatorRole 'Technical Planner' `
  -CoordinationAuthorityRef docs/decisions/ADR-NNN.md
```

The coordination ref must already exist and contain only `coordination.json`. Keep tokens and
machine configuration outside Git. Leaving `coordination_ref` empty disables command handling;
merely pushing or commenting on a PR never invokes it.

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
claim's current PR/result identity, or zero/empty when none exists. Feedback is untrusted data;
its immutable GitHub reference, digest and introducing GitHub actor are all checked.

Commands are append-only. Mutating or removing a published command fails closed. The dispatcher
locates the commit that first introduced the command and verifies GitHub's associated actor login
against the configured allowlist; a self-declared `issuer_actor` is insufficient.

## Invoke and recovery

Invoke exactly one explicit command ID:

```powershell
.\invoke-dispatch.ps1 -Config <external-host-config> -CoordinationCommand review-0001
```

The generated workflow exposes the same `coordination_command` manual input. It is mutually
exclusive with `retry_wi` and `publish_wi`. No PR event automatically fills or executes it.

Before Codex starts, the dispatcher publishes an `accepted` receipt by non-force CAS. Therefore
duplicate, reordered and competing invocations cannot run the same command twice. A crash after
acceptance leaves an accepted or `failed_uncertain` receipt and is never replayed automatically,
even if Codex may not have started. Reconcile the saved task, checkout, claim and logs, then issue
a newly authorized command ID only when governance permits it.

A successful revision resumes the recorded task ID, checkpoints the same branch, updates the
same Draft PR handoff block and finishes the receipt with result evidence. Missing tasks, dirty
checkouts, stale main/WI/PR heads, mismatched roles/actors or ambiguous claims stop without a
replacement task, force push, fence clearing, merge or lifecycle approval.
