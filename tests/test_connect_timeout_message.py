"""Connect timeout messaging must include node host:port; not bare 'timed out'."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import (  # noqa: E402
    ConnectState,
    RptClient,
    format_connect_failure,
)
from client.endpoint import Endpoint  # noqa: E402
from client.ui_theme import plain_tunnel_status  # noqa: E402


class TestFormatConnectFailure(unittest.TestCase):
    def test_timeout_includes_host_port(self):
        msg = format_connect_failure(
            TimeoutError("timed out"),
            host="104.156.224.47",
            port=44044,
            timeout_s=20.0,
        )
        self.assertIn("104.156.224.47", msg)
        self.assertIn("44044", msg)
        self.assertIn("20", msg)
        self.assertNotEqual(msg.strip().lower(), "timed out")
        self.assertIn("No reply", msg)

    def test_socket_timeout_message(self):
        msg = format_connect_failure(
            socket.timeout("timed out"),
            host="1.2.3.4",
            port=9,
            timeout_s=5,
        )
        self.assertIn("1.2.3.4:9", msg)
        self.assertNotEqual(msg.lower(), "timed out")

    def test_other_errors_keep_detail(self):
        msg = format_connect_failure(
            RuntimeError("bad secrets"),
            host="h.example",
            port=1,
            timeout_s=1,
        )
        self.assertIn("bad secrets", msg)


class TestConnectTimeoutPath(unittest.TestCase):
    def test_connect_timeout_user_message_via_real_connect(self):
        """Drive RptClient.connect with patched recv that times out."""
        client = RptClient(endpoint=Endpoint(host="203.0.113.50", port=44044))
        # UK gate pass + secrets + hello build, then UDP never replies
        sock = mock.Mock()
        sock.sendto = mock.Mock()
        sock.recvfrom = mock.Mock(side_effect=socket.timeout("timed out"))
        sock.settimeout = mock.Mock()

        with mock.patch.object(
            client, "run_uk_gate", return_value=mock.Mock(allowed=True, message="ok")
        ), mock.patch(
            "client.connect.ensure_device_admission_key", return_value=Path(".")
        ), mock.patch(
            "client.connect.load_client_private_key"
        ) as load_priv, mock.patch(
            "client.connect.load_node_elgamal_public"
        ) as load_pub, mock.patch(
            "client.connect.build_authorized_client_hello",
            return_value=(b"HELLO", b"\x00" * 32, b"\x11" * 32),
        ), mock.patch(
            "client.connect.assert_protocol_magic"
        ), mock.patch(
            "client.connect.socket.socket", return_value=sock
        ):
            # loaders just need to return anything truthy used only for hello builder (mocked)
            load_priv.return_value = mock.Mock()
            load_pub.return_value = mock.Mock()
            result = client.connect(timeout=2.0)

        self.assertFalse(result.ok)
        self.assertEqual(result.state, ConnectState.ERROR)
        self.assertIn("203.0.113.50", result.message)
        self.assertIn("44044", result.message)
        self.assertNotEqual(result.message.strip().lower(), "timed out")
        # UI plain status path must accept the rich message
        ui = plain_tunnel_status("error", detail=result.message)
        self.assertIn("Could not connect", ui)
        self.assertIn("203.0.113.50", ui)


class TestNoAutoConnectPreserved(unittest.TestCase):
    def test_windows_app_still_manual(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_start_connect", src)
        self.assertNotIn("_auto_connect", src)


if __name__ == "__main__":
    unittest.main()
