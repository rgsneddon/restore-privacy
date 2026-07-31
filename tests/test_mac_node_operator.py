"""Mac node operator app: priority, update-push, admin sessions, title-only public."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestClientPriority(unittest.TestCase):
    def test_higher_priority_preferred_and_ordered(self) -> None:
        from node.client_priority import (
            ClientPriorityStore,
            apply_priorities,
            honour_priority_order,
            prefer_client,
            reset_global_priority_store_for_tests,
        )

        reset_global_priority_store_for_tests()
        st = ClientPriorityStore()
        apply_priorities({"alice": 10, "bob": 50, "carol": 1}, store=st)
        ordered = honour_priority_order(["alice", "bob", "carol"], store=st)
        self.assertEqual(ordered, ["bob", "alice", "carol"])
        self.assertEqual(prefer_client(["alice", "carol"], store=st), "alice")
        self.assertEqual(prefer_client(["alice", "bob", "carol"], store=st), "bob")
        self.assertEqual(st.set_priority("alice", 100), 100)
        self.assertEqual(prefer_client(["alice", "bob"], store=st), "alice")


class TestUpdatePush(unittest.TestCase):
    def test_operator_push_and_client_receive_apply(self) -> None:
        from node.protocol import MsgType, pack_update_push, parse_update_push, peek_type
        from node.update_push import (
            apply_client_update_directive,
            client_receive_update_directives,
            operator_push_update,
            pack_update_push_json,
            parse_update_push_json,
            reset_global_update_queue_for_tests,
        )

        q = reset_global_update_queue_for_tests()
        r = operator_push_update(
            version="0.5.9",
            url="https://restoreprivacy.online/",
            message="Please upgrade",
            connected_client_ids=["aa11", "bb22"],
            queue=q,
        )
        self.assertTrue(r["ok"], r)
        self.assertEqual(set(r["delivered_to"]), {"aa11", "bb22"})

        pending = client_receive_update_directives("aa11", queue=q)
        self.assertGreaterEqual(len(pending), 1)
        applied = apply_client_update_directive(pending[0])
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(applied["store"]["pending_update_version"], "0.5.9")
        self.assertIn("restoreprivacy.online", applied["store"]["pending_update_url"])

        raw = pack_update_push_json(pending[0])
        frame = pack_update_push(b"\x01" * 8, raw)
        self.assertEqual(peek_type(frame), MsgType.UPDATE_PUSH)
        sid, body = parse_update_push(frame)
        self.assertEqual(sid, b"\x01" * 8)
        blob = parse_update_push_json(body)
        self.assertEqual(blob["version"], "0.5.9")

        r2 = operator_push_update(
            version="0.6.0",
            target_client_id="only-me",
            connected_client_ids=["aa11", "bb22"],
            queue=q,
        )
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["delivered_to"], ["only-me"])
        only = client_receive_update_directives("only-me", queue=q)
        self.assertTrue(any(x.get("version") == "0.6.0" for x in only))


class TestOperatorController(unittest.TestCase):
    def test_lab_start_stop_sessions_title_only(self) -> None:
        from node.client_priority import reset_global_priority_store_for_tests
        from node.operator_admin import NodeOperatorController
        from node.update_push import reset_global_update_queue_for_tests

        reset_global_priority_store_for_tests()
        reset_global_update_queue_for_tests()
        ctrl = NodeOperatorController(repo_root=ROOT)
        st = ctrl.start(mode="lab")
        self.assertEqual(st.state, "running")
        self.assertEqual(st.mode, "lab")

        a = ctrl.inject_lab_session(vpn_ip="10.88.0.2")
        b = ctrl.inject_lab_session(vpn_ip="10.88.0.3")
        self.assertNotEqual(a["client_id"], b["client_id"])

        ctrl.set_client_priority(a["client_id"], 5)
        ctrl.set_client_priority(b["client_id"], 90)
        order = ctrl.service_order()
        self.assertEqual(order[0], b["client_id"])
        self.assertEqual(ctrl.preferred_client(), b["client_id"])

        rows = ctrl.list_sessions_admin()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["client_id"], b["client_id"])

        pub = ctrl.public_status_title_only()
        self.assertEqual(pub.get("title"), "RESTORE PRIVACY")
        self.assertNotIn("live", pub)
        self.assertNotIn("sessions", pub)
        self.assertNotIn("clients_connected", pub)

        push = ctrl.push_update(
            version="0.5.9",
            url="https://example.com/u",
            message="upgrade",
        )
        self.assertTrue(push["ok"], push)
        self.assertGreaterEqual(push["count"], 1)
        pulled = ctrl.client_pull_updates(a["client_id"])
        self.assertTrue(any(p.get("version") == "0.5.9" for p in pulled))

        stopped = ctrl.stop()
        self.assertEqual(stopped.state, "stopped")
        self.assertEqual(ctrl.list_sessions_admin(), [])


class TestNodeOperatorAppEntry(unittest.TestCase):
    def test_app_smoke_and_gui_shell(self) -> None:
        from node_operator import APP_TITLE
        from node_operator.app import get_controller, main as app_main
        from node_operator.gui_html import render_operator_page

        self.assertIn("Node Operator", APP_TITLE)
        self.assertEqual(app_main(["--smoke"]), 0)

        ctrl = get_controller()
        ctrl.start(mode="lab")
        try:
            html = render_operator_page(ctrl)
        finally:
            ctrl.stop()
        self.assertIn('id="op-app-title"', html)
        self.assertIn("Node Operator", html)
        self.assertIn('id="op-start-btn"', html)
        self.assertIn('id="op-priority-btn"', html)
        self.assertIn('id="op-push-btn"', html)
        self.assertIn('id="op-sessions-table"', html)

    def test_client_update_receive_module(self) -> None:
        from client.update_receive import (
            apply_client_update_directive,
            handle_residual_update_frame,
        )
        from node.protocol import pack_update_push
        from node.update_push import pack_update_push_json

        frame = pack_update_push(
            b"\xab" * 8,
            pack_update_push_json(
                {
                    "version": "0.5.9",
                    "url": "https://restoreprivacy.online/",
                    "message": "hi",
                }
            ),
        )
        got = handle_residual_update_frame(frame)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["store"]["pending_update_version"], "0.5.9")
        bad = handle_residual_update_frame(b"RPT2\x03not-update")
        self.assertFalse(bad["ok"])
        applied = apply_client_update_directive({"version": "1.0.0"})
        self.assertTrue(applied["ok"])


if __name__ == "__main__":
    unittest.main()
