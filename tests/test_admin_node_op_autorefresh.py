"""Admin Node Operator page auto-refreshes every 5 seconds (meta refresh)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminNodeOperatorAutoRefresh(unittest.TestCase):
    def test_meta_refresh_helper_five_seconds_and_node(self) -> None:
        from admin_node_operator import (
            ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC,
            ADMIN_NODE_OPERATOR_PATH,
            node_operator_auto_refresh_meta,
        )

        self.assertEqual(ADMIN_NODE_OPERATOR_AUTO_REFRESH_SEC, 5)
        bare = node_operator_auto_refresh_meta("")
        self.assertIn('http-equiv="refresh"', bare)
        self.assertIn('content="5"', bare)
        self.assertIn('data-auto-refresh-sec="5"', bare)
        self.assertIn('id="admin-node-op-auto-refresh"', bare)

        lab = node_operator_auto_refresh_meta("lab")
        self.assertIn('content="5;url=', lab)
        self.assertIn(f"{ADMIN_NODE_OPERATOR_PATH}?node=lab", lab)
        self.assertIn('data-auto-refresh-node="lab"', lab)
        self.assertIn('data-auto-refresh-sec="5"', lab)

        # Strip unsafe characters from node id (no HTML injection in meta content)
        dirty = node_operator_auto_refresh_meta('lab"><script>')
        self.assertNotIn("<script>", dirty)
        self.assertNotIn('">', dirty)

    def test_page_render_includes_five_second_refresh_with_selected_node(self) -> None:
        from admin_node_operator import (
            ADMIN_NODE_OPERATOR_PATH,
            render_admin_node_operator_page_html,
        )

        page = render_admin_node_operator_page_html(selected_node="lab").decode(
            "utf-8"
        )
        self.assertIn('id="admin-node-op-auto-refresh"', page)
        self.assertIn('http-equiv="refresh"', page)
        self.assertIn('data-auto-refresh-sec="5"', page)
        self.assertIn('data-auto-refresh-node="lab"', page)
        # Full meta content targets same admin path + node
        m = re.search(
            r'<meta[^>]+id="admin-node-op-auto-refresh"[^>]*>',
            page,
        )
        self.assertIsNotNone(m)
        tag = m.group(0)
        self.assertIn('content="5;url=', tag)
        self.assertIn(f"{ADMIN_NODE_OPERATOR_PATH}?node=lab", tag)
        # Meta is in document head (before body)
        self.assertLess(page.index("admin-node-op-auto-refresh"), page.index("<body"))

        is_page = render_admin_node_operator_page_html(selected_node="IS").decode(
            "utf-8"
        )
        self.assertIn(f"{ADMIN_NODE_OPERATOR_PATH}?node=IS", is_page)
        self.assertIn('data-auto-refresh-node="IS"', is_page)

    def test_public_and_other_admin_do_not_get_node_op_refresh(self) -> None:
        from admin_panel import render_admin_home_html
        from public_chrome import public_brand_header_html, public_site_css

        # Public chrome
        pub = public_brand_header_html()
        css = public_site_css()
        self.assertNotIn("admin-node-op-auto-refresh", pub)
        self.assertNotIn('http-equiv="refresh"', pub)
        self.assertNotIn("admin-node-op-auto-refresh", css)

        # Other admin page (home) must not inherit Node Operator 5s refresh
        home = render_admin_home_html().decode("utf-8")
        self.assertNotIn("admin-node-op-auto-refresh", home)
        self.assertNotIn('data-auto-refresh-sec="5"', home)
        # Bare shell has no node-operator refresh unless extra_head is passed
        from admin_panel import _admin_page_shell

        bare = _admin_page_shell(
            title="Other",
            active="home",
            main_html="<p>x</p>",
        ).decode("utf-8")
        self.assertNotIn("admin-node-op-auto-refresh", bare)
        self.assertNotIn('data-auto-refresh-sec="5"', bare)


if __name__ == "__main__":
    unittest.main()
