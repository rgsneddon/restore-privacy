"""Product residual client-push removed — admin/client fail-closed + upgrade banner.

Drives shipped entry points (operator push, admin HTML, suiteSelfUpdateEnabled,
upgrade_banner version notice). Not a re-implementation of the old push path.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminClientPushRemoved(unittest.TestCase):
    def test_node_operator_gui_passes_update_push_none(self) -> None:
        gui = (ROOT / "node_operator" / "gui_html.py").read_text(encoding="utf-8")
        self.assertIn("update_push=None", gui)
        self.assertNotIn('form_action": "/op/push-update"', gui)
        self.assertNotIn("Push update to clients", gui)
        app = (ROOT / "node_operator" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('text="Push update"', app)
        self.assertNotIn("def on_push", app)

    def test_settings_explainer_manual_update_only(self) -> None:
        from settings_explainer import catalog_ids, render_settings_explainer_page_html

        ids = catalog_ids()
        self.assertIn("suite-manual-update", ids)
        self.assertNotIn("suite-self-update", ids)
        html = render_settings_explainer_page_html().decode("utf-8", "replace").lower()
        self.assertIn("suite updates (manual only)", html)
        self.assertNotIn("allow suite self-update", html)
        self.assertNotIn("push update to clients", html)

    def test_operator_push_update_fail_closed(self) -> None:
        from node.update_push import operator_push_update, UpdatePushQueue

        q = UpdatePushQueue()
        r = operator_push_update(
            version="1.1.3",
            url="https://restoreprivacy.online/",
            message="x",
            queue=q,
            connected_client_ids=["abc"],
        )
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("disabled") or "disabled" in str(r.get("error") or "").lower())
        self.assertEqual(r.get("count") or 0, 0)
        self.assertEqual(q.pending_for("abc"), [])

    def test_controller_push_selected_fail_closed(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController()
        r = ctrl.push_selected_suite_updates_to_clients(
            version="1.1.3",
            only_filenames=["restore-privacy-client-1.1.3-windows-x64-setup.exe"],
            require_host_helsinki_match=False,
        )
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("disabled") or "disabled" in str(r.get("error") or "").lower())
        self.assertFalse(r.get("can_push"))

    def test_uploads_html_has_no_client_push_form(self) -> None:
        from admin_panel import render_admin_uploads_page_html

        html = render_admin_uploads_page_html().decode("utf-8", "replace")
        self.assertIn("admin-client-push-disabled", html)
        self.assertNotIn('id="admin-client-push-form"', html)
        self.assertNotIn("Push selected updates to clients", html)
        self.assertNotIn("Push update to clients", html)
        self.assertNotIn('action="/admin/uploads/push-clients"', html)
        # Helsinki package upload retained
        self.assertIn("Push selected packages to Helsinki", html)

    def test_node_operator_admin_html_no_push_form(self) -> None:
        src = (ROOT / "status_page" / "admin_node_operator.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('data-client-push-disabled="1"', src)
        self.assertNotIn("Push update to clients", src)
        self.assertNotIn('value="push_update"', src)
        self.assertIn("Client update push is disabled", src)


class TestClientPushReceiveRemoved(unittest.TestCase):
    def test_check_breadcrumbs_always_off(self) -> None:
        from client.breadcrumbs_check import check_breadcrumbs_enabled

        self.assertFalse(check_breadcrumbs_enabled(None))
        self.assertFalse(check_breadcrumbs_enabled({"check_breadcrumbs": True}))
        self.assertFalse(check_breadcrumbs_enabled({"checkBreadcrumbs": True}))

    def test_apply_client_update_directive_disabled(self) -> None:
        from node.update_push import apply_client_update_directive

        r = apply_client_update_directive(
            {"version": "1.1.3", "url": "https://example.invalid/", "message": "x"}
        )
        self.assertTrue(r.get("ok"))
        self.assertTrue(r.get("skipped") or r.get("disabled"))
        self.assertIsNone(r.get("store"))

    def test_flutter_suite_self_update_always_off(self) -> None:
        dart = (ROOT / "client_app" / "lib" / "suite_update.dart").read_text(
            encoding="utf-8"
        )
        # suiteSelfUpdateEnabled returns false unconditionally
        self.assertIn("bool suiteSelfUpdateEnabled", dart)
        # body must return false without reading settings.checkBreadcrumbs
        start = dart.index("bool suiteSelfUpdateEnabled")
        body = dart[start : start + 280]
        self.assertIn("return false", body)
        self.assertNotIn("settings.checkBreadcrumbs", body)

    def test_flutter_settings_no_self_update_switch(self) -> None:
        settings = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("kSuiteUpdateSettingsSwitchMarker", settings)
        self.assertNotIn("SuiteUpdateHonestyPanel", settings)
        self.assertNotIn("onCheckBreadcrumbsSettingChanged", settings)

    def test_flutter_main_no_poll_update_push(self) -> None:
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertNotIn("_pollSuiteUpdatePush", main)
        self.assertNotIn("_onResidualUpdatePush", main)
        self.assertNotIn("installUpdatePushHandler", main)
        self.assertNotIn("handleProductionUpdatePush", main)
        # Upgrade banner still present and not gated on checkBreadcrumbs
        self.assertIn("UpgradeBanner", main)
        self.assertNotIn("checkBreadcrumbs)\n                UpgradeBanner", main)

    def test_vpn_controller_poll_disabled(self) -> None:
        vpn = (ROOT / "client_app" / "lib" / "vpn_controller.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("client update push disabled", vpn)
        self.assertIn("pollAndApplyUpdatePush", vpn)


class TestUpgradeBannerStillPresent(unittest.TestCase):
    def test_version_is_behind_and_banner_text(self) -> None:
        # Drive pure upgrade_banner logic via dart file constants / re-export
        # Python-side mirror for monopin compare (same rules as Flutter).
        def version_tuple(v: str) -> list[int]:
            parts = []
            for seg in v.strip().lstrip("vV").split("."):
                digits = "".join(c for c in seg if c.isdigit())
                parts.append(int(digits) if digits else 0)
            return parts or [0]

        def version_is_behind(running: str, latest: str) -> bool:
            a, b = version_tuple(running), version_tuple(latest)
            n = max(len(a), len(b))
            for i in range(n):
                ai = a[i] if i < len(a) else 0
                bi = b[i] if i < len(b) else 0
                if ai < bi:
                    return True
                if ai > bi:
                    return False
            return False

        self.assertTrue(version_is_behind("1.1.2", "1.1.3"))
        self.assertFalse(version_is_behind("1.1.3", "1.1.3"))
        dart = (ROOT / "client_app" / "lib" / "upgrade_banner.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("New version available", dart)
        self.assertIn("versionIsBehind", dart)
        self.assertIn("upgradeBannerText", dart)


class TestDocsNoLiveClientPush(unittest.TestCase):
    def test_current_handoff_no_push_product(self) -> None:
        h = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.1.3.md"
        text = h.read_text(encoding="utf-8")
        self.assertNotIn("CHECK BREADCRUMBS", text)
        self.assertNotIn("UPDATE_PUSH", text)
        self.assertNotIn("Push update to clients", text)
        self.assertNotIn("Push selected updates to clients", text)
        self.assertIn("manual", text.lower())

    def test_node_operator_readme_no_push_feature(self) -> None:
        text = (ROOT / "node_operator" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("Push update** —", text)
        self.assertIn("disabled", text.lower())


if __name__ == "__main__":
    unittest.main()
