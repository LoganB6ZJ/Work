# Center Dashboard: instructions for Claude Code

Read this file first in every session. Then read `docs/BRIEF.md` (the original, approved brief) and `docs/DECISIONS.md` (every decision and environment fact so far). `docs/START_PROMPT.md` has the message Logan pastes to start a session.

Owner: Logan, Manager of Technical Paint Training, Caliber Collision (technical training for automotive refinish technicians at a multi-location collision company).
This folder is a local database and browser app (Python, SQLite, pandas, openpyxl, Flask) covering about 1,800 to 1,900 centers.
Scope today is Milestone 1 only. Do not build anything beyond it.

## Privacy rules (hard, they override everything else)

The data contains real people's names, emails and employee IDs. Anything you read or print is sent to Anthropic's API, which Logan's rules forbid for this data.

1. Never open, read, cat, head, preview or search inside: `raw\`, any `.xlsx` or `.csv` data file, `*.db`, `exports\`. Do not use the Read, Grep or Glob tools on them. File names and sizes are fine.
2. Never run a query or script that prints names, emails or Emplids. SQL against `center_dashboard.db` may only return counts and non-personal columns (center_id, snapshot_date, job_family, job_code, counts). Never SELECT `people.name`, `people.emplid`, `staffing_snapshots.emplid`, or the org chart email columns.
3. Run only the project scripts and read their output. The scripts print counts and center IDs only. If any output ever shows a name, email or Emplid, stop and tell Logan.
4. Do not open the dashboard pages yourself (no curl, Playwright or screenshots of the app). Logan opens http://127.0.0.1:5000 in his own browser.
5. Never modify, rename, move or re-save the raw source files. Never commit data, the database, exports or the manifest. No network calls, no uploads.
6. Do not install software beyond `pip install --user pandas openpyxl flask`. Ask first if anything else is needed. Logan has no admin rights.
7. In chat, report counts and structure only.

`snapshot_manifest.csv` holds only file names, dates and notes. You may read and edit it.

## How to work with Logan

- Ask before building anything. Every time. When he asks for an edit, make that specific edit and do not rebuild.
- Before building a file, confirm which source assets exist and whether they are correct. If information, context or assets are missing, stop, state the gap and ask how to close it. Do not substitute or assume.
- If scope, format, audience or intent is uncertain, ask one clear question first. One question at a time, short answers.
- Keep answers short and professional. No em dashes (use commas, colons or semicolons). Avoid "this vs that" and "x is not y" framing.
- Source discipline. Label every claim by basis: published science, named document, or reasoned inference. No source, no procedure. If he asks for a specific OEM, ALLDATA, Mitchell, I-CAR, regulatory or standards-based procedure, state exactly what source you have, what you do not, and your confidence. If unavailable, say "I don't know."
- Research (if ever asked) uses peer-reviewed literature, recognized standards bodies (ASTM, ISO, SAE, AMPP) and primary sources. No forums, no anecdotal evidence. For technical coatings questions reason from first principles as a coatings and polymer chemist would (molecular structure, reaction pathways, surface energy, cure mechanisms, failure modes), using TDS and SDS documents first without limiting reasoning to them.
- Any SOP or Caliber-branded document belongs in Logan's SOP creation project, where branding, fonts and colorways live. Do not create branded material here.

## Environment

Windows, PowerShell. Use `py`, not `python`. Run commands from this folder (`center_dashboard`). Quote paths that contain spaces.
Project path: `C:\Local Claude Projects\Work-claude-build-this-1kdq8z\center_dashboard`. It is deliberately outside OneDrive (cloud sync would break the privacy rules and can lock the database). Keep it there.
Python 3.14.8 per user; pandas, openpyxl and Flask installed with `py -m pip install --user`. The Scripts folder is not on PATH, which is fine.
Tests on fake data: `py -m unittest discover -s tests` (22 tests, all passing at handoff).
Git may not be installed on this computer. The code reaches it by ZIP download from GitHub (`LoganB6ZJ/Work`, branch `claude/build-this-1kdq8z`). Do not push data anywhere.

## Milestone 1 steps

Logan reports that steps 1 to 3 were run in a local session. Do not assume. Check with `py verify.py` and the import log counts before repeating anything. Every step is safe to re-run.

1. **Manifest edit.** Touch only `include` and `date_confirmed`, and print only file names and those two values.
   - `include = 0` for `(1)`; `date_confirmed = yes` for exactly these 13 files: `(3)` and `(5)` through `(16)`.
   - The unnumbered file, `(1)`, `(2)` and `(4)` stay `include = 0`, `date_confirmed = no`.
2. **Load.** `py import_painters.py --from-manifest`. Report rows read, loaded and skipped per file. The three blank-job-family rows per file are skipped by design. On a header mismatch stop and tell Logan the header names (safe to share).
3. **Verify.** `py verify.py`. Report counts: transfers detected, center IDs that failed to normalize, duplicate Emplids per snapshot, centers in painter files missing from the centers table (center IDs are safe to list).
4. **Idempotency.** Run the load a second time. Every file should say "already loaded" and the verify counts should not change.
5. **Dashboard.** Tell Logan to run `py app.py` and open http://127.0.0.1:5000. He checks a center that changed painters across snapshots. You do not view it.
6. **Done means** (from the brief): all chosen painter files loaded once and dated correctly, a clean verification report, re-runs change nothing, the center page works for any center, no personal data in any output, and the README explains adding a monthly file in three steps (already written).

## Adding a new monthly painter file

1. Run `py profile_painters.py` on the new file (counts only). Check the headers match, the job families are still only ones on the allow-list, and nothing new appeared. Report any header drift to Logan and stop; do not guess a mapping.
2. Copy the file into `raw\painters`, run `py make_manifest.py raw\painters`, check the new row's date with Logan, and set `date_confirmed = yes` only after he confirms the date.
3. `py import_painters.py --from-manifest`, then `py verify.py`. Record the counts in the status log.

## Starting a new milestone

Stop. Milestones after 1 (program enrollments and class history, PSP and IonStar imports, monthly LCPH, flags, leadership snapshots, QTC map, Axalta PM list, body techs, scheduling) have no specs in the brief. Ask Logan for a written brief for that milestone. Never invent file formats, columns or schemas. Confirm the cohort numbering against one known class date before building enrollments.

## Decisions already made by Logan

- Load only `Paint` and `Paint Help`. Body, body apprentice (TAP) and mechanical families stay out for now. `ALLOWLIST_CONFIRMED = True` is set in `config.py`.
- Skip file `Tech Capacity (Paid Flag Hrs per Week) (1).xlsx` (2025-05-16). It has `6MO Flag Avg` instead of `12 MO Flag Avg`, a different metric. Do not map it into the 12-month field.
- Damaged files, excluded: the unnumbered file (2025-04-25) and `(4)` (2025-06-24).
- `(2)` (2025-06-11, 4:44 PM) is a subset of `(3)` (4:48 PM). Skip `(2)`, load `(3)`.
- Logan confirmed he never opened or re-saved any painter file, so the modified dates are valid.
- Teammate Planned Capacity differs from 12 MO Flag Avg in about 1.5% to 5% of rows, so it is not redundant. It stays unloaded unless Logan asks for a schema change.
- `BENCHMARK_REGION_SOURCE` stays `None` until Logan decides where region comes from. Do not change it.
- Original painter folder: `C:\Local Claude Projects\CWP Program Center Technician Tracker` (read only, never touch).

## Open questions for Logan (one at a time)

- Whether to store Teammate Planned Capacity (needs a schema change).
- Where region should come from for `region_benchmarks`.
- What to do with file `(1)` later (for example a 6-month column in the schema).
- Whether the three active centers missing from the org chart (1190, 1271, 2033) belong in it.
- Cohort numbering check against one known class date.

## Status log (update after every working session; counts only)

Add a dated entry at the top each time you finish work: what ran, the counts, what is next. Never record names, emails or Emplids.

- 2026-10-02 (cloud session): Code built and tested on fake data. Centers loaded from the "Org Chart" tab (snapshot date 2026-09-11) and the Selection Tool: 1,955 centers (1,881 org chart, 74 Selection Tool only stubs), 71 inactive, 28 unknown active flag. Cohorts 1 to 25 generated and checked. Painter files profiled (17 files: 14 matching headers, 2 damaged, 1 with the 6MO column), allow-list confirmed, manifest built. Logan then ran a local session to edit the manifest and load; those counts were not recorded here. Next local session: run `py verify.py`, record the counts in a new entry, and continue from the steps above.

## Out of scope for milestone 1 (do not build)

PSP and IonStar imports, enrollments and class history, monthly LCPH, flags, leadership snapshots, the QTC map, the Axalta PM list, body techs, Power Automate or scheduling, anything cloud hosted.

## Code map

`config.py` settings | `common.py` schema and helpers | `cohorts.py` | `import_centers.py` (`--org-sheet` for a named tab) | `make_manifest.py` | `profile_painters.py` | `import_painters.py` | `verify.py` | `timeline.py` and `app.py` with `templates\` | `tests\` (fake data only) | `README.md`.
