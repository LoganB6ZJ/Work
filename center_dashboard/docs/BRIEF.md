# Claude Code Brief: Center Dashboard (Milestone 1)

**Owner:** Logan, Manager of Technical Paint Training, Caliber Collision
**Status:** Plan approved. Build milestone 1 only. Do not build beyond it.

---

## 1. What this is

A local database and browser app, center-centric, covering about 1,800 to 1,900 Caliber centers. Click a center and see its leaders, painters, programs, and metrics, with full history. The dashboard exists to answer questions Logan cannot answer by hand, such as:

- Who was the painter at this center when it was in cohort 19?
- Did this painter come from another center that had already been through a program?

Centers and people are **equal anchors**. Program enrollments and metrics attach to the center. Staffing history attaches to people and links to centers through dated snapshots. Neither is more important than the other.

---

## 2. Privacy rules (hard)

These files contain real people's names, emails, and employee IDs.

1. Everything runs and stays on this computer. No network calls, no cloud services, no uploading file contents anywhere.
2. When you report results to Logan, report **counts and structure only**. Never print names, emails, or Emplids in chat output, logs, test output, or error messages. Use masked values (for example the last 2 digits) if you must show an example.
3. Never modify, rename, move, or re-save the raw source files. Copy them to a `raw/` folder if needed and treat that copy as read-only.
4. Do not commit data files or the database to any git repository. Add `raw/`, `*.db`, and `exports/` to `.gitignore` on day one.
5. This is company data on a company computer. If anything requires installing software beyond standard Python packages, stop and ask Logan first.

---

## 3. Stack

- **Python 3** and **SQLite** (single file, standard SQL so it can migrate to a company-approved database later).
- **pandas** and **openpyxl** for reading Excel.
- A small local web app (Flask or FastAPI with plain HTML templates is fine). No front-end framework required. Keep it simple and readable.
- Importers are plain command-line scripts: `python import_painters.py <file> --snapshot-date YYYY-MM-DD`.

---

## 4. Global rules (apply to every importer)

**Center ID**
- Stored as **text**, zero-padded to 4 digits (`"2"` becomes `"0002"`, `"3733"` stays `"3733"`).
- Excel and CSV strip leading zeros, so read every ID column with `dtype=str` and normalize.
- Some sources embed the ID in a name field (for example `"0002 - Los Angeles - Mid Wilshire"`). Split on the **first** `" - "` only.
- Center names differ between sources (the same center is called "Hollywood" in one file and "Los Angeles - Mid Wilshire" in another). **The ID is the only join.** Use the leadership org chart for the official name.

**People**
- Painters match on **Emplid** (store as text).
- Leadership (SVP, VP, RM, GM) matches on **lowercase email**. The leadership chart has no Emplid.
- Never match people by name. Names are `Last, First` in some files and `First Last` in others.

**Snapshots**
- Every people or leadership file is loaded as a **dated snapshot** and never overwrites an earlier one.
- The files contain **no date inside them**. Snapshot date comes from a manifest (section 6), defaulting to file modified date.
- Loading the same file twice must be a no-op. Use a hash of the file plus the snapshot date in `import_log` to detect duplicates.

**Derived values**
- Do not import calculated columns (quintiles, savings, tiers, flags per hour, tech count). Recompute them if needed.

**Closed centers** stay in the database, flagged inactive, so their history is never lost.

**Dates** are stored as `YYYY-MM-DD` text. Missing is `NULL`, never an empty string.

---

## 5. Cohort calendar (generate by formula, do not import)

- One cohort starts on the **1st of every month**. Each runs 3 months and ends on the **last day of its third month**. No skipped months. Cohorts overlap, so three are live at any time.
- **Cohort 25 starts 2026-10-01.** Count backward one month per cohort.
- Cohort 1 starts 2024-10-01. Cohort 24 starts 2026-09-01.
- Formula: `start(n) = 2026-10-01 minus (25 - n) months`; `end(n) = last day of the month that is 2 months after start(n)`.
- Cohorts **1 to 5** predate Logan running the program. Give them dates but set `tracked = 0` with the note "predates tracking". No staffing history exists for them.
- The numbering is assumed to match the `Program Class` and `Previous Class` columns in the Selection Tool. Confirm this with Logan using one known class date before building enrollments (a later milestone).

---

## 6. Source files

Logan will point you at a folder. **Ask him before assuming anything not listed here.**

### A. Painter snapshots: "Tech Capacity (Paid) Flag Hrs per Week" Excel exports

Power BI exports. One row per technician, current snapshot at export time.

Headers:
`CenterID + Name, Name, JobFamily, JobCode, Hire Date, Position Start Date, 12 MO Flag Avg, 5 week Flag Avg, Weekly Flag Region Avg, Teammate Planned Capacity, Flags Per Clocked Hr, Clocked Hours, Emplid, Tech Count`

