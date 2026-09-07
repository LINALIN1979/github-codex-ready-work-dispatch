# Claims and recovery

The host remote owns codex/dispatch-state:state.json (schema_version 1). Never move that
branch into the tool repository or clear it during an upgrade. Read with git ls-remote,
fetch and git show FETCH_HEAD:state.json; inability to read fails closed.
Normal non-force pushes compare-and-swap the full document. Only the successful claimant
starts work. A running claim fences all further work for that host, even after a crash;
a completed claim permanently fences its WI ID. There is no expiry, stealing or lease reset.
Each record retains source blob/base, branch, checkout, task ID, attempts and results.

Execution conditions running, review, blocked, quota, execution_error, timeout are separate
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
