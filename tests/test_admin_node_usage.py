"""Admin fleet node usage panel: bandwidth used vs capacity; public-safe."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestBandwidthMath(unittest.TestCase):
    def test_average_bps_and_util(self):
        from admin_node_usage import (
            average_bps_from_bytes,
            bandwidth_utilization,
            format_bps,
            format_pct,
        )

        # 1 MiB over 8 seconds → 1 MiB/s → 8 Mibps average
        bps = average_bps_from_bytes(1_048_576, 8)
        self.assertIsNotNone(bps)
        assert bps is not None
        self.assertAlmostEqual(bps, 1_048_576 * 8 / 8.0, delta=1.0)
        util = bandwidth_utilization(bps, int(bps * 2))
        self.assertAlmostEqual(util or 0, 0.5, delta=0.01)
        self.assertIn("Mbps", format_bps(bps))
        self.assertEqual(format_pct(0.5), "50.0%")
        self.assertIsNone(average_bps_from_bytes(None, 10))
        self.assertIsNone(bandwidth_utilization(100.0, None))


class TestFleetRows(unittest.TestCase):
    def test_rows_cover_catalog_is_ro_de(self):
        from admin_node_usage import build_fleet_usage_rows, product_catalog_peers

        peers = product_catalog_peers()
        codes = {p["code"] for p in peers}
        self.assertTrue({"IS", "RO", "DE"}.issubset(codes))
        # Inject bandwidth payload for IS only
        probes = {
            "82.221.101.241": {
                "live": 10,
                "capacity": 100,
                "utilization": 0.1,
                "total_bytes_relayed": 8_000_000,
                "process_uptime_sec": 100,
                "bandwidth_cap_bps": 10_000_000,
                "private": True,
            }
        }
        rows = build_fleet_usage_rows(
            probes_by_host=probes,
            peers=peers,
            env={"RPT_NODE_BANDWIDTH_CAP_BPS": "10000000"},
        )
        by_code = {r.code: r for r in rows}
        self.assertIn("IS", by_code)
        self.assertIn("RO", by_code)
        self.assertIn("DE", by_code)
        is_row = by_code["IS"]
        self.assertEqual(is_row.status, "ok")
        self.assertIsNotNone(is_row.bandwidth_used_bps)
        self.assertIsNotNone(is_row.bandwidth_cap_bps)
        self.assertIsNotNone(is_row.bandwidth_util)
        # RO/DE unknown without probe
        self.assertIn(by_code["RO"].status, ("unknown", "error"))


class TestAdminHtmlSection(unittest.TestCase):
    def test_admin_html_places_usage_below_nav(self):
        import admin_panel
        from admin_node_usage import NodeUsageRow

        rows = [
            NodeUsageRow(
                code="IS",
                name="Iceland",
                host="82.221.101.241",
                port=44044,
                bandwidth_used_bps=1_000_000.0,
                bandwidth_cap_bps=10_000_000,
                bandwidth_util=0.1,
                bytes_relayed=5_000_000,
                uptime_sec=40,
                sessions_live=2,
                sessions_cap=256,
                session_util=2 / 256,
                status="ok",
            ),
            NodeUsageRow(
                code="RO",
                name="Romania",
                host="185.146.232.107",
                port=44044,
                bandwidth_used_bps=None,
                bandwidth_cap_bps=10_000_000,
                bandwidth_util=None,
                bytes_relayed=None,
                uptime_sec=None,
                sessions_live=None,
                sessions_cap=None,
                session_util=None,
                status="unknown",
                detail="not probed",
            ),
            NodeUsageRow(
                code="DE",
                name="Germany",
                host="167.233.224.5",
                port=44044,
                bandwidth_used_bps=500_000.0,
                bandwidth_cap_bps=10_000_000,
                bandwidth_util=0.05,
                bytes_relayed=1_000_000,
                uptime_sec=16,
                sessions_live=1,
                sessions_cap=256,
                session_util=1 / 256,
                status="ok",
            ),
        ]
        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            try:
                html = admin_panel.render_admin_html(
                    grants=[],
                    node_usage_rows=rows,
                    node_usage_live=False,
                ).decode("utf-8")
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

        self.assertIn('id="admin-node-usage"', html)
        self.assertIn("Fleet node usage", html)
        self.assertIn("admin-node-usage-table", html)
        nav_i = html.find('id="admin-nav"')
        usage_i = html.find('id="admin-node-usage"')
        arch_i = html.find('id="admin-architecture"')
        self.assertGreater(usage_i, nav_i)
        self.assertGreater(arch_i, usage_i)
        for code in ("IS", "RO", "DE"):
            self.assertIn(code, html)
            self.assertIn(f"admin-node-bw-used-{code}", html)
            self.assertIn(f"admin-node-bw-cap-{code}", html)
        self.assertIn("Mbps", html)  # formatted used/cap
        # Public shop must not get this block from admin render alone is fine;
        # ensure section is admin-only marker
        self.assertIn("data-admin-node-usage", html)


class TestPublicStatusSafe(unittest.TestCase):
    def test_public_status_filter_still_title_only(self):
        from node.aggregate_metrics import filter_public_status, assert_public_status_minimal
        from node.private_capacity import (
            build_private_capacity_payload,
            public_status_must_not_include_capacity,
        )

        priv = build_private_capacity_payload(
            live=5,
            capacity=100,
            total_bytes_relayed=999,
            process_uptime_sec=10,
            bandwidth_cap_bps_value=1_000_000,
            host="82.221.101.241",
        )
        self.assertIn("total_bytes_relayed", priv)
        self.assertIn("bandwidth_cap_bps", priv)
        public = filter_public_status(
            {
                "title": "RESTORE PRIVACY",
                "total_bytes_relayed": 999,
                "utilization": 0.5,
                "live": 5,
                "bandwidth_cap_bps": 1_000_000,
            }
        )
        self.assertEqual(public, {"title": "RESTORE PRIVACY"})
        self.assertEqual(assert_public_status_minimal(public), [])
        self.assertTrue(public_status_must_not_include_capacity(public))

    def test_sessions_private_payload_includes_bytes(self):
        from node.aggregate_metrics import process_counters, reset_process_counters_for_tests
        from node.sessions import SessionRegistry

        reset_process_counters_for_tests()
        process_counters().record_inbound(1000)
        process_counters().record_outbound(2000)
        reg = SessionRegistry()
        payload = reg.private_capacity_payload(host="test.local")
        self.assertEqual(payload.get("total_bytes_in"), 1000)
        self.assertEqual(payload.get("total_bytes_out"), 2000)
        self.assertEqual(payload.get("total_bytes_relayed"), 3000)
        self.assertTrue(payload.get("private"))


if __name__ == "__main__":
    unittest.main()
