# Message to paste into Claude Code at the start of a session

Paste this into Claude Code in VS Code, with the `center_dashboard` folder open:

---

Read CLAUDE.md, docs/BRIEF.md and docs/DECISIONS.md in this folder before doing anything. Follow the privacy rules in CLAUDE.md exactly: never open anything in raw\, any spreadsheet, the .db file or exports\, never run a query that returns names, emails or Emplids, and never view the dashboard pages yourself. Report counts only.

Then:
1. Run `py verify.py` and tell me the counts.
2. Tell me which Milestone 1 steps in CLAUDE.md are done and which remain, based on the verify counts and the import log, without assuming.
3. Add a dated entry to the Status log in CLAUDE.md with those counts.
4. Continue with the next remaining step. Ask me one question at a time if you need a decision, and ask before building anything new.

---
