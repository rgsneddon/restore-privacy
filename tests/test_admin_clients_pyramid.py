"""Admin Connected clients graphic: Chronoflux-style animated pyramid of blobs."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminClientsPyramid(unittest.TestCase):
    def setUp(self) -> None:
        from admin_node_operator import reset_operator_controller_for_tests
        from node.client_priority import reset_global_priority_store_for_tests
        from node.update_push import reset_global_update_queue_for_tests

        reset_global_priority_store_for_tests()
        reset_global_update_queue_for_tests()
        reset_operator_controller_for_tests()

    def tearDown(self) -> None:
        from admin_node_operator import reset_operator_controller_for_tests
        from node.client_priority import reset_global_priority_store_for_tests
        from node.update_push import reset_global_update_queue_for_tests

        reset_operator_controller_for_tests()
        reset_global_priority_store_for_tests()
        reset_global_update_queue_for_tests()

    def test_pyramid_row_sizes(self) -> None:
        from node_operator.client_visuals import pyramid_row_sizes

        self.assertEqual(pyramid_row_sizes(0), [])
        self.assertEqual(pyramid_row_sizes(1), [1])
        self.assertEqual(pyramid_row_sizes(2), [1, 1])
        self.assertEqual(pyramid_row_sizes(3), [1, 2])
        self.assertEqual(pyramid_row_sizes(6), [1, 2, 3])
        self.assertEqual(pyramid_row_sizes(5), [1, 2, 2])
        self.assertEqual(sum(pyramid_row_sizes(11)), 11)

    def test_empty_has_no_blobs(self) -> None:
        from node_operator.client_visuals import render_connected_clients_visual_html

        empty = render_connected_clients_visual_html([], id_prefix="admin-node-op-client")
        self.assertIn('data-client-visual-empty="1"', empty)
        self.assertNotIn('data-client-tile="1"', empty)
        self.assertNotIn('data-client-blob="1"', empty)
        self.assertNotIn('data-client-pyramid-stack="1"', empty)
        self.assertIn('data-client-count="0"', empty)

    def test_multi_session_pyramid_structure_and_animation(self) -> None:
        from admin_node_operator import (
            get_operator_controller,
            render_admin_node_operator_page_html,
        )
        from node_operator.client_visuals import (
            pyramid_row_sizes,
            render_connected_clients_visual_html,
        )

        ctrl = get_operator_controller()
        ctrl.start(mode="lab")
        try:
            sessions_ids = []
            for i in range(6):
                row = ctrl.inject_lab_session(
                    vpn_ip=f"10.88.0.{40 + i}",
                    product_version="0.6.0" if i % 2 == 0 else "",
                )
                sessions_ids.append(row["client_id"])
                ctrl.set_client_priority(row["client_id"], 100 - i * 10)

            sessions = ctrl.list_sessions_admin()
            self.assertEqual(len(sessions), 6)
            sizes = pyramid_row_sizes(6)
            self.assertEqual(sizes, [1, 2, 3])

            html = render_connected_clients_visual_html(
                sessions,
                id_prefix="admin-node-op-client",
                update_push={
                    "form_action": "/admin/node-operator/action",
                    "version": ctrl.catalog_version_default(),
                    "url": "https://restoreprivacy.online/",
                    "hidden_fields": {"node": "lab", "action": "push_update"},
                },
            )
            # Pyramid markers — not a flat flex card grid only
            self.assertIn('data-client-pyramid="1"', html)
            self.assertIn('data-client-pyramid-stack="1"', html)
            self.assertIn('data-client-pyramid-row="1"', html)
            self.assertIn('data-pyramid-rows="3"', html)
            self.assertIn('data-pyramid-row-sizes="1,2,3"', html)
            self.assertIn("admin-node-op-client-pyramid", html)
            rows = re.findall(r'data-client-pyramid-row="1"', html)
            self.assertEqual(len(rows), 3)
            # One blob per real session
            blobs = re.findall(r'data-client-blob="1"', html)
            tiles = re.findall(r'data-client-tile="1"', html)
            self.assertEqual(len(blobs), 6)
            self.assertEqual(len(tiles), 6)
            for cid in sessions_ids:
                self.assertIn(f'data-client-id="{cid}"', html)
            # Apex row has higher priority first session
            apex = re.search(
                r'data-pyramid-row="0"[^>]*data-client-id="([^"]+)"',
                html,
            )
            if not apex:
                apex = re.search(
                    r'data-client-tile="1"[^>]*data-client-id="([^"]+)"'
                    r'[^>]*data-pyramid-row="0"',
                    html,
                )
            self.assertIsNotNone(apex)
            assert apex is not None
            self.assertEqual(apex.group(1), sessions[0]["client_id"])
            # Version known / unknown preserved
            self.assertIn('data-client-version="0.6.0"', html)
            self.assertIn('data-client-version-unknown="1"', html)
            # Animation present (CSS keyframes + animation properties on blobs)
            self.assertIn("@keyframes", html)
            self.assertIn("blob-float", html)
            self.assertIn("blob-pulse", html)
            self.assertIn("blob-morph", html)
            self.assertRegex(html, r"animation\s*:")
            # Per-blob update affordance
            self.assertIn('data-client-tile-push="1"', html)
            self.assertIn('name="target_client_id"', html)
            self.assertIn('data-client-tiles-pushable="1"', html)

            page = render_admin_node_operator_page_html(selected_node="lab").decode(
                "utf-8"
            )
            self.assertIn('data-client-pyramid="1"', page)
            self.assertIn('data-client-pyramid-stack="1"', page)
            self.assertIn("@keyframes", page)
            self.assertEqual(page.count('data-client-blob="1"'), 6)
            for cid in sessions_ids:
                self.assertIn(cid, page)
        finally:
            ctrl.stop()

    def test_public_title_only_and_empty_pyramid(self) -> None:
        from admin_node_operator import get_operator_controller
        from node_operator.client_visuals import render_connected_clients_visual_html

        empty = render_connected_clients_visual_html([], id_prefix="op-client")
        self.assertIn('data-client-visual-empty="1"', empty)
        self.assertEqual(empty.count('data-client-blob="1"'), 0)

        ctrl = get_operator_controller()
        ctrl.start(mode="lab")
        try:
            ctrl.inject_lab_session(product_version="0.6.0")
            pub = ctrl.public_status_title_only()
            self.assertEqual(list(pub.keys()), ["title"])
            self.assertEqual(pub.get("title"), "RESTORE PRIVACY")
            blob = str(pub)
            self.assertNotIn("pyramid", blob.lower())
            self.assertNotIn("data-client", blob)
            self.assertNotIn("product_version", blob)
        finally:
            ctrl.stop()


if __name__ == "__main__":
    unittest.main()
