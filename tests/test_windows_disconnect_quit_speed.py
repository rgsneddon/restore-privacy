"""Windows Disconnect/Quit teardown: single-pass residual restore, faster shell waits."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestTeardownPlan(unittest.TestCase):
    def test_extra_restore_skipped_on_plan(self):
        from client.windows.app import windows_disconnect_quit_teardown_plan

        plan = windows_disconnect_quit_teardown_plan()
        by = {s["stage"]: s for s in plan}
        self.assertTrue(by["disconnect_full_tunnel"]["includes_residual_restore"])
        self.assertTrue(by["extra_restore_after_disconnect"]["skipped"])
        self.assertFalse(by["extra_restore_after_disconnect"]["blocks_exit"])


class TestStopFullTunnelSecondPassCheap(unittest.TestCase):
    def test_second_restore_skips_ks_and_fw(self):
        """Post-TUN restore is routes-only (no KS/FW re-run)."""
        from client.windows.tunnel_win import stop_full_tunnel, WindowsTunnelResult

        calls: list[dict] = []

        def fake_restore(**kw):
            calls.append(dict(kw))
            return ["route delete"]

        res = WindowsTunnelResult(
            ok=True,
            message="up",
            applied_commands=[],
            server_host="82.221.101.241",
            if_index=1,
        )
        with mock.patch(
            "client.windows.tunnel_win.restore_windows_residual_path",
            side_effect=fake_restore,
        ):
            stop_full_tunnel(res, client=None, disconnect_session=False)
        self.assertGreaterEqual(len(calls), 2)
        first, second = calls[0], calls[1]
        self.assertTrue(first.get("run_kill_switch_rollback", True))
        self.assertTrue(first.get("run_ipv6_rollback", True))
        self.assertTrue(first.get("reapply_fw_allows", True))
        self.assertFalse(second.get("run_kill_switch_rollback"))
        self.assertFalse(second.get("run_ipv6_rollback"))
        self.assertFalse(second.get("reapply_fw_allows"))

    def test_restore_timeout_capped(self):
        from client.windows.tunnel_win import residual_restore_cmd_timeout_s

        self.assertLessEqual(residual_restore_cmd_timeout_s(), 8.0)
        self.assertGreaterEqual(residual_restore_cmd_timeout_s(), 2.0)


class TestDisconnectFullTunnelAlwaysRestores(unittest.TestCase):
    def test_stop_failure_still_restores(self):
        from client.windows.app import disconnect_full_tunnel

        tunnel = mock.Mock()
        tunnel.server_host = "185.146.232.107"
        client = mock.Mock()
        with mock.patch(
            "client.windows.app.stop_full_tunnel",
            side_effect=RuntimeError("boom"),
        ), mock.patch(
            "client.windows.app.restore_windows_residual_path"
        ) as rest:
            disconnect_full_tunnel(tunnel, client)
            client.disconnect.assert_called()
            rest.assert_called()
            self.assertEqual(
                rest.call_args.kwargs.get("server_host"), "185.146.232.107"
            )


class TestSourceStructural(unittest.TestCase):
    def test_quit_teardown_no_double_restore_call(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        start = src.index("def run_quit_residual_teardown")
        end = src.index("\ndef ", start + 1)
        body = src[start:end]
        self.assertIn("disconnect_full_tunnel", body)
        # Must not call restore again after disconnect in this function
        self.assertEqual(body.count("restore_windows_residual_path"), 0)

    def test_stop_full_tunnel_second_pass_flags(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("reapply_fw_allows=False", src)
        self.assertIn("run_kill_switch_rollback=False", src)
        self.assertIn("RESIDUAL_RESTORE_CMD_TIMEOUT_S", src)


if __name__ == "__main__":
    unittest.main()
