# github-codex-ready-work-dispatch

Run approved repository work on a local Codex installation when a GitHub workflow detects a Ready work item.

```text
Ready WI pushed to GitHub
          ↓
GitHub Actions queues the self-hosted Windows runner
          ↓
The dispatcher records a claim and starts local Codex
          ↓
Codex works in an isolated clone and publishes a Review or Blocked branch
```

It does not approve requirements, merge changes, retry uncertain work, buy credits, or wake a sleeping computer.

## What you need

- A trusted GitHub repository.
- Windows with Git, Python 3.10+ and Codex installed.
- A GitHub self-hosted runner registered for that repository.
- A unique runner label, such as `my-project-codex-dispatch`.

Only trusted base-branch writers should be able to trigger this runner. Read [SECURITY.md](SECURITY.md) before enabling it.

## Setup — about 10 minutes

1. Clone this repository on the Windows machine that runs Codex.

2. In the host repository, open **Settings → Actions → Runners → New self-hosted runner**. Register the runner using GitHub's commands and add a project-specific label.

3. Run setup from this repository:

```powershell
.\setup.ps1 `
  -HostRepo D:\repos\my-project `
  -RunnerLabel my-project-codex-dispatch
```

Use `-ExpectedRunnerUser`, `-WorkflowPath` or `-AdditionalTriggerPath` only when the host needs those extra restrictions. Existing installations can pass `-DataRoot` and `-HostLockRoot` to preserve their claim, work and log locations.

Setup detects the host GitHub remote, Codex and Python. It installs a checked copy of the dispatcher under `%LOCALAPPDATA%`, writes the local untracked config, and creates:

```text
HOST_PROJECT/.github/workflows/codex-ready-dispatch.yml
HOST_PROJECT/docs/work-items/
```

4. Review and commit the generated workflow. The workflow contains local runner paths, so do not copy it blindly to another machine.

```powershell
git -C D:\repos\my-project add .github/workflows/codex-ready-dispatch.yml
git -C D:\repos\my-project commit -m "Add local Codex Ready dispatcher"
git -C D:\repos\my-project push
```

Setup does not register the runner automatically because GitHub supplies a short-lived registration token to the repository owner.

## Create a Ready work item — about 2 minutes

```powershell
.\new-work-item.ps1 `
  -HostRepo D:\repos\my-project `
  -Title "Add export command" `
  -Goal "Add the approved export command"
```

The generated file is intentionally small:

```markdown
# WI-001 — Add export command

Status: Ready
Owner Role: Implementer

## Goal

Add the approved export command.

## Acceptance criteria

- Export produces the expected file.
- Relevant tests pass.
```

Review the file, then commit and push it. `Ready` is authorization to execute that bounded work. Do not use `Ready` while requirements, dependencies, or owner decisions are unresolved.

## Is Ready a GitHub standard?

No. It is the default host-project contract used by this dispatcher. A work item must be a Markdown file named `WI-NNN-name.md` under `docs/work-items` and contain:

- `Status: Ready`
- `## Goal`
- `## Acceptance criteria`

`Owner Role` defaults to `Implementer`. `Capability Tier` defaults to `T2 Standard`. Projects with stronger governance can add Scope, Out of scope, Dependencies, Validation and linked specifications. The Codex task reads those files when they exist.

The current adapter does not treat GitHub Issues, Projects, milestones or labels as authorization.

## What is the automatic claim?

Before Codex starts, the dispatcher automatically records that the WI was claimed in the host repository's internal `codex/dispatch-state` branch. This prevents duplicate GitHub events from starting the same WI twice. The record survives a process crash or reboot.

You do not create, edit or merge this branch. Normal use does not require understanding its JSON format. See [docs/internals.md](docs/internals.md) only when diagnosing or recovering interrupted work.

The WI lifecycle remains in its original Markdown file. The internal claim records execution facts such as the task, branch and failure state; it does not replace the WI status.

## Results and retry

Successful work is pushed to a dedicated branch and reported as `Review`. The dispatcher never merges it.

Quota, timeout and execution failures preserve the checkout and pause further dispatch. After fixing the technical problem, retry from **Actions → Codex Ready work dispatcher → Run workflow**, entering the same `WI-NNN`. Product or approval blockers require a new decision, not a technical retry.

See [docs/recovery.md](docs/recovery.md) for the recovery checklist.

## Update

Pull and review a new dispatcher version, run its tests, then rerun `setup.ps1` with the same host and runner label. Setup replaces only the local installed tool and regenerates the workflow/config. It does not delete claims, worktrees or logs.

```powershell
git pull --ff-only
python -m unittest discover -s . -p "test_*.py" -v
.\setup.ps1 -HostRepo D:\repos\my-project -RunnerLabel my-project-codex-dispatch
```

Drain or stop the runner before updating. Never update while a claim is running or uncertain.

## Uninstall or disable

Disable the GitHub workflow or stop the runner. Keep the local data directory and `codex/dispatch-state` branch until every claim and result has been reviewed. Removing those records can cause duplicate execution.

## Files in this repository

- `setup.ps1` — one-command host setup.
- `new-work-item.ps1` — creates the next minimal WI.
- `invoke-dispatch.ps1` — verifies installed files and runs the bridge.
- `bridge.py` — selection, claim, Codex execution and result publication.
- `templates/ready-dispatch.yml.template` — workflow installed by setup.
- `config.example.json` — configuration reference; real config stays local.
- `test_bridge.py` — offline tests using temporary Git remotes and fake Codex output.

No third-party Python package is required.
