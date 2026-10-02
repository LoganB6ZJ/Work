"""Load the centers master.

  py import_centers.py --org <org chart xlsx> --org-snapshot-date YYYY-MM-DD --selection <selection tool xlsx>

The leadership org chart is the source of truth for the center list, official name,
region, type, address and dates. The Selection Tool only adds the active flag and
the paint partner. Leadership people are NOT loaded in milestone 1.
Output is counts and center IDs only.
"""
import argparse
import sys
from pathlib import Path

import config
from common import (already_logged, clean, connect, file_sha256, log_import, norm_header,
                    normalize_center_id, now_iso, parse_bool01, parse_date, read_table,
                    split_center_field, valid_iso_date)

ORG_FIELDS = {
    "center_id": ["centerid", "center id"],
    "name": ["center"],
    "region": ["region"],
    "center_type": ["centertype", "center type"],
    "build_type": ["buildtype", "build type"],
    "city": ["city"],
    "state": ["state"],
    "zip": ["zip"],
    "open_date": ["opendate", "open date"],
    "sales_effective_date": ["sales effective date"],
}
SEL_FIELDS = {
    "center_id": ["center id"],
    "center_name": ["center name"],
    "region": ["region"],
    "paint_partner": ["paint partner"],
    "active": ["active center"],
}


def _map(columns, fields):
    lookup = {}
    for col in columns:
        lookup.setdefault(norm_header(col), col)
    mapping, missing = {}, []
    for key, aliases in fields.items():
        hit = next((lookup[a] for a in aliases if a in lookup), None)
        if hit is None:
            missing.append(key)
        else:
            mapping[key] = hit
    return mapping, missing


def _zip(value):
    z = clean(value)
    if z and z.isdigit() and len(z) < 5:
        z = z.zfill(5)
    return z


def load_org(conn, path, snapshot_date, force=False, sheet=0):
    path = Path(path)
    fhash = file_sha256(path)
    if not force and already_logged(conn, fhash, "org_chart", snapshot_date):
        return {"status": "already loaded"}
    if sheet != 0 and path.suffix.lower() != ".csv":
        import pandas as pd
        with pd.ExcelFile(path) as xf:
            names = list(xf.sheet_names)
        if sheet not in names:
            return {"status": "sheet_not_found", "sheets": names}
    df = read_table(path, sheet_name=sheet)
    mapping, missing = _map(df.columns, ORG_FIELDS)
    if missing:
        return {"status": "header_mismatch", "missing": missing}
    seen, ids, dup, id_fail, loaded = set(), set(), 0, 0, 0
    now = now_iso()
    for rec in df.to_dict("records"):
        cid = normalize_center_id(rec[mapping["center_id"]])
        if cid is None:
            id_fail += 1
            continue
        if cid in seen:
            dup += 1
            continue
        seen.add(cid)
        conn.execute(
            "INSERT INTO centers(center_id,name,region,center_type,build_type,city,state,zip,open_date,"
            "sales_effective_date,source_org_snapshot,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(center_id) DO UPDATE SET name=excluded.name, region=excluded.region,"
            " center_type=excluded.center_type, build_type=excluded.build_type, city=excluded.city,"
            " state=excluded.state, zip=excluded.zip, open_date=excluded.open_date,"
            " sales_effective_date=excluded.sales_effective_date,"
            " source_org_snapshot=excluded.source_org_snapshot, updated_at=excluded.updated_at",
            (cid, clean(rec[mapping["name"]]), clean(rec[mapping["region"]]),
             clean(rec[mapping["center_type"]]), clean(rec[mapping["build_type"]]),
             clean(rec[mapping["city"]]), clean(rec[mapping["state"]]), _zip(rec[mapping["zip"]]),
             parse_date(rec[mapping["open_date"]]), parse_date(rec[mapping["sales_effective_date"]]),
             snapshot_date, now),
        )
        loaded += 1
    log_import(conn, path.name, fhash, "org_chart", snapshot_date, len(df), loaded,
               len(df) - loaded, f"duplicate_ids={dup};id_fail={id_fail}")
    conn.commit()
    return {"status": "loaded", "rows_read": len(df), "loaded": loaded, "duplicate_ids": dup,
            "id_fail": id_fail, "ids": seen}


def _read_selection(path):
    import pandas as pd
    raw = pd.read_excel(path, sheet_name=config.SELECTION_SHEET, header=None, dtype=str)
    header_row = None
    for i in range(min(len(raw), 30)):
        cells = {norm_header(v) for v in raw.iloc[i].tolist() if clean(v)}
        if "center id" in cells and "paint partner" in cells:
            header_row = i
            break
    if header_row is None:
        return None
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [clean(c) or f"_col{j}" for j, c in enumerate(raw.iloc[header_row].tolist())]
    return df.reset_index(drop=True)


