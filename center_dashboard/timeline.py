"""Center page data: current staff, snapshot timeline with moves, counts over time."""
from collections import Counter, defaultdict
from datetime import date


def _d(text):
    y, m, d = (int(x) for x in text.split("-"))
    return date(y, m, d)


def snapshot_dates(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT snapshot_date FROM staffing_snapshots ORDER BY snapshot_date")]


def center_view(conn, center_id):
    dates = snapshot_dates(conn)
    here = defaultdict(dict)  # date -> emplid -> row
    for r in conn.execute(
            "SELECT s.*, p.name, p.hire_date FROM staffing_snapshots s JOIN people p ON p.emplid=s.emplid "
            "WHERE s.center_id=?", (center_id,)):
        here[r["snapshot_date"]][r["emplid"]] = dict(r)

    hist = defaultdict(list)  # emplid -> [(date, center_id)] for everyone ever here
    for r in conn.execute(
            "SELECT emplid, snapshot_date, center_id FROM staffing_snapshots WHERE emplid IN "
            "(SELECT emplid FROM staffing_snapshots WHERE center_id=?) ORDER BY snapshot_date", (center_id,)):
        hist[r["emplid"]].append((r["snapshot_date"], r["center_id"]))

    names = {r[0]: r[1] for r in conn.execute("SELECT center_id, name FROM centers")}

    def label(cid):
        return f"{cid} {names.get(cid) or ''}".strip()

    timeline, counts = [], []
    for i, d in enumerate(dates):
        prev = dates[i - 1] if i else None
        cur = here.get(d, {})
        entry = {"date": d, "gap_days": (_d(d) - _d(prev)).days if prev else None, "staff": [], "left": []}
        prev_here = here.get(prev, {}) if prev else {}
        for emp, row in cur.items():
            tag, detail, corroborated = "same" if prev else "baseline", "", False
            if prev and emp not in prev_here:
                earlier = [h for h in hist[emp] if h[0] < d]
                if not earlier:
                    tag, detail = "new", "first appearance in the data"
                else:
                    last_date, last_center = earlier[-1]
                    if last_center == center_id:
                        tag, detail = "returned", f"was here before; last seen here {last_date}"
                    else:
                        tag, detail = "from_other", f"from {label(last_center)} (seen there {last_date})"
                psd = row["position_start_date"]
                corroborated = bool(psd and prev < psd <= d)
            elif prev and emp in prev_here and prev_here[emp]["job_family"] != row["job_family"]:
                tag, detail = "role_change", f"was {prev_here[emp]['job_family']}"
            entry["staff"].append({**row, "tag": tag, "detail": detail, "corroborated": corroborated})
        entry["staff"].sort(key=lambda s: (s["job_family"], s["name"] or ""))
        for emp, row in prev_here.items():
            if emp in cur:
                continue
            later = [h for h in hist[emp] if h[0] >= d]
            if not later:
                dest = "not in any later snapshot"
            elif later[0][1] == center_id:
                dest = "absent this snapshot, returns later"
            else:
                dest = f"now at {label(later[0][1])} (seen {later[0][0]})"
            entry["left"].append({"name": row["name"], "job_family": row["job_family"], "destination": dest})
        timeline.append(entry)
        counts.append({"date": d, "by_family": dict(Counter(s["job_family"] for s in entry["staff"]))})

    families = sorted({f for c in counts for f in c["by_family"]})
    current = timeline[-1]["staff"] if timeline else []
    return {"dates": dates, "timeline": timeline, "counts": counts, "families": families,
            "current": current, "latest_date": dates[-1] if dates else None}
