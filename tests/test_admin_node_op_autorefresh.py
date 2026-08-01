"""Admin Node Operator page must NOT auto-reload on a timer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminNodeOperatorNoAutoRefresh(unittest.TestCase):
    def test_auto_refresh_disabled_helper_returns_empty(self) -> None:
        from admin_node_operator import (
            ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC,
            node_operator_auto_refresh_meta,
        )

        self.assertLessEqual(ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC, 0)
        bare = node_operator_auto_refresh_meta("")
        self.assertEqual(bare, "")
        lab = node_operator_auto_refresh_meta("lab")
        self.assertEqual(lab, "")
        is_meta = node_operator_auto_refresh_meta("IS")
        self.assertEqual(is_meta, "")
        dirty = node_operator_auto_refresh_meta('lab"><script>')
        self.assertEqual(dirty, "")
        self.assertNotIn("http-equiv", bare)
        self.assertNotIn("refresh", bare.lower())
        self.assertNotIn("admin-node-op-auto-refresh", bare)

    def test_page_render_has_no_meta_refresh(self) -> None:
        from admin_node_operator import (
            ADMIN_NAV_NODE_OPERATOR_ID,
            ADMIN_NODE_OPERATOR_PATH,
            ADMIN_NODE_OPERATOR_POST_PATH,
            render_admin_node_operator_page_html,
        )

        page = render_admin_node_operator_page_html(selected_node="lab").decode(
            "utf-8"
        )
        # Core chrome still present
        self.assertIn('id="admin-node-operator"', page)
        self.assertIn(ADMIN_NODE_OPERATOR_PATH, page)
        self.assertIn(ADMIN_NODE_OPERATOR_POST_PATH, page)
        self.assertIn('data-selected-node="lab"', page)
        self.assertIn('id="admin-node-tab-lab"', page)
        # No timed full-page reload
        self.assertNotIn('http-equiv="refresh"', page)
        self.assertNotIn("admin-node-op-auto-refresh", page)
        self.assertNotIn("data-auto-refresh-sec", page)
        self.assertNotIn('content="5', page)
        # Node selection still in tab links (manual navigation)
        self.assertIn(f"{ADMIN_NODE_OPERATOR_PATH}?node=lab", page)
        self.assertIn(f"{ADMIN_NODE_OPERATOR_PATH}?node=IS", page)

        is_page = render_admin_node_operator_page_html(selected_node="IS").decode(
            "utf-8"
        )
        self.assertIn('id="admin-node-operator"', is_page)
        self.assertIn('data-selected-node="IS"', is_page)
        self.assertIn(f"{ADMIN_NODE_OPERATOR_PATH}?node=IS", is_page)
        self.assertNotIn('http-equiv="refresh"', is_page)
        self.assertNotIn("admin-node-op-auto-refresh", is_page)
        self.assertNotIn("data-auto-refresh-sec", is_page)
        # Sidebar / nav id stable
        self.assertIn(ADMIN_NAV_NODE_OPERATOR_ID, is_page)

    def test_public_and_other_admin_do_not_get_node_op_refresh(self) -> None:
        from admin_panel import render_admin_home_html
        from public_chrome import public_brand_header_html, public_site_css

        pub = public_brand_header_html()
        css = public_site_css()
        self.assertNotIn("admin-node-op-auto-refresh", pub)
        self.assertNotIn('http-equiv="refresh"', pub)
        self.assertNotIn("admin-node-op-auto-refresh", css)

        home = render_admin_home_html().decode("utf-8")
        self.assertNotIn("admin-node-op-auto-refresh", home)
        self.assertNotIn("data-auto-refresh-sec", home)

        from admin_panel import _admin_page_shell

        bare = _admin_page_shell(
            title="Other",
            active="home",
            main_html="<p>x</p>",
        ).decode("utf-8")
        self.assertNotIn("admin-node-op-auto-refresh", bare)
        self.assertNotIn("data-auto-refresh-sec", bare)


if __name__ == "__main__":
    unittest.main()
