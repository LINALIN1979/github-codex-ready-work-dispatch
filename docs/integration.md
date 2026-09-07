# Host integration

Run `setup.ps1 -HostRepo <path> -RunnerLabel <label>`. Setup creates the host workflow and keeps the runtime config outside Git under `%LOCALAPPDATA%\github-codex-ready-work-dispatch`.

The host owns its work items, governance, workflow trigger and results. This repository owns setup, invocation, claims and execution. A host does not need a submodule or copied bridge files.

Use a different data directory for each host. Setup does this automatically. All installed hosts share one machine lock so one local Codex dispatch runs at a time.

To update, stop or drain the runner, review and test the new checkout, then rerun setup. Existing state, logs and preserved work remain in the host installation directory.
