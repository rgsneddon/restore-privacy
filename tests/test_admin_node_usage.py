"""Admin fleet node usage panel: bandwidth used vs capacity; public-safe."""

from __future__ import annotations

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
            format_bandwidth_cap,
        )

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
        self.assertEqual(format_bandwidth_cap(None, code="IS"), "unlimited")
        self.assertEqual(format_bandwidth_cap(None, code="DE"), "unlimited")
        self.assertEqual(
            format_bandwidth_cap(200_000_000, code="US"), "200.00 Mbps"
        )


class TestProductPerPeerCaps(unittest.TestCase):
    """DE > IS/US sessions; IS/DE bandwidth unlimited-class; US fixed 200 Mbps."""

    def test_session_soft_max_de_dedicated_above_is_us(self):
        from admin_node_usage import resolve_session_soft_max
        from node.private_capacity import (
            DEFAULT_MAX_SESSIONS_DE,
            DEFAULT_MAX_SESSIONS_IS,
            DEFAULT_MAX_SESSIONS_US,
            default_max_sessions,
            product_session_soft_max,
        )

        env = {}
        is_cap = resolve_session_soft_max(code="IS", host="82.221.101.241", env=env)
        de_cap = resolve_session_soft_max(code="DE", host="178.105.187.178", env=env)
        us_cap = resolve_session_soft_max(code="US", host="5.161.242.85", env=env)
        self.assertEqual(de_cap, DEFAULT_MAX_SESSIONS_DE)
        self.assertEqual(is_cap, DEFAULT_MAX_SESSIONS_IS)
        self.assertEqual(us_cap, DEFAULT_MAX_SESSIONS_US)
        self.assertGreater(de_cap, is_cap)
        self.assertEqual(product_session_soft_max(code="IS"), is_cap)
        self.assertEqual(product_session_soft_max(code="DE"), de_cap)
        self.assertEqual(default_max_sessions({"RPT_NODE_PEER_CODE": "IS"}), is_cap)
        self.assertEqual(default_max_sessions({"RPT_NODE_PEER_CODE": "DE"}), de_cap)

    def test_is_de_bandwidth_unlimited_class_us_fixed(self):
        from admin_node_usage import resolve_bandwidth_cap_bps, format_bandwidth_cap
        from node.private_capacity import (
            product_bandwidth_cap_bps,
            product_bandwidth_unlimited,
        )

        env = {}
        self.assertTrue(product_bandwidth_unlimited(code="IS"))
        self.assertTrue(product_bandwidth_unlimited(code="DE"))
        self.assertFalse(product_bandwidth_unlimited(code="US"))
        self.assertIsNone(
            resolve_bandwidth_cap_bps(code="IS", host="82.221.101.241", env=env)
        )
        self.assertIsNone(
            resolve_bandwidth_cap_bps(code="DE", host="178.105.187.178", env=env)
        )
        self.assertEqual(
            resolve_bandwidth_cap_bps(code="US", host="5.161.242.85", env=env),
            200_000_000,
        )
        self.assertIsNone(product_bandwidth_cap_bps(code="IS"))
        self.assertIsNone(product_bandwidth_cap_bps(code="DE"))
        self.assertEqual(product_bandwidth_cap_bps(code="US"), 200_000_000)
        # Must not treat flat 100 Mbps as product truth for IS/DE
        self.assertNotEqual(
            resolve_bandwidth_cap_bps(code="IS", host="82.221.101.241", env=env),
            100_000_000,
        )
        self.assertEqual(format_bandwidth_cap(None, code="IS", host="82.221.101.241"), "unlimited")
        self.assertEqual(
            format_bandwidth_cap(None, code="DE", host="178.105.187.178"), "unlimited"
        )

    def test_fleet_rows_use_per_peer_caps(self):
        from admin_node_usage import build_fleet_usage_rows, product_catalog_peers

        peers = product_catalog_peers()
        self.assertEqual({p["code"] for p in peers}, {"DE"})
        probes = {
            "82.221.101.241": {
                "live": 10,
                "capacity": 256,
                "total_bytes_relayed": 8_000_000,
                "process_uptime_sec": 100,
                "bandwidth_cap_bps": 100_000_000,  # legacy node pin — ignored for IS
                "private": True,
            },
            "178.105.187.178": {
                "live": 5,
                "capacity": 1024,
                "bandwidth_cap_bps": 100_000_000,
                "private": True,
            },
        }
        rows = build_fleet_usage_rows(probes_by_host=probes, peers=peers, env={})
        by = {r.code: r for r in rows}
        self.assertEqual(set(by), {"DE"})
        self.assertEqual(by["DE"].sessions_cap, 1024)
        self.assertIsNone(by["DE"].bandwidth_cap_bps)


