# Repository governance

This repository maintains reusable dispatch tooling. Act on explicitly authorized work;
otherwise inspect docs/work-items before implementation. Never infer authorization from
another host or earlier execution. Preserve Ready gates, claims, sandbox restrictions and review.
Before work: inspect git status and upstream; pull --ff-only only when clean and an
upstream exists. Never discard/stash unknown work or rewrite published history.
Use only Idea, Planned, Ready, In Progress, Review, Playtest, Done, Blocked for work items.
Read the target host's AGENTS.md, PROJECT_STATE and WORKFLOW before dispatch work.
Run python -m unittest discover -s . -p "test_*.py" -v for code changes.
Do not start a live agent/runner, publish a remote, merge, force push, purchase or reset
credits without the relevant explicit authorization. Preserve all claim and recovery data.
