"""Run: py -m unittest discover -s tests -v   (from the center_dashboard folder)

Uses only FAKE generated data. Confirms no names or Emplids appear in script output.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import config  # noqa: E402
import cohorts  # noqa: E402
import common  # noqa: E402
import import_centers  # noqa: E402
import import_painters  # noqa: E402
import make_manifest  # noqa: E402
import make_synthetic  # noqa: E402
import timeline  # noqa: E402
import verify  # noqa: E402
from app import create_app  # noqa: E402

ALLOW = ["Paint", "Paint Help"]
SECRETS = ["Fake Person", "0012345", "9000002", "9000003", "example.com"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.files = make_synthetic.build(self.dir / "src")
        self.db = self.dir / "t.db"
        self.patches = [mock.patch.object(config, "DB_PATH", self.db),
                        mock.patch.object(config, "MANIFEST_PATH", self.dir / "manifest.csv"),
                        mock.patch.object(config, "RAW_PAINTERS_DIR", self.dir / "raw" / "painters"),
                        mock.patch.object(config, "EXPORTS_DIR", self.dir / "exports")]
        for p in self.patches:
            p.start()
        self.conn = common.connect()

    def tearDown(self):
        self.conn.close()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def load_all_painters(self):
        res = {}
        for k in ("a_2025-05-16", "b_full_2025-06-11", "c_2025-09-04", "d_2026-10-01"):
            date = k.split("_")[-1]
            res[k] = import_painters.load_file(self.conn, self.files[k], date, ALLOW)
        return res

    def load_centers(self):
        import_centers.load_org(self.conn, self.files["org"], "2026-10-01")
        import_centers.load_selection(self.conn, self.files["selection"])


class TestCommon(unittest.TestCase):
    def test_center_id(self):
        n = common.normalize_center_id
        self.assertEqual(n("2"), "0002")
        self.assertEqual(n(2), "0002")
        self.assertEqual(n("3733"), "3733")
        self.assertEqual(n("3733.0"), "3733")
        self.assertEqual(n("12345"), "12345")
        self.assertIsNone(n("ABC"))
        self.assertIsNone(n(None))
        self.assertIsNone(n(float("nan")))

    def test_split_first_dash_only(self):
        self.assertEqual(common.split_center_field("0002 - Los Angeles - Mid Wilshire"),
                         ("0002", "Los Angeles - Mid Wilshire"))
        self.assertEqual(common.split_center_field("3 - Rialto"), ("0003", "Rialto"))

    def test_dates(self):
        self.assertEqual(common.parse_date("04/05/21"), "2021-04-05")
        self.assertEqual(common.parse_date("2021-04-05 00:00:00"), "2021-04-05")
        self.assertIsNone(common.parse_date(""))
        self.assertIsNone(common.parse_date("garbage"))

    def test_emplid_text(self):
        self.assertEqual(common.normalize_emplid("0012345"), "0012345")
        self.assertEqual(common.normalize_emplid("123456.0"), "123456")


class TestCohorts(Base):
    def test_calendar(self):
        self.assertEqual(cohorts.cohort_dates(1), ("2024-10-01", "2024-12-31"))
        self.assertEqual(cohorts.cohort_dates(24), ("2026-09-01", "2026-11-30"))
        self.assertEqual(cohorts.cohort_dates(25), ("2026-10-01", "2026-12-31"))
        self.assertEqual(cohorts.cohort_dates(26), ("2026-11-01", "2027-01-31"))
        self.assertEqual(cohorts.cohort_dates(18), ("2026-03-01", "2026-05-31"))  # ends 31 May
        rows = cohorts.load_cohorts(self.conn, 25)
        self.assertEqual(len(rows), 25)
        tracked = {r[0]: r[3] for r in rows}
        self.assertEqual([n for n, t in tracked.items() if not t], [1, 2, 3, 4, 5])
        cohorts.load_cohorts(self.conn, 25)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM cohorts").fetchone()[0], 25)


class TestCenters(Base):
    def test_load(self):
        org = import_centers.load_org(self.conn, self.files["org"], "2026-10-01")
        self.assertEqual((org["status"], org["loaded"], org["duplicate_ids"]), ("loaded", 5, 1))
        sel = import_centers.load_selection(self.conn, self.files["selection"])
        self.assertEqual((sel["status"], sel["updated"], sel["stubs_added"]), ("loaded", 4, 1))
        row = self.conn.execute("SELECT * FROM centers WHERE center_id='0002'").fetchone()
        self.assertEqual(row["name"], "Los Angeles - Mid Wilshire")  # org chart name wins
        self.assertEqual((row["paint_partner"], row["active"]), ("Axalta", 1))
        self.assertEqual(self.conn.execute("SELECT zip FROM centers WHERE center_id='0012'").fetchone()[0], "02134")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM centers").fetchone()[0], 6)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM centers WHERE active=0").fetchone()[0], 2)
        self.assertEqual(org["ids"] - sel["ids"], {"5001"})
        self.assertEqual(sel["ids"] - org["ids"], {"9999"})

    def test_rerun_is_noop(self):
        self.load_centers()
        before = self.conn.execute("SELECT COUNT(*) FROM import_log").fetchone()[0]
        self.assertEqual(import_centers.load_org(self.conn, self.files["org"], "2026-10-01")["status"], "already loaded")
        self.assertEqual(import_centers.load_selection(self.conn, self.files["selection"])["status"], "already loaded")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM import_log").fetchone()[0], before)


class TestPainters(Base):
    def test_load_counts(self):
        res = self.load_all_painters()
        b = res["b_full_2025-06-11"]
        self.assertEqual((b["rows_read"], b["loaded"], b["skipped"]), (8, 4, 4))
        self.assertEqual((b["skipped_family"], b["dup"], b["id_fail"]), (2, 1, 1))
        self.assertEqual(res["d_2026-10-01"]["loaded"], 5)
        self.assertEqual(self.conn.execute("SELECT COUNT(DISTINCT snapshot_date) FROM staffing_snapshots").fetchone()[0], 4)
        self.assertEqual(self.conn.execute("SELECT emplid FROM people WHERE emplid='0012345'").fetchone()[0], "0012345")
        p1 = self.conn.execute("SELECT * FROM people WHERE emplid='0012345'").fetchone()
        self.assertEqual((p1["first_seen_snapshot"], p1["last_seen_snapshot"]), ("2025-05-16", "2026-10-01"))
        self.assertEqual(p1["hire_date"], "2021-04-05")

    def test_idempotent(self):
        self.load_all_painters()
        counts = lambda: [self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                          for t in ("people", "staffing_snapshots", "import_log")]
        before = counts()
        for k in ("a_2025-05-16", "b_full_2025-06-11", "c_2025-09-04", "d_2026-10-01"):
            r = import_painters.load_file(self.conn, self.files[k], k.split("_")[-1], ALLOW)
            self.assertEqual(r["status"], "already loaded")
        self.assertEqual(counts(), before)

    def test_load_order_independent(self):
        for k in ("d_2026-10-01", "c_2025-09-04", "b_full_2025-06-11", "a_2025-05-16"):
            import_painters.load_file(self.conn, self.files[k], k.split("_")[-1], ALLOW)
        p1 = self.conn.execute("SELECT * FROM people WHERE emplid='0012345'").fetchone()
        self.assertEqual((p1["first_seen_snapshot"], p1["last_seen_snapshot"]), ("2025-05-16", "2026-10-01"))

    def test_same_date_conflict(self):
        import_painters.load_file(self.conn, self.files["b_full_2025-06-11"], "2025-06-11", ALLOW)
        r = import_painters.load_file(self.conn, self.files["b_small_2025-06-11"], "2025-06-11", ALLOW)
        self.assertEqual(r["status"], "date_conflict")

    def test_header_mismatch(self):
        r = import_painters.load_file(self.conn, self.files["bad_header"], "2025-01-01", ALLOW)
        self.assertEqual(r["status"], "header_mismatch")
        self.assertIn("clocked_hours", r["missing"])
        r = import_painters.load_file(self.conn, self.files["extra_col"], "2025-01-02", ALLOW)
        self.assertEqual(r["status"], "header_mismatch")
        self.assertEqual(r["unknown"], ["Surprise"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM staffing_snapshots").fetchone()[0], 0)

    def test_allowlist_is_config_driven(self):
        r = import_painters.load_file(self.conn, self.files["b_full_2025-06-11"], "2025-06-11", ALLOW + ["Body"])
        self.assertEqual(r["loaded"], 6)

    def test_benchmarks_skipped_without_region_source(self):
        self.load_all_painters()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM region_benchmarks").fetchone()[0], 0)
        notes = self.conn.execute("SELECT notes FROM import_log LIMIT 1").fetchone()[0]
        self.assertIn("bench=skipped_no_region_source", notes)

    def test_benchmarks_from_centers(self):
        self.load_centers()
        with mock.patch.object(config, "BENCHMARK_REGION_SOURCE", "centers"):
            self.load_all_painters()
        self.assertGreater(self.conn.execute("SELECT COUNT(*) FROM region_benchmarks").fetchone()[0], 0)

    def test_gate(self):
        with mock.patch.object(config, "ALLOWLIST_CONFIRMED", False):
            with self.assertRaises(SystemExit):
                import_painters._check_gate()


class TestReportAndTimeline(Base):
    def setUp(self):
        super().setUp()
        self.load_centers()
        self.load_all_painters()

    def test_verify_counts(self):
        text = verify.build(self.conn)
        self.assertIn("transfers detected): 2", text)
        self.assertIn("consecutive snapshots: 2", text)
        self.assertIn("failed to normalize (painter files): 1", text)
        self.assertIn("within one snapshot (painter files): 1", text)
        self.assertIn("missing from the centers table: 0 (0 staffing rows)", text)
        self.conn.execute("DELETE FROM centers WHERE center_id='0012'")
        self.assertIn("missing from the centers table: 1 (1 staffing rows)", verify.build(self.conn))
        for s in SECRETS:
            self.assertNotIn(s, text)

    def test_arrival_and_departure(self):
        v3 = timeline.center_view(self.conn, "0003")
        e = {x["date"]: x for x in v3["timeline"]}["2025-09-04"]
        arrivals = [s for s in e["staff"] if s["tag"] == "from_other"]
        self.assertEqual(len(arrivals), 1)
        self.assertIn("0002", arrivals[0]["detail"])
        self.assertTrue(arrivals[0]["corroborated"])
        v2 = timeline.center_view(self.conn, "0002")
        e2 = {x["date"]: x for x in v2["timeline"]}
        left = e2["2025-09-04"]["left"]
        self.assertTrue(any("now at 0003" in x["destination"] for x in left))
        d_arr = [s for s in e2["2026-10-01"]["staff"] if s["tag"] == "from_other"]
        self.assertEqual(len(d_arr), 1)
        self.assertEqual(v2["latest_date"], "2026-10-01")
        self.assertEqual({s["job_family"] for s in v2["current"]}, {"Paint", "Paint Help"})
        self.assertEqual(v2["families"], ["Paint", "Paint Help"])

    def test_pages(self):
        client = create_app(self.db).test_client()
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.get("/?q=Rialto").status_code, 200)
        r = client.get("/center/0002")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Los Angeles - Mid Wilshire", r.data)
        self.assertEqual(client.get("/center/5001").status_code, 200)   # center with no staff
        self.assertEqual(client.get("/center/9999").status_code, 200)   # stub center
        self.assertEqual(client.get("/center/0404").status_code, 404)

    def test_cli_output_has_no_personal_data(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), mock.patch.object(config, "ALLOWLIST_CONFIRMED", True), \
                mock.patch.object(sys, "argv", ["x", str(self.files["a_2025-05-16"]), "--snapshot-date", "2025-05-16"]):
            import_painters.main()
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            import_centers.report(self.conn, {"0002"}, {"0002"})
        for s in SECRETS:
            self.assertNotIn(s, buf.getvalue() + buf2.getvalue())


class TestManifest(Base):
    def test_manifest_flow(self):
        src = self.dir / "orig"
        src.mkdir()
        import shutil
        for k, stamp in (("a_2025-05-16", "2025-05-16"), ("b_small_2025-06-11", "2025-06-11"),
                         ("b_full_2025-06-11", "2025-06-11"), ("c_2025-09-04", "2025-09-04")):
            dest = src / self.files[k].name
            shutil.copy(self.files[k], dest)
            t = common.datetime.strptime(stamp + " 12:00", "%Y-%m-%d %H:%M").timestamp()
            os.utime(dest, (t, t))
        dmg = src / "damaged.xlsx"
        shutil.copy(self.files["a_2025-05-16"], dmg)
        t = common.datetime.strptime("2025-04-25 12:00", "%Y-%m-%d %H:%M").timestamp()
        os.utime(dmg, (t, t))
        with mock.patch.object(sys, "argv", ["x", str(src), "--copy"]), contextlib.redirect_stdout(io.StringIO()):
            make_manifest.main()
        rows = {r["filename"]: r for r in make_manifest.read_manifest()}
        self.assertEqual(rows["damaged.xlsx"]["include"], "0")
        self.assertEqual(rows[self.files["b_small_2025-06-11"].name]["include"], "0")
        self.assertEqual(rows[self.files["b_full_2025-06-11"].name]["include"], "1")
        self.assertTrue(all(r["date_confirmed"] == "no" for r in rows.values()))
        self.assertTrue((config.RAW_PAINTERS_DIR / self.files["c_2025-09-04"].name).exists())
        # edits survive a re-run
        edited = list(rows.values())
        for r in edited:
            if "c_2025" in r["filename"]:
                r["date_confirmed"] = "yes"
            if "a_2025" in r["filename"]:
                r["date_confirmed"] = "yes"
        make_manifest.write_manifest(edited)
        with mock.patch.object(sys, "argv", ["x", str(src)]), contextlib.redirect_stdout(io.StringIO()):
            make_manifest.main()
        again = {r["filename"]: r for r in make_manifest.read_manifest()}
        self.assertEqual(sum(r["date_confirmed"] == "yes" for r in again.values()), 2)
        # manifest load: only confirmed + included files load
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(config, "ALLOWLIST_CONFIRMED", True), \
                mock.patch.object(sys, "argv", ["x", "--from-manifest"]):
            import_painters.main()
        dates = [r[0] for r in self.conn.execute("SELECT DISTINCT snapshot_date FROM staffing_snapshots ORDER BY 1")]
        self.assertEqual(dates, ["2025-05-16", "2025-09-04"])
        self.assertIn("2 ready", out.getvalue())


if __name__ == "__main__":
    unittest.main()
