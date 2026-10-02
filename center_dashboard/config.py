"""Project settings. Edit this file, not the scripts."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Database and folders. Environment variables override the defaults (used by tests).
DB_PATH = Path(os.environ.get("CENTER_DASH_DB", BASE_DIR / "center_dashboard.db"))
RAW_DIR = Path(os.environ.get("CENTER_DASH_RAW", BASE_DIR / "raw"))
RAW_PAINTERS_DIR = RAW_DIR / "painters"
RAW_CENTERS_DIR = RAW_DIR / "centers"
EXPORTS_DIR = BASE_DIR / "exports"
MANIFEST_PATH = Path(os.environ.get("CENTER_DASH_MANIFEST", BASE_DIR / "snapshot_manifest.csv"))

# JobFamily values to load. Run profile_painters.py first, then confirm this list with Logan.
# Add body techs later by adding their JobFamily value here. No code change needed.
JOB_FAMILY_ALLOWLIST = ["Paint", "Paint Help"]

# The painter importer refuses to run until this is True.
# Set it to True only after the profile report has been reviewed and the list above is confirmed.
ALLOWLIST_CONFIRMED = False

# Where the region for region_benchmarks comes from. The painter file has no region column.
#   None      : benchmarks are not loaded (default; ask Logan before changing)
#   "centers" : use centers.region for the row's center
BENCHMARK_REGION_SOURCE = None

# Center Selection Tool sheet name
SELECTION_SHEET = "Center Selection Tool"

# Cohort calendar
COHORT_ANCHOR_NUMBER = 25
COHORT_ANCHOR_START = (2026, 10)   # year, month
COHORT_UNTRACKED_THROUGH = 5       # cohorts 1 to 5 predate tracking

# Files modified on these dates were damaged and must not be loaded (per the brief).
DAMAGED_FILE_DATES = ["2025-04-25", "2025-06-24"]