def load_selection(conn, path, snapshot_date=None, force=False):
    path = Path(path)
    fhash = file_sha256(path)
    if not force and already_logged(conn, fhash, "selection_tool", snapshot_date):
        return {"status": "already loaded"}
    df = _read_selection(path)
    if df is None:
        return {"status": "header_mismatch", "missing": ["header row with Center ID and Paint Partner"]}
    mapping, missing = _map(df.columns, SEL_FIELDS)
    if missing:
        return {"status": "header_mismatch", "missing": missing}
    seen, ids, dup, id_fail, updated, stubs, inactive_rows = set(), set(), 0, 0, 0, 0, 0
    now = now_iso()
    for rec in df.to_dict("records"):
        cid = normalize_center_id(rec[mapping["center_id"]])
        if cid is None:
            cid, _ = split_center_field(rec[mapping["center_name"]])
        if cid is None:
            if any(clean(v) for v in rec.values()):
                id_fail += 1
            continue
        if cid in seen:
            dup += 1
            continue
        seen.add(cid)
        partner = clean(rec[mapping["paint_partner"]])
        active = parse_bool01(rec[mapping["active"]])
        if active == 0:
            inactive_rows += 1
        cur = conn.execute("UPDATE centers SET paint_partner=?, active=?, updated_at=? WHERE center_id=?",
                           (partner, active, now, cid))
        if cur.rowcount:
            updated += 1
        else:
            # Center is in the Selection Tool but not the org chart (usually closed).
            # Keep a stub so its history is never lost. The org chart fills it in if it appears later.
            _, nm = split_center_field(rec[mapping["center_name"]])
            conn.execute(
                "INSERT INTO centers(center_id,name,region,paint_partner,active,updated_at) VALUES (?,?,?,?,?,?)",
                (cid, nm, clean(rec[mapping["region"]]), partner, active, now))
            stubs += 1
    log_import(conn, path.name, fhash, "selection_tool", snapshot_date, len(df), len(seen),
               len(df) - len(seen), f"duplicate_ids={dup};id_fail={id_fail};stubs_added={stubs}")
    conn.commit()
    return {"status": "loaded", "rows_read": len(df), "loaded": len(seen), "updated": updated,
            "stubs_added": stubs, "duplicate_ids": dup, "id_fail": id_fail, "ids": seen}


def report(conn, org_ids, sel_ids):
    total = conn.execute("SELECT COUNT(*) FROM centers").fetchone()[0]
    inactive = conn.execute("SELECT COUNT(*) FROM centers WHERE active=0").fetchone()[0]
    unknown = conn.execute("SELECT COUNT(*) FROM centers WHERE active IS NULL").fetchone()[0]
    print(f"Centers in database: {total}")
    print(f"  inactive (active=0): {inactive}")
    print(f"  active flag unknown (not in Selection Tool): {unknown}")
    if org_ids is not None and sel_ids is not None:
        only_org = sorted(org_ids - sel_ids)
        only_sel = sorted(sel_ids - org_ids)
        print(f"In org chart only: {len(only_org)}  {', '.join(only_org[:40])}{' ...' if len(only_org) > 40 else ''}")
        print(f"In Selection Tool only: {len(only_sel)}  {', '.join(only_sel[:40])}{' ...' if len(only_sel) > 40 else ''}")


def main():
    ap = argparse.ArgumentParser(description="Load the centers master.")
    ap.add_argument("--org", required=True, help="leadership org chart (xlsx)")
    ap.add_argument("--org-sheet", default=0, help="tab name holding the org chart (default: first tab)")
    ap.add_argument("--org-snapshot-date", required=True, help="YYYY-MM-DD the org chart represents")
    ap.add_argument("--selection", help="Center Selection Tool workbook (xlsx)")
    ap.add_argument("--selection-snapshot-date", help="optional YYYY-MM-DD for the Selection Tool")
    ap.add_argument("--force", action="store_true", help="re-apply files already loaded")
    args = ap.parse_args()
    for d in (args.org_snapshot_date, args.selection_snapshot_date):
        if d and not valid_iso_date(d):
            sys.exit("Dates must look like YYYY-MM-DD.")
    conn = connect()
    try:
        _run(args, conn)
    finally:
        conn.close()


def _run(args, conn):
    org = load_org(conn, args.org, args.org_snapshot_date, args.force, args.org_sheet)
    print(f"Org chart: {org['status']}")
    if org["status"] == "sheet_not_found":
        sys.exit(f"No tab with that name. Tabs in the file: {', '.join(org['sheets'])}")
    if org["status"] == "header_mismatch":
        sys.exit(f"Org chart is missing expected columns: {', '.join(org['missing'])}")
    if org["status"] == "loaded":
        print(f"  rows read {org['rows_read']}, centers loaded {org['loaded']}, "
              f"duplicate IDs {org['duplicate_ids']}, IDs that failed to normalize {org['id_fail']}")
    sel = None
    if args.selection:
        sel = load_selection(conn, args.selection, args.selection_snapshot_date, args.force)
        print(f"Selection Tool: {sel['status']}")
        if sel["status"] == "header_mismatch":
            sys.exit(f"Selection Tool is missing expected columns: {', '.join(sel['missing'])}")
        if sel["status"] == "loaded":
            print(f"  rows read {sel['rows_read']}, matched {sel['updated']}, stubs added {sel['stubs_added']}, "
                  f"duplicate IDs {sel['duplicate_ids']}, IDs that failed to normalize {sel['id_fail']}")
    report(conn, org.get("ids"), (sel or {}).get("ids"))


if __name__ == "__main__":
    main()
