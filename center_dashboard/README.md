# Center Dashboard (Milestone 1)

Local database and browser app for about 1,800 to 1,900 centers. Runs only on this computer.
Python 3, SQLite, pandas, openpyxl, Flask. No network calls.

**Privacy.** Scripts print counts and center IDs only. Never paste names, emails or Emplids into chat.
`raw/`, `*.db`, `exports/` and `snapshot_manifest.csv` are git-ignored. Do not commit data.

Run every command below from this folder (`center_dashboard`) in the VS Code terminal, using `py`.

## One-time setup

1. `py -m pip install --user pandas openpyxl flask`
2. Put the leadership org chart and the Selection Tool in `raw\centers`. Put painter files in `raw\painters` (or use `--copy` in step 3 of "Load the history").
3. Run the tests on fake data: `py -m unittest discover -s tests`

## First load (in this order)

1. **Centers.** `py import_centers.py --org raw\centers\<org chart>.xlsx --org-snapshot-date YYYY-MM-DD --selection raw\centers\<selection tool>.xlsx`
   Check the counts, and the center IDs that appear in only one file.
2. **Cohorts.** `py cohorts.py` prints the table. Compare it with what you know. Use `--through 40` to extend.
3. **Profile the painter files.** `py profile_painters.py <folder of painter files>`
   Review the job family and job code counts, header problems, and the same-day subset check.
4. **Confirm the allow-list.** In `config.py` set `JOB_FAMILY_ALLOWLIST`, then `ALLOWLIST_CONFIRMED = True`.
5. **Manifest.** `py make_manifest.py <original painter folder> --copy` writes `snapshot_manifest.csv` and copies files to `raw\painters` with their modified dates kept. Open the CSV, fix any wrong date, set `date_confirmed` to `yes` for files you trust. Files from 2025-04-25 and 2025-06-24 are pre-set to `include = 0` (damaged). A smaller same-day file is also set to `include = 0`.
6. **Load.** `py import_painters.py --from-manifest` loads confirmed files in date order. Safe to re-run; loaded files are skipped.
7. **Verify.** `py verify.py` prints counts and saves them to `exports\verification_report.txt`.
8. **Open the dashboard.** `py app.py`, then browse to http://127.0.0.1:5000

## Add a new monthly painter file (three steps)

1. Copy the new export into `raw\painters`, then run `py make_manifest.py raw\painters`. Open `snapshot_manifest.csv`, check the new row's date, and set `date_confirmed` to `yes`.
2. `py import_painters.py --from-manifest`
3. `py verify.py`

Or load one file directly: `py import_painters.py <file> --snapshot-date YYYY-MM-DD`

## Decisions still open (ask before changing)

- **Job families and codes:** confirm after step 3.
- **Region for benchmarks:** the painter file has no region column. `BENCHMARK_REGION_SOURCE` is `None`, so `region_benchmarks` stays empty until you decide. Setting it to `"centers"` uses the center's region from the org chart.
- **Snapshot dates:** loaded only after you set `date_confirmed` to `yes`.
- **Selection Tool only centers:** a center in the Selection Tool but not the org chart (usually closed) is kept as a stub row so its history is not lost. The org chart fills it in if it appears later.
- **Cohort numbering:** confirm against one known class date before the enrollments milestone.

## How it behaves

- Center IDs are text, zero-padded to 4 digits. The ID is the only join between files.
- Every painter file is a dated snapshot. Nothing overwrites an earlier one. A second, different file for a date already loaded is refused.
- A file whose headers differ from the expected set is reported and not loaded.
- Position Start Date is shown as a corroborating signal only. It never proves a transfer.
- Derived columns (quintiles, savings, flags per hour, tech count) are not imported.

## Files

`config.py` settings | `common.py` helpers and schema | `cohorts.py` | `import_centers.py` | `make_manifest.py` | `profile_painters.py` | `import_painters.py` | `verify.py` | `timeline.py` and `app.py` with `templates\` | `tests\` (fake data only)
