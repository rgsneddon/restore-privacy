"""Admin connected-clients: product version on list/table/tiles + per-client push."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminClientsVersionAndTilePush(unittest.TestCase):
    def setUp(self) -> None:
        from node.client_priority import reset_global_priority_store_for_tests
        from node.update_push import reset_global_update_queue_for_tests
        from admin_node_operator import reset_operator_controller_for_tests

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

    def test_list_sessions_admin_product_version_known_and_unknown(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ctrl.start(mode="lab")
        try:
            known = ctrl.inject_lab_session(
                vpn_ip="10.88.0.10", product_version="0.6.0"
            )
            unknown = ctrl.inject_lab_session(vpn_ip="10.88.0.11")
            rows = ctrl.list_sessions_admin()
            by = {r["client_id"]: r for r in rows}
            self.assertIn("product_version", by[known["client_id"]])
            self.assertEqual(by[known["client_id"]]["product_version"], "0.6.0")
            # Honest empty — never invent Suite/monopin when unreported
            self.assertEqual(by[unknown["client_id"]]["product_version"], "")
            self.assertNotEqual(
                by[unknown["client_id"]].get("product_version"), "1.0.0"
            )
        finally:
            ctrl.stop()

    def test_admin_table_and_tiles_surface_version(self) -> None:
        from admin_node_operator import (
            get_operator_controller,
            render_admin_node_operator_page_html,
        )
        from node_operator.client_visuals import (
            product_version_label,
            render_connected_clients_visual_html,
        )

        ctrl = get_operator_controller()
        ctrl.start(mode="lab")
        try:
            a = ctrl.inject_lab_session(
                vpn_ip="10.88.0.20", product_version="0.6.0"
            )
            b = ctrl.inject_lab_session(vpn_ip="10.88.0.21")
            sessions = ctrl.list_sessions_admin()
            self.assertEqual(product_version_label(a)[0], "0.6.0")
            self.assertEqual(product_version_label(b)[1], "unknown")

            html = render_connected_clients_visual_html(
                sessions,
                id_prefix="admin-node-op-client",
                update_push={
                    "form_action": "/admin/node-operator/action",
                    "version": ctrl.catalog_version_default(),
                    "url": "https://restoreprivacy.online/",
                    "hidden_fields": {
                        "node": "lab",
                        "action": "push_update",
                    },
                },
            )
            self.assertIn('data-client-version="0.6.0"', html)
            self.assertIn("Version 0.6.0", html)
            self.assertIn('data-client-version-unknown="1"', html)
            self.assertIn("Version unknown", html)
            self.assertIn(f'data-client-id="{a["client_id"]}"', html)
            self.assertIn(f'data-client-id="{b["client_id"]}"', html)

            page = render_admin_node_operator_page_html(selected_node="lab").decode(
                "utf-8"
            )
            self.assertIn('id="admin-node-op-sessions-table"', page)
            self.assertIn("<th>Version</th>", page)
            self.assertIn('data-client-version="0.6.0"', page)
            self.assertIn("Version 0.6.0", page)
            self.assertIn("Version unknown", page)
            self.assertIn('data-client-version-unknown="1"', page)
            # Client residual update-push tiles removed (manual update only)
            self.assertNotIn('data-client-tiles-pushable="1"', page)
            self.assertNotIn('data-client-tile-push="1"', page)
            self.assertNotIn('data-client-tile-update="1"', page)
            self.assertNotIn('name="action" value="push_update"', page)
            self.assertNotIn(
                f'data-client-update-target="{a["client_id"]}"', page
            )
            # Version display still present (not a push form)
            self.assertIn('data-client-version="0.6.0"', page)
        finally:
            ctrl.stop()

    def test_tile_push_drives_shipped_per_client_update(self) -> None:
        """Per-client tile push removed; admin action and controller reject."""
        from admin_node_operator import (
            get_operator_controller,
            handle_admin_node_operator_action,
            render_admin_node_operator_page_html,
        )

        ctrl = get_operator_controller()
        ctrl.start(mode="lab")
        try:
            target = ctrl.inject_lab_session(
                vpn_ip="10.88.0.30", product_version="0.6.0"
            )
            other = ctrl.inject_lab_session(
                vpn_ip="10.88.0.31", product_version="0.5.9"
            )
            page = render_admin_node_operator_page_html(selected_node="lab").decode(
                "utf-8"
            )
            self.assertNotIn('data-client-tile-push="1"', page)
            self.assertNotIn(
                f'data-client-update-target="{target["client_id"]}"', page
            )

            ok, msg, node = handle_admin_node_operator_action(
                {
                    "node": "lab",
                    "action": "push_update",
                    "version": "0.6.0",
                    "url": "https://restoreprivacy.online/",
                    "message": "tile push test",
                    "target_client_id": target["client_id"],
                }
            )
            self.assertFalse(ok, msg)
            self.assertIn("disabled", msg.lower())
            self.assertEqual(node, "lab")

            got_t = ctrl.client_pull_updates(target["client_id"])
            got_o = ctrl.client_pull_updates(other["client_id"])
            self.assertFalse(got_t)
            self.assertFalse(got_o)

            r = ctrl.push_update(
                version="0.6.0",
                url="https://restoreprivacy.online/",
                message="second",
                target_client_id=target["client_id"],
            )
            self.assertFalse(r.get("ok"), r)
            self.assertEqual(int(r.get("count") or 0), 0)
            self.assertEqual(list(r.get("delivered_to") or []), [])
        finally:
            ctrl.stop()


    def test_public_status_title_only_no_sessions_or_versions(self) -> None:
        from admin_node_operator import get_operator_controller

        ctrl = get_operator_controller()
        ctrl.start(mode="lab")
        try:
            ctrl.inject_lab_session(product_version="0.6.0")
            ctrl.inject_lab_session(product_version="1.0.0")
            pub = ctrl.public_status_title_only()
            self.assertEqual(pub.get("title"), "RESTORE PRIVACY")
            self.assertEqual(list(pub.keys()), ["title"])
            blob = str(pub)
            self.assertNotIn("product_version", blob)
            self.assertNotIn("0.6.0", blob)
            self.assertNotIn("sessions", blob.lower())
            self.assertNotIn("client_id", blob)
        finally:
            ctrl.stop()


if __name__ == "__main__":
    unittest.main()
