# Host integration

Run `setup.ps1 -HostRepo <path> -RunnerLabel <label>`. Setup creates the host workflow and keeps the runtime config outside Git under `%LOCALAPPDATA%\github-codex-ready-work-dispatch`.

The host owns its work items, governance, workflow trigger and results. This public repository owns setup, invocation, claims and execution. The default setup installs a checked local copy. Setup must run from the repository root of a clean Git checkout: it fail-closes on changes to `setup.ps1`, `bridge.py`, `invoke-dispatch.ps1` or the workflow template, and the install manifest records the reviewed revision plus material-source hashes. A host may instead pin this repository as a submodule and call its `invoke-dispatch.ps1`; executable files must remain clean in that checkout. In either mode, keep the real host configuration outside Git and pass its local path with `-Config`. Non-Git setup sources are not verified.

The dispatcher is Developer-oriented with a closed execution contract. Host work items
may use only `Implementer`, `Tester / Playtester` or `Docs / Traceability` as execution
roles, and only T1/T2 capability-tier prefixes. Arbitrary host roles are not supported;
host-neutral policy would require a separately authorized design and implementation.
Coordinator trust-policy roles are distinct from these execution roles.

Optional coordinator revision commands remain disabled unless the host configures the complete
dedicated-ref trust policy and explicitly invokes one command ID. They are not activated by PR
events or comments. See [coordination.md](coordination.md).

Use a different data directory for each host. Setup does this automatically. All installed hosts share one machine lock so one local Codex dispatch runs at a time.

To update, stop or drain the runner, review and test the new checkout, then rerun setup. Existing state, logs and preserved work remain in the host installation directory.

PR-based cloud orchestration uses the [generic handoff contract](coordinator-handoff.md).
Hosts own provider configuration, event validation and authorization. Upgrade the pinned
tool before adding `PublishWi` to a host workflow; older pins do not accept that parameter.
Do not update a host gitlink to an unreviewed or unreachable commit. Real config stays
outside Git and this contract does not authorize an active runner upgrade.
