"""CHECK BREADCRUMBS Settings gate → breadcrumbs fetch → apply_client_update_directive.

Drives shipped client.breadcrumbs_check and client.update_receive (not a re-impl).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.breadcrumbs_check import (  # noqa: E402
    CHECK_BREADCRUMBS_LABEL,
    KEY_CHECK_BREADCRUMBS,
    apply_breadcrumbs_update,
    check_breadcrumbs_and_apply,
    check_breadcrumbs_enabled,
    load_local_breadcrumbs_manifest,
)
from client.windows import settings_store as win_ss  # noqa: E402
from client.linux import settings_store as lin_ss  # noqa: E402


class TestCheckBreadcrumbsLabelAndGate(unittest.TestCase):
    def test_label_exact(self) -> None:
        self.assertEqual(CHECK_BREADCRUMBS_LABEL, "CHECK BREADCRUMBS")
        self.assertEqual(KEY_CHECK_BREADCRUMBS, "check_breadcrumbs")
        # Flutter Settings surface carries the same literal label
        dart = (ROOT / "client_app" / "lib" / "settings_store.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("CHECK BREADCRUMBS", dart)
        screen = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kCheckBreadcrumbsLabel", screen)
        self.assertIn("_setCheckBreadcrumbs", screen)
        self.assertIn("CHECK BREADCRUMBS", (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8"))

    def test_enabled_false_when_off_or_missing(self) -> None:
        self.assertFalse(check_breadcrumbs_enabled(None))
        self.assertFalse(check_breadcrumbs_enabled({}))
        self.assertFalse(check_breadcrumbs_enabled({KEY_CHECK_BREADCRUMBS: False}))
        self.assertTrue(check_breadcrumbs_enabled({KEY_CHECK_BREADCRUMBS: True}))
        self.assertTrue(check_breadcrumbs_enabled({"checkBreadcrumbs": True}))

    def test_windows_linux_settings_persist_check_breadcrumbs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wpath = Path(td) / "win.json"
            s = win_ss.ProductSettings(check_breadcrumbs=True)
            win_ss.save_settings(s, path=wpath)
            loaded = win_ss.load_settings(path=wpath)
            self.assertTrue(loaded.check_breadcrumbs)
            raw = json.loads(wpath.read_text(encoding="utf-8"))
            self.assertTrue(raw.get(win_ss.KEY_CHECK_BREADCRUMBS))

            lpath = Path(td) / "lin.json"
            ls = lin_ss.ProductSettings(check_breadcrumbs=True)
            lin_ss.save_settings(ls, path=lpath)
            l2 = lin_ss.load_settings(path=lpath)
            self.assertTrue(l2.check_breadcrumbs)
            self.assertEqual(lin_ss.CHECK_BREADCRUMBS_LABEL, "CHECK BREADCRUMBS")


class TestBreadcrumbsApplyPath(unittest.TestCase):
    def test_off_skips_auto_update(self) -> None:
        man = {"schema": "rpt.breadcrumbs.v1", "monopin": "9.9.9"}
        r = apply_breadcrumbs_update(
            settings={KEY_CHECK_BREADCRUMBS: False},
            product_version="1.0.0",
            manifest=man,
        )
        self.assertTrue(r.get("ok"))
        self.assertTrue(r.get("skipped"))
        self.assertIn("off", (r.get("reason") or "").lower())
        self.assertIsNone(r.get("store"))
        self.assertEqual(r.get("label"), "CHECK BREADCRUMBS")

        r2 = check_breadcrumbs_and_apply(
            settings={KEY_CHECK_BREADCRUMBS: False},
            product_version="1.0.0",
            local_manifest_path=None,
        )
        self.assertTrue(r2.get("skipped"))
        self.assertEqual(r2.get("reason"), "CHECK BREADCRUMBS off")

    def test_on_applies_via_update_receive(self) -> None:
        man = {
            "schema": "rpt.breadcrumbs.v1",
            "monopin": "9.9.9",
            "source_of_truth": "helsinki_breadcrumbs_vault",
        }
        r = apply_breadcrumbs_update(
            settings={KEY_CHECK_BREADCRUMBS: True},
            product_version="1.0.0",
            manifest=man,
        )
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r.get("skipped"))
        store = r.get("store") or {}
        self.assertEqual(store.get("pending_update_version"), "9.9.9")
        self.assertIn("restoreprivacy.online", store.get("pending_update_url") or "")
        self.assertEqual(r.get("label"), "CHECK BREADCRUMBS")

    def test_on_same_version_skips(self) -> None:
        man = {"monopin": "1.0.0"}
        r = apply_breadcrumbs_update(
            settings={KEY_CHECK_BREADCRUMBS: True},
            product_version="1.0.0",
            manifest=man,
        )
        self.assertTrue(r.get("ok"))
        self.assertTrue(r.get("skipped"))
        self.assertIsNone(r.get("store"))

    def test_check_and_apply_local_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "rpt.breadcrumbs.v1",
                        "monopin": "2.0.0",
                        "source_of_truth": "helsinki_breadcrumbs_vault",
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_local_breadcrumbs_manifest(path)
            self.assertTrue(loaded.get("ok"), loaded)

            off = check_breadcrumbs_and_apply(
                settings={KEY_CHECK_BREADCRUMBS: False},
                product_version="1.0.0",
                local_manifest_path=path,
            )
            self.assertTrue(off.get("skipped"))
            self.assertIsNone(off.get("store"))

            on = check_breadcrumbs_and_apply(
                settings={KEY_CHECK_BREADCRUMBS: True},
                product_version="1.0.0",
                local_manifest_path=path,
            )
            self.assertTrue(on.get("ok"), on)
            self.assertFalse(on.get("skipped"))
            self.assertEqual(
                (on.get("store") or {}).get("pending_update_version"), "2.0.0"
            )

    def test_check_and_apply_transport_fixture(self) -> None:
        body = json.dumps({"monopin": "3.1.0", "schema": "rpt.breadcrumbs.v1"})

        def transport(url: str, headers: dict, timeout_s: float) -> str:
            self.assertIn("manifest", url)
            return body

        r = check_breadcrumbs_and_apply(
            settings={KEY_CHECK_BREADCRUMBS: True},
            product_version="1.0.0",
            transport=transport,
        )
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(
            (r.get("store") or {}).get("pending_update_version"), "3.1.0"
        )


class TestOperatorGuiPushDeploySurfaces(unittest.TestCase):
    """Regression: Helsinki upload control + clients×packages matrix remain on GUI."""

    def test_gui_has_upload_and_delivery_matrix(self) -> None:
        from node.operator_admin import NodeOperatorController
        from node_operator.gui_html import handle_operator_post, render_operator_page

        ctrl = NodeOperatorController(repo_root=ROOT)
        ctrl.start(mode="lab")
        try:
            ctrl.inject_lab_session()
            html = render_operator_page(ctrl)
        finally:
            ctrl.stop()
        self.assertIn("op-upload-packages-btn", html)
        self.assertIn("op-packages-table", html)
        self.assertIn("op-push-btn", html)
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(plat, html.lower())
        self.assertIn("data-peer-code=\"IS\"", html)
        self.assertIn("data-peer-code=\"DE\"", html)
        self.assertIn("op-delivery-matrix", html)
        self.assertIn("CHECK BREADCRUMBS", html)

        ver = ctrl.catalog_version_default()
        code, flash = handle_operator_post(
            ctrl,
            "/op/upload-packages",
            f"version={ver}&upload=1&dry_run=1&allow_missing=1".encode(),
        )
        self.assertIn(code, (200, 400))
        self.assertTrue(flash)


class TestProductionCallSitesWireBreadcrumbsCheck(unittest.TestCase):
    """Skeptic gap: CHECK BREADCRUMBS must invoke breadcrumbs_check at runtime."""

    def test_windows_settings_source_calls_on_check_breadcrumbs(self) -> None:
        win_app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("on_check_breadcrumbs_setting_changed", win_app)
        self.assertIn("from client.breadcrumbs_check import", win_app)
        self.assertIn("CHECK BREADCRUMBS", win_app)

    def test_linux_settings_source_calls_on_check_breadcrumbs(self) -> None:
        lin_app = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("on_check_breadcrumbs_setting_changed", lin_app)
        self.assertIn("from client.breadcrumbs_check import", lin_app)

    def test_connect_calls_run_check_after_hello(self) -> None:
        connect_src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertIn("_maybe_check_breadcrumbs_after_connect", connect_src)
        self.assertIn("run_check_breadcrumbs_for_product", connect_src)

    def test_flutter_settings_calls_on_check_breadcrumbs(self) -> None:
        screen = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("onCheckBreadcrumbsSettingChanged", screen)
        self.assertIn("breadcrumbs_check.dart", screen)
        dart = (ROOT / "client_app" / "lib" / "breadcrumbs_check.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("checkBreadcrumbsAndApply", dart)
        self.assertIn("CHECK BREADCRUMBS", dart)

    def test_on_setting_changed_production_entry_applies(self) -> None:
        """Drive shipped on_check_breadcrumbs_setting_changed (enable path)."""
        from client.breadcrumbs_check import on_check_breadcrumbs_setting_changed

        off = on_check_breadcrumbs_setting_changed(False)
        self.assertTrue(off.get("skipped"))
        self.assertIsNone(off.get("store"))

        body = json.dumps(
            {"schema": "rpt.breadcrumbs.v1", "monopin": "8.8.8"}
        )

        def transport(url: str, headers: dict, timeout_s: float) -> str:
            return body

        on = on_check_breadcrumbs_setting_changed(
            True,
            settings={"check_breadcrumbs": True},
            product_version="1.0.0",
            transport=transport,
        )
        self.assertTrue(on.get("ok"), on)
        self.assertFalse(on.get("skipped"))
        self.assertEqual(
            (on.get("store") or {}).get("pending_update_version"), "8.8.8"
        )

    def test_run_for_product_respects_settings_object(self) -> None:
        from client.breadcrumbs_check import run_check_breadcrumbs_for_product
        from client.windows.settings_store import ProductSettings

        s_off = ProductSettings(check_breadcrumbs=False)
        r = run_check_breadcrumbs_for_product(
            settings=s_off, product_version="1.0.0"
        )
        self.assertTrue(r.get("skipped"))

        s_on = ProductSettings(check_breadcrumbs=True)

        def transport(url: str, headers: dict, timeout_s: float) -> str:
            return json.dumps({"monopin": "7.7.7"})

        r2 = run_check_breadcrumbs_for_product(
            settings=s_on,
            product_version="1.0.0",
            transport=transport,
            platform="windows",
        )
        self.assertTrue(r2.get("ok"), r2)
        self.assertEqual(
            (r2.get("store") or {}).get("pending_update_version"), "7.7.7"
        )

    def test_rpt_client_method_invokes_breadcrumbs_check(self) -> None:
        """Exercise RptClient._maybe_check_breadcrumbs_after_connect (connect path)."""
        from unittest import mock

        from client.connect import RptClient

        ctrl = RptClient.__new__(RptClient)
        statuses: list[str] = []
        ctrl._status = statuses.append  # type: ignore[method-assign]

        with mock.patch(
            "client.breadcrumbs_check.run_check_breadcrumbs_for_product",
            return_value={
                "ok": True,
                "skipped": False,
                "store": {
                    "pending_update_version": "4.4.4",
                    "pending_update_url": "https://restoreprivacy.online/",
                },
                "monopin": "4.4.4",
            },
        ) as m:
            ctrl._maybe_check_breadcrumbs_after_connect()
            m.assert_called_once()
        self.assertTrue(any("4.4.4" in s for s in statuses), statuses)

        # Off / skipped must not raise or pollute hard
        statuses.clear()
        with mock.patch(
            "client.breadcrumbs_check.run_check_breadcrumbs_for_product",
            return_value={"ok": True, "skipped": True, "reason": "off"},
        ):
            ctrl._maybe_check_breadcrumbs_after_connect()
        self.assertEqual(statuses, [])


if __name__ == "__main__":
    unittest.main()