Example row shape (fake values): `0003 - Rialto | Jane Doe | Paint | 55P% | 04/05/21 | 09/14/26 | 134.7 | 93.7 | 128.9 | 134.7 | 3.2 | 43.1 | 123456 | 1`

Rules:
- `CenterID + Name` splits into center ID and a source-side name (ignore the name).
- `Emplid` is the person key (text).
- `JobFamily` values seen so far: `Paint` (painter) and `Paint Help` (helper/apprentice role). The full workforce file also contains **body techs** and other families. **Load only paint-related families for now.** Keep an allow-list in one config constant so body techs can be added later without code changes. Profile the file first and **report the distinct JobFamily and JobCode values with row counts** to Logan, and have him confirm the allow-list. Do not guess.
- `Position Start Date` marks the last time pay or employment changed (raise, store move, apprentice added). Store it. It is a **corroborating signal only**, not proof of a transfer.
- Per-person metrics to store: `12 MO Flag Avg`, `5 week Flag Avg`, `Clocked Hours`.
- `Weekly Flag Region Avg` repeats on every row. Store once per region-and-job-family-and-snapshot, not per person. If region is not in the file, ask Logan; do not invent it.
- `Teammate Planned Capacity` appeared identical to `12 MO Flag Avg` in sampled rows. Verify across the full file with a count of mismatches. If it is always identical, skip it.
- `Flags Per Clocked Hr` is derived. Recompute. `Tech Count` is always 1. Ignore.

**File inventory (15 usable files).** The two files below were damaged by Logan and **must be excluded**:
- the 4/25/2025 file (about 778 KB)
- the 6/24/2025 file (about 1,388 KB)

Usable files, by date modified:

| Date modified | Notes |
|---|---|
| 2025-05-16 | earliest usable |
| 2025-06-11 4:44 PM | likely painters only, same day as the next row |
| 2025-06-11 4:48 PM | **full workforce, about 14,000 rows**, includes body techs and apprentices. Use this one for 2025-06-11. Verify by counts that the 4:44 file is a subset, then skip the 4:44 file so nothing double counts. |
| 2025-09-04 | |
| 2025-09-15 | |
| 2025-10-22 | |
| 2025-11-18 | |
| 2025-12-19 | |
| 2026-01-21 | |
| 2026-04-09 | |
| 2026-04-22 | |
| 2026-05-11 | |
| 2026-06-24 | |
| 2026-09-25 | |
| 2026-10-01 7:27 PM | first export that includes apprentices (larger file). **Cohort 25 baseline. Treat as precious.** |

Gaps with no snapshot: roughly 6/11 to 9/4/2025, 1/21 to 4/9/2026, and 6/24 to 9/25/2026. A move inside a gap is recorded as "between snapshot X and snapshot Y".

**Snapshot dates:** Date modified is only valid if Logan never opened and re-saved the file. Build a `snapshot_manifest.csv` (filename, snapshot_date) that Logan can edit, pre-filled from file modified dates. The importer reads the manifest first. **Never infer a date silently.** Copying a file can reset its modified date, so confirm with Logan before loading.

**Column drift:** older and newer exports may differ slightly (columns added or renamed). Map each file's headers to the canonical fields above, and report any file whose headers do not match instead of guessing.

### B. Leadership org chart (centers master)

Excel export. One row per center, with address, market, and the full leadership chain.

Headers:
`CBSA, Region, CenterType, ADAS Station, CenterId, Center, Street, City, State, Zip, PhoneNum, BuildType, TimeZone, Sales Effective Date, OpenDate, Center Website, SVP, SVP Email, VP, VP Email, RM, RM Email, GM, GM Email, ROM, CMEmail, CSREmail, OMEmail, OutsideSVCEmail, ServiceAdvisorEmail, Saturday Hours`

Notes:
- `CenterId` is **not** zero-padded here (for example `3733`). Normalize.
- Names are `Last, First`. Emails are the stable person key. Lowercase them.
- Source of truth for the center list, official center name, region, open date, and leadership.
- `OpenDate` and `Sales Effective Date` support a later "new center" flag. Store them.
- `Saturday Hours` is noise. Ignore it. Service advisor and CSR emails are shared mailboxes, not people. Do not load them as people.
- Milestone 1 loads this into the `centers` table only. Dated leadership snapshots come in a later milestone.

### C. Center Selection Tool (LCPH program status)

An Excel workbook with 7 tabs. The `Center Selection Tool` tab is formula-driven. Milestone 1 uses it only to enrich `centers` (active flag, Axalta paint partner).

