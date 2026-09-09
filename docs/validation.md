# Validation — 2026-09-07

## WI-003 source and installation integrity — 2026-09-09

Baseline remote `main`: `1886a4268c9f2e5cf5e917372174c19cb89ba7d5`; focused branch
checkpoint: `24d9028`. The suspected setup provenance issue was confirmed: the prior
script recorded `git rev-parse HEAD` while copying potentially dirty executable and
template sources. The fix is fail-closed and covers `setup.ps1`, `bridge.py`,
`invoke-dispatch.ps1` and `templates/ready-dispatch.yml.template` before any install or
host workflow write. It records their SHA-256 hashes alongside the reviewed revision.

`python -m unittest test_installation -v`: **3 tests passed**. The complete suite
`python -m unittest discover -s . -p 'test_*.py' -v`: **37 tests passed** in 98.137
seconds on Windows / Python 3.14.6. Fixtures cover clean reviewed source, harmless
untracked files, dirty material-source rejection before host mutation, installed hash
tamper detection and clean pinned-submodule invocation. Python 3.10 AST and PowerShell
AST parsing, `git diff --check` and credential-pattern scan passed. Local YAML parser and
actionlint binaries were unavailable; no workflow/template content changed, and WI-004
will provide independent GitHub-hosted CI coverage.

The source-without-Git policy is explicit: setup fails closed. No host repository,
runner, provider, live Codex, claim, log, recovery checkout, config, or coordination
state was modified. The WI remains Review pending independent review.

## WI-004 independent GitHub-hosted CI — 2026-09-09

Base is the internally validated WI-003 branch; focused checkpoint `43d2de4` plus
the YAML quoting correction in the current Review branch. The new `.github/workflows/ci.yml`
uses only GitHub-hosted Ubuntu/Windows runners, read-only contents permission, no secrets,
Codex, SSH, coordination commands or repository writes. It covers Python 3.10/3.14 full
suite, PowerShell AST, Python 3.10 grammar, credential/diff checks, PyYAML 6.0.3
workflow/template validation and actionlint v1.7.7.

The full local suite passed: **37 tests in 94.815 seconds**. Python 3.10 AST,
PowerShell AST, `git diff --check`, credential scan and isolated `ci/validate_yaml.py`
passed. GitHub-hosted run `34253865489` validated the workflow/template job, actionlint
and both Ubuntu Python jobs, but exposed two Windows-only issues: the credential scan
matched its own workflow file, and temporary-path normalization differed between
`Path.resolve()` and an unresolved `Path`. The current branch fixes both without
weakening the checks: the dedicated scanner excludes only its own workflow and the
validation record, while all work-root containment comparisons normalize both
operands. The corrected local suite now passes **37 tests in 102.987 seconds**, including
the short-path resume regression exposed by the hosted runner. Corrected GitHub-hosted
run **34295193351** passed all six jobs: Ubuntu/Windows × Python 3.10/3.14, PowerShell
and static checks, and workflow/template validation including actionlint v1.7.7. The
dedicated `ci/check_credentials.py` scan and isolated PyYAML 6.0.3 workflow/template
validation also pass locally.
Documentation distinguishes real local/disposable behavior from simulated GitHub/Codex/
provider behavior and unproven live host behavior. No host repository or live runner was
modified. WI-004 remains Review.

## WI-005 safe work-item creation and explicit Ready authorization — 2026-09-09

WI-004 is internally validated on Draft PR #6. The implementation changes normal
`new-work-item.ps1` output to `Planned` and adds explicit `mark-ready.ps1` validation;
it does not change the closed Ready parser or invent a lifecycle state.

`python -m unittest test_work_items -v`: **3 tests passed**. Creation/promotion,
malformed or incomplete non-promotion with byte-preserved files, and existing valid
manual Ready support are covered. The complete suite and static checks will be rerun
at the branch checkpoint. No host repository, live dispatcher, claims, runner or
provider was used. WI-005 remains Review.

## WI-006 coordinator actor-role authorization binding — 2026-09-09

WI-005 is internally validated on Draft PR #7. The former independent actor and role
allowlists were confirmed to authorize their Cartesian product. The fix adds explicit
`trusted_coordination_principals` actor→roles mappings, rejects malformed/conflicting
configuration, and deliberately supports legacy configuration only for one actor plus
one role. Setup's repeated `actor=role` binding input and migration documentation are
included.

`python -m unittest test_actor_role_binding -v`: **3 tests passed**. Tests cover two
actors/two roles with authorized and cross-pair/forged-role outcomes, disabled-default
compatibility and legacy single-principal migration versus ambiguous legacy rejection.
The complete WI-002 coordination suite and static checks are being rerun before this
branch checkpoint. No live coordination command, host, provider, runner or PR-comment
execution occurred. WI-006 remains Review.

## WI-005 review revisions — 2026-09-09

`mark-ready.ps1` now decodes only strict UTF-8, explicitly rejects UTF-16/UTF-32 and
invalid byte sequences, and writes the original BOM plus encoded content while changing
only `Status: Planned` to `Status: Ready`. Regression coverage proves byte-preserving
promotion for UTF-8 BOM/no-BOM and CRLF, and byte-for-byte preservation on validation
failure. Bridge Ready eligibility semantics are unchanged.

## WI-004 review revisions — 2026-09-09

`run_revision` again resolves the recorded checkout and allowed work root once, then uses
the canonical checkout for execution and checkpoint operations. The focused resume test
now compares canonical identities and asserts canonical containment. The credential scan
reports only relative path, line number and a bounded type label; a regression fixture
proves a fake token never appears in serialized stdout/stderr.

`ci/check_diff_range.py` validates full SHAs and checks pull-request base→head, push
before→head, or first-commit→head for initial/edge pushes using argument-list subprocess
calls. The workflow fetches complete history and `ci/validate_yaml.py` verifies the
range-validation wiring. A fresh hosted run is required for these revisions.

## WI-002 original-task review revisions — 2026-09-08

Baseline remote main: `a9f2673250f73a1cf567b5e5204f16f2ddaede0c`. The accepted ADR-001
and Ready work item were integrated before implementation. The work branch changes WI-002 to
Review; host activation and live deployment remain out of scope.

`python -B -m unittest discover -s . -p "test_*.py" -v`: **34 tests passed** on Windows /
Python 3.14.6. Fifteen WI-002 tests cover the closed command and receipt schemas, verified commit
author/committer/signature binding, exact GitHub feedback identity/body/actor, the PR-zero-only
empty technical-retry exception, durable sanitized rejection receipts,
exact identity/stale-head/changed-WI/dirty-checkout fencing, preservation of the same task/branch/PR,
exact resume and PR-bearing technical-retry invocation, command-origin immutability, real Git CAS
accepted/completed/rejected persistence, duplicate receipts and interrupted-command no-replay.
They also exercise the real technical-retry `run_one` boundary and prove a mismatched resumed
task ID is rejected without replacing the saved claim identity.
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
