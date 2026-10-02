"""Build or extend snapshot_manifest.csv for the painter files.

  py make_manifest.py <folder with the original painter files> [--copy]

Reads each file's modified date from the folder you give it and writes a row per
file. Existing rows (and your edits) are never overwritten. Nothing is loaded.
With --copy, files are copied (modified date preserved) into raw/painters.
The originals are never changed.

Columns you edit:
  snapshot_date   YYYY-MM-DD the export represents
  include         1 to load, 0 to skip
  date_confirmed  yes once you have checked the date. The importer ignores rows that are not 'yes'.
"""
import argparse
import csv
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import config
from common import file_mtime

FIELDS = ["filename", "snapshot_date", "include", "date_confirmed", "note"]


def read_manifest(path=None):
    path = Path(path or config.MANIFEST_PATH)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_manifest(rows, path=None):
    path = Path(path or config.MANIFEST_PATH)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Build snapshot_manifest.csv.")
    ap.add_argument("folder")
    ap.add_argument("--copy", action="store_true", help="copy files into raw/painters (originals untouched)")
    args = ap.parse_args()
    folder = Path(args.folder)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".xlsx", ".xls", ".csv") and not p.name.startswith("~$"))
    if not files:
        sys.exit("No spreadsheet files found in that folder.")
    rows = read_manifest()
    known = {r["filename"] for r in rows}
    by_date = defaultdict(list)
    info = {}
    for p in files:
        m = file_mtime(p)
        info[p.name] = (m, p.stat().st_size)
        by_date[m.strftime("%Y-%m-%d")].append(p)
    added = 0
    for p in files:
        if p.name in known:
            continue
        m, size = info[p.name]
        d = m.strftime("%Y-%m-%d")
        include, note = "1", f"modified {m.strftime('%Y-%m-%d %H:%M')}; {size // 1024} KB"
        if d in config.DAMAGED_FILE_DATES:
            include, note = "0", note + "; damaged per brief, excluded"
        elif len(by_date[d]) > 1:
            largest = max(by_date[d], key=lambda q: q.stat().st_size)
            if p != largest:
                include = "0"
                note += "; smaller same-day file, confirm it is a subset with profile_painters.py"
        rows.append({"filename": p.name, "snapshot_date": d, "include": include,
                     "date_confirmed": "no", "note": note})
        added += 1
        if args.copy:
            config.RAW_PAINTERS_DIR.mkdir(parents=True, exist_ok=True)
            dest = config.RAW_PAINTERS_DIR / p.name
            if not dest.exists():
                shutil.copy2(p, dest)
    rows.sort(key=lambda r: (r["snapshot_date"], r["filename"]))
    write_manifest(rows)
    print(f"Manifest: {len(rows)} rows ({added} added). Path: {config.MANIFEST_PATH}")
    print("Open it, fix any date that is wrong, and set date_confirmed to yes for each file you trust.")


if __name__ == "__main__":
    main()
