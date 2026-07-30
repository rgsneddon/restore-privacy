"""Structural + unit checks for idle-drain P0–P3 on shipped client paths."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestP0AndroidPrivacyScale(unittest.TestCase):
    def test_android_runtime_flags_default_lean_off(self):
        shape = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/RptTrafficShape.kt"
        ).read_text(encoding="utf-8")
        obfs = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/RptObfuscation.kt"
        ).read_text(encoding="utf-8")
        svc = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client/RptVpnService.kt"
        ).read_text(encoding="utf-8")
        # Runtime vars (not const true)
        self.assertIn("var productPadding: Boolean = false", shape)
        self.assertIn("var productCover: Boolean = false", shape)
        self.assertIn("fun applyPrivacyScale", shape)
        self.assertIn("var productObfsEnabled: Boolean = false", obfs)
        self.assertIn("EXTRA_TRAFFIC_SHAPE", svc)
        self.assertIn("RptTrafficShape.applyPrivacyScale", svc)
        self.assertIn("productCover", svc)
        # Cover interval sleep (not 200ms spin when shape on)
        self.assertIn("PRODUCT_COVER_INTERVAL_MS", svc)


class TestP1DataplaneIdleBackoff(unittest.TestCase):
    def test_dataplane_adaptive_select(self):
        src = (ROOT / "client/dataplane.py").read_text(encoding="utf-8")
        self.assertIn("idle_select_s", src)
        self.assertIn("idle_select_max_s", src)
        self.assertIn("last_activity", src)
        # Must not hard-spin only fixed 0.05 forever without backoff
        self.assertIn("quiet_s", src)

    def test_apple_cover_timer_matches_interval(self):
        for rel in (
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("repeating: interval", src)
            self.assertNotIn("repeating: 0.25", src)
            self.assertIn("productCover", src)

    def test_apple_session_crypto_reused(self):
        for rel in (
            "client_app/apple_shared/Rpt2/Sources/Rpt2/RptClientEngine.swift",
            "client_app/macos/NativePrep/Rpt2/RptClientEngine.swift",
            "client_app/ios/NativePrep/Rpt2/RptClientEngine.swift",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("sessionCrypto", src)
            self.assertIn("dataPlaneCrypto", src)
            self.assertIn("self.sessionCrypto = RptSessionCrypto", src)

    def test_nativeprep_still_embeds_traffic_shape_and_obfs(self):
        """Packet Tunnel NativePrep must compile without separate shape/obfs files."""
        for rel in (
            "client_app/macos/NativePrep/Rpt2/RptClientEngine.swift",
            "client_app/ios/NativePrep/Rpt2/RptClientEngine.swift",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("public enum RptTrafficShape", src)
            self.assertIn("public enum RptObfuscation", src)
            self.assertIn("productCoverIntervalS", src)
            self.assertIn("productObfsEnabled", src)


class TestP2ConnectedIdleHonesty(unittest.TestCase):
    def test_copy_present_python_and_dart(self):
        py = (ROOT / "client/transparency_copy.py").read_text(encoding="utf-8")
        dart = (ROOT / "client_app/lib/transparency_copy.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("CONNECTED_IDLE_POWER_HONESTY", py)
        self.assertIn("Disconnect when you do not need protection", py)
        self.assertIn("kConnectedIdlePowerHonesty", dart)
        self.assertIn("Disconnect when you do not need protection", dart)
        win = (ROOT / "client/windows/app.py").read_text(encoding="utf-8")
        self.assertIn("CONNECTED_IDLE_POWER_HONESTY", win)
        settings = (ROOT / "client_app/lib/settings_screen.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kConnectedIdlePowerHonesty", settings)


class TestProductPolicyCoverInterval(unittest.TestCase):
    def test_cover_interval_two_seconds(self):
        from client.product_policy import PRODUCT_ENABLED_TRAFFIC_SHAPE

        self.assertEqual(PRODUCT_ENABLED_TRAFFIC_SHAPE.cover_interval_s, 2.0)
        self.assertTrue(PRODUCT_ENABLED_TRAFFIC_SHAPE.cover_traffic)


if __name__ == "__main__":
    unittest.main()
