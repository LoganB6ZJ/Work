"""Shared helpers: schema, normalizers, hashing, import log."""
import hashlib
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS centers (
  center_id TEXT PRIMARY KEY,
  name TEXT, region TEXT, center_type TEXT, build_type TEXT,
  city TEXT, state TEXT, zip TEXT,
  open_date TEXT, sales_effective_date TEXT,
  paint_partner TEXT,
  active INTEGER,
  source_org_snapshot TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS cohorts (
  cohort_number INTEGER PRIMARY KEY,
  start_date TEXT, end_date TEXT,
  tracked INTEGER, note TEXT
);
CREATE TABLE IF NOT EXISTS people (
  emplid TEXT PRIMARY KEY,
  name TEXT, hire_date TEXT,
  first_seen_snapshot TEXT, last_seen_snapshot TEXT
);
CREATE TABLE IF NOT EXISTS staffing_snapshots (
  snapshot_date TEXT, emplid TEXT, center_id TEXT,
  job_family TEXT, job_code TEXT,
  position_start_date TEXT,
  flag_avg_12mo REAL, flag_avg_5wk REAL, clocked_hours REAL,
  PRIMARY KEY (snapshot_date, emplid)
);
CREATE TABLE IF NOT EXISTS region_benchmarks (
  snapshot_date TEXT, region TEXT, job_family TEXT, weekly_flag_region_avg REAL,
  PRIMARY KEY (snapshot_date, region, job_family)
);
CREATE TABLE IF NOT EXISTS import_log (
  id INTEGER PRIMARY KEY, file_name TEXT, file_hash TEXT,
  source_type TEXT, snapshot_date TEXT,
  rows_read INTEGER, rows_loaded INTEGER, rows_skipped INTEGER,
  loaded_at TEXT, notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_staff_center ON staffing_snapshots(center_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_staff_emplid ON staffing_snapshots(emplid, snapshot_date);
"""

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M:%S")


def connect(db_path=None):
    conn = sqlite3.connect(str(db_path or config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean(value):
    """Strip text. Missing, NaN and blank become None, never an empty string."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("nan", "nat"):
        return None
    return s


def clean_id_text(value):
    """Digits-as-text cleanup: removes a trailing '.0' left by numeric cells."""
    s = clean(value)
    if s is None:
        return None
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    return s


def normalize_center_id(value):
    """Zero-pad to 4 digits as text. Returns None if the value is not all digits."""
    s = clean_id_text(value)
    if s is None or not s.isdigit():
        return None
    return s.zfill(4)


def split_center_field(value):
    """'0002 - Los Angeles - Mid Wilshire' -> ('0002', 'Los Angeles - Mid Wilshire').
    Splits on the FIRST ' - ' only. The ID is the join; the name is informational."""
    s = clean(value)
    if s is None:
        return None, None
    if " - " in s:
        id_part, name = s.split(" - ", 1)
    else:
        id_part, name = s, None
    return normalize_center_id(id_part), clean(name)


def normalize_emplid(value):
    return clean_id_text(value)


def normalize_email(value):
    s = clean(value)
    return s.lower() if s else None


def parse_date(value):
    """Return YYYY-MM-DD text or None."""
    if value is None:
        return None
    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return value.strftime("%Y-%m-%d")
        except ValueError:
            return None
    s = clean(value)
    if s is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_float(value):
    s = clean(value)
    if s is None:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def parse_bool01(value):
    s = clean(value)
    if s is None:
        return None
    u = s.upper()
    if u in ("TRUE", "1", "YES", "Y"):
        return 1
    if u in ("FALSE", "0", "NO", "N"):
        return 0
    return None


def norm_header(h):
    return re.sub(r"\s+", " ", str(h).strip()).lower()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def file_mtime(path):
    return datetime.fromtimestamp(Path(path).stat().st_mtime)


def read_table(path, sheet_name=0, header=0):
    """Read a spreadsheet or CSV with every cell as text (keeps leading zeros)."""
    import pandas as pd
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str, header=header, keep_default_na=False, na_values=[""])
    else:
        df = pd.read_excel(path, sheet_name=sheet_name, dtype=str, header=header)
    return df


def already_logged(conn, file_hash, source_type, snapshot_date=None):
    row = conn.execute(
        "SELECT 1 FROM import_log WHERE file_hash=? AND source_type=? AND IFNULL(snapshot_date,'')=IFNULL(?,'') LIMIT 1",
        (file_hash, source_type, snapshot_date),
    ).fetchone()
    return row is not None


def log_import(conn, file_name, file_hash, source_type, snapshot_date,
               rows_read, rows_loaded, rows_skipped, notes=""):
    conn.execute(
        "INSERT INTO import_log(file_name,file_hash,source_type,snapshot_date,rows_read,rows_loaded,rows_skipped,loaded_at,notes)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (file_name, file_hash, source_type, snapshot_date, rows_read, rows_loaded, rows_skipped, now_iso(), notes),
    )


def valid_iso_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False
