# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Platform: Windows 10, PowerShell
- Shell: Use PowerShell syntax (`$env:VAR`, backtick for line continuation, `;` not `&&` for chaining)

## Claude Code Settings

Permitted PowerShell commands are defined in `.claude/settings.local.json`. Update that file to add or remove allowed commands rather than approving them one-by-one.

## Output language

Always write every response to the user in Korean (한글), including skill outputs, analysis reports, summaries and status messages — even when a skill's instructions or glossary are in English. Keep code, identifiers, file paths and commands as they are. Applies to every project under this workspace.

## Running things locally

When the user asks to run something locally ("로컬에서 실행해줘" 등), run it yourself — start the server/script in the background and verify it works (curl, Playwright screenshot, etc.). Do not tell the user to open/run it themselves; only report back once it's actually running and verified. This applies to every project under this workspace.

## Don't repeat the same mistake

Applies to every project under this workspace.

- When an error occurs and you diagnose and fix it, record the cause and the fix as a `feedback_*` memory (or in the project's own CLAUDE.md if it is project-specific). Record only non-obvious lessons, not what the code or git history already shows.
- Before acting in a situation that resembles a past error (same tool, same build step, same kind of failure), check memory and the project's CLAUDE.md for a recorded lesson and follow it from the start.
- If the same kind of failure shows up twice in a session, or a retry looks like it will hit the same error, stop. Do not retry the same command. Re-read the actual source (file, log, live setting), change the approach, and only then continue.
- When the user doubts a result or repeats a request, treat it as a sign the previous attempt failed: re-verify against the real source instead of restating the earlier claim.
- After a fix, verify it actually works (run it, check output) before reporting it done.

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
