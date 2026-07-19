"""Android aligned with Windows: manual Connect/Disconnect, stay-alive on minimize."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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


class TestAndroidConnectDisconnect(unittest.TestCase):
    def test_flutter_manual_connect_only(self):
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        cfg = (LIB / "rpt_config.dart").read_text(encoding="utf-8")
        ctrl = (LIB / "vpn_controller.dart").read_text(encoding="utf-8")
        self.assertIn("connectButtonLabel", main)
        self.assertIn("_onToggle", main)
        self.assertIn("_vpn.connect()", main)
        self.assertIn("_vpn.disconnect()", main)
        self.assertIn("autoConnectOnLaunch = false", cfg)
        self.assertIn("'autoConnect': false", ctrl)
        self.assertNotIn("autoConnectOnLaunch()", main)
        # dispose must not call disconnect API
        disp = main[main.index("void dispose") : main.index("void dispose") + 280]
        self.assertNotIn("_vpn.disconnect", disp)
        self.assertNotIn("disconnect()", disp)

    def test_lifecycle_must_not_stop_tunnel(self):
        status = (LIB / "connect_status.dart").read_text(encoding="utf-8")
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        self.assertIn("shouldStopTunnelOnAppLifecycle", status)
        self.assertIn("return false", status)
        self.assertIn("shouldStopTunnelOnAppLifecycle", main)
        self.assertIn("WidgetsBindingObserver", main)
        self.assertIn("_rehydrateSession", main)
        self.assertIn("querySession", main)
        # resume rehydrates; does not call disconnect on pause
        self.assertIn("AppLifecycleState.resumed", main)

    def test_native_activity_no_destroy_disconnect(self):
        act = (KT / "MainActivity.kt").read_text(encoding="utf-8")
        self.assertIn("onDestroy", act)
        on_destroy = act[act.index("onDestroy") : act.index("onDestroy") + 200]
        self.assertIn("super.onDestroy()", on_destroy)
        self.assertNotIn("sendDisconnect()", on_destroy)
        self.assertIn('"status"', act)
        self.assertIn("isSessionActive", act)
        self.assertIn("fullTunnelActive", act)

    def test_service_teardown_only_on_disconnect_or_revoke(self):
        svc = (KT / "RptVpnService.kt").read_text(encoding="utf-8")
        self.assertIn("ACTION_DISCONNECT", svc)
        self.assertIn("userStopped", svc)
        self.assertIn("desiredConnected", svc)
        self.assertIn("isSessionActive", svc)
        self.assertIn("START_STICKY", svc)
        self.assertIn("onRevoke", svc)
        # Notification stay-alive copy
        self.assertIn("minimize", svc.lower())
        self.assertIn("Privacy Restored", svc)


class TestAndroidUiAlignment(unittest.TestCase):
    def test_theme_matches_windows_product_direction(self):
        theme = (LIB / "theme.dart").read_text(encoding="utf-8")
        self.assertIn("0xFFF2F5F7", theme)  # chrome
        self.assertIn("0xFF2779AA", theme)  # primary
        self.assertIn("Restore Privacy", theme)
        self.assertIn("kLogoAsset", theme)
        self.assertIn("connectButtonLabel", theme)
        self.assertIn("plainConnectedStatus", theme)

    def test_main_ui_has_status_card_and_logo(self):
        main = (LIB / "main.dart").read_text(encoding="utf-8")
        self.assertIn("kLogoAsset", main)
        self.assertIn("plainConnectedStatus", main)
        self.assertIn("SafeArea", main)
        self.assertIn("top: true", main)
        self.assertIn("bottom: true", main)
        self.assertIn("ElevatedButton", main)
        self.assertIn("Brightness.light", main)


if __name__ == "__main__":
    unittest.main()
