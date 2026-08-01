"""Admin UPLOADS page: dedicated home for brand Helsinki package push."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminUploadsPage(unittest.TestCase):
    def test_uploads_page_and_nav(self) -> None:
        from admin_panel import (
            ADMIN_UPLOADS_PATH,
            render_admin_processors_page_html,
            render_admin_uploads_page_html,
        )

        self.assertEqual(ADMIN_UPLOADS_PATH, "/admin/uploads")
        page = render_admin_uploads_page_html().decode("utf-8")
        self.assertIn('id="admin-uploads"', page)
        self.assertIn("UPLOADS", page)
        self.assertIn('id="admin-suite-push-upload"', page)
        self.assertIn('id="admin-suite-push-form"', page)
        self.assertIn("/admin/uploads/push-suite", page)
        self.assertIn('data-brand-wide="1"', page)
        self.assertIn('id="admin-nav-uploads"', page)
        self.assertIn('href="/admin/uploads"', page)
        # Active sidebar marker when page is UPLOADS
        self.assertIn('class="sb-btn active" id="admin-nav-uploads"', page)

        proc = render_admin_processors_page_html().decode("utf-8")
        self.assertNotIn('id="admin-suite-push-upload"', proc)
        self.assertIn("admin-processors-uploads-link", proc)
        self.assertIn("/admin/uploads", proc)

    def test_uploads_inventory_is_brand_wide_repo_current(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        # Same default path the UPLOADS card uses (brand_wide=True).
        inv = ctrl.list_local_packages()
        self.assertTrue(inv.get("ok"), inv)
        self.assertGreaterEqual(int(inv.get("total") or 0), 5)
        kinds = set(inv.get("kinds") or [])
        self.assertIn("suite_client", kinds)
        self.assertTrue(
            kinds & {"rpos", "rpos_app", "browser", "node_installer", "node_operator"},
            kinds,
        )
        pkgs = inv.get("packages") or []
        self.assertTrue(any(p.get("kind") == "suite_client" for p in pkgs))
        self.assertTrue(
            any(p.get("kind") in ("rpos", "rpos_app") for p in pkgs),
            "UPLOADS inventory must include rpOS / free apps when present",
        )
        # Page markup reflects that inventory (filenames from live list).
        from admin_panel import render_admin_uploads_page_html

        html = render_admin_uploads_page_html().decode("utf-8")
        present = [p for p in pkgs if p.get("present")]
        self.assertGreaterEqual(len(present), 1)
        # At least one present basename appears in the table.
        self.assertTrue(
            any(str(p.get("filename") or "") in html for p in present[:5]),
            "UPLOADS table should list live release basenames",
        )

    def test_app_registers_uploads_routes(self) -> None:
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn('"/admin/uploads"', app_src)
        self.assertIn("/admin/uploads/push-suite", app_src)
        self.assertIn("/admin/uploads/push-suite/status", app_src)
        self.assertIn("/admin/uploads/upload-path", app_src)
        self.assertIn("render_admin_uploads_page_html", app_src)


if __name__ == "__main__":
    unittest.main()
