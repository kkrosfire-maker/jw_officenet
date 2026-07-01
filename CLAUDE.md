# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Platform: Windows 10, PowerShell
- Shell: Use PowerShell syntax (`$env:VAR`, backtick for line continuation, `;` not `&&` for chaining)

## Claude Code Settings

Permitted PowerShell commands are defined in `.claude/settings.local.json`. Update that file to add or remove allowed commands rather than approving them one-by-one.

## Running things locally

When the user asks to run something locally ("로컬에서 실행해줘" 등), run it yourself — start the server/script in the background and verify it works (curl, Playwright screenshot, etc.). Do not tell the user to open/run it themselves; only report back once it's actually running and verified. This applies to every project under this workspace.

## Project

<!-- TODO: Fill in once a project is added to this workspace -->
<!-- Example sections to add:

### Build & Run

```powershell
npm install       # install dependencies
npm run dev       # start dev server
npm run build     # production build
npm test          # run all tests
npm test -- path/to/file.test.ts  # run a single test file
```

### Architecture

Brief description of the high-level architecture and key design decisions.

-->
