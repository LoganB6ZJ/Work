"""Profile painter files BEFORE loading. Counts only; nothing is written to the database.

  py profile_painters.py <folder or file> [<folder or file> ...]

Reports per file: row count, header check, distinct JobFamily and JobCode counts,
Teammate Planned Capacity vs 12 MO Flag Avg mismatches, duplicate Emplids, center IDs
that fail to normalize, and whether smaller same-day files are subsets of larger ones.
Review the job family list, then set JOB_FAMILY_ALLOWLIST and ALLOWLIST_CONFIRMED in config.py.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import clean, normalize_emplid, parse_float, read_table, split_center_field
from import_painters import map_headers


def collect(paths):
    files = []
    for a in paths:
        p = Path(a)
        if p.is_dir():
            files += sorted(q for q in p.iterdir() if q.suffix.lower() in (".xlsx", ".xls", ".csv") and not q.name.startswith("~$"))
        else:
            files.append(p)
    return files


def profile_file(path):
    df = read_table(path)
    mapping, missing, unknown = map_headers(list(df.columns))
    out = {"rows": len(df), "missing": missing, "unknown": unknown, "families": Counter(),
           "codes": Counter(), "id_fail": 0, "dup": 0, "cap_mismatch": 0, "cap_compared": 0,
           "emplids": set(), "region_vals": defaultdict(set)}
    if missing:
        return out
    seen = set()
    for rec in df.to_dict("records"):
        fam = clean(rec[mapping["job_family"]]) or "(blank)"
        code = clean(rec[mapping["job_code"]]) or "(blank)"
        out["families"][fam] += 1
        out["codes"][(fam, code)] += 1
        cid, _ = split_center_field(rec[mapping["center_field"]])
        if cid is None:
            out["id_fail"] += 1
        emp = normalize_emplid(rec[mapping["emplid"]])
        if emp is not None:
            if emp in seen:
                out["dup"] += 1
            seen.add(emp)
        if "planned_capacity" in mapping:
            a, b = parse_float(rec[mapping["planned_capacity"]]), parse_float(rec[mapping["flag_avg_12mo"]])
            out["cap_compared"] += 1
            if a != b and not (a is not None and b is not None and abs(a - b) < 1e-6):
                out["cap_mismatch"] += 1
        if "weekly_region_avg" in mapping and cid:
            out["region_vals"][cid].add(parse_float(rec[mapping["weekly_region_avg"]]))
    out["emplids"] = seen
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    files = collect(sys.argv[1:])
    if not files:
        sys.exit("No spreadsheet files found.")
    total_fam, total_code = Counter(), Counter()
    results = {}
    for f in files:
        try:
            r = profile_file(f)
        except Exception as exc:
            print(f"{f.name}: could not be read ({type(exc).__name__})")
            continue
        results[f] = r
        print(f"\n{f.name}")
        print(f"  rows: {r['rows']}")
        if r["missing"] or r["unknown"]:
            print(f"  HEADER MISMATCH. missing: {', '.join(r['missing']) or 'none'}; unexpected: {', '.join(r['unknown']) or 'none'}")
            continue
        print("  headers: OK")
        print(f"  job families: {dict(r['families'])}")
        print(f"  center IDs that failed to normalize: {r['id_fail']}; duplicate Emplids: {r['dup']}")
        if r["cap_compared"]:
            print(f"  Teammate Planned Capacity differs from 12 MO Flag Avg in {r['cap_mismatch']} of {r['cap_compared']} rows")
        total_fam.update(r["families"])
        total_code.update(r["codes"])

    print("\n=== JobFamily across all files (rows) ===")
    for fam, n in total_fam.most_common():
        print(f"  {fam}: {n}")
    print("\n=== JobFamily / JobCode across all files (rows) ===")
    for (fam, code), n in sorted(total_code.items()):
        print(f"  {fam} / {code}: {n}")

    by_mtime = defaultdict(list)
    for f in results:
        from common import file_mtime
        by_mtime[file_mtime(f).strftime("%Y-%m-%d")].append(f)
    for d, group in sorted(by_mtime.items()):
        group = [g for g in group if not results[g]["missing"]]
        if len(group) > 1:
            group.sort(key=lambda g: len(results[g]["emplids"]))
            big = group[-1]
            for g in group[:-1]:
                miss = len(results[g]["emplids"] - results[big]["emplids"])
                print(f"\nSame-day files ({d}): {g.name} has {miss} Emplids not in {big.name} "
                      f"({'subset, safe to skip it' if miss == 0 else 'NOT a subset, do not skip'})")
    print("\nNext: confirm the job families to load, then edit config.py.")


if __name__ == "__main__":
    main()
