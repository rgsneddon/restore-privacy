"""Structural tests for Android UI insets + honest connect path (shipped sources)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"
LIB = APP / "lib"
KT = (
    APP
    / "android"
    / "app"
    / "src"
    / "main"
    / "kotlin"
    / "com"
    / "restoreprivacy"
    / "restore_privacy_client"
)


class TestAndroidUiInsets(unittest.TestCase):
    def test_main_uses_safe_area(self):
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        self.assertIn("SafeArea", main)
        self.assertIn("top: true", main)
        self.assertIn("bottom: true", main)
        self.assertIn("SystemUiMode.edgeToEdge", main)
        # Banner is inside SafeArea child tree
        safe_idx = main.index("SafeArea")
        banner_idx = main.index("kBannerTitle")
        self.assertLess(safe_idx, banner_idx)


class TestAndroidConnectPath(unittest.TestCase):
    def test_no_false_connected_on_service_start(self):
        main_act = (KT / "MainActivity.kt").read_text(encoding="utf-8")
        svc = (KT / "RptVpnService.kt").read_text(encoding="utf-8")
        # Must wait for ResultReceiver, not immediate ok:true after startService
        self.assertIn("ResultReceiver", main_act)
        self.assertIn("EXTRA_RECEIVER", main_act)
        self.assertIn("secretsPresent", main_act)
        self.assertIn("Missing admission secrets", main_act)
        self.assertIn("VPN permission denied", main_act)
        # Immediate success after startForegroundService is gone
        self.assertNotIn(
            '"Full VPN starting (RPT2 auto-connect)',
            main_act,
        )
        self.assertIn("report(", svc)
        self.assertIn("Missing admission secrets", svc)
        self.assertIn("handshake failed", svc.lower().replace("rpt ", ""))
        self.assertIn("RESULT_OK", svc)
        self.assertIn("RESULT_ERR", svc)

    def test_flutter_maps_status_honestly(self):
        ctrl = (LIB / "vpn_controller.dart").read_text(encoding="utf-8")
        status = (LIB / "connect_status.dart").read_text(encoding="utf-8")
        self.assertIn("isConnectSuccess", ctrl)
        self.assertIn("mapConnectStatusMessage", ctrl)
        self.assertIn("isConnectSuccess", status)
        self.assertIn("result['ok'] == true", status)
        self.assertIn("Missing admission secrets", status)

    def test_secrets_assets_gitignore_and_build_inject(self):
        gradle = (
            APP / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn("copyRptSecretsToAssets", gradle)
        self.assertIn("client_ed25519.priv", gradle)
        assets_gi = (
            APP / "android" / "app" / "src" / "main" / "assets" / "secrets" / ".gitignore"
        )
        self.assertTrue(assets_gi.is_file())
        gi = assets_gi.read_text(encoding="utf-8")
        self.assertIn("*.priv", gi)


if __name__ == "__main__":
    unittest.main()
