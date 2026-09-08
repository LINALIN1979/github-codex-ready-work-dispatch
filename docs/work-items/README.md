# Dispatcher work items

This repository can use its own dispatcher contract for future development. Create
`WI-NNN-name.md` with `Status: Planned`, `## Goal` and `## Acceptance criteria`.
`new-work-item.ps1` creates this non-executable format. After review, use the explicit
`mark-ready.ps1` operation to validate and promote a Planned item to `Ready`. `Ready`
is the automatic execution authorization boundary; creation never grants it.
