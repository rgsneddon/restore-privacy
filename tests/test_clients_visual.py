"""Graphic visuals of connected clients in node operator GUIs."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestClientVisualBuilder(unittest.TestCase):
    def test_empty_and_multi_from_real_sessions(self) -> None:
        from node.client_priority import reset_global_priority_store_for_tests
        from node.operator_admin import NodeOperatorController
        from node.update_push import reset_global_update_queue_for_tests
        from node_operator.client_visuals import (
            render_connected_clients_visual_html,
            short_client_id,
        )
        from node_operator.gui_html import render_operator_page

        reset_global_priority_store_for_tests()
        reset_global_update_queue_for_tests()
        ctrl = NodeOperatorController(repo_root=ROOT)

        # Empty
        empty = render_connected_clients_visual_html([], id_prefix="op-client")
        self.assertIn('data-client-visuals="1"', empty)
        self.assertIn('data-client-count="0"', empty)
        self.assertIn('data-client-visual-empty="1"', empty)
        self.assertIn("op-client-visual-empty", empty)
        self.assertNotIn('data-client-tile="1"', empty)

        page0 = render_operator_page(ctrl)
        self.assertIn('id="op-client-visuals"', page0)
        self.assertIn('data-client-visual-empty="1"', page0)

        # Multi
        ctrl.start(mode="lab")
        try:
            a = ctrl.inject_lab_session(vpn_ip="10.88.0.2")
            b = ctrl.inject_lab_session(vpn_ip="10.88.0.3")
            ctrl.set_client_priority(a["client_id"], 5)
            ctrl.set_client_priority(b["client_id"], 90)
            sessions = ctrl.list_sessions_admin()
            self.assertEqual(len(sessions), 2)
            # higher priority first
            self.assertEqual(sessions[0]["client_id"], b["client_id"])

            html = render_connected_clients_visual_html(
                sessions, id_prefix="op-client"
            )
            self.assertIn('data-client-count="2"', html)
            self.assertNotIn('data-client-visual-empty="1"', html)
            tiles = re.findall(r'data-client-tile="1"', html)
            self.assertEqual(len(tiles), 2)
            # Each real id present
            self.assertIn(f'data-client-id="{a["client_id"]}"', html)
            self.assertIn(f'data-client-id="{b["client_id"]}"', html)
            self.assertIn('data-client-priority="90"', html)
            self.assertIn('data-client-priority="5"', html)
            self.assertIn("10.88.0.2", html)
            self.assertIn("10.88.0.3", html)
            # Order: first tile is high priority (b)
            first_id = re.search(
                r'data-client-tile="1"[^>]*data-client-id="([^"]+)"', html
            )
            self.assertIsNotNone(first_id)
            assert first_id is not None
            self.assertEqual(first_id.group(1), b["client_id"])
            self.assertIn(short_client_id(b["client_id"]), html)

            page = render_operator_page(ctrl)
            self.assertIn('id="op-client-visuals"', page)
            self.assertIn('data-client-tile="1"', page)
            self.assertIn(a["client_id"], page)
            self.assertIn(b["client_id"], page)
        finally:
            ctrl.stop()

    def test_admin_page_shares_visuals(self) -> None:
        from admin_node_operator import (
            get_operator_controller,
            render_admin_node_operator_page_html,
            reset_operator_controller_for_tests,
        )
        from node.client_priority import reset_global_priority_store_for_tests
        from node.update_push import reset_global_update_queue_for_tests

        reset_global_priority_store_for_tests()
        reset_global_update_queue_for_tests()
        reset_operator_controller_for_tests()
        shared = get_operator_controller()
        shared.start(mode="lab")
        try:
            a = shared.inject_lab_session()
            b = shared.inject_lab_session()
            shared.set_client_priority(a["client_id"], 1)
            shared.set_client_priority(b["client_id"], 50)
            page = render_admin_node_operator_page_html(selected_node="lab").decode(
                "utf-8"
            )
            self.assertIn('id="admin-node-op-client-visuals"', page)
            self.assertIn('data-client-visuals="1"', page)
            self.assertIn('data-client-count="2"', page)
            self.assertIn('data-client-tile="1"', page)
            self.assertIn(a["client_id"], page)
            self.assertIn(b["client_id"], page)
            # higher priority first among tiles
            first = re.search(
                r'id="admin-node-op-client-tile-0"[^>]*data-client-id="([^"]+)"',
                page,
            )
            if not first:
                first = re.search(
                    r'data-client-tile="1"[^>]*data-client-id="([^"]+)"', page
                )
            self.assertIsNotNone(first)
            assert first is not None
            self.assertEqual(first.group(1), b["client_id"])
            pub = shared.public_status_title_only()
            self.assertEqual(pub.get("title"), "RESTORE PRIVACY")
            self.assertEqual(list(pub.keys()), ["title"])
        finally:
            reset_operator_controller_for_tests()


if __name__ == "__main__":
    unittest.main()
