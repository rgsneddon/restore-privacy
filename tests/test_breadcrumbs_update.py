"""CHECK BREADCRUMBS / residual push-receive removed — fail-closed product path."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestCheckBreadcrumbsGateDisabled(unittest.TestCase):
    def test_label_kept_as_historical_constant(self) -> None:
        from client.breadcrumbs_check import CHECK_BREADCRUMBS_LABEL

        # Label may remain as string for prefs migration; gate is always off.
        self.assertIsInstance(CHECK_BREADCRUMBS_LABEL, str)

    def test_enabled_always_false(self) -> None:
        from client.breadcrumbs_check import check_breadcrumbs_enabled

        self.assertFalse(check_breadcrumbs_enabled(None))
        self.assertFalse(check_breadcrumbs_enabled({"check_breadcrumbs": True}))
        self.assertFalse(check_breadcrumbs_enabled({"checkBreadcrumbs": True}))

        class S:
            check_breadcrumbs = True

        self.assertFalse(check_breadcrumbs_enabled(S()))


class TestBreadcrumbsApplyPathDisabled(unittest.TestCase):
    def test_check_and_apply_skips_when_disabled(self) -> None:
        from client.breadcrumbs_check import check_breadcrumbs_and_apply

        r = check_breadcrumbs_and_apply(
            settings={"check_breadcrumbs": True},
            product_version="1.0.0",
        )
        self.assertTrue(
            r.get("skipped")
            or r.get("store") is None
            or not r.get("ok")
        )
        reason = str(r.get("reason") or r.get("error") or "")
        self.assertTrue(
            "off" in reason.lower()
            or "disabled" in reason.lower()
            or "CHECK" in reason
            or r.get("skipped")
        )

    def test_run_for_product_skips(self) -> None:
        from client.breadcrumbs_check import run_check_breadcrumbs_for_product

        r = run_check_breadcrumbs_for_product(settings={"check_breadcrumbs": True})
        self.assertTrue(
            r.get("skipped")
            or r.get("store") is None
            or "off" in str(r.get("reason", "")).lower()
        )

    def test_on_setting_changed_does_not_store_pending(self) -> None:
        from client.breadcrumbs_check import on_check_breadcrumbs_setting_changed

        r = on_check_breadcrumbs_setting_changed(
            True,
            settings={"check_breadcrumbs": True},
            platform="macos",
        )
        self.assertIsNone(r.get("store"))


class TestProductionCallSitesNoPushReceive(unittest.TestCase):
    def test_flutter_settings_no_on_check_breadcrumbs(self) -> None:
        src = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("onCheckBreadcrumbsSettingChanged", src)
        self.assertNotIn("kSuiteUpdateSettingsSwitchMarker", src)

    def test_windows_settings_no_check_breadcrumbs_row(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('"CHECK BREADCRUMBS"', src)
        self.assertNotIn("on_check_breadcrumbs_setting_changed", src)

    def test_connect_no_live_breadcrumbs_after_connect(self) -> None:
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        # Method may exist but returns immediately
        self.assertIn("push-receive removed", src.lower() or src)
        # ensure early return before apply
        self.assertIn("return", src.split("_maybe_check_breadcrumbs_after_connect")[1][:200])


class TestOperatorGuiNoPushButton(unittest.TestCase):
    def test_gui_no_push_update_to_clients(self) -> None:
        src = (ROOT / "node_operator" / "gui_html.py").read_text(encoding="utf-8")
        self.assertNotIn("Push update to clients", src)
        self.assertIn("data-client-push-disabled", src)
        self.assertIn("/op/push-update", src)  # route may still 410
        self.assertIn("Client update push is disabled", src)


if __name__ == "__main__":
    unittest.main()
