# Validation — 2026-09-07

## WI-002 original-task review revisions — 2026-09-08

Baseline remote main: `a9f2673250f73a1cf567b5e5204f16f2ddaede0c`. The accepted ADR-001
and Ready work item were integrated before implementation. The work branch changes WI-002 to
Review; host activation and live deployment remain out of scope.

`python -B -m unittest discover -s . -p "test_*.py" -v`: **33 tests passed** on Windows /
Python 3.14.6. Fourteen WI-002 tests cover the closed command and receipt schemas, verified commit
author/committer/signature binding, exact GitHub feedback identity/body/actor, the PR-zero-only
empty technical-retry exception, durable sanitized rejection receipts,
exact identity/stale-head/changed-WI/dirty-checkout fencing, preservation of the same task/branch/PR,
exact resume and PR-bearing technical-retry invocation, command-origin immutability, real Git CAS
accepted/completed/rejected persistence, duplicate receipts and interrupted-command no-replay.
The 19 pre-existing tests continue to cover
Ready dispatch, technical retries, real Git claim CAS, result publication/recovery, PR identity
conflicts, token failures and host locking.

Additional checks passed:

- Python sources parse with the Python 3.10 AST grammar; JSON configuration parses.
- PowerShell AST accepts `setup.ps1` and `invoke-dispatch.ps1`.
- `setup.ps1` generated an opted-in disposable host config and workflow, installed hash-checked
  files and passed `-ValidateOnly`; a legacy config without coordination keys also passed.
- Disabled-by-default invocation rejected `-CoordinationCommand` before starting Codex.
- Actionlint 1.7.12 accepted the rendered workflow with only its known disposable custom runner
  label excluded from the built-in-label check.
- `git diff --check`, Markdown link, credential-pattern and scope checks passed.

All Git remotes, checkouts and coordination CAS writes in tests are disposable local fixtures;
GitHub/Codex identities and model execution are fake. No live runner, provider event, host
coordination branch, repository merge, credential/configuration change or game work occurred.

## WI-001 reliable PR handoff — 2026-09-08

Baseline remote main: `8f3ff77a61009a7e5651208c7b4b8a2257230dae`; clean fresh clone and
`pull --ff-only` verified. Direct Owner authorization and Ready gate committed in `9caa9a0`
before implementation. Technical Owner review completed on 2026-09-08 and authorized
merge; deployment and host live cutover are not part of this WI.

`python -m unittest discover -s . -p "test_*.py" -v`: **19 tests passed in 114.829 s**
on Windows / Python 3.14.6. Git helper path was set only for the test process.
The final suite covers Review, Blocked, same-head duplicate/update/retry, preserving human
PR text/title/template, lost POST response, known PR with delayed empty list, closed/merged/
non-draft/retargeted/foreign/ambiguous PR rejection, missing token and HTTP 401/403/422/429/500
sanitization, failed/unverified PATCH, real Git durable publication-error pause, publication-only
recovery with one Developer invocation, and interrupted evidence push/dirty-checkout fencing.
Existing tests retain real local Git CAS conflicts, claim deduplication, quota/timeout,
environment token stripping, host locks, custom base and pinned submodule behavior.

Additional checks passed:

- Python AST accepted all Python sources under the Python 3.10 grammar.
- PowerShell AST parsed all four scripts.
- PyYAML 6.0.3 parsed the rendered workflow and host YAML; explicit assertions checked
  `publish_wi` wiring, trusted push/manual triggers, contents read / pull-requests write.
- Actionlint 1.7.12 passed the rendered template and actual setup-generated workflow
  with the fixture runner label declared. No new PR-triggered local runner was introduced.
- `setup.ps1` ran only against a disposable `fixture/repo` Git host and installation
  directory. It generated PublishWi wiring and passed installed-file hash validation.
  Python `--version` was the safe executable substitute; no live Codex task was started.
- Work-item state vocabulary, host schema and Markdown links checked; `git diff --check`
  and source scope/credential-pattern scans passed. No new runtime Python dependency.

GitHub API/Codex behavior is simulated; Git remotes, commits, pushes and CAS are real and
local. No live fixture, account credential change, provider task, runner upgrade or historical
WI execution occurred. The work keeps schema version 1 with optional additive PR fields;
legacy results without a publication snapshot require manual reconciliation. Git/PR/state
writes are not atomic; running fences and preserved local evidence cover interruption gaps.

## Historical baseline evidence

Python 3.14; Git 2.54.0.windows.1; Windows.
`python -m unittest discover -s . -p "test_*.py" -v`: 11 tests passed.
Coverage includes Ready gates, duplicate/crash fencing, quota recovery, malformed results,
token stripping, actual process timeout, interprocess host lock, conflicting CAS writers,
independent same-ID claims in two host remotes, remote mismatch rejection, complete/quota
result publication, main/develop base branches and real pinned host submodule initialization.
Model execution and PR creation are stubbed; Git remotes/process tests are real and local.
No live model dispatch, quota exhaustion, remote creation or deployment was performed.

`setup.ps1` was also exercised against a new local Git host with a GitHub-format remote.
It detected `codex.exe` and `python.exe`, installed and hash-validated the tool, generated
the workflow with repository/user/runner/path guards, and created a minimal Ready WI.

For the test shell, Git's usr/bin was prepended to PATH because this sandbox's default PATH
omitted Git helper utilities. This was process-scoped; no global machine configuration changed.
