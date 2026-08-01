"""Ned · rpAI growth on ChronoFlux confirmed blocks + secondary signals.

Drives shipped admin_rps / admin_chronoflux entry points with a temp stats store.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


class TestChronoFluxBlockGrowth(unittest.TestCase):
    def test_apply_confirmed_block_increases_growth_pure(self) -> None:
        from admin_rps import (
            BLOCK_GROWTH_POINTS,
            apply_confirmed_block_growth,
            capability_tier_for_score,
        )

        base = {
            "growth_score": 0,
            "chronoflux_blocks_grown": 0,
            "learning_epochs": 0,
            "last_chronoflux_height": -1,
            "grown_fingerprints": [],
        }
        g1 = apply_confirmed_block_growth(
            base,
            height=0,
            fingerprint="fp_aaa",
            action_kind="mint_keygen",
            label="Admin: Mint Keygen",
        )
        self.assertTrue(g1["grew"])
        self.assertEqual(g1["chronoflux_blocks_grown"], 1)
        self.assertEqual(g1["growth_score"], BLOCK_GROWTH_POINTS)
        self.assertEqual(g1["learning_epochs"], 1)
        self.assertEqual(g1["last_chronoflux_height"], 0)
        self.assertIn("fp_aaa", g1["grown_fingerprints"])
        self.assertEqual(
            g1["capability_tier"],
            capability_tier_for_score(g1["growth_score"]),
        )

        # Same fingerprint is idempotent
        g2 = apply_confirmed_block_growth(
            g1, height=0, fingerprint="fp_aaa", action_kind="mint_keygen"
        )
        self.assertFalse(g2["grew"])
        self.assertEqual(g2["chronoflux_blocks_grown"], 1)
        self.assertEqual(g2["growth_score"], BLOCK_GROWTH_POINTS)

        # New block grows further
        g3 = apply_confirmed_block_growth(
            g2, height=1, fingerprint="fp_bbb", action_kind="push_suite_packages"
        )
        self.assertTrue(g3["grew"])
        self.assertEqual(g3["chronoflux_blocks_grown"], 2)
        self.assertEqual(g3["growth_score"], BLOCK_GROWTH_POINTS * 2)
        self.assertEqual(g3["last_chronoflux_height"], 1)

    def test_progress_admin_action_records_ned_growth(self) -> None:
        """Real ChronoFlux seal path must raise Ned growth score."""
        from admin_chronoflux import progress_admin_action
        from admin_rps import load_rps_stats

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ledger = td_path / "ledger.json"
            stats = td_path / "rps_ned_stats.json"
            with mock.patch("admin_rps.rps_stats_path", return_value=stats):
                before = load_rps_stats(stats_path=stats)
                self.assertEqual(int(before.get("growth_score") or 0), 0)
                r1 = progress_admin_action(
                    action_kind="mint_keygen",
                    label="Admin: Mint Keygen",
                    path="/admin/mint-keygen",
                    ledger_path=ledger,
                    remote=False,
                )
                self.assertTrue(r1.get("ok"), r1)
                ned = r1.get("nedGrowth") or {}
                self.assertTrue(ned.get("ok"), ned)
                self.assertTrue(ned.get("grew"), ned)
                after = load_rps_stats(stats_path=stats)
                self.assertGreater(
                    int(after["growth_score"]), int(before.get("growth_score") or 0)
                )
                self.assertGreaterEqual(int(after["chronoflux_blocks_grown"]), 1)
                self.assertGreaterEqual(int(after["learning_epochs"]), 1)

                # Second seal grows again
                score1 = int(after["growth_score"])
                r2 = progress_admin_action(
                    action_kind="clear_licences",
                    label="Admin: Clear Licences",
                    path="/admin/clear-licences",
                    ledger_path=ledger,
                    remote=False,
                )
                self.assertTrue(r2.get("ok"), r2)
                after2 = load_rps_stats(stats_path=stats)
                self.assertGreater(int(after2["growth_score"]), score1)
                self.assertEqual(int(after2["chronoflux_blocks_grown"]), 2)

                # Admin surface HTML reflects real numbers
                from admin_rps import render_admin_rps_stats_html

                html = render_admin_rps_stats_html(after2)
                self.assertIn(f'data-growth-score="{after2["growth_score"]}"', html)
                self.assertIn(
                    f'data-chronoflux-blocks-grown="{after2["chronoflux_blocks_grown"]}"',
                    html,
                )
                self.assertIn("ChronoFlux blocks grown", html)
                self.assertIn(str(after2["growth_score"]), html)


class TestSecondaryGrowthSignals(unittest.TestCase):
    def test_heartbeat_increases_growth(self) -> None:
        from admin_rps import (
            HEARTBEAT_GROWTH_POINTS,
            load_rps_stats,
            record_rps_heartbeat,
        )

        with tempfile.TemporaryDirectory() as td:
            stats = Path(td) / "rps_ned_stats.json"
            before = load_rps_stats(stats_path=stats)
            after = record_rps_heartbeat(nodes_online=3, stats_path=stats)
            self.assertEqual(after["nodes_online"], 3)
            self.assertGreaterEqual(after["nodes_total_seen"], 3)
            self.assertEqual(
                int(after["growth_score"]),
                int(before.get("growth_score") or 0) + HEARTBEAT_GROWTH_POINTS,
            )
            self.assertGreater(int(after["learning_epochs"]), int(before.get("learning_epochs") or 0))
            # Second heartbeat still grows (nodes stay present)
            after2 = record_rps_heartbeat(nodes_online=3, stats_path=stats)
            self.assertGreater(int(after2["growth_score"]), int(after["growth_score"]))

    def test_narrative_session_increases_growth(self) -> None:
        from admin_rps import (
            NARRATIVE_GROWTH_POINTS,
            load_rps_stats,
            record_narrative_session,
        )

        with tempfile.TemporaryDirectory() as td:
            stats = Path(td) / "rps_ned_stats.json"
            before = load_rps_stats(stats_path=stats)
            after = record_narrative_session(stats_path=stats)
            self.assertEqual(
                int(after["narrative_sessions"]),
                int(before.get("narrative_sessions") or 0) + 1,
            )
            self.assertEqual(
                int(after["growth_score"]),
                int(before.get("growth_score") or 0) + NARRATIVE_GROWTH_POINTS,
            )

    def test_oobe_complete_hooks_narrative_growth(self) -> None:
        """Shipped mark_oobe_complete_on_prefix calls narrative growth when available."""
        sys.path.insert(0, str(ROOT / "rpos" / "installer"))
        from ned_oobe import mark_oobe_complete_on_prefix

        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "install"
            stats = Path(td) / "rps_ned_stats.json"
            with mock.patch("admin_rps.rps_stats_path", return_value=stats):
                # Ensure admin_rps importable under status_page path
                sys.path.insert(0, str(ROOT / "status_page"))
                data = mark_oobe_complete_on_prefix(
                    prefix,
                    {
                        "timezone": "Europe/London",
                        "language": "en",
                        "rpmail": {"address": "user@example.com", "bound": True},
                    },
                )
            # Growth may attach if import path works
            from admin_rps import load_rps_stats

            s = load_rps_stats(stats_path=stats)
            if data.get("ned_growth"):
                self.assertGreaterEqual(int(s.get("narrative_sessions") or 0), 1)
                self.assertGreater(int(s.get("growth_score") or 0), 0)
            # Structural: function source still calls record_narrative_session
            src = (ROOT / "rpos" / "installer" / "ned_oobe.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("record_narrative_session", src)


class TestGrowthSurfaces(unittest.TestCase):
    def test_public_snapshot_and_api_wiring(self) -> None:
        from admin_rps import (
            ned_growth_public_snapshot,
            record_chronoflux_block_growth,
            record_rps_heartbeat,
        )

        with tempfile.TemporaryDirectory() as td:
            stats = Path(td) / "rps_ned_stats.json"
            record_chronoflux_block_growth(
                height=5,
                fingerprint="snap_fp",
                action_kind="support_ticket_close",
                label="Admin: Support",
                stats_path=stats,
            )
            record_rps_heartbeat(nodes_online=2, stats_path=stats)
            from admin_rps import load_rps_stats

            snap = ned_growth_public_snapshot(load_rps_stats(stats_path=stats))
            self.assertGreater(snap["growth_score"], 0)
            self.assertGreaterEqual(snap["chronoflux_blocks_grown"], 1)
            self.assertIn("chronoflux_confirmed_block", snap["growth_methods"])
            self.assertIn("node_heartbeat", snap["growth_methods"])
            self.assertNotIn("grown_fingerprints", snap)

        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/api/ned-growth", app_src)
        self.assertIn("ned_growth_public_snapshot", app_src)
        self.assertIn("admin/rps/stats.json", app_src)

        # ChronoFlux seal path wired
        cf_src = (ROOT / "status_page" / "admin_chronoflux.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("record_chronoflux_block_growth", cf_src)
        self.assertIn("nedGrowth", cf_src)

        # Suite tab formatter present
        dart = (ROOT / "client_app" / "lib" / "suite_rpai_tab.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("formatGrowthSummary", dart)
        self.assertIn("chronoflux", dart.lower())
        self.assertIn("growth_score", dart)


if __name__ == "__main__":
    unittest.main()