class TestFleetRows(unittest.TestCase):
    def test_rows_cover_catalog_is_de_only(self):
        from admin_node_usage import build_fleet_usage_rows, product_catalog_peers

        peers = product_catalog_peers()
        codes = {p["code"] for p in peers}
        self.assertEqual(codes, {"DE"})
        self.assertNotIn("IS", codes)
        self.assertNotIn("RO", codes)
        self.assertNotIn("US", codes)
        probes = {
            "82.221.101.241": {
                "live": 10,
                "capacity": 512,
                "total_bytes_relayed": 8_000_000,
                "process_uptime_sec": 100,
                "private": True,
                # Legacy fixed Mbps pin on node — must not override unlimited-class
                "bandwidth_cap_bps": 100_000_000,
            }
        }
        rows = build_fleet_usage_rows(
            probes_by_host=probes,
            peers=peers,
            env={},
        )
        by_code = {r.code: r for r in rows}
        self.assertEqual(set(by_code), {"DE"})
        self.assertIn(by_code["DE"].status, ("unknown", "error", "ok"))
        self.assertEqual(by_code["DE"].sessions_cap, 1024)
        self.assertIsNone(by_code["DE"].bandwidth_cap_bps)


class TestAdminHtmlSection(unittest.TestCase):
    def test_admin_html_is_de_unlimited_and_catalog_honesty(self):
        import admin_panel
        from admin_node_usage import (
            NodeUsageRow,
            build_fleet_usage_rows,
            format_bandwidth_cap,
            product_catalog_peers,
            render_admin_node_usage_section_html,
            resolve_session_soft_max,
        )

        # Real catalog path → only IS+DE rows from builder
        peers = product_catalog_peers()
        probes = {
            "82.221.101.241": {
                "live": 2,
                "capacity": 512,
                "total_bytes_relayed": 5_000_000,
                "process_uptime_sec": 40,
                "bandwidth_cap_bps": 100_000_000,  # ignored for unlimited-class
                "private": True,
            },
        }
        rows = build_fleet_usage_rows(probes_by_host=probes, peers=peers, env={})
        by = {r.code: r for r in rows}
        self.assertEqual(set(by), {"DE"})
        self.assertIsNone(by["DE"].bandwidth_cap_bps)
        self.assertEqual(by["DE"].sessions_cap, 1024)
        self.assertEqual(
            format_bandwidth_cap(by["DE"].bandwidth_cap_bps, code="DE", host=by["DE"].host),
            "unlimited",
        )
        self.assertEqual(
            resolve_session_soft_max(code="DE", host=by["DE"].host, env={}), 1024
        )

        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            try:
                # Fleet usage lives on /admin/fleet (multi-page admin shell)
                html = admin_panel.render_admin_fleet_page_html(
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
        # No long node-column why essay
        self.assertNotIn("admin-node-why", html)
        self.assertNotIn("admin-node-usage-limits-why", html)
        self.assertNotIn("admin-node-limit-bandwidth", html)
        self.assertNotIn("Bandwidth budget — operator", html)
        self.assertNotIn("Session soft max — soft", html)
        # Short node labels remain — live catalog only
        self.assertIn("Iceland", html)
        self.assertIn("Germany", html)
        self.assertNotIn("Romania", html)
        self.assertNotIn("United States", html)
        self.assertIn("unlimited", html)  # IS/DE capacity display
        self.assertIn('id="admin-node-bw-cap-IS">unlimited<', html)
        self.assertIn('id="admin-node-sess-IS">', html)
        self.assertIn("2/512", html)
        # Probe note: IS+DE honesty, not RO/US as live residual peers
        self.assertIn("admin-node-usage-probe-note", html)
        note = html[html.index("admin-node-usage-probe-note") : html.index("admin-node-usage-probe-note") + 800]
        self.assertIn("IS", note)
        self.assertIn("DE", note)
        self.assertIn("unlimited-class", note)
        self.assertIn("512", note)
        self.assertIn("1024", note)
        self.assertNotIn("IS / RO / US", note)
        self.assertIn("retired", note.lower())
        # Live refresh still present (script externalized for CSP)
        self.assertIn("data-fleet-refresh-ms", html)
        self.assertIn("/admin/api/fleet-usage", html)
        self.assertIn("/static/admin_fleet_usage.js", html)
        js = (ROOT / "status_page" / "static" / "admin_fleet_usage.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("setInterval", js)

        # Section-only render (same blurb / IS row)
        section = render_admin_node_usage_section_html(rows, live=False)
        self.assertIn('id="admin-node-bw-cap-IS">unlimited<', section)
        self.assertNotIn("IS / RO / US", section)
        self.assertNotIn("United States", section)

    def test_section_html_short_labels_only(self):
        from admin_node_usage import (
            NodeUsageRow,
            render_admin_node_usage_section_html,
        )

        rows = [
            NodeUsageRow(
                code="IS",
                name="Iceland",
                host="82.221.101.241",
                port=44044,
                bandwidth_used_bps=None,
                bandwidth_cap_bps=None,
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
        self.assertNotIn("admin-node-why", html)
        self.assertNotIn("operator product allowance", html.lower())
        self.assertIn("Iceland", html)
        self.assertIn("unlimited", html)
        self.assertIn("/static/admin_fleet_usage.js", html)
        js = (ROOT / "status_page" / "static" / "admin_fleet_usage.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("setInterval", js)


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
                bandwidth_cap_bps=None,
                bandwidth_util=None,
                bytes_relayed=1000,
                uptime_sec=10,
                sessions_live=3,
                sessions_cap=512,
                session_util=3 / 512,
                status="ok",
            ),
            NodeUsageRow(
                code="DE",
                name="Germany",
                host="178.105.187.178",
                port=44044,
                bandwidth_used_bps=2_000_000.0,
                bandwidth_cap_bps=None,
                bandwidth_util=None,
                bytes_relayed=2000,
                uptime_sec=10,
                sessions_live=6,
                sessions_cap=1024,
                session_util=6 / 1024,
                status="ok",
            ),
        ]
        payload = fleet_usage_json_payload(rows=rows, live=False)
        self.assertIn("refreshed_at", payload)
        self.assertGreater(payload["refresh_ms"], 0)
        by = {r["code"]: r for r in payload["rows"]}
        self.assertEqual(by["IS"]["sessions_cap"], 512)
        self.assertIsNone(by["IS"]["bandwidth_cap_bps"])
        self.assertEqual(by["IS"]["bandwidth_cap_display"], "unlimited")
        self.assertEqual(by["DE"]["sessions_cap"], 1024)
        self.assertIsNone(by["DE"]["bandwidth_cap_bps"])
        self.assertEqual(by["DE"]["bandwidth_cap_display"], "unlimited")

    def test_admin_api_route_requires_auth(self):
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/api/fleet-usage", src)
        self.assertIn("fleet_usage_json_payload", src)


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

    def test_is_de_us_private_payload_defaults(self):
        from node.private_capacity import build_private_capacity_payload

        p_us = build_private_capacity_payload(live=1, host="5.161.242.85", env={})
        self.assertEqual(p_us["capacity"], 512)
        self.assertEqual(p_us.get("bandwidth_cap_bps"), 200_000_000)
        p_is = build_private_capacity_payload(live=1, host="82.221.101.241", env={})
        self.assertEqual(p_is["capacity"], 512)
        self.assertNotIn("bandwidth_cap_bps", p_is)  # unlimited-class
        p_de = build_private_capacity_payload(live=1, host="178.105.187.178", env={})
        self.assertEqual(p_de["capacity"], 1024)
        self.assertNotIn("bandwidth_cap_bps", p_de)
        self.assertGreater(p_de["capacity"], p_is["capacity"])


class TestInstallScriptDefaults(unittest.TestCase):
    def test_install_script_documents_per_peer_defaults(self):
        text = (ROOT / "scripts" / "install_capacity_token_env.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("DEFAULT_MAX=512", text)
        self.assertIn("DEFAULT_MAX=1024", text)
        self.assertIn("DEFAULT_MAX=256", text)
        self.assertIn("unlimited-class", text)
        self.assertIn("200000000", text)
        self.assertIn("178.105.187.178) PEER_CODE=DE", text)
        # IS is not pinned to flat 100 Mbps default
        self.assertNotIn("IS|RO)\n    DEFAULT_MAX=256\n    DEFAULT_BW=100000000", text)


if __name__ == "__main__":
    unittest.main()
