"""Fleet usage: package-store host load + drive table (no paths)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "node"))


class TestHostMetricsCollector(unittest.TestCase):
    def test_collect_host_metrics_from_fixture_files(self) -> None:
        from serve_paid_assets import collect_host_metrics

        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            (t / "loadavg").write_text("0.50 0.75 1.00 1/100 1\n", encoding="utf-8")
            (t / "uptime").write_text("3661.0 100.0\n", encoding="utf-8")
            # disk_path: use td itself so shutil.disk_usage works
            m = collect_host_metrics(
                loadavg_path=t / "loadavg",
                uptime_path=t / "uptime",
                disk_path=str(t),
            )
        self.assertTrue(m["ok"])
        self.assertEqual(m["load_1"], 0.5)
        self.assertEqual(m["load_5"], 0.75)
        self.assertEqual(m["load_15"], 1.0)
        self.assertEqual(m["uptime_sec"], 3661)
        self.assertIsNotNone(m["disk_total_bytes"])
        self.assertGreater(m["disk_total_bytes"], 0)
        self.assertIsNotNone(m["disk_util"])
        # No paths in payload keys/values for operators
        blob = json.dumps(m)
        self.assertNotIn("/opt/", blob)
        self.assertNotIn("paid_assets", blob)
        self.assertNotIn("loadavg", blob)


class TestPackageHostRowBuilder(unittest.TestCase):
    def test_row_from_metrics_load_and_disk(self) -> None:
        from admin_node_usage import package_host_row_from_metrics

        row = package_host_row_from_metrics(
            host_id="pkg-store",
            label="Package store (HEL1)",
            host="135.181.152.10.sslip.io",
            metrics={
                "ok": True,
                "load_1": 0.12,
                "load_5": 0.08,
                "load_15": 0.05,
                "disk_total_bytes": 40_000_000_000,
                "disk_used_bytes": 2_000_000_000,
                "disk_avail_bytes": 38_000_000_000,
                "disk_util": 0.05,
                "uptime_sec": 7200,
            },
        )
        d = row.to_dict()
        self.assertEqual(d["status"], "ok")
        self.assertIn("0.12", d["load_display"])
        self.assertNotEqual(d["disk_used_display"], "—")
        self.assertNotEqual(d["disk_total_display"], "—")
        self.assertEqual(d["disk_util_display"], "5.0%")
        # Public shape has no path-like fields
        for k in d:
            self.assertNotIn("path", k.lower())
            self.assertNotIn("dir", k.lower())
            self.assertNotIn("file", k.lower())
        blob = json.dumps(d)
        self.assertNotIn("/opt/", blob)
        self.assertNotIn("paid_assets", blob)
        self.assertNotIn("restore-privacy-client", blob)

    def test_probe_failure_honest_unavailable(self) -> None:
        from admin_node_usage import collect_package_host_rows, fleet_usage_json_payload

        rows = collect_package_host_rows(
            env={"RPT_VPS_ASSET_BASE": "https://example.invalid"},
            error="unreachable",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "error")
        self.assertIn("unreachable", rows[0].detail)
        self.assertIsNone(rows[0].load_1)
        payload = fleet_usage_json_payload(
            rows=[],
            live=False,
            package_host_rows=rows,
            env={"RPT_VPS_ASSET_BASE": "https://example.invalid"},
        )
        self.assertIn("package_hosts", payload)
        self.assertEqual(payload["package_hosts"][0]["status"], "error")

    def test_fleet_json_includes_package_hosts_from_injected_metrics(self) -> None:
        from admin_node_usage import (
            fleet_usage_json_payload,
            package_host_row_from_metrics,
        )

        pkg = package_host_row_from_metrics(
            metrics={
                "ok": True,
                "load_1": 1.0,
                "load_5": 1.0,
                "load_15": 1.0,
                "disk_total_bytes": 1000,
                "disk_used_bytes": 250,
                "disk_avail_bytes": 750,
                "disk_util": 0.25,
            },
            host="store.example",
        )
        data = fleet_usage_json_payload(
            rows=[],
            live=False,
            package_host_rows=[pkg],
        )
        self.assertEqual(len(data["package_hosts"]), 1)
        ph = data["package_hosts"][0]
        self.assertEqual(ph["disk_util_display"], "25.0%")
        self.assertIn("1.00", ph["load_display"])


class TestPackageHostHtmlStructure(unittest.TestCase):
    def test_fleet_page_has_second_table_without_paths(self) -> None:
        from admin_node_usage import (
            package_host_row_from_metrics,
            render_admin_node_usage_section_html,
        )

        pkg = package_host_row_from_metrics(
            metrics={
                "ok": True,
                "load_1": 0.0,
                "load_5": 0.0,
                "load_15": 0.0,
                "disk_total_bytes": 10_000,
                "disk_used_bytes": 1_000,
                "disk_avail_bytes": 9_000,
                "disk_util": 0.1,
            },
            host="135.181.152.10.sslip.io",
            label="Package store (HEL1)",
        )
        html = render_admin_node_usage_section_html(
            rows=[],
            live=False,
            package_host_rows=[pkg],
        )
        self.assertIn('id="admin-node-usage-table"', html)
        self.assertIn('id="admin-package-host-usage-table"', html)
        self.assertIn("Installer package host", html)
        self.assertIn("admin-pkg-load-pkg-store", html)
        self.assertIn("Load (1 / 5 / 15)", html)
        self.assertIn("Disk used", html)
        # No path leakage
        low = html.lower()
        self.assertNotIn("/opt/", low)
        self.assertNotIn("paid_assets", low)
        self.assertNotIn("c:\\", low)
        self.assertNotIn("restore-privacy-client-", low)
        # Residual table still present
        self.assertIn("Fleet node usage", html)
        self.assertIn("admin-fleet-usage-script", html)

        js = (ROOT / "status_page" / "static" / "admin_fleet_usage.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("package_hosts", js)
        self.assertIn("applyPackageHost", js)

        serve = (ROOT / "node" / "serve_paid_assets.py").read_text(encoding="utf-8")
        self.assertIn("HOST_METRICS_PATH", serve)
        self.assertIn("/api/private/host-metrics", serve)
        self.assertIn("def collect_host_metrics", serve)


if __name__ == "__main__":
    unittest.main()
