# Host integration

Run `setup.ps1 -HostRepo <path> -RunnerLabel <label>`. Setup creates the host workflow and keeps the runtime config outside Git under `%LOCALAPPDATA%\github-codex-ready-work-dispatch`.

The host owns its work items, governance, workflow trigger and results. This public repository owns setup, invocation, claims and execution. The default setup installs a checked local copy. A host may instead pin this repository as a submodule and call its `invoke-dispatch.ps1`; executable files must remain clean in that checkout. In either mode, keep the real host configuration outside Git and pass its local path with `-Config`.

Use a different data directory for each host. Setup does this automatically. All installed hosts share one machine lock so one local Codex dispatch runs at a time.

To update, stop or drain the runner, review and test the new checkout, then rerun setup. Existing state, logs and preserved work remain in the host installation directory.
