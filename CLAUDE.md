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

## Reference material must actually be seen

Applies to every project under this workspace.

- When the user gives a reference (a site to imitate, a design, a file, a screenshot), do not start building until you have actually seen its real content (rendered page, screenshot, full text). Page title, a few links, or general knowledge of "typical sites" is not seeing it.
- If fetching returns a thin shell (JS-rendered page) or the Chrome-extension screenshot fails, capture it yourself with headless Playwright (`python script.py`, not `-I`; it is installed): `goto(wait_until="networkidle")`, then scroll with REAL `page.mouse.wheel()` steps with waits and screenshot each viewport (`scrollTo` does not trigger scroll-reveal animations on React/GSAP sites and gives blank shots). Also dump `#root` innerText for copy/structure. Only if that also fails, ask the user for screenshots or saved HTML. Do not substitute a guessed structure and present it as finished work. (Lesson 2026-11-06: joeunmarketing.com reference was captured this way after wrongly giving up.)
- If you must produce a draft without the reference, say so first in the report, and label it clearly as a guess — never claim it resembles the reference.
- Do not report "opened/ran/works" unless you verified the actual result (e.g. process launched is not the same as window shown). Say exactly what was and was not verified.
- Before making a deliverable the user will open themselves (HTML etc.), consider whether it opens on their machine (e.g. `.html` has no default app on this PC → provide a launcher .bat that opens it in Chrome).

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
