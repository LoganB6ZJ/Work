"""Load painter staffing snapshots.

  py import_painters.py <file> --snapshot-date YYYY-MM-DD
  py import_painters.py --from-manifest

Every file is a dated snapshot and never overwrites an earlier one. Loading the same
file twice changes nothing. Output is counts only: no names, emails or Emplids.
"""
import argparse
import sys
from pathlib import Path

import config
from common import (already_logged, clean, connect, file_sha256, log_import, norm_header,
                    normalize_emplid, parse_date, parse_float, read_table, split_center_field,
                    valid_iso_date)

CANON = {
    "center_field": ["centerid + name", "center id + name", "centerid+name"],
    "name": ["name"],
    "job_family": ["jobfamily", "job family"],
    "job_code": ["jobcode", "job code"],
    "hire_date": ["hire date", "hiredate"],
    "position_start_date": ["position start date"],
    "flag_avg_12mo": ["12 mo flag avg", "12mo flag avg", "12 month flag avg"],
    "flag_avg_5wk": ["5 week flag avg", "5wk flag avg", "5 wk flag avg"],
    "weekly_region_avg": ["weekly flag region avg"],
    "planned_capacity": ["teammate planned capacity"],
    "flags_per_hr": ["flags per clocked hr"],
    "clocked_hours": ["clocked hours"],
    "emplid": ["emplid"],
    "tech_count": ["tech count"],
    "region": ["region"],
}
REQUIRED = ["center_field", "name", "job_family", "job_code", "hire_date", "position_start_date",
            "flag_avg_12mo", "flag_avg_5wk", "clocked_hours", "emplid"]
IGNORED = ["planned_capacity", "flags_per_hr", "tech_count", "weekly_region_avg", "region"]


def map_headers(columns):
    """Returns (mapping canonical->actual column, missing required, unknown columns)."""
    lookup = {}
    for col in columns:
        lookup.setdefault(norm_header(col), col)
    mapping = {}
    for key, aliases in CANON.items():
        hit = next((lookup[a] for a in aliases if a in lookup), None)
        if hit is not None:
            mapping[key] = hit
    missing = [k for k in REQUIRED if k not in mapping]
    used = set(mapping.values())
    unknown = [str(c) for c in columns if c not in used]
    return mapping, missing, unknown


def load_file(conn, path, snapshot_date, allowlist, force=False):
    path = Path(path)
    fhash = file_sha256(path)
    if already_logged(conn, fhash, "painter_snapshot", snapshot_date):
        return {"status": "already loaded"}
    other = conn.execute(
        "SELECT file_name FROM import_log WHERE source_type='painter_snapshot' AND snapshot_date=? LIMIT 1",
        (snapshot_date,)).fetchone()
    if other is not None:
        return {"status": "date_conflict"}
    df = read_table(path)
    mapping, missing, unknown = map_headers(list(df.columns))
    if missing or unknown:
        return {"status": "header_mismatch", "missing": missing, "unknown": unknown}

    allowed = {a.strip().lower() for a in allowlist}
    c = {"skipped_family": 0, "id_fail": 0, "emplid_fail": 0, "dup": 0}
    seen, rows = set(), []
    bench, bench_conflicts = {}, 0
    region_src = config.BENCHMARK_REGION_SOURCE
    center_region = {}
    if region_src == "centers":
        center_region = {r[0]: r[1] for r in conn.execute("SELECT center_id, region FROM centers")}

    for rec in df.to_dict("records"):
        fam = clean(rec[mapping["job_family"]])
        if fam is None or fam.lower() not in allowed:
            c["skipped_family"] += 1
            continue
        cid, _ = split_center_field(rec[mapping["center_field"]])
        if cid is None:
            c["id_fail"] += 1
            continue
        emp = normalize_emplid(rec[mapping["emplid"]])
        if emp is None:
            c["emplid_fail"] += 1
            continue
        if emp in seen:
            c["dup"] += 1
            continue
        seen.add(emp)
        rows.append((snapshot_date, emp, cid, fam, clean(rec[mapping["job_code"]]),
                     parse_date(rec[mapping["position_start_date"]]),
                     parse_float(rec[mapping["flag_avg_12mo"]]), parse_float(rec[mapping["flag_avg_5wk"]]),
                     parse_float(rec[mapping["clocked_hours"]]),
                     clean(rec[mapping["name"]]), parse_date(rec[mapping["hire_date"]])))
        if "weekly_region_avg" in mapping:
            if "region" in mapping:
                region = clean(rec[mapping["region"]])
            else:
                region = center_region.get(cid)
            val = parse_float(rec[mapping["weekly_region_avg"]])
            if region and val is not None:
                key = (region, fam)
                if key in bench and abs(bench[key] - val) > 1e-6:
                    bench_conflicts += 1
                bench.setdefault(key, val)

    if "weekly_region_avg" not in mapping:
        bench_status = "no_column"
    elif "region" not in mapping and region_src != "centers":
        bench_status = "skipped_no_region_source"
    else:
        bench_status = "loaded"

    try:
        for r in rows:
            sd, emp, cid, fam, code, psd, f12, f5, hrs, nm, hire = r
            conn.execute(
                "INSERT INTO staffing_snapshots(snapshot_date,emplid,center_id,job_family,job_code,position_start_date,"
                "flag_avg_12mo,flag_avg_5wk,clocked_hours) VALUES (?,?,?,?,?,?,?,?,?)",
                (sd, emp, cid, fam, code, psd, f12, f5, hrs))
            conn.execute(
                "INSERT INTO people(emplid,name,hire_date,first_seen_snapshot,last_seen_snapshot) VALUES (?,?,?,?,?)"
                " ON CONFLICT(emplid) DO UPDATE SET"
                " name = CASE WHEN excluded.last_seen_snapshot >= people.last_seen_snapshot"
                "   THEN COALESCE(excluded.name, people.name) ELSE COALESCE(people.name, excluded.name) END,"
                " hire_date = CASE WHEN excluded.last_seen_snapshot >= people.last_seen_snapshot"
                "   THEN COALESCE(excluded.hire_date, people.hire_date) ELSE COALESCE(people.hire_date, excluded.hire_date) END,"
                " first_seen_snapshot = MIN(people.first_seen_snapshot, excluded.first_seen_snapshot),"
                " last_seen_snapshot = MAX(people.last_seen_snapshot, excluded.last_seen_snapshot)",
                (emp, nm, hire, sd, sd))
        if bench_status == "loaded":
            for (region, fam), val in bench.items():
                conn.execute("INSERT OR REPLACE INTO region_benchmarks VALUES (?,?,?,?)",
                             (snapshot_date, region, fam, val))
        skipped = len(df) - len(rows)
        notes = (f"skipped_family={c['skipped_family']};id_fail={c['id_fail']};emplid_fail={c['emplid_fail']};"
                 f"dup={c['dup']};bench={bench_status};bench_rows={len(bench) if bench_status == 'loaded' else 0};"
                 f"bench_conflicts={bench_conflicts}")
        log_import(conn, path.name, fhash, "painter_snapshot", snapshot_date, len(df), len(rows), skipped, notes)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return {"status": "error", "error_type": type(exc).__name__}
    return {"status": "loaded", "rows_read": len(df), "loaded": len(rows), "skipped": skipped,
            "bench": bench_status, **c}


