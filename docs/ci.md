# Independent CI

`.github/workflows/ci.yml` is intentionally independent from the privileged host
dispatcher workflow. It runs only on GitHub-hosted `ubuntu-latest` and `windows-latest`
runners with `contents: read`; it does not start Codex, use a self-hosted runner, access
secrets or SSH keys, execute coordination commands, mutate a host repository or write
back to GitHub.

The CI exercises the complete Python suite, including disposable local Git remotes and
fake Codex/GitHub endpoints, on Python 3.10 and 3.14. Windows additionally exercises
the PowerShell parser and installation fixtures. It validates the workflow and rendered
dispatcher template with PyYAML, runs actionlint, checks Python 3.10 grammar, scans for
credential patterns and runs `git diff --check`.

The static job checks the complete reviewed range: pull requests use the event's
base SHA to head SHA, normal pushes use the event's before SHA to head SHA, and an
initial/edge push falls back to the first repository commit. The checkout fetches
complete history, all SHAs are validated as full commit IDs, and
`ci/check_diff_range.py` passes them as separate `git` arguments; no shell text is
evaluated as a command.

The tests prove real local Python, PowerShell and disposable Git behavior. GitHub API,
provider identity, Codex execution and live host/runner behavior remain simulated or
unproven. CI does not establish permission to activate or upgrade a host dispatcher.
