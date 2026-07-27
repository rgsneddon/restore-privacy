"""Admin fleet node usage panel: bandwidth used vs capacity; public-safe."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestProductPerPeerCaps(unittest.TestCase):
    """US session soft max is 2× IS and 2× RO; bandwidth 100/100/200 Mbps."""

    def test_session_soft_max_us_is_double_is_and_ro(self):
        from admin_node_usage import resolve_session_soft_max
        from node.private_capacity import (
            DEFAULT_MAX_SESSIONS,
            DEFAULT_MAX_SESSIONS_US,
            default_max_sessions,
            product_session_soft_max,
        )

        env = {}  # no overrides — pure product map
        is_cap = resolve_session_soft_max(code="IS", host="82.221.101.241", env=env)
        ro_cap = resolve_session_soft_max(code="RO", host="185.146.232.107", env=env)
        us_cap = resolve_session_soft_max(code="US", host="5.161.242.85", env=env)
        self.assertEqual(is_cap, ro_cap)
        self.assertEqual(is_cap, DEFAULT_MAX_SESSIONS)
        self.assertEqual(us_cap, DEFAULT_MAX_SESSIONS_US)
        self.assertEqual(us_cap, is_cap * 2)
        self.assertEqual(us_cap, ro_cap * 2)
        # Product helpers agree
        self.assertEqual(product_session_soft_max(code="US"), us_cap)
        self.assertEqual(product_session_soft_max(code="IS"), is_cap)
        # Node default_max_sessions with peer identity
        self.assertEqual(default_max_sessions({"RPT_NODE_PEER_CODE": "US"}), us_cap)
        self.assertEqual(default_max_sessions({"RPT_NODE_PEER_CODE": "IS"}), is_cap)
        self.assertEqual(default_max_sessions({"RPT_NODE_PEER_CODE": "RO"}), ro_cap)
        # Explicit env still wins
        self.assertEqual(
            default_max_sessions(
                {"RPT_NODE_PEER_CODE": "US", "RPT_NODE_MAX_SESSIONS": "100"}
            ),
            100,
        )

    def test_bandwidth_product_allowances_100_100_200(self):
        from admin_node_usage import resolve_bandwidth_cap_bps
        from node.private_capacity import product_bandwidth_cap_bps

        env = {}
        is_bps = resolve_bandwidth_cap_bps(
            code="IS", host="82.221.101.241", env=env
        )
        ro_bps = resolve_bandwidth_cap_bps(
            code="RO", host="185.146.232.107", env=env
        )
        us_bps = resolve_bandwidth_cap_bps(
            code="US", host="5.161.242.85", env=env
        )
        self.assertEqual(is_bps, 100_000_000)
        self.assertEqual(ro_bps, 100_000_000)
        self.assertEqual(us_bps, 200_000_000)
        self.assertEqual(us_bps, is_bps * 2)
        self.assertEqual(product_bandwidth_cap_bps(code="US"), us_bps)

    def test_fleet_rows_use_per_peer_session_caps(self):
        from admin_node_usage import build_fleet_usage_rows, product_catalog_peers

        peers = product_catalog_peers()
        probes = {
            "82.221.101.241": {
                "live": 10,
                "capacity": 256,  # node may still report flat 256
                "utilization": 10 / 256,
                "total_bytes_relayed": 8_000_000,
                "process_uptime_sec": 100,
                "private": True,
            },
            "185.146.232.107": {
                "live": 5,
                "capacity": 256,
                "private": True,
            },
            "5.161.242.85": {
                "live": 20,
                "capacity": 256,  # stale node env — admin still shows product 512
                "private": True,
            },
        }
        rows = build_fleet_usage_rows(probes_by_host=probes, peers=peers, env={})
        by = {r.code: r for r in rows}
        self.assertEqual(by["IS"].sessions_cap, 256)
        self.assertEqual(by["RO"].sessions_cap, 256)
        self.assertEqual(by["US"].sessions_cap, 512)
        self.assertEqual(by["US"].sessions_live, 20)
        # util vs product cap
        self.assertAlmostEqual(by["US"].session_util or 0, 20 / 512, delta=0.001)
        # US bandwidth product default applied when probe omits bandwidth_cap
        self.assertEqual(by["US"].bandwidth_cap_bps, 200_000_000)
        self.assertEqual(by["IS"].bandwidth_cap_bps, 100_000_000)


class TestFleetRows(unittest.TestCase):
    def test_rows_cover_catalog_is_ro_us(self):
        from admin_node_usage import build_fleet_usage_rows, product_catalog_peers

        peers = product_catalog_peers()
        codes = {p["code"] for p in peers}
        self.assertEqual(codes, {"IS", "RO", "US"})
        self.assertNotIn("DE", codes)
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
        self.assertIn("US", by_code)
        self.assertNotIn("DE", by_code)
        is_row = by_code["IS"]
        self.assertEqual(is_row.status, "ok")
        self.assertIsNotNone(is_row.bandwidth_used_bps)
        self.assertIsNotNone(is_row.bandwidth_cap_bps)
        self.assertIsNotNone(is_row.bandwidth_util)
        # RO/US unknown without probe
        self.assertIn(by_code["RO"].status, ("unknown", "error"))
        self.assertIn(by_code["US"].status, ("unknown", "error"))
        # Product session soft max still present when not probed
        self.assertEqual(by_code["US"].sessions_cap, 512)
        self.assertEqual(by_code["RO"].sessions_cap, 256)


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
                bandwidth_cap_bps=100_000_000,
                bandwidth_util=0.01,
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
                bandwidth_cap_bps=100_000_000,
                bandwidth_util=None,
                bytes_relayed=None,
                uptime_sec=None,
                sessions_live=None,
                sessions_cap=256,
                session_util=None,
                status="unknown",
                detail="not probed",
            ),
            NodeUsageRow(
                code="US",
                name="United States",
                host="5.161.242.85",
                port=44044,
                bandwidth_used_bps=2_000_000.0,
                bandwidth_cap_bps=200_000_000,
                bandwidth_util=0.01,
                bytes_relayed=9_000_000,
                uptime_sec=40,
                sessions_live=4,
                sessions_cap=512,
                session_util=4 / 512,
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
        for code in ("IS", "RO", "US"):
            self.assertIn(code, html)
            self.assertIn(f"admin-node-bw-used-{code}", html)
            self.assertIn(f"admin-node-bw-cap-{code}", html)
            self.assertIn(f"admin-node-sess-{code}", html)
        self.assertNotIn("admin-node-bw-used-DE", html)
        self.assertIn("Mbps", html)  # formatted used/cap
        # Public shop must not get this block from admin render alone is fine;
        # ensure section is admin-only marker
        self.assertIn("data-admin-node-usage", html)
        # Explains bandwidth vs sessions and per-peer difference
        self.assertIn("admin-node-usage-limits-why", html)
        self.assertIn("admin-node-limit-bandwidth", html)
        self.assertIn("admin-node-limit-sessions", html)
        self.assertIn("Bandwidth budget", html)
        self.assertIn("Session soft max", html)
        self.assertIn("not", html.lower())
        self.assertIn("hard", html.lower())  # not a hard admission lock
        self.assertIn("200", html)  # US Mbps
        self.assertIn("512", html)  # US sessions
        # Live refresh contract
        self.assertIn("data-fleet-refresh-ms", html)
        self.assertIn("data-fleet-usage-api", html)
        self.assertIn("/admin/api/fleet-usage", html)
        self.assertIn("setInterval", html)
        self.assertIn("fetch(", html)

    def test_section_html_copy_markers_directly(self):
        from admin_node_usage import (
            NodeUsageRow,
            render_admin_node_usage_section_html,
        )

        rows = [
            NodeUsageRow(
                code="US",
                name="United States",
                host="5.161.242.85",
                port=44044,
                bandwidth_used_bps=None,
                bandwidth_cap_bps=200_000_000,
                bandwidth_util=None,
                bytes_relayed=None,
                uptime_sec=None,
                sessions_live=None,
                sessions_cap=512,
                session_util=None,
                status="unknown",
            )
        ]
        html = render_admin_node_usage_section_html(rows, live=False)
        low = html.lower()
        self.assertIn("bandwidth budget", low)
        self.assertIn("session soft max", low)
        self.assertIn("per peer", low)
        # Must not claim a single hard 256 for every peer as only truth
        self.assertIn("512", html)
        self.assertIn("2×", html)
        self.assertNotIn("flat 256 for every peer", low)


class TestLiveRefreshContract(unittest.TestCase):
    def test_fleet_usage_json_payload_shape_and_interval(self):
        from admin_node_usage import (
            DEFAULT_FLEET_REFRESH_MS,
            NodeUsageRow,
            fleet_refresh_interval_ms,
            fleet_usage_json_payload,
        )

        self.assertGreater(DEFAULT_FLEET_REFRESH_MS, 0)
        self.assertGreaterEqual(fleet_refresh_interval_ms({}), 2000)
        rows = [
            NodeUsageRow(
                code="IS",
                name="Iceland",
                host="82.221.101.241",
                port=44044,
                bandwidth_used_bps=1_000_000.0,
                bandwidth_cap_bps=100_000_000,
                bandwidth_util=0.01,
                bytes_relayed=1000,
                uptime_sec=10,
                sessions_live=3,
                sessions_cap=256,
                session_util=3 / 256,
                status="ok",
            ),
            NodeUsageRow(
                code="US",
                name="United States",
                host="5.161.242.85",
                port=44044,
                bandwidth_used_bps=2_000_000.0,
                bandwidth_cap_bps=200_000_000,
                bandwidth_util=0.01,
                bytes_relayed=2000,
                uptime_sec=10,
                sessions_live=6,
                sessions_cap=512,
                session_util=6 / 512,
                status="ok",
            ),
        ]
        payload = fleet_usage_json_payload(rows=rows, live=False)
        self.assertIn("refreshed_at", payload)
        self.assertIn("refresh_ms", payload)
        self.assertGreater(payload["refresh_ms"], 0)
        self.assertIn("rows", payload)
        self.assertEqual(len(payload["rows"]), 2)
        by = {r["code"]: r for r in payload["rows"]}
        self.assertEqual(by["IS"]["sessions_cap"], 256)
        self.assertEqual(by["US"]["sessions_cap"], 512)
        self.assertEqual(by["US"]["bandwidth_cap_bps"], 200_000_000)
        self.assertIn("sessions_display", by["US"])
        self.assertIn("bandwidth_used_display", by["IS"])
        # Keys align with NodeUsageRow / UI updaters
        for key in (
            "bandwidth_used_bps",
            "bandwidth_cap_bps",
            "bandwidth_util",
            "sessions_live",
            "sessions_cap",
            "status",
        ):
            self.assertIn(key, by["IS"])

    def test_admin_api_route_requires_auth(self):
        """Shipped app.py registers authenticated fleet-usage JSON route."""
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/api/fleet-usage", src)
        self.assertIn("fleet_usage_json_payload", src)
        self.assertIn("is_authenticated", src)
        # Route sits with other admin handlers
        admin_at = src.find('path == "/admin"')
        fleet_at = src.find("/admin/api/fleet-usage")
        self.assertGreater(fleet_at, 0)
        self.assertGreater(fleet_at, admin_at - 5000)


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

    def test_us_private_payload_default_capacity_is_512(self):
        from node.private_capacity import build_private_capacity_payload

        p = build_private_capacity_payload(
            live=1,
            host="5.161.242.85",
            env={},  # no RPT_NODE_MAX_SESSIONS
        )
        self.assertEqual(p["capacity"], 512)
        p_is = build_private_capacity_payload(
            live=1,
            host="82.221.101.241",
            env={},
        )
        self.assertEqual(p_is["capacity"], 256)


class TestInstallScriptDefaults(unittest.TestCase):
    def test_install_script_documents_per_peer_defaults(self):
        text = (ROOT / "scripts" / "install_capacity_token_env.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("DEFAULT_MAX=512", text)
        self.assertIn("DEFAULT_MAX=256", text)
        self.assertIn("200000000", text)
        self.assertIn("100000000", text)
        self.assertIn("RPT_NODE_PEER_CODE", text)
        self.assertIn("5.161.242.85", text)


if __name__ == "__main__":
    unittest.main()
