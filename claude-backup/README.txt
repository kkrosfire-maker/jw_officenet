=== Claude Code Backup ===
Created: 2026-05-19 12:26

HOW TO RESTORE ON A NEW COMPUTER
----------------------------------
1. Insert this USB drive into the new computer.
2. Double-click  run_restore.bat
   (If Windows blocks it: right-click -> Run as administrator)
3. Follow the on-screen prompts.
   - You will be asked where to place the workspace folder.
   - Default is  Desktop\workspace  (press Enter to accept).
4. After the restore completes, open a terminal and run 'claude'
   to log in to your Anthropic account.
   (Login cannot be automated for security reasons.)

WHAT IS INCLUDED
-----------------
  workspace\           -> All project files, scripts, and skills
  claude-settings\     -> Claude settings files + conversation memory
  claude-cli\          -> Claude Code CLI binary (claude.exe)

SKILLS INCLUDED
-----------------
  - caveman
  - diagnose
  - grill-me
  - grill-with-docs
  - handoff
  - improve-codebase-architecture
  - prototype
  - setup-matt-pocock-skills
  - tdd
  - to-issues
  - to-prd
  - triage
  - write-a-skill
  - zoom-out

NOTES
------
- Skills (.agents\skills\) are restored as part of the workspace.
- If any skill shows [MISSING] during restore, open a terminal
  in the workspace folder and run:  claude skills install