Headers:
`Region, Paint Partner, Center Name, Center ID, SVP, VP, RM, RPM/PM, 3 Month Rolling LCPH, 3 Month Rolling ACPH, 3 Month Refinish Hours, LCPH Quintile, Allied Cost Per Hour Quintile, Hours Quintile, Annual Savings Opportunity, Program Class, Previous Class, PSP Cohort, Active Center`

Notes:
- `Center Name` has the ID baked in (for example `0002 - Hollywood`). `Center ID` is zero-padded text.
- `Annual Savings Opportunity` has a trailing space in its header. Strip header whitespace on read.
- `RPM/PM` is `First Last` order, unlike the other leadership columns.
- `Active Center` is TRUE/FALSE. Inactive rows can still carry class history.
- Quintiles and savings are derived. Do not import them.
- Program history (`Program Class`, `Previous Class`, `PSP Cohort`) is a later milestone. It will be unpivoted to one row per center per class.

---

## 7. Schema for milestone 1

```sql
centers (
  center_id TEXT PRIMARY KEY,       -- 4+ digit text
  name TEXT, region TEXT, center_type TEXT, build_type TEXT,
  city TEXT, state TEXT, zip TEXT,
  open_date TEXT, sales_effective_date TEXT,
  paint_partner TEXT,               -- from Selection Tool
  active INTEGER,                   -- from Selection Tool
  source_org_snapshot TEXT, updated_at TEXT
);

cohorts (
  cohort_number INTEGER PRIMARY KEY,
  start_date TEXT, end_date TEXT,
  tracked INTEGER, note TEXT
);

people (
  emplid TEXT PRIMARY KEY,
  name TEXT, hire_date TEXT,
  first_seen_snapshot TEXT, last_seen_snapshot TEXT
);

staffing_snapshots (
  snapshot_date TEXT, emplid TEXT, center_id TEXT,
  job_family TEXT, job_code TEXT,
  position_start_date TEXT,
  flag_avg_12mo REAL, flag_avg_5wk REAL, clocked_hours REAL,
  PRIMARY KEY (snapshot_date, emplid)
);

region_benchmarks (
  snapshot_date TEXT, region TEXT, job_family TEXT, weekly_flag_region_avg REAL,
  PRIMARY KEY (snapshot_date, region, job_family)
);

import_log (
  id INTEGER PRIMARY KEY, file_name TEXT, file_hash TEXT,
  source_type TEXT, snapshot_date TEXT,
  rows_read INTEGER, rows_loaded INTEGER, rows_skipped INTEGER,
  loaded_at TEXT, notes TEXT
);
```

Keep names, emails, and Emplids out of `import_log`. Counts only.

---

## 8. Milestone 1 scope (build only this)

1. **Project setup:** folder structure, `.gitignore`, config file with the job-family allow-list, and the snapshot manifest.
2. **Centers:** load the leadership org chart, then enrich from the Selection Tool. Report count of centers, count inactive, and any center ID that appears in one file but not the other.
3. **Cohorts:** generate cohorts 1 to 25 by formula (with room to extend). Print the table for Logan to eyeball against his own knowledge.
4. **Painter importer:** profile the files first (distinct job families and codes with counts, column header check, row counts per file), get the allow-list confirmed, then load snapshots in date order.
5. **Center page (local web app):** pick a center, see:
   - current painters and helpers (from the latest snapshot),
   - a timeline of who was there at each snapshot date, with joins, leaves, and arrivals from other centers highlighted,
   - a simple count-over-time per job family.
   Plain and functional. No design polish yet.
6. **Verification report** (counts only):
   - rows read, loaded, and skipped per file,
   - Emplids appearing at more than one center across snapshots (transfers detected),
   - IDs that failed to normalize,
   - duplicate Emplids within one snapshot,
   - centers in painter files that are missing from the centers table.

**Out of scope for milestone 1** (do not build): PSP and IonStar imports, enrollments and class history, monthly LCPH, flags, leadership snapshots, the QTC map, the Axalta PM list, body techs, Power Automate or scheduling, and anything cloud-hosted.

---

## 9. Ask Logan before you assume

- The distinct job family and job code values, and which count as painter, helper, and apprentice.
- Whether any snapshot's modified date is unreliable.
- Where region comes from for the benchmark table, if the painter file lacks it.
- Anything in a file that does not match the headers listed above.

Ask one concise question at a time. Logan prefers short answers and decisions, not long explanations.

---

## 10. Done means

- All 15 usable painter files loaded once, dated correctly, with a clean verification report.
- Re-running any importer changes nothing.
- The center page works for any center and for a center that has changed painters across snapshots.
- No personal data appears in any output, log, or committed file.
- A short `README.md` explains how to add a new monthly painter file in three steps.
