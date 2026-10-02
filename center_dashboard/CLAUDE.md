# Center Dashboard: instructions for Claude Code

Owner: Logan, Manager of Technical Paint Training, Caliber Collision.
This folder is a local database and browser app (Python, SQLite, pandas, openpyxl, Flask).
Scope is Milestone 1 only. Do not build anything beyond it. Ask Logan before building anything new.
Style: short, professional answers. No em dashes. Ask one clear question at a time. When Logan asks for an edit, make that edit and nothing more.

## Privacy rules (hard, they override everything else)

The data contains real people's names, emails and employee IDs. Anything you read or print is sent to Anthropic's API, which Logan's rules forbid for this data.

1. Never open, read, cat, head, preview or search inside: `raw\`, any `.xlsx` or `.csv` data file, `*.db`, `exports\`. Do not use the Read, Grep or Glob tools on them. File names and sizes are fine.
2. Never run a query or script that prints names, emails or Emplids. SQL against `center_dashboard.db` may only return counts and non-personal columns (center_id, snapshot_date, job_family, job_code, counts). Never SELECT from `people.name`, `people.emplid`, `staffing_snapshots.emplid`, or the org chart email columns.
3. Run only the project scripts and read their output. The scripts print counts and center IDs only. If any output ever shows a name, email or Emplid, stop and tell Logan.
4. Do not open the dashboard pages yourself (no curl, Playwright or screenshots of the app). Logan opens http://127.0.0.1:5000 in his own browser.
5. Never modify, rename, move or re-save the raw source files. Never commit data, the database, exports or the manifest. No network calls, no uploads.
6. Do not install software beyond `pip install --user pandas openpyxl flask`. Ask first if anything else is needed. Logan has no admin rights.
7. In chat, report counts and structure only.

`snapshot_manifest.csv` holds only file names, dates and notes. You may read and edit it.

## Environment

Windows, PowerShell. Use `py`, not `python`. Run commands from this folder (`center_dashboard`). Quote paths that contain spaces.
Project is at `C:\Local Claude Projects\Work-claude-build-this-1kdq8z\center_dashboard`. It is deliberately outside OneDrive. Keep it there.
Test suite on fake data: `py -m unittest discover -s tests` (22 tests, all passing).

## Current state

- Centers loaded from the "Org Chart" tab and the Selection Tool: 1,955 centers (1,881 from the org chart, 74 Selection Tool only stubs), 71 inactive, 28 with an unknown active flag. Three active centers (1190, 1271, 2033) are in the Selection Tool but not in the org chart; Logan is checking them. Nothing to fix in code.
- Cohorts 1 to 25 generated and checked by Logan. Cohorts 1 to 5 are untracked.
- Painter files were profiled. Job family allow-list confirmed by Logan: `Paint` and `Paint Help`. `ALLOWLIST_CONFIRMED = True` is set in `config.py`.
- Manifest built (`snapshot_manifest.csv`, 17 rows), files copied to `raw\painters`.
- Logan confirmed he never opened or re-saved any painter file, so the modified dates are valid.
- Original painter folder: `C:\Local Claude Projects\CWP Program Center Technician Tracker` (read only, never touch).

## Decisions already made by Logan

- Load only `Paint` and `Paint Help`. Body, body apprentice (TAP) and mechanical families stay out for now.
- Skip file `Tech Capacity (Paid Flag Hrs per Week) (1).xlsx` (2025-05-16). It has a `6MO Flag Avg` column instead of `12 MO Flag Avg`, a different metric. Do not map it into the 12-month field.
- Damaged files, excluded: the unnumbered file (2025-04-25) and `(4)` (2025-06-24).
- `(2)` (2025-06-11, 4:44 PM) is a subset of `(3)` (4:48 PM). Skip `(2)`, load `(3)`.
- Teammate Planned Capacity differs from 12 MO Flag Avg in about 1.5% to 5% of rows, so it is not redundant. It stays unloaded unless Logan asks for a schema change.
- Region benchmarks: `BENCHMARK_REGION_SOURCE` stays `None` until Logan decides. Do not change it.

## Next steps, in order

1. **Edit the manifest** with a short script that touches only `include` and `date_confirmed` and prints only file names and those two values:
   - set `include` to `0` for `(1)`;
   - set `date_confirmed` to `yes` for exactly these 13 files: `(3)` and `(5)` through `(16)`;
   - leave the unnumbered file, `(1)`, `(2)` and `(4)` as `include = 0`, `date_confirmed = no`.
2. **Load:** `py import_painters.py --from-manifest`. Report rows read, loaded and skipped per file. Expect the three blank-job-family rows per file to be skipped. If a file reports a header mismatch, stop and tell Logan the header names (headers are safe to share).
3. **Verify:** `py verify.py`. Report the counts: transfers detected, IDs that failed to normalize, duplicate Emplids per snapshot, and centers in painter files that are missing from the centers table (center IDs are safe to list).
4. **Idempotency check:** run `py import_painters.py --from-manifest` a second time. Every file should say "already loaded" and `py verify.py` counts should not change.
5. **Dashboard:** tell Logan to run `py app.py` and open http://127.0.0.1:5000. He checks a center that changed painters across snapshots. You do not view it.
6. **Done means** (milestone 1): all 13 chosen painter files loaded once and dated correctly, a clean verification report, re-runs change nothing, the center page works for any center, no personal data in any output, and the README explains adding a monthly file in three steps (already written).

## Open questions to bring to Logan (one at a time, short answers)

- Whether to store Teammate Planned Capacity (needs a schema change).
- Where region should come from for `region_benchmarks`.
- What to do about file `(1)` later (for example a 6-month column in the schema).
- Confirm the cohort numbering against one known class date before the enrollments milestone.

## Out of scope for milestone 1 (do not build)

PSP and IonStar imports, enrollments and class history, monthly LCPH, flags, leadership snapshots, the QTC map, the Axalta PM list, body techs, Power Automate or scheduling, anything cloud hosted.

## Code map

`config.py` settings | `common.py` schema and helpers | `cohorts.py` | `import_centers.py` | `make_manifest.py` | `profile_painters.py` | `import_painters.py` | `verify.py` | `timeline.py` and `app.py` with `templates\` | `tests\` (fake data only). See `README.md`.
