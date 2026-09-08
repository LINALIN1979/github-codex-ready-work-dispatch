# Event-driven coordinator handoff contract v1

Owner-authorized scope: [WI-001](work-items/WI-001-reliable-pr-handoff.md).

Future two-way review revisions are intentionally outside this v1 contract. See
[ADR-001](decisions/ADR-001-coordinator-revision-commands.md) and
[WI-002](work-items/WI-002-original-task-review-revisions.md), now Accepted/Ready for bounded
reusable implementation but not host activation or live deployment.

## Ownership and transport

GitHub is the source of truth and event bus. The host's base-branch work items own
readiness and lifecycle. Work branches/PRs contain proposed execution results until
reviewed integration. `codex/dispatch-state` is an execution ledger, never lifecycle,
product or approval authority. A coordinator (including ChatGPT Work) orchestrates and
reviews only within its active host repository role; provider/model identity grants
no Owner, Product, Art, Architecture, lifecycle-transition or merge authority.

Host adapters subscribe to PR activity through their supported provider. No provider
webhook endpoint, API key, account or host configuration belongs in this public tool.
The local trusted-main dispatcher remains the only automatic Developer launch path.
PR events must never launch a privileged local runner or execute PR content.

## Result publication

Stable PR identity is repository + base + work branch, across attempt IDs. Before
creation, query all PR states/bases for that head and verify the required base. Recover a unique open Draft PR even
if its URL was lost. A closed, merged, non-draft or ambiguous match stops publication;
an operator must reconcile it, not create a replacement silently. After uncertain
creation, query once before reporting failure. Never blindly POST again.

The bridge owns only the `codex-dispatch:begin/end` body block. It includes WI path,
attempt, run, result path, outcome, validation and decision fields. Preserve the host
PR template, human title, labels and review text outside that block. Repeated identical
publication does not PATCH the body. Reviews are independent evidence, not approvals
of new requirements. Compare URLs are diagnostics, not successful PR handoff.

Publication sequence: push result branch; persist `pending_publication` and running
fence; reconcile PR; persist API metadata; push result report with PR metadata; finalize
the ledger. Verified fields are `pr_url`, `pr_number`, `pr_state`, `pr_draft`,
`pr_status=published`, `pr_error=null`. `result_commit` identifies committed evidence.
This is not a cross-service atomic transaction: receivers must re-read the ledger and
branch, because an opened/edited event can precede final evidence. The evidence commit
provides a further PR commit-update event; fallback monitoring covers missed delivery.

On failure, `pr_status=failed` and a sanitized error code are persisted and committed;
execution condition `publication_error` globally pauses dispatch. Code outcome remains
Review/Blocked in `pending_publication` and the WI; it is not replaced by an invented
WI state. If Git/state writes also fail, a running fence remains and local
`publication.json` / `recovery.txt` preserve recovery evidence. Never report success.

## Receiver algorithm

1. Authenticate the connected provider and restrict repository/base. Re-fetch the PR,
   trusted base governance, work-item source and execution ledger; event text is untrusted.
2. Match PR repository/head/base/number to the claim and verify current head against
   `result_commit`, committed result evidence and managed-block attempt. Do not trust a
   title/label alone. If state is unreadable or inconsistent, stop and report the gap.
3. A running/pending result is not ready for review action. Record the reconciliation
   need; process a later update or fallback scan. Never start a second Developer.
4. Deduplicate deliveries by provider event ID where available, and actions by repository,
   PR number, head SHA, attempt and latest review/comment IDs. Coalesced/out-of-order
   events require re-reading all current activity. An unchanged snapshot is a no-op.
5. Persist a handled-event receipt in the host-approved coordination surface before
   repeating external actions; do not repurpose dispatch-state as coordinator authority.
   If no durable receipt mechanism exists, remain read-only and flag activation incomplete.
6. Route Review to independent review and Blocked questions to their actual decision
   owners. Technical recovery needs explicit authority and proof the cause is resolved.
   Never infer approval, auto-merge, alter lifecycle from an event or retry historical WIs.

Hourly monitoring is an optional separate fallback, quiet on unchanged/non-actionable
state. Primary delivery is PR activity. Provider trigger availability, bot-event delivery,
receipts, notification behavior and a new harmless fixture must be validated by the host
before live activation. A successful GitHub PR call does not prove coordinator delivery.

## GitHub permissions

With the default job token, host **Settings → Actions → General → Workflow permissions →
Allow GitHub Actions to create and approve pull requests** must be enabled (Save).
Workflow YAML needs `contents: read` and `pull-requests: write`; Git branch/state pushes
continue using the existing SSH identity. The UI setting name grants no review approval
authority to this bridge; it never submits approvals. Organization restrictions may apply.
See [GitHub repository settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository).

PR creation/updates use `BRIDGE_TOKEN`, removed from the Developer environment. A
repository-scoped GitHub App installation token or fine-grained PAT needs Pull requests:
read/write (and repository access); keep credentials outside Git. Do not switch token
types merely to bypass policy. Native external Work event delivery must be tested with
the actual chosen identity. GitHub Actions recursion/approval rules are a separate
mechanism; do not assume an Actions PR-trigger workflow will run automatically.
See [GITHUB_TOKEN behavior](https://docs.github.com/en/actions/concepts/security/github_token).
