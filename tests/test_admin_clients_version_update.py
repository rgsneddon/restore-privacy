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
            # Tiles operable for update
            self.assertIn('data-client-tiles-pushable="1"', page)
            self.assertIn('data-client-tile-push="1"', page)
            self.assertIn('data-client-tile-update="1"', page)
            self.assertIn(
                f'data-client-update-target="{a["client_id"]}"', page
            )
            self.assertIn(
                f'name="target_client_id" value="{a["client_id"]}"', page
            )
            self.assertIn(
                f'name="target_client_id" value="{b["client_id"]}"', page
            )
            self.assertIn('name="action" value="push_update"', page)
            self.assertIn('action="/admin/node-operator/action"', page)
            # Catalog directive version present on tile form (not invent client version)
            cat = ctrl.catalog_version_default()
            self.assertTrue(cat)
            self.assertIn(f'name="version" value="{cat}"', page)
        finally:
            ctrl.stop()

    def test_tile_push_drives_shipped_per_client_update(self) -> None:
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
            # Extract the target-specific form fields from shipped HTML
            m = re.search(
                rf'data-client-update-target="{re.escape(target["client_id"])}"[^>]*>'
                r"(.*?)</form>",
                page,
                re.DOTALL,
            )
            self.assertIsNotNone(m, "target tile form missing from admin HTML")
            form_html = m.group(0)
            self.assertIn(
                f'name="target_client_id" value="{target["client_id"]}"',
                form_html,
            )
            self.assertNotIn(
                f'name="target_client_id" value="{other["client_id"]}"',
                form_html,
            )
            ver_m = re.search(r'name="version" value="([^"]*)"', form_html)
            self.assertIsNotNone(ver_m)
            directive_ver = ver_m.group(1)
            self.assertTrue(directive_ver)

            # Drive the real admin handler (same path as form POST)
            ok, msg, node = handle_admin_node_operator_action(
                {
                    "node": "lab",
                    "action": "push_update",
                    "version": directive_ver,
                    "url": "https://restoreprivacy.online/",
                    "message": "tile push test",
                    "target_client_id": target["client_id"],
                }
            )
            self.assertTrue(ok, msg)
            self.assertEqual(node, "lab")
            self.assertIn("1", msg)  # Pushed to 1 target(s)

            # Controller-level: only target receives directive
            got_t = ctrl.client_pull_updates(target["client_id"])
            got_o = ctrl.client_pull_updates(other["client_id"])
            self.assertTrue(got_t, "target should receive UPDATE_PUSH")
            self.assertEqual(len(got_t), 1)
            self.assertEqual(got_t[0].get("version"), directive_ver)
            self.assertFalse(got_o, "other client must not receive targeted push")

            # Direct controller path with target (shipped push_update)
            r = ctrl.push_update(
                version=directive_ver,
                url="https://restoreprivacy.online/",
                message="second",
                target_client_id=target["client_id"],
            )
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(int(r.get("count") or 0), 1)
            delivered = list(r.get("delivered_to") or [])
            self.assertEqual(delivered, [target["client_id"]])
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
