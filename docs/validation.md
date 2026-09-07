# Validation — 2026-09-07

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
