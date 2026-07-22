"""Node ping helper + AUDIT UK ping RAG section (shipped modules)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestNodePingHelper(unittest.TestCase):
    def test_probe_tcp_success_and_failure(self) -> None:
        from client.node_ping import PingResult, probe_tcp_rtt_ms

        with mock.patch("client.node_ping.socket.create_connection") as cc:
            # successful connect context manager
            cm = mock.MagicMock()
            cc.return_value = cm
            cm.__enter__.return_value = object()
            cm.__exit__.return_value = None
            r = probe_tcp_rtt_ms("127.0.0.1", 9, timeout_s=0.5)
            # may ok if mock works
            self.assertIsInstance(r, PingResult)
            self.assertEqual(r.method, "tcp")

        with mock.patch(
            "client.node_ping.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            r2 = probe_tcp_rtt_ms("127.0.0.1", 9, timeout_s=0.2)
            self.assertFalse(r2.ok)
            self.assertIsNone(r2.rtt_ms)
            self.assertIn("refused", r2.error.lower() or "refused")

    def test_measure_settings_pings_exit_only_when_multihop(self) -> None:
        from client.node_ping import PingResult, measure_settings_pings

        fake_entry = PingResult(
            host="82.221.101.241", port=44044, ok=True, rtt_ms=42.0, method="tcp"
        )
        fake_exit = PingResult(
            host="185.146.232.107", port=44044, ok=True, rtt_ms=50.0, method="tcp"
        )
        with mock.patch(
            "client.node_ping.probe_entry_rtt_ms", return_value=fake_entry
        ):
            with mock.patch(
                "client.node_ping.probe_exit_rtt_ms", return_value=fake_exit
            ) as ex:
                off = measure_settings_pings(multihop_enabled=False)
                self.assertEqual(off.entry_display(), "42 ms")
                self.assertIn("multi-hop off", off.exit_display().lower())
                ex.assert_not_called()

                on = measure_settings_pings(multihop_enabled=True)
                self.assertEqual(on.exit_display(), "50 ms")
                ex.assert_called_once()

    def test_settings_ui_has_ping_surface(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("measure_settings_pings", src)
        self.assertIn("Ping statistics", src)
        self.assertIn("Entry (Iceland)", src)
        self.assertIn("Exit (Romania)", src)
        self.assertIn("Measure ping now", src)


class TestAuditUkPingSection(unittest.TestCase):
    def test_render_section_has_matrix_and_method(self) -> None:
        from client.uk_ping_estimates import (
            all_privacy_scale_prefs,
            render_audit_uk_ping_section,
            uk_ping_matrix_rows,
        )

        text = render_audit_uk_ping_section()
        self.assertIn("UK approximate ping", text)
        self.assertIn("Method (honesty)", text)
        self.assertIn("Approximate", text)
        self.assertIn("82.221.101.241", text)
        self.assertIn("185.146.232.107", text)
        self.assertIn("multi-hop", text.lower())
        rows = uk_ping_matrix_rows()
        self.assertEqual(len(rows), 8)
        self.assertEqual(len(all_privacy_scale_prefs()), 8)
        # multi-hop on rows have exit range
        mh_on = [r for r in rows if r.multihop]
        self.assertTrue(mh_on)
        for r in mh_on:
            self.assertIsNotNone(r.exit_ms_low)
            self.assertIn("ms", r.exit_range())
        mh_off = [r for r in rows if not r.multihop]
        for r in mh_off:
            self.assertIn("multi-hop off", r.exit_range().lower())

    def test_audit_md_contains_shipped_section(self) -> None:
        audit = (ROOT / "AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("Privacy-scale settings — UK approximate ping + RAG", audit)
        self.assertIn("UK→entry (approx)", audit)
        self.assertIn("UK→exit (approx)", audit)
        self.assertIn("0.3.9", audit)
        self.assertIn("n/a (multi-hop off)", audit)
        # method honesty
        self.assertIn("Approximate", audit)
        self.assertIn("typical UK", audit)


class TestVersion039(unittest.TestCase):
    def test_version_pin_039(self) -> None:
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "0.3.9")
        from status_page import downloads as dl

        self.assertEqual(dl.RELEASE_VERSION, "0.3.9")
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 0.3.9+", pub)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("0.3.9", cfg)


if __name__ == "__main__":
    unittest.main()
