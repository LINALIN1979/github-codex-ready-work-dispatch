# Claims and recovery

The host remote owns codex/dispatch-state:state.json (schema_version 1). Never move that
branch into the tool repository or clear it during an upgrade. Read with git ls-remote,
fetch and git show FETCH_HEAD:state.json; inability to read fails closed.
Normal non-force pushes compare-and-swap the full document. Only the successful claimant
starts work. A running claim fences all further work for that host, even after a crash;
a completed claim permanently fences its WI ID. There is no expiry, stealing or lease reset.
Each record retains source blob/base, branch, checkout, task ID, attempts and results.

Execution conditions running, review, blocked, quota, execution_error, timeout, publication_error are separate
from WI lifecycle. Quota/error/timeout checkpoint Blocked evidence and globally pause that
host. Malformed output/publication failure preserves a running claim and local recovery.txt.
No automatic retry, credit purchase, reset, account switch or guessed reset time occurs.

After a stopped technical failure, resolve its cause, verify unchanged source WI/base and
clean preserved checkout, then use the GitHub workflow's `retry_wi` input or:
`invoke-dispatch.ps1 -Config <host-config> -RetryWi WI-NNN`.
It resumes the same work branch and saved task if captured. Changed base/WI requires explicit
coordinator reconciliation first; a product/approval Blocked result is not retryable this way.

After a crash, check the GitHub run, local logs and entire process tree. Only after proving
all old processes stopped, preserve/checkpoint legitimate unfinished work and reconcile
published branch/state. An authorized coordinator may then use Store.read/write CAS to
record execution_error and a global pause with the recovery reason. No automatic command
clears uncertain live claims. Never delete logs/checkouts, reset or stash unknown work.
Review is evidence for a human/reviewer, not approval; no automatic merge is performed.

## PR publication-only recovery

`publication_error` is never eligible for `retry_wi`. Fix token/repository permission or
the reported PR conflict, prove the earlier bridge stopped, then invoke the reviewed tool:

```powershell
.\invoke-dispatch.ps1 -Config <external-host-config> -PublishWi WI-NNN
```

The generated workflow exposes the equivalent `publish_wi` input. Never combine it with
`retry_wi`. It uses the saved result/attempt/work branch and never invokes Codex, scans
Ready work, buys credits or changes approved requirements. The checkout must be clean,
inside its saved data root, on the recorded branch, and match both the durable result
commit and remote branch. Unrelated running claims/pauses block recovery.

## Coordinator-command recovery

An accepted coordination receipt is an at-most-once fence. Never delete it or replay the same
command ID after a crash. Inspect the command receipt, dispatch claim, saved task, checkout and
local logs. If execution may have started, prove it stopped before any new authorization. A new
command ID is required for another attempt and must reference the then-current exact identities.
See [coordination.md](coordination.md). This recovery never creates a replacement task or clears
an uncertain claim automatically.

A crash after a branch push but before ledger completion can leave different heads.
Preserve files and reconcile exact branch/report/PR evidence through authorized CAS;
do not reset, discard or simply change the expected SHA to make a check pass. Legacy
claims without `pending_publication` are not automatically replayable. Repeated publication
uses the same PR. Technical quota/error/timeout pauses remain after PR repair; resolve
the original cause separately. Product/Art/Architecture blockers still need their owners.

See [handoff contract](coordinator-handoff.md) for transaction gaps and receiver behavior.
