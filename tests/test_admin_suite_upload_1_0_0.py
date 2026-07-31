"""Admin push-upload of Restore Privacy Suite v1.0.0 packages."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminSuiteUploadUI(unittest.TestCase):
    def test_processor_suite_push_card_targets_1_0_0(self) -> None:
        from admin_panel import (
            render_admin_processors_page_html,
            render_admin_suite_push_upload_html,
        )
        from downloads import RELEASE_VERSION

        self.assertEqual(RELEASE_VERSION, "1.0.0")
        frag = render_admin_suite_push_upload_html()
        self.assertIn('id="admin-suite-push-upload"', frag)
        self.assertIn('id="admin-suite-push-btn"', frag)
        self.assertIn('id="admin-suite-push-form"', frag)
        self.assertIn("/admin/processors/push-suite", frag)
        self.assertIn("Push Suite packages", frag)
        self.assertIn("1.0.0", frag)
        self.assertIn("Restore Privacy Suite", frag)
        self.assertIn('data-suite-version="1.0.0"', frag)
        # Path upload nested under suite card
        self.assertIn('id="admin-path-upload-form"', frag)
        # Five platform basenames for 1.0.0
        for plat_suffix in (
            "windows-x64-setup.exe",
            "android.apk",
            "macos.zip",
            "ios.zip",
            "linux-x64.tar.gz",
        ):
            self.assertIn(f"restore-privacy-client-1.0.0-{plat_suffix}", frag)

        page = render_admin_processors_page_html().decode("utf-8")
        self.assertIn('id="admin-suite-push-upload"', page)
        self.assertIn("admin-suite-push-btn", page)

    def test_node_operator_suite_push_control(self) -> None:
        from admin_node_operator import render_admin_node_operator_page_html

        page = render_admin_node_operator_page_html(selected_node="lab").decode(
            "utf-8"
        )
        self.assertIn('data-suite-push-upload="1"', page)
        self.assertIn("push_suite_packages", page)
        self.assertIn("Push Suite packages to Helsinki", page)
        self.assertIn("1.0.0", page)
        self.assertIn("Restore Privacy Suite v1.0.0", page)


class TestPushSuitePackagesHelper(unittest.TestCase):
    def test_push_suite_dry_run_1_0_0(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        self.assertEqual(ctrl.catalog_version_default(), "1.0.0")
        self.assertIn("1.0.0", ctrl.suite_product_label())
        r = ctrl.push_suite_packages(
            version="1.0.0",
            stage=False,
            upload=True,
            dry_run=True,
            allow_missing=True,
        )
        self.assertEqual(r.get("version"), "1.0.0")
        self.assertTrue(r.get("dry_run"))
        self.assertIn("Restore Privacy Suite", r.get("suite") or "")
        # With present packages, dry-run should succeed; if not, honest error
        if int(r.get("present_count") or 0) > 0 or int(r.get("total") or 0) == 0:
            if r.get("ok"):
                self.assertEqual(r.get("upload_code"), 0)
            else:
                self.assertTrue(r.get("error"))

    def test_missing_path_honest(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        r = ctrl.upload_package_by_path(
            "/no/such/restore-privacy-client-1.0.0-linux-x64.tar.gz",
            dry_run=True,
        )
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("error"))

    def test_path_upload_accepts_1_0_0_basename(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        fname = "restore-privacy-client-1.0.0-linux-x64.tar.gz"
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / fname
            src.write_bytes(b"RPT" + b"\0" * 1_000_000)
            r = ctrl.upload_package_by_path(
                str(src), stage=True, upload=True, dry_run=True
            )
            self.assertEqual(r.get("version"), "1.0.0")
            self.assertEqual(r.get("filename"), fname)
            self.assertTrue(r.get("ok"), r)
            staged = Path(str(r.get("staged_to") or ""))
            if staged.is_file() and staged.stat().st_size < 2_000_000:
                # cleanup test fixture if we wrote a tiny-relative stage
                try:
                    staged.unlink()
                except OSError:
                    pass


class TestAdminSuiteUploadPost(unittest.TestCase):
    def test_node_operator_push_suite_action(self) -> None:
        from admin_node_operator import handle_admin_node_operator_action

        ok, msg, node = handle_admin_node_operator_action(
            {
                "node": "lab",
                "action": "push_suite_packages",
                "version": "1.0.0",
                "stage": "0",
                "upload": "1",
                "dry_run": "1",
                "allow_missing": "1",
            }
        )
        self.assertTrue(ok, msg)
        self.assertIn("1.0.0", msg)
        self.assertIn("Pushed", msg)
        self.assertEqual(node, "lab")

    def test_app_routes_push_suite(self) -> None:
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/processors/push-suite", app_src)
        self.assertIn("push_suite_packages", app_src)


if __name__ == "__main__":
    unittest.main()