def _print_result(label, res):
    s = res["status"]
    if s == "loaded":
        print(f"{label}: loaded. read {res['rows_read']}, loaded {res['loaded']}, skipped {res['skipped']} "
              f"(other job family {res['skipped_family']}, bad center ID {res['id_fail']}, "
              f"missing Emplid {res['emplid_fail']}, duplicate Emplid {res['dup']}); benchmarks: {res['bench']}")
    elif s == "header_mismatch":
        print(f"{label}: NOT loaded, headers do not match. missing: {', '.join(res['missing']) or 'none'}; "
              f"unexpected: {', '.join(res['unknown']) or 'none'}")
    elif s == "date_conflict":
        print(f"{label}: NOT loaded. A different file is already loaded for that snapshot date.")
    elif s == "error":
        print(f"{label}: NOT loaded, database error ({res['error_type']}). Nothing was saved from this file.")
    else:
        print(f"{label}: already loaded, nothing changed.")


def _check_gate():
    if not config.ALLOWLIST_CONFIRMED:
        sys.exit("Job-family allow-list is not confirmed. Run profile_painters.py, review the job families, "
                 "then set ALLOWLIST_CONFIRMED = True in config.py.")


def main():
    ap = argparse.ArgumentParser(description="Load painter staffing snapshots.")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--snapshot-date")
    ap.add_argument("--from-manifest", action="store_true", help="load every confirmed, included file in date order")
    args = ap.parse_args()
    _check_gate()
    conn = connect()
    allow = config.JOB_FAMILY_ALLOWLIST
    if args.from_manifest:
        from make_manifest import read_manifest
        rows = read_manifest()
        if not rows:
            sys.exit("No manifest found. Run make_manifest.py first.")
        todo = [r for r in rows if r["include"].strip() == "1" and r["date_confirmed"].strip().lower() == "yes"]
        unconfirmed = [r for r in rows if r["include"].strip() == "1" and r["date_confirmed"].strip().lower() != "yes"]
        print(f"Manifest: {len(rows)} rows, {len(todo)} ready, {len(unconfirmed)} included but date not confirmed.")
        for r in sorted(todo, key=lambda r: (r["snapshot_date"], r["filename"])):
            if not valid_iso_date(r["snapshot_date"]):
                print(f"{r['filename']}: skipped, snapshot_date is not YYYY-MM-DD")
                continue
            p = config.RAW_PAINTERS_DIR / r["filename"]
            if not p.exists():
                print(f"{r['filename']}: skipped, file not found in raw/painters")
                continue
            _print_result(f"{r['snapshot_date']} {r['filename']}", load_file(conn, p, r["snapshot_date"], allow))
        return
    if not args.file or not args.snapshot_date:
        sys.exit("Give a file and --snapshot-date YYYY-MM-DD, or use --from-manifest.")
    if not valid_iso_date(args.snapshot_date):
        sys.exit("--snapshot-date must look like YYYY-MM-DD.")
    _print_result(Path(args.file).name, load_file(conn, args.file, args.snapshot_date, allow))


if __name__ == "__main__":
    main()
