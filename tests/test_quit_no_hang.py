"""Quit path: status remark + residual teardown off UI thread (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.app import (  # noqa: E402
    QUIT_STATUS_REMARK,
    apply_quit_status_remark,
    run_quit_residual_teardown,
)


class TestQuitStatusRemark(unittest.TestCase):
    def test_phrase_exact(self):
        self.assertEqual(QUIT_STATUS_REMARK, "quitting RPT client...")

    def test_apply_sets_status_var(self):
        status = mock.Mock()
        detail = mock.Mock()
        out = apply_quit_status_remark(status, detail)
        self.assertEqual(out, QUIT_STATUS_REMARK)
        status.set.assert_called_once_with(QUIT_STATUS_REMARK)
        detail.set.assert_called_once()
        self.assertIn("residual", detail.set.call_args[0][0].lower())


class TestQuitResidualTeardown(unittest.TestCase):
    def test_calls_disconnect_then_restore(self):
        tunnel = mock.Mock()
        tunnel.server_host = "82.221.101.241"
        client = mock.Mock()
        order: list[str] = []

        def _disc(t, c, **kw):
            order.append("disconnect")
            self.assertIs(t, tunnel)
            self.assertIs(c, client)

        def _restore(**kw):
            order.append("restore")
            self.assertEqual(kw.get("server_host"), "82.221.101.241")

        with mock.patch(
            "client.windows.app.disconnect_full_tunnel", side_effect=_disc
        ), mock.patch(
            "client.windows.app.restore_windows_residual_path", side_effect=_restore
        ):
            run_quit_residual_teardown(tunnel, client)
        self.assertEqual(order, ["disconnect", "restore"])

    def test_none_tunnel_still_restores(self):
        with mock.patch(
            "client.windows.app.disconnect_full_tunnel"
        ) as disc, mock.patch(
            "client.windows.app.restore_windows_residual_path"
        ) as rest:
            run_quit_residual_teardown(None, mock.Mock())
            disc.assert_called_once()
            rest.assert_called_once()
            self.assertIsNone(rest.call_args.kwargs.get("server_host"))


class TestQuitAppSourceOrder(unittest.TestCase):
    def test_quit_app_shows_status_before_thread_teardown(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Exact product phrase on real path
        self.assertIn('QUIT_STATUS_REMARK = "quitting RPT client..."', src)
        self.assertIn("def _quit_app", src)
        # Slice only TunnelClientApp._quit_app → .run (not module-level run_quit_*)
        start = src.index("    def _quit_app")
        end = src.index("    def run(self)", start)
        quit_src = src[start:end]
        self.assertIn("_show_quitting_status", quit_src)
        self.assertIn("run_quit_residual_teardown", quit_src)
        self.assertIn("threading.Thread", quit_src)
        self.assertIn("rpt-quit-teardown", quit_src)
        self.assertIn("root.after", quit_src)
        self.assertIn("destroy", quit_src)
        # Must not call disconnect_full_tunnel synchronously as first residual step
        # on the quit stack before scheduling the worker (status first).
        self.assertIn("_show_quitting_status()", quit_src)
        status_i = quit_src.index("_show_quitting_status()")
        thread_i = quit_src.index("threading.Thread")
        self.assertLess(status_i, thread_i)
        self.assertNotIn("disconnect_full_tunnel(", quit_src)
        # Tray quit shares _quit_app
        self.assertIn("on_quit=lambda: self.root.after(0, self._quit_app)", src)


if __name__ == "__main__":
    unittest.main()
