# Internal claim state

This document is for troubleshooting. Normal setup and use do not require these steps.

The dispatcher creates `refs/heads/codex/dispatch-state` in the host Git remote on the first claim. The branch contains `state.json` and is not merged into the base branch.

Each claim records the WI path and content blob, base commit, attempt ID, work branch, local recovery checkout, Codex task ID, run URL, timestamps and result. A normal non-force Git push acts as compare-and-swap: two dispatchers reading the same state cannot both publish the next commit. Only the successful writer starts Codex.

Execution conditions are `running`, `review`, `blocked`, `quota`, `execution_error` and `timeout`. These are internal execution facts, not work-item lifecycle states.

A claim does not expire. A crash can leave `running`; this intentionally blocks another task until a coordinator proves the old process stopped and reconciles preserved work. See [recovery.md](recovery.md).

Read state without checking out the branch:

```powershell
git fetch origin refs/heads/codex/dispatch-state
git show FETCH_HEAD:state.json
```

Do not delete, force-push or manually edit claim state during ordinary recovery.
