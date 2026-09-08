# WI-004 — Independent GitHub-hosted CI

Status: Ready
Work Type: Code
Owner Role: Implementer
Capability Tier: T2 Standard

## Authorization and linked source of truth

Authorized by the repository Owner's dispatcher hardening request dated 2026-09-09.
References: `AGENTS.md`, `SECURITY.md`, `templates/ready-dispatch.yml.template`,
`docs/validation.md` and the existing Python/PowerShell/workflow checks.

## Goal

Provide independent, GitHub-hosted CI that verifies this reusable dispatcher
without using a privileged desktop runner or live Codex/provider behavior.

## Scope

Add a repository CI workflow and deterministic validation for the full Python
suite, Python 3.10 compatibility where claimed, PowerShell parsing, YAML/template
validation, actionlint where practical, `git diff --check` and existing static /
security checks; document tested versus simulated behavior.

## Out of scope

No self-hosted runner targeting, Codex execution, host mutation, SSH keys,
coordination commands, secrets, repository settings, branch protection or ruleset
changes.

## Acceptance criteria

1. CI runs only on GitHub-hosted runners and requires no secrets or repository writes.
2. The complete existing test suite and stated compatibility/static checks run in CI.
3. Third-party actions use immutable commit pins where practical.
4. Documentation distinguishes real tests, disposable local Git behavior, simulated
   GitHub/Codex/provider behavior and unproven live-host behavior.
5. CI configuration and checks are reviewable offline without starting a runner.

## Dependencies and Ready gate

WI-003 must be internally validated first because CI will exercise its installation
and provenance checks. No live host or provider dependency is required. WI-003 is
internally validated and suitable for independent review on Draft PR #5; the
dependency gate is satisfied for this focused branch.

## Validation / evidence

Pending the implementation checks recorded in `docs/validation.md`. No GitHub-hosted
runner, provider or host repository mutation is required to implement this item.
