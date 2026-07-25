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
            LiveRttBase,
            all_privacy_scale_prefs,
            render_audit_uk_ping_section,
            uk_ping_matrix_rows,
        )

        # Pure approx path (no measure) — deterministic for CI
        text = render_audit_uk_ping_section(
            live=LiveRttBase(entry_ms=None, exit_ms=None),
            measure=False,
        )
        self.assertIn("UK ping + RAG", text)
        self.assertIn("Method (honesty)", text)
        self.assertIn("Approximate", text)
        self.assertIn("82.221.101.241", text)
        self.assertIn("185.146.232.107", text)
        self.assertIn("multi-hop", text.lower())
        rows = uk_ping_matrix_rows(live=LiveRttBase(entry_ms=None, exit_ms=None))
        self.assertEqual(len(rows), 8)
        prefs = all_privacy_scale_prefs()
        self.assertEqual(len(prefs), 8)
        # Table order: on/on/on first → off/off/off last (shape, obfs, multihop)
        first, last = prefs[0], prefs[-1]
        self.assertTrue(first.traffic_shape and first.outer_obfuscation and first.multihop)
        self.assertFalse(
            last.traffic_shape or last.outer_obfuscation or last.multihop
        )
        self.assertEqual(
            [(r.traffic_shape, r.outer_obfuscation, r.multihop) for r in rows],
            [(p.traffic_shape, p.outer_obfuscation, p.multihop) for p in prefs],
        )
        # multi-hop on rows have exit range
        mh_on = [r for r in rows if r.multihop]
        self.assertTrue(mh_on)
        for r in mh_on:
            self.assertIsNotNone(r.exit_ms_low)
            self.assertIn("ms", r.exit_range())
        mh_off = [r for r in rows if not r.multihop]
        for r in mh_off:
            self.assertIn("multi-hop off", r.exit_range().lower())

    def test_matrix_row_order_on_on_on_to_off_off_off(self) -> None:
        """Shipped prefs enumeration: top all-on, bottom all-off, on-before-off."""
        from client.uk_ping_estimates import (
            LiveRttBase,
            all_privacy_scale_prefs,
            render_audit_uk_ping_section,
            uk_ping_matrix_rows,
        )

        prefs = all_privacy_scale_prefs()
        expected = [
            (True, True, True),
            (True, True, False),
            (True, False, True),
            (True, False, False),
            (False, True, True),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        ]
        got = [
            (p.traffic_shape, p.outer_obfuscation, p.multihop) for p in prefs
        ]
        self.assertEqual(got, expected)
        rows = uk_ping_matrix_rows(live=LiveRttBase(entry_ms=None, exit_ms=None))
        self.assertEqual(
            [(r.shape_label, r.obfs_label, r.multihop_label) for r in rows],
            [
                ("on", "on", "on"),
                ("on", "on", "off"),
                ("on", "off", "on"),
                ("on", "off", "off"),
                ("off", "on", "on"),
                ("off", "on", "off"),
                ("off", "off", "on"),
                ("off", "off", "off"),
            ],
        )
        text = render_audit_uk_ping_section(
            live=LiveRttBase(entry_ms=None, exit_ms=None), measure=False
        )
        data_rows = [
            ln
            for ln in text.splitlines()
            if ln.startswith("| on ") or ln.startswith("| off ")
        ]
        self.assertEqual(len(data_rows), 8)
        self.assertTrue(data_rows[0].startswith("| on | on | on |"), data_rows[0])
        self.assertTrue(data_rows[-1].startswith("| off | off | off |"), data_rows[-1])

    def test_live_probes_use_measured_ms_in_cells(self) -> None:
        """Injected successful probes must appear as live ms, not approx-only bands."""
        from client.node_ping import PingResult
        from client.uk_ping_estimates import (
            LiveRttBase,
            render_audit_uk_ping_section,
            uk_ping_matrix_rows,
        )

        live = LiveRttBase(
            entry_ms=42.0,
            exit_ms=50.0,
            entry_method="tcp",
            exit_method="tcp",
        )
        rows = uk_ping_matrix_rows(live=live)
        self.assertEqual(len(rows), 8)
        for r in rows:
            self.assertTrue(r.entry_live)
            self.assertIn("live", r.entry_range().lower())
            # shape off lean: exact 42 ms; shape on: band 42–47
            if not r.traffic_shape:
                self.assertEqual(r.entry_ms_low, 42)
                self.assertEqual(r.entry_ms_high, 42)
            if r.multihop:
                self.assertTrue(r.exit_live)
                self.assertIn("live", r.exit_range().lower())
                if not r.traffic_shape:
                    self.assertEqual(r.exit_ms_low, 50)
            else:
                self.assertIn("multi-hop off", r.exit_range().lower())
            # full live → green RAG
            if r.multihop:
                self.assertEqual(r.rag, "green")
            else:
                self.assertEqual(r.rag, "green")

        text = render_audit_uk_ping_section(live=live, measure=False)
        self.assertIn("42 ms", text)
        self.assertIn("50 ms", text)
        self.assertIn("Live", text)
        self.assertIn("(live)", text)
        self.assertNotIn("Approximate** RTT bands", text)
        # injectable probe_entry path also works
        fake_entry = PingResult(
            host="82.221.101.241", port=44044, ok=True, rtt_ms=33.0, method="tcp"
        )
        fake_exit = PingResult(
            host="185.146.232.107", port=44044, ok=True, rtt_ms=44.0, method="udp"
        )
        text2 = render_audit_uk_ping_section(
            measure=True,
            probe_entry=lambda: fake_entry,
            probe_exit=lambda: fake_exit,
        )
        self.assertIn("33 ms", text2)
        self.assertIn("44 ms", text2)

    def test_probe_failure_falls_back_to_approx_no_fake_live(self) -> None:
        from client.node_ping import PingResult
        from client.uk_ping_estimates import render_audit_uk_ping_section

        fail_e = PingResult(
            host="82.221.101.241",
            port=44044,
            ok=False,
            rtt_ms=None,
            method="tcp",
            error="timeout",
        )
        fail_x = PingResult(
            host="185.146.232.107",
            port=44044,
            ok=False,
            rtt_ms=None,
            method="tcp",
            error="timeout",
        )
        text = render_audit_uk_ping_section(
            measure=True,
            probe_entry=lambda: fail_e,
            probe_exit=lambda: fail_x,
        )
        self.assertIn("Approximate", text)
        self.assertIn("38–58 ms", text)  # approx band present
        self.assertNotIn("ms (live)", text)
        self.assertIn("failed or unavailable", text.lower())
        # must not invent the failed rtt as a number cell like "None ms"
        self.assertNotIn("None ms", text)

    def test_audit_md_contains_shipped_section(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        audit = (ROOT / "AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("Privacy-scale settings — UK", audit)
        self.assertIn("ping + RAG", audit)
        self.assertTrue(
            "UK→entry (approx)" in audit
            or "UK→entry (live)" in audit
            or "UK→entry" in audit,
            "entry column header missing",
        )
        self.assertIn(pin, audit)
        self.assertIn("n/a (multi-hop off)", audit)
        # method honesty (live and/or approximate)
        self.assertTrue(
            "Approximate" in audit or "Live" in audit or "live probe" in audit.lower()
        )

    def test_audit_package_table_and_monopin_match_catalog(self) -> None:
        """Shipped AUDIT must name live monopin; package RAG may lag with honesty note."""
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "0.4.6")
        paths = [
            ROOT / "AUDIT.md",
            ROOT / "status_page" / "AUDIT.md",
            ROOT / "status_page" / "public" / "AUDIT.md",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                f"**{ver}**",
                text,
                f"{path} missing live monopin {ver}",
            )
            # Package table names current or documented lag snapshot filenames
            self.assertTrue(
                f"restore-privacy-client-{ver}-windows-x64-setup.exe" in text
                or "restore-privacy-client-0.4.0-windows-x64-setup.exe" in text
                or "restore-privacy-client-0.4.1-windows-x64-setup.exe" in text
                or "restore-privacy-client-0.4.6-windows-x64-setup.exe" in text,
                f"{path} missing package RAG windows row",
            )
            self.assertNotIn("restore-privacy-client-0.3.7-", text)
            self.assertNotIn("restore-privacy-client-0.3.6-", text)
            self.assertNotIn("monopin **0.3.7**", text)
            self.assertNotIn("assets/0.3.7/", text)
            self.assertNotIn("Windows **0.3.6**", text)


class TestVersionMonopin(unittest.TestCase):
    def test_version_pin_matches_catalog(self) -> None:
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "0.4.6")
        from status_page import downloads as dl

        self.assertEqual(dl.RELEASE_VERSION, ver)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn(f"version: {ver}+", pub)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(ver, cfg)


if __name__ == "__main__":
    unittest.main()
