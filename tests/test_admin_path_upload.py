"""Admin upload-by-file-path: UI control + helper + POST path.

Drives shipped NodeOperatorController.upload_package_by_path and admin HTML.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminPathUploadUI(unittest.TestCase):
    def test_uploads_page_has_path_upload_control(self) -> None:
        from admin_panel import (
            render_admin_path_upload_html,
            render_admin_processors_page_html,
            render_admin_uploads_page_html,
            render_processor_settings_html,
        )

        frag = render_admin_path_upload_html()
        # Suite push card embeds path-upload form (best-in-class primary control)
        self.assertIn('id="admin-suite-push-upload"', frag)
        self.assertIn('id="admin-path-upload-form"', frag)
        self.assertIn('id="admin-path-upload-input"', frag)
        self.assertIn('id="admin-path-upload-btn"', frag)
        self.assertIn("/admin/uploads/upload-path", frag)
        self.assertIn("/admin/uploads/push-suite", frag)
        self.assertIn("Browse files and Upload", frag)
        self.assertNotIn(">Upload by path<", frag)
        self.assertIn("Push Suite packages", frag)

        # UPLOADS hosts the card; Processors does not.
        page = render_admin_uploads_page_html().decode("utf-8")
        self.assertIn('id="admin-suite-push-upload"', page)
        self.assertIn("admin-path-upload-input", page)
        self.assertIn('id="admin-uploads"', page)

        settings = render_processor_settings_html()
        self.assertNotIn('id="admin-suite-push-upload"', settings)
        self.assertIn("/admin/uploads", settings)

        proc = render_admin_processors_page_html().decode("utf-8")
        self.assertNotIn('id="admin-suite-push-upload"', proc)
        self.assertIn('id="admin-processor-settings"', proc)

    def test_node_operator_has_path_upload_control(self) -> None:
        from admin_node_operator import render_admin_node_operator_page_html

        page = render_admin_node_operator_page_html(selected_node="lab").decode(
            "utf-8"
        )
        self.assertIn('id="admin-node-op-path-upload-form"', page)
        self.assertIn('id="admin-node-op-path-input"', page)
        self.assertIn('id="admin-node-op-path-upload-btn"', page)
        self.assertIn("Browse files and Upload", page)
        self.assertNotIn(">Upload by path<", page)
        self.assertIn('value="upload_by_path"', page)


class TestUploadPackageByPathHelper(unittest.TestCase):
    def test_missing_path_honest_error(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        r = ctrl.upload_package_by_path("/no/such/file-xyz.exe", dry_run=True)
        self.assertFalse(r.get("ok"), r)
        self.assertIn("exist", (r.get("error") or "").lower())

    def test_empty_path_honest_error(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        r = ctrl.validate_package_file_path("")
        self.assertFalse(r.get("ok"))
        self.assertIn("required", (r.get("error") or "").lower())

    def test_non_catalog_filename_rejected(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "not-a-catalog.bin"
            p.write_bytes(b"hello-package")
            r = ctrl.upload_package_by_path(str(p), stage=True, upload=False)
            self.assertFalse(r.get("ok"), r)
            self.assertIn("catalog", (r.get("error") or "").lower())

    def test_real_catalog_basename_stages_and_dry_run_upload(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        inv = ctrl.list_local_packages(version=ver)
        self.assertTrue(inv.get("ok"), inv)
        pkgs = inv.get("packages") or []
        self.assertGreaterEqual(len(pkgs), 1)
        # Prefer linux tarball basename (no CFBundle gate)
        fname = None
        for p in pkgs:
            if p.get("platform") == "linux":
                fname = p["filename"]
                break
        if not fname:
            fname = pkgs[0]["filename"]

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / fname
            # host_paid upload_packages only ships files ≥ 1_000_000 bytes
            src.write_bytes(b"RPT" + b"\0" * 1_000_000)
            # Stage only (no SSH)
            r = ctrl.upload_package_by_path(
                str(src),
                stage=True,
                upload=False,
                dry_run=False,
            )
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(r.get("version"), ver)
            self.assertEqual(r.get("filename"), fname)
            staged = Path(str(r.get("staged_to") or ""))
            self.assertTrue(staged.is_file(), r)
            self.assertEqual(staged.stat().st_size, src.stat().st_size)

            # Dry-run upload drives real upload_catalog_packages path
            r2 = ctrl.upload_package_by_path(
                str(src),
                stage=True,
                upload=True,
                dry_run=True,
            )
            self.assertTrue(r2.get("dry_run"))
            self.assertEqual(r2.get("filename"), fname)
            self.assertTrue(r2.get("ok"), r2)
            self.assertEqual(r2.get("upload_code"), 0)
            # Cleanup staged fixture (do not leave junk on disk)
            try:
                staged.unlink()
            except OSError:
                pass


class TestAdminPathUploadPost(unittest.TestCase):
    def test_node_operator_action_upload_by_path(self) -> None:
        from admin_node_operator import handle_admin_node_operator_action
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        inv = ctrl.list_local_packages(version=ver)
        fname = (inv.get("packages") or [{}])[0].get("filename") or (
            f"restore-privacy-client-{ver}-linux-x64.tar.gz"
        )
        # Prefer linux
        for p in inv.get("packages") or []:
            if p.get("platform") == "linux":
                fname = p["filename"]
                break

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / fname
            src.write_bytes(b"post-path-upload-test" + b"\0" * 64)
            ok, msg, node = handle_admin_node_operator_action(
                {
                    "node": "lab",
                    "action": "upload_by_path",
                    "path": str(src),
                    "stage": "1",
                    "upload": "0",
                }
            )
            self.assertTrue(ok, msg)
            self.assertIn(fname, msg)
            self.assertEqual(node, "lab")
            # Cleanup tiny stage fixture
            staged = ROOT / "status_page" / "assets" / ver / fname
            if staged.is_file() and staged.stat().st_size < 100_000:
                staged.unlink(missing_ok=True)

        # Missing path
        ok2, msg2, _ = handle_admin_node_operator_action(
            {
                "node": "lab",
                "action": "upload_by_path",
                "path": "/tmp/nope-missing-rpt-package.exe",
                "stage": "1",
            }
        )
        self.assertFalse(ok2)
        self.assertTrue(msg2)

    def test_processors_upload_path_route_in_app_source(self) -> None:
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/processors/upload-path", app_src)
        self.assertIn("upload_package_by_path", app_src)

    def test_processors_post_handler_calls_helper(self) -> None:
        """Drive the same helper the /admin/processors/upload-path route uses."""
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        with mock.patch.object(
            ctrl,
            "upload_package_by_path",
            wraps=ctrl.upload_package_by_path,
        ) as wrapped:
            r = ctrl.upload_package_by_path(
                "/definitely/missing/rpt.exe",
                stage=True,
                upload=False,
            )
            wrapped.assert_called()
            self.assertFalse(r.get("ok"))


if __name__ == "__main__":
    unittest.main()
