"""Admin Node Operator page: nav, operable nodes, inventory/upload, title-only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestOperableNodes(unittest.TestCase):
    def test_list_includes_is_de_lab_and_package_store(self) -> None:
        from admin_node_operator import list_operable_nodes, resolve_operable_node

        nodes = list_operable_nodes()
        ids = {n["id"] for n in nodes}
        codes = {n.get("code") for n in nodes}
        self.assertIn("lab", ids)
        self.assertIn("IS", ids)
        self.assertIn("DE", ids)
        self.assertIn("helsinki-store", ids)
        self.assertIn("IS", codes)
        self.assertIn("DE", codes)
        for n in nodes:
            self.assertTrue(n.get("operable"))
        is_n = resolve_operable_node("IS")
        self.assertEqual(is_n["id"], "IS")
        self.assertEqual(is_n["kind"], "residual")
        self.assertEqual(is_n["host"], "82.221.101.241")
        de_n = resolve_operable_node("DE")
        self.assertEqual(de_n["code"], "DE")
        lab = resolve_operable_node("lab")
        self.assertEqual(lab["kind"], "lab")
        # default when empty prefers IS residual
        default = resolve_operable_node(None)
        self.assertEqual(default["id"], "IS")


class TestAdminNodeOperatorPage(unittest.TestCase):
    def test_sidebar_nav_and_page_render(self) -> None:
        from admin_node_operator import (
            ADMIN_NAV_NODE_OPERATOR_ID,
            ADMIN_NODE_OPERATOR_PATH,
            ADMIN_NODE_OPERATOR_POST_PATH,
            render_admin_node_operator_page_html,
        )
        from admin_panel import _admin_sidebar_html

        side = _admin_sidebar_html(active="node-operator")
        self.assertIn(f'id="{ADMIN_NAV_NODE_OPERATOR_ID}"', side)
        self.assertIn(f'href="{ADMIN_NODE_OPERATOR_PATH}"', side)
        self.assertIn("Node Operator", side)
        self.assertIn("active", side)
        bare = _admin_sidebar_html(active="home")
        self.assertIn(ADMIN_NAV_NODE_OPERATOR_ID, bare)
        self.assertIn(ADMIN_NODE_OPERATOR_PATH, bare)

        page = render_admin_node_operator_page_html(selected_node="IS").decode(
            "utf-8"
        )
        self.assertIn('id="admin-node-operator"', page)
        self.assertIn('id="admin-node-op-tabs"', page)
        self.assertIn('id="admin-node-tab-IS"', page)
        self.assertIn('id="admin-node-tab-DE"', page)
        self.assertIn('id="admin-node-tab-lab"', page)
        self.assertIn('id="admin-node-tab-helsinki-store"', page)
        self.assertIn('data-selected-node="IS"', page)
        self.assertIn("is-active", page)
        self.assertIn(ADMIN_NODE_OPERATOR_POST_PATH, page)
        # Project work surfaces — manual upload packages to host
        self.assertIn('id="admin-node-op-deploy-packages"', page)
        self.assertIn("Upload packages to host", page)
        self.assertIn('id="admin-node-op-upload-btn"', page)
        self.assertIn("Upload packages to Helsinki", page)
        self.assertIn('id="admin-node-op-packages-table"', page)
        self.assertIn("1.0.0", page)
        self.assertIn("windows", page.lower())
        self.assertIn("android", page.lower())
        self.assertIn("macos", page.lower())
        self.assertIn("linux", page.lower())
        self.assertIn('id="admin-node-op-priority-btn"', page)
        self.assertIn('id="admin-node-op-push-btn"', page)
        self.assertIn('id="admin-node-op-connect-btn"', page)
        self.assertIn('id="admin-node-op-start-btn"', page)

        de_page = render_admin_node_operator_page_html(selected_node="DE").decode(
            "utf-8"
        )
        self.assertIn('data-selected-node="DE"', de_page)
        self.assertIn('id="admin-node-tab-DE"', de_page)

    def test_upload_inventory_and_dry_run_action(self) -> None:
        from admin_node_operator import (
            get_operator_controller,
            handle_admin_node_operator_action,
        )

        ctrl = get_operator_controller()
        ver = ctrl.catalog_version_default()
        self.assertTrue(ver, "catalog version must be non-empty")
        inv = ctrl.list_local_packages(version=ver)
        self.assertTrue(inv.get("ok"), inv)
        self.assertEqual(inv.get("total"), 5)
        platforms = {p["platform"] for p in inv.get("packages") or []}
        self.assertEqual(
            platforms, {"windows", "android", "macos", "ios", "linux"}
        )

        r = ctrl.upload_catalog_packages(
            version=ver,
            stage=False,
            upload=True,
            dry_run=True,
            allow_missing=True,
        )
        self.assertEqual(r["version"], ver)
        self.assertTrue(r.get("dry_run"))
        # Honest: missing packages → not fake success
        if not r.get("ok"):
            self.assertTrue(r.get("error"))

        ok, msg, node_id = handle_admin_node_operator_action(
            {
                "node": "helsinki-store",
                "action": "upload_packages",
                "version": ver,
                "upload": "1",
                "dry_run": "1",
                "allow_missing": "1",
            }
        )
        # dry-run with no packages may fail honestly
        self.assertEqual(node_id, "helsinki-store")
        self.assertTrue(msg)

    def test_public_status_title_only_with_operator(self) -> None:
        from admin_node_operator import get_operator_controller
        from node.aggregate_metrics import filter_public_status

        ctrl = get_operator_controller()
        ctrl.start(mode="lab")
        try:
            ctrl.inject_lab_session()
            pub = ctrl.public_status_title_only()
            self.assertEqual(pub.get("title"), "RESTORE PRIVACY")
            self.assertEqual(list(pub.keys()), ["title"])
            safe = filter_public_status(
                {"title": "RESTORE PRIVACY", "live": 9, "sessions": 3}
            )
            self.assertEqual(safe, {"title": "RESTORE PRIVACY"})
        finally:
            ctrl.stop()

    def test_app_routes_mention_node_operator(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/node-operator", src)
        self.assertIn("render_admin_node_operator_page_html", src)
        self.assertIn("/admin/node-operator/action", src)
        self.assertIn("handle_admin_node_operator_action", src)


if __name__ == "__main__":
    unittest.main()
