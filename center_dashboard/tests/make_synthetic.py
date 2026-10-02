"""Builds FAKE spreadsheets that mimic the real file shapes. No real data is used here."""
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

ORG_HEADERS = ["CBSA", "Region", "CenterType", "ADAS Station", "CenterId", "Center", "Street", "City", "State", "Zip",
               "PhoneNum", "BuildType", "TimeZone", "Sales Effective Date", "OpenDate", "Center Website", "SVP",
               "SVP Email", "VP", "VP Email", "RM", "RM Email", "GM", "GM Email", "ROM", "CMEmail", "CSREmail",
               "OMEmail", "OutsideSVCEmail", "ServiceAdvisorEmail", "Saturday Hours"]
SEL_HEADERS = ["Region", "Paint Partner", "Center Name", "Center ID", "SVP", "VP", "RM", "RPM/PM",
               "3 Month Rolling LCPH", "3 Month Rolling ACPH", "3 Month Refinish Hours", "LCPH Quintile",
               "Allied Cost Per Hour Quintile", "Hours Quintile", "Annual Savings Opportunity ", "Program Class",
               "Previous Class", "PSP Cohort", "Active Center"]
PAINTER_HEADERS = ["CenterID + Name", "Name", "JobFamily", "JobCode", "Hire Date", "Position Start Date",
                   "12 MO Flag Avg", "5 week Flag Avg", "Weekly Flag Region Avg", "Teammate Planned Capacity",
                   "Flags Per Clocked Hr", "Clocked Hours", "Emplid", "Tech Count"]

ORG = [  # CenterId (unpadded, as in the real file), name, region, city, zip
    (2, "Los Angeles - Mid Wilshire", "West", "Los Angeles", "90028"),
    (3, "Rialto", "West", "Rialto", "92376"),
    (12, "Boston - Back Bay", "East", "Boston", "2134"),
    (3733, "Austin North", "South", "Austin", "78758"),
    (5001, "New Center", "South", "Dallas", "75201"),
]
SELECTION = [  # center id text, name in Selection Tool, active
    ("0002", "0002 - Hollywood", "Axalta", "TRUE"),
    ("0003", "0003 - Rialto", "Axalta", "TRUE"),
    ("0012", "0012 - Boston", "Sherwin", "FALSE"),
    ("3733", "3733 - Austin N", "Axalta", "TRUE"),
    ("9999", "9999 - Closed Place", "Sherwin", "FALSE"),
]
# Each person: emplid, name, family, code
P = {
    "P1": ("0012345", "Fake Person One", "Paint", "55P1"),
    "P2": ("9000002", "Fake Person Two", "Paint", "55P1"),
    "P3": ("9000003", "Fake Person Three", "Paint", "55P2"),
    "P4": ("9000004", "Fake Person Four", "Paint", "55P1"),
    "P5": ("9000005", "Fake Person Five", "Paint", "55P1"),
    "H1": ("9000006", "Fake Person Six", "Paint Help", "55H1"),
    "B1": ("9000007", "Fake Person Seven", "Body", "44B1"),
    "B2": ("9000008", "Fake Person Eight", "Body", "44B1"),
}


def _row(key, center_field, psd="09/14/20", hire="04/05/21", f12=100.0, f5=95.0, hrs=40.0, region_avg=120.0):
    emp, name, fam, code = P[key]
    return [center_field, name, fam, code, hire, psd, f12, f5, region_avg, f12, 2.5, hrs, emp, 1]


def _write(path, headers, rows, title_rows=0, sheet="Sheet1", extra_sheet=False):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for i in range(title_rows):
        ws.append([f"Title row {i + 1}"])
    ws.append(headers)
    for r in rows:
        ws.append(r)
    if extra_sheet:
        wb.create_sheet("Notes").append(["not used"])
    wb.save(path)


def build(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    org_rows = []
    for cid, name, region, city, zp in ORG:
        r = [""] * len(ORG_HEADERS)
        for h, v in (("Region", region), ("CenterType", "Retail"), ("CenterId", cid), ("Center", name),
                     ("City", city), ("State", "XX"), ("Zip", int(zp) if zp.isdigit() and zp.startswith("2134") else zp),
                     ("BuildType", "Conversion"), ("OpenDate", datetime(2015, 3, 2)),
                     ("Sales Effective Date", datetime(2015, 4, 1)), ("SVP Email", "Fake.Svp@example.com")):
            r[ORG_HEADERS.index(h)] = v
        org_rows.append(r)
    org_rows.append(org_rows[0])  # duplicate center row
    out["org"] = folder / "org_chart.xlsx"
    _write(out["org"], ORG_HEADERS, org_rows)

    sel_rows = []
    for cid, nm, partner, active in SELECTION:
        r = [""] * len(SEL_HEADERS)
        r[SEL_HEADERS.index("Region")] = "West"
        r[SEL_HEADERS.index("Paint Partner")] = partner
        r[SEL_HEADERS.index("Center Name")] = nm
        r[SEL_HEADERS.index("Center ID")] = cid
        r[SEL_HEADERS.index("Active Center")] = active
        sel_rows.append(r)
    out["selection"] = folder / "selection_tool.xlsx"
    _write(out["selection"], SEL_HEADERS, sel_rows, title_rows=2, sheet="Center Selection Tool", extra_sheet=True)

    c2, c3, c12 = "0002 - Hollywood", "3 - Rialto", "0012 - Boston"
    snaps = {
        "a_2025-05-16": [_row("P1", c2), _row("P2", c2), _row("P3", c3), _row("B1", c2)],
        "b_small_2025-06-11": [_row("P1", c2), _row("P2", c2)],
        "b_full_2025-06-11": [_row("P1", c2), _row("P2", c2), _row("P3", c3), _row("P4", c12), _row("B1", c2),
                              _row("B2", c3), _row("P1", c2), _row("P1", "ABC - Broken")],
        "c_2025-09-04": [_row("P1", c2), _row("P2", c3, psd="08/01/25"), _row("P3", c3), _row("P5", c2)],
        "d_2026-10-01": [_row("P1", c2), _row("P2", c3), _row("P3", c2, psd="09/20/26"), _row("P5", c2),
                         _row("H1", c2)],
    }
    for key, rows in snaps.items():
        out[key] = folder / f"Tech Capacity {key}.xlsx"
        _write(out[key], PAINTER_HEADERS, rows)
    # a file with a renamed header and one with an unexpected extra column
    bad_headers = [h if h != "Clocked Hours" else "Clocked Hrs" for h in PAINTER_HEADERS]
    out["bad_header"] = folder / "bad_header.xlsx"
    _write(out["bad_header"], bad_headers, [_row("P1", c2)])
    out["extra_col"] = folder / "extra_col.xlsx"
    _write(out["extra_col"], PAINTER_HEADERS + ["Surprise"], [_row("P1", c2) + ["x"]])
    return out
