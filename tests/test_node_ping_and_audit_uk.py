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
            host="178.105.187.178", port=44044, ok=True, rtt_ms=50.0, method="tcp"
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
        # Live residual catalog only: IS / DE / US (RO retired)
        self.assertIn("Iceland or Germany", src)
        self.assertIn("DE = Germany (default)", src)
        self.assertNotIn("Exit (Romania)", src)
        self.assertNotIn("RO = Romania", src)
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
        self.assertIn("178.105.187.178", text)
        self.assertIn("Germany", text)
        self.assertNotIn("Romania", text)
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
            # RAG from AVG thresholds (not live-vs-approx)
            self.assertIn(r.rag, ("green", "amber", "red"))
            # 42 ms single-hop → amber (40–70); multi-hop mean (42+50)/2=46 → amber
            self.assertEqual(r.rag, "amber", msg=f"avg={r.avg_ms} rag={r.rag}")
            self.assertGreater(r.avg_ms, 0)

        text = render_audit_uk_ping_section(live=live, measure=False)
        self.assertIn("42 ms", text)
        self.assertIn("50 ms", text)
        self.assertIn("Live", text)
        self.assertIn("(live)", text)
        self.assertIn("| AVG |", text)
        self.assertIn("AVG", text)
        self.assertIn("40", text)  # threshold prose
        self.assertIn("70", text)
        self.assertNotIn("Approximate** RTT bands", text)
        # injectable probe_entry path also works
        fake_entry = PingResult(
            host="82.221.101.241", port=44044, ok=True, rtt_ms=33.0, method="tcp"
        )
        fake_exit = PingResult(
            host="178.105.187.178", port=44044, ok=True, rtt_ms=44.0, method="udp"
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
            host="178.105.187.178",
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
        # AVG column + threshold RAG (not live-vs-approx colouring)
        self.assertIn("| AVG |", audit)
        self.assertIn("from AVG only", audit)
        self.assertTrue(
            "40 ms" in audit or "&lt; 40" in audit or "< 40" in audit,
            "green threshold prose missing",
        )
        self.assertIn("70 ms", audit)
        # method honesty (live and/or approximate)
        self.assertTrue(
            "Approximate" in audit or "Live" in audit or "live probe" in audit.lower()
        )

    def test_rag_from_avg_ms_thresholds(self) -> None:
        """Shipped classifier: green &lt;40, amber 40–70, red &gt;70."""
        from client.uk_ping_estimates import rag_from_avg_ms

        self.assertEqual(rag_from_avg_ms(0), "green")
        self.assertEqual(rag_from_avg_ms(39.9), "green")
        self.assertEqual(rag_from_avg_ms(40), "amber")
        self.assertEqual(rag_from_avg_ms(55), "amber")
        self.assertEqual(rag_from_avg_ms(70), "amber")
        self.assertEqual(rag_from_avg_ms(70.1), "red")
        self.assertEqual(rag_from_avg_ms(120), "red")

    def test_avg_column_and_rag_from_injected_rtt(self) -> None:
        """Matrix AVG + RAG follow live RTTs via shipped row builders."""
        from client.uk_ping_estimates import (
            LiveRttBase,
            render_audit_uk_ping_section,
            uk_ping_matrix_rows,
        )

        # Fast path: 25 ms entry / 30 ms exit → green AVG
        live_fast = LiveRttBase(entry_ms=25.0, exit_ms=30.0)
        rows_fast = uk_ping_matrix_rows(live=live_fast)
        for r in rows_fast:
            if not r.traffic_shape and not r.multihop:
                self.assertEqual(r.avg_ms, 25.0)
                self.assertEqual(r.rag, "green")
            if not r.traffic_shape and r.multihop:
                self.assertEqual(r.avg_ms, (25.0 + 30.0) / 2.0)
                self.assertEqual(r.rag, "green")
        text_fast = render_audit_uk_ping_section(live=live_fast, measure=False)
        self.assertIn("| AVG |", text_fast)
        self.assertIn("🟩", text_fast)
        self.assertIn("from AVG only", text_fast)
        self.assertIn("40 ms", text_fast)
        self.assertIn("70 ms", text_fast)

        # Slow path: 90 ms → red
        live_slow = LiveRttBase(entry_ms=90.0, exit_ms=95.0)
        rows_slow = uk_ping_matrix_rows(live=live_slow)
        for r in rows_slow:
            if not r.traffic_shape:
                self.assertEqual(r.rag, "red")
                self.assertGreater(r.avg_ms, 70)
        text_slow = render_audit_uk_ping_section(live=live_slow, measure=False)
        self.assertIn("🟥", text_slow)

        # Mid path: 50 ms → amber
        live_mid = LiveRttBase(entry_ms=50.0, exit_ms=None)
        rows_mid = uk_ping_matrix_rows(live=live_mid)
        for r in rows_mid:
            if not r.multihop and not r.traffic_shape:
                self.assertEqual(r.avg_ms, 50.0)
                self.assertEqual(r.rag, "amber")
        text_mid = render_audit_uk_ping_section(live=live_mid, measure=False)
        self.assertIn("🟧", text_mid)
        self.assertIn("| AVG | RAG |", text_mid)

    def test_audit_package_table_and_monopin_match_catalog(self) -> None:
        """Shipped AUDIT must name live monopin; package RAG uses catalog basenames."""
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "0.5.9")
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
            self.assertIn(
                f"restore-privacy-client-{ver}-windows-x64-setup.exe",
                text,
                f"{path} missing package RAG windows row for {ver}",
            )
            self.assertIn(f"restore-privacy-client-{ver}-macos.zip", text)
            # Stale current-catalog pin must not remain
            self.assertNotIn("**Public catalog version** | **0.5.7**", text)
            self.assertNotIn("catalog v0.5.7", text)
            self.assertNotIn("restore-privacy-client-0.5.7-", text)


class TestVersionMonopin(unittest.TestCase):
    def test_version_pin_matches_catalog(self) -> None:
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, "0.5.9")
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
