"""Connect must not show teardown success as the attach failure reason."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.app import (  # noqa: E402
    attach_failure_user_message,
    auto_connect_on_launch_enabled,
    disconnect_full_tunnel,
)
from client.windows.tunnel_win import (  # noqa: E402
    WindowsTunnelResult,
    stop_full_tunnel,
)


class TestAttachFailureMessage(unittest.TestCase):
    def test_strips_teardown_success_string(self):
        self.assertEqual(
            attach_failure_user_message("tunnel stopped — full teardown complete"),
            "Tunnel setup failed",
        )
        self.assertEqual(
            attach_failure_user_message("TUN failed: no admin"),
            "TUN failed: no admin",
        )
        self.assertEqual(attach_failure_user_message(""), "Tunnel setup failed")
        self.assertEqual(attach_failure_user_message(None), "Tunnel setup failed")

    def test_stop_overwrites_message_unless_preserve(self):
        res = WindowsTunnelResult(False, "Wintun adapter failed", [], routes_applied=False)
        stop_full_tunnel(res, client=None)
        self.assertIn("teardown", res.message.lower())

        res2 = WindowsTunnelResult(False, "Wintun adapter failed", [], routes_applied=False)
        stop_full_tunnel(res2, client=None, preserve_message=True)
        self.assertEqual(res2.message, "Wintun adapter failed")

    def test_disconnect_preserve_message_real_path(self):
        """Product cleanup after failed attach must keep original error text."""
        res = WindowsTunnelResult(
            False,
            "Administrator required for residual-IP full tunnel",
            [],
            routes_applied=False,
        )
        client = mock.Mock()
        original = res.message
        disconnect_full_tunnel(res, client, preserve_message=True)
        # stop may clear dataplane but message must remain usable
        shown = attach_failure_user_message(original)
        self.assertIn("Administrator", shown)
        self.assertNotIn("teardown complete", shown.lower())
        # After preserve stop, message not replaced with teardown success
        self.assertNotIn("full teardown complete", (res.message or "").lower())

    def test_app_source_captures_error_before_cleanup(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("attach_failure_user_message", src)
        self.assertIn("preserve_message=True", src)
        # Failure branch must not read message only after disconnect without preserve
        fail = src[src.index("else:") : src.index("def _start_disconnect")]
        # original_err captured before disconnect_full_tunnel
        self.assertIn("original_err", fail)
        self.assertLess(fail.index("original_err"), fail.index("disconnect_full_tunnel"))
        self.assertIn("preserve_message=True", fail)

    def test_still_manual_connect_only(self):
        self.assertFalse(auto_connect_on_launch_enabled())
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("_auto_connect", src)
        self.assertIn("_start_connect", src)


if __name__ == "__main__":
    unittest.main()
