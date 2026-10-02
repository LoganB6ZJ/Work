"""Verification report. Counts only. Also saved to exports/verification_report.txt."""
import re
import sys

import config
from common import connect


def build(conn):
    L = []
    q = lambda sql, *a: conn.execute(sql, a).fetchall()
    L.append("VERIFICATION REPORT (counts only)")
    L.append("")
    L.append("Files loaded (rows read / loaded / skipped)")
    logs = q("SELECT * FROM import_log ORDER BY source_type, snapshot_date, id")
    totals = {"id_fail": 0, "dup": 0, "emplid_fail": 0, "skipped_family": 0}
    for r in logs:
        L.append(f"  [{r['source_type']}] {r['snapshot_date'] or '-'}  {r['file_name']}: "
                 f"{r['rows_read']} / {r['rows_loaded']} / {r['rows_skipped']}")
        if r["source_type"] == "painter_snapshot":
            for k, v in re.findall(r"(\w+)=(\d+)", r["notes"] or ""):
                if k in totals:
                    totals[k] += int(v)
    if not logs:
        L.append("  none")
    L.append("")
    L.append(f"Center IDs that failed to normalize (painter files): {totals['id_fail']}")
    L.append(f"Duplicate Emplids within one snapshot (painter files): {totals['dup']}")
    L.append(f"Rows with missing Emplid (painter files): {totals['emplid_fail']}")
    L.append(f"Rows skipped for job family not on the allow-list: {totals['skipped_family']}")
    L.append("")
    snaps = q("SELECT COUNT(DISTINCT snapshot_date) FROM staffing_snapshots")[0][0]
    L.append(f"Snapshots loaded: {snaps}")
    L.append(f"People: {q('SELECT COUNT(*) FROM people')[0][0]}")
    L.append(f"Staffing rows: {q('SELECT COUNT(*) FROM staffing_snapshots')[0][0]}")
    multi = q("SELECT COUNT(*) FROM (SELECT emplid FROM staffing_snapshots GROUP BY emplid HAVING COUNT(DISTINCT center_id) > 1)")[0][0]
    trans = q("SELECT COUNT(*) FROM (SELECT center_id, LAG(center_id) OVER (PARTITION BY emplid ORDER BY snapshot_date) AS prev "
              "FROM staffing_snapshots) WHERE prev IS NOT NULL AND prev <> center_id")[0][0]
    L.append(f"Emplids at more than one center across snapshots (transfers detected): {multi}")
    L.append(f"Center-to-center moves between consecutive snapshots: {trans}")
    missing = q("SELECT COUNT(DISTINCT center_id), COUNT(*) FROM staffing_snapshots WHERE center_id NOT IN (SELECT center_id FROM centers)")[0]
    L.append(f"Centers in painter files missing from the centers table: {missing[0]} ({missing[1]} staffing rows)")
    L.append("")
    L.append(f"Centers: {q('SELECT COUNT(*) FROM centers')[0][0]}, "
             f"inactive: {q('SELECT COUNT(*) FROM centers WHERE active=0')[0][0]}")
    L.append(f"Cohorts: {q('SELECT COUNT(*) FROM cohorts')[0][0]}")
    return "\n".join(L)


def main():
    text = build(connect())
    print(text)
    config.EXPORTS_DIR.mkdir(exist_ok=True)
    (config.EXPORTS_DIR / "verification_report.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
