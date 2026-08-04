"""Lean residual idle keep-alive vs node session prune (non-Windows)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestResidualKeepalivePolicy(unittest.TestCase):
    def test_interval_beats_node_idle(self) -> None:
        from client.residual_keepalive_policy import (
            RESIDUAL_KEEPALIVE_INTERVAL_SEC,
            residual_keepalive_beats_node_idle,
            residual_keepalive_interval_sec,
            residual_keepalive_is_lean,
        )
        from node.sessions import DEFAULT_SESSION_IDLE_SEC

        interval = residual_keepalive_interval_sec()
        self.assertEqual(interval, RESIDUAL_KEEPALIVE_INTERVAL_SEC)
        self.assertTrue(residual_keepalive_is_lean(interval))
        self.assertTrue(
            residual_keepalive_beats_node_idle(interval, DEFAULT_SESSION_IDLE_SEC)
        )
        self.assertLess(interval, DEFAULT_SESSION_IDLE_SEC)
        # Margin: not within 5s of prune
        self.assertLessEqual(interval, DEFAULT_SESSION_IDLE_SEC - 5.0)

    def test_requested_interval_clamped_under_node_idle(self) -> None:
        from client.residual_keepalive_policy import residual_keepalive_interval_sec
        from node.sessions import DEFAULT_SESSION_IDLE_SEC

        # Operator mistake: 90s would never beat 60s prune
        interval = residual_keepalive_interval_sec(90.0, node_idle_sec=DEFAULT_SESSION_IDLE_SEC)
        self.assertLess(interval, DEFAULT_SESSION_IDLE_SEC)
        self.assertGreaterEqual(interval, 5.0)

    def test_linux_dataplane_uses_policy(self) -> None:
        src = (ROOT / "client" / "dataplane.py").read_text(encoding="utf-8")
        self.assertIn("residual_keepalive_interval_sec", src)
        self.assertIn("send_keepalive", src)
        # Must not rely on cover_traffic for session liveness
        self.assertIn("Periodic KEEPALIVE", src)

    def test_android_has_keepalive_path(self) -> None:
        svc = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "RptVpnService.kt"
        ).read_text(encoding="utf-8")
        eng = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "RptClientEngine.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("KEEPALIVE_INTERVAL_MS", svc)
        self.assertIn("rpt-keepalive", svc)
        self.assertIn("sealAndWrapKeepalive", svc)
        self.assertIn("fun packKeepalive", eng)
        self.assertIn("0x04", eng)
        # Independent of cover: cover thread still separate
        self.assertIn("rpt-cover", svc)
        # Lean interval under 60s node idle (25s = 25000ms)
        self.assertIn("25_000", svc)

    def test_apple_keepalive_timer_contract(self) -> None:
        for rel in (
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("startKeepalive", src, msg=rel)
            self.assertIn("residualKeepaliveIntervalSec", src, msg=rel)
            self.assertIn("sendKeepalive", src, msg=rel)
            self.assertIn("self.running", src, msg=rel)
            # 25s lean period (not 60+ that would lose to node prune)
            self.assertRegex(
                src,
                r"residualKeepaliveIntervalSec:\s*TimeInterval\s*=\s*25",
                msg=rel,
            )
            # Cover is separate opt-in path
            self.assertIn("startCoverTraffic", src, msg=rel)
            self.assertIn("productCover", src, msg=rel)


if __name__ == "__main__":
    unittest.main()
