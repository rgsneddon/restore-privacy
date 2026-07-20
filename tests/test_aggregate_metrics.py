"""Aggregate-only monitoring: non-identifying counters; public status stays minimal."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

from node.aggregate_metrics import (  # noqa: E402
    ALLOWED_AGGREGATE_INTERNAL_KEYS,
    ALLOWED_PUBLIC_STATUS_KEYS,
    FORBIDDEN_PUBLIC_METRIC_KEYS,
    AggregateCounters,
    assert_metrics_non_identifying,
    assert_public_status_minimal,
    filter_public_status,
    is_allowed_aggregate_key,
    is_identifying_metric_key,
    process_counters,
    reset_process_counters_for_tests,
    sanitize_aggregate_snapshot,
)
from node.config import build_node_config, validate_node_config  # noqa: E402
from node.ui import public_status_from_payload  # noqa: E402
import app as status_app  # noqa: E402


class TestAggregatePolicy(unittest.TestCase):
    def test_total_bandwidth_is_allowed_aggregate(self):
        self.assertTrue(is_allowed_aggregate_key("total_bytes_in"))
        self.assertTrue(is_allowed_aggregate_key("total_bytes_out"))
        self.assertTrue(is_allowed_aggregate_key("total_bytes_relayed"))
        self.assertIn("total_bytes_relayed", ALLOWED_AGGREGATE_INTERNAL_KEYS)

    def test_per_client_keys_rejected(self):
        for key in (
            "bytes_per_client",
            "per_client_bandwidth",
            "client_id",
            "session_id",
            "by_client",
            "clients_connected",
            "client_ip",
        ):
            self.assertTrue(
                is_identifying_metric_key(key), f"expected identifying: {key}"
            )
        self.assertFalse(is_allowed_aggregate_key("bytes_per_client"))

    def test_assert_metrics_non_identifying(self):
        good = {
            "total_bytes_in": 100,
            "total_bytes_out": 50,
            "total_bytes_relayed": 150,
        }
        self.assertEqual(assert_metrics_non_identifying(good), [])
        bad = {
            "total_bytes_in": 1,
            "per_client": {"alice": 9},
            "clients_connected": 3,
        }
        viol = assert_metrics_non_identifying(bad)
        self.assertTrue(any("per_client" in v or "identifying" in v for v in viol))
        self.assertTrue(any("clients_connected" in v for v in viol))

    def test_nested_map_rejected(self):
        viol = assert_metrics_non_identifying(
            {"total_bytes_in": {"10.0.0.1": 5}}
        )
        self.assertTrue(any("map" in v for v in viol))

    def test_sanitize_keeps_only_aggregates(self):
        raw = {
            "total_bytes_in": 10,
            "clients_connected": 2,
            "client_id": "x",
            "total_bytes_out": 3,
            "junk": 1,
        }
        clean = sanitize_aggregate_snapshot(raw)
        self.assertEqual(set(clean.keys()) & set(FORBIDDEN_PUBLIC_METRIC_KEYS), set())
        self.assertEqual(clean["total_bytes_in"], 10)
        self.assertEqual(clean["total_bytes_out"], 3)
        self.assertNotIn("clients_connected", clean)
        self.assertNotIn("client_id", clean)


class TestAggregateCounters(unittest.TestCase):
    def test_process_wide_totals_no_client_keys(self):
        c = AggregateCounters()
        c.record_inbound(100)
        c.record_inbound(50)
        c.record_outbound(40)
        snap = c.snapshot()
        self.assertEqual(snap["total_bytes_in"], 150)
        self.assertEqual(snap["total_bytes_out"], 40)
        self.assertEqual(snap["total_bytes_relayed"], 190)
        self.assertEqual(assert_metrics_non_identifying(snap), [])
        # Public fragment must not leak aggregates onto the status page
        self.assertEqual(c.public_status_fragment(), {})
        self.assertEqual(filter_public_status({**snap, "title": "RESTORE PRIVACY"}), {
            "title": "RESTORE PRIVACY"
        })

    def test_process_counters_singleton_records(self):
        reset_process_counters_for_tests()
        process_counters().record_inbound(7)
        process_counters().record_outbound(3)
        snap = process_counters().snapshot()
        self.assertEqual(snap["total_bytes_in"], 7)
        self.assertEqual(snap["total_bytes_out"], 3)
        self.assertNotIn("client_id", snap)


class TestPublicStatusStripsInjectedPayloads(unittest.TestCase):
    def test_filter_public_status_strips_everything_but_title(self):
        dirty = {
            "title": "RESTORE PRIVACY",
            "clients_connected": 12,
            "sessions": [{"id": "a"}],
            "ip": "9.9.9.9",
            "total_bytes_relayed": 999999,
            "per_client": {"x": 1},
            "active_sessions": 4,
        }
        out = filter_public_status(dirty)
        self.assertEqual(out, {"title": "RESTORE PRIVACY"})
        self.assertEqual(assert_public_status_minimal(out), [])
        self.assertEqual(ALLOWED_PUBLIC_STATUS_KEYS, frozenset({"title"}))

    def test_status_page_normalize_strips_injected(self):
        out = status_app.normalize_status(
            {
                "title": "RESTORE PRIVACY",
                "clients_connected": 3,
                "total_bytes_in": 1000,
                "sessions": [1, 2],
                "client_ip": "1.2.3.4",
            }
        )
        self.assertEqual(out, {"title": "RESTORE PRIVACY"})
        pub = status_app.public_status_payload(
            {
                "title": "RESTORE PRIVACY",
                "total_bytes_relayed": 50,
                "clients": [{"id": "z"}],
            }
        )
        self.assertEqual(set(pub.keys()), {"title"})
        for k in status_app.FORBIDDEN_STATUS_KEYS:
            self.assertNotIn(k, pub)

    def test_node_ui_public_status_from_payload(self):
        out = public_status_from_payload(
            {
                "title": "RESTORE PRIVACY",
                "clients_connected": 9,
                "total_bytes_out": 100,
            }
        )
        self.assertEqual(out, {"title": "RESTORE PRIVACY"})

    def test_html_no_live_count(self):
        html = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        # Minimal public page: no live count chrome; downloads + legal links remain
        self.assertNotIn("clients_connected", html)
        self.assertNotIn("Currently connected", html)
        self.assertNotIn('id="clients-connected"', html)
        self.assertIn("Download client", html)
        self.assertIn("LICENCE", html)


class TestConfigNoPublicClientCount(unittest.TestCase):
    def test_product_default_show_client_count_false(self):
        cfg = build_node_config()
        ui = cfg["ui"]
        self.assertFalse(ui.get("show_client_count"))
        self.assertFalse(ui.get("show_client_identities"))
        self.assertFalse(ui.get("show_client_ips"))
        self.assertFalse(ui.get("publish_aggregate_metrics"))
        self.assertTrue(ui.get("aggregate_metrics_only"))
        self.assertEqual(validate_node_config(cfg), [])

    def test_validate_rejects_show_client_count_true(self):
        cfg = build_node_config()
        cfg["ui"]["show_client_count"] = True
        viol = validate_node_config(cfg)
        self.assertTrue(any("show_client_count" in v for v in viol))

    def test_nolog_flags_still_off(self):
        cfg = build_node_config()
        logging = cfg.get("logging") or {}
        self.assertFalse(logging.get("connection_log"))
        self.assertFalse(logging.get("session_log"))
        self.assertFalse(logging.get("user_info_log"))
        self.assertFalse(logging.get("traffic_log"))
        self.assertFalse(cfg.get("connection_log"))


if __name__ == "__main__":
    unittest.main()
