"""Tests drive the shipped client connect / full-tunnel / UI theme paths."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import (  # noqa: E402
    assert_protocol_magic,
    build_authorized_client_hello,
    complete_server_hello,
)
from client.full_tunnel import (  # noqa: E402
    android_vpn_builder_config,
    assert_full_tunnel_plan,
    build_full_tunnel_plan,
    windows_route_commands,
)
from client.ui_theme import (  # noqa: E402
    BANNER_BG,
    PRIVACY_MESSAGE_TEXT,
    WINDOW_BG,
    WINDOW_FG,
)
from node.elgamal import generate_keypair  # noqa: E402
from node.handshake import (  # noqa: E402
    AdmissionError,
    NodeHandshake,
    ed25519_pub_raw,
    generate_client_admission_keypair,
    node_complete_hello,
)


class TestClientProtocol(unittest.TestCase):
    def test_protocol_magic_rpt2(self):
        self.assertEqual(assert_protocol_magic(), b"RPT2")

    def test_authorized_client_hello_and_session(self):
        node_priv = generate_keypair()
        cpriv, cpub = generate_client_admission_keypair()
        allow = [ed25519_pub_raw(cpub)]
        node = NodeHandshake(node_priv, allow)

        frame, client_nonce, client_pub, _eph = build_authorized_client_hello(
            cpriv, node_priv.public
        )
        self.assertTrue(frame.startswith(b"RPT2"))
        reply, result = node_complete_hello(node, frame, "10.88.0.7")
        session = complete_server_hello(reply, client_nonce, client_pub, _eph)
        self.assertEqual(session.session_id, result.session_id)
        self.assertEqual(session.vpn_ip, "10.88.0.7")
        # AEAD roundtrip on session key
        n, sealed = session.crypto.seal(b"\x45" + b"\x00" * 19, aad=b"t")
        self.assertEqual(session.crypto.open(n, sealed, aad=b"t"), b"\x45" + b"\x00" * 19)

    def test_unauthorized_client_fails(self):
        node_priv = generate_keypair()
        good_priv, good_pub = generate_client_admission_keypair()
        bad_priv, _ = generate_client_admission_keypair()
        # Free-product default admits unknown devices; enforce allow-list for this check
        node = NodeHandshake(
            node_priv,
            [ed25519_pub_raw(good_pub)],
            admit_unknown_devices=False,
        )
        frame, _, _, _eph = build_authorized_client_hello(bad_priv, node_priv.public)
        with self.assertRaises(AdmissionError):
            node_complete_hello(node, frame, "10.88.0.2")


class TestFullTunnel(unittest.TestCase):
    def test_plan_is_full_tunnel(self):
        plan = build_full_tunnel_plan("10.88.0.2")
        self.assertEqual(assert_full_tunnel_plan(plan), [])
        self.assertTrue(plan.is_full_tunnel())
        cfg = android_vpn_builder_config(plan)
        self.assertIn({"addr": "0.0.0.0", "prefix": 0}, cfg["routes"])
        self.assertIn({"addr": "::", "prefix": 0}, cfg["routes"])
        self.assertTrue(cfg["allowAllApps"])
        cmds = "\n".join(windows_route_commands(plan, "82.221.101.241", if_index=9))
        self.assertIn("0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 9", cmds)
        self.assertIn("128.0.0.0 mask 128.0.0.0 0.0.0.0 IF 9", cmds)
        self.assertIn("10.88.0.1 mask 255.255.255.255 0.0.0.0 IF 9", cmds)
        self.assertIn("IF 9", cmds)
        self.assertIn("82.221.101.241", cmds)
        self.assertNotIn("mask 128.0.0.0 10.88.0.1", cmds)


class TestUiTheme(unittest.TestCase):
    def test_privacy_message_string_exact(self):
        self.assertEqual(
            PRIVACY_MESSAGE_TEXT,
            "lightweight vpn to restore your privacy - no user data is retained - your privacy is restored",
        )
        # Product shell uses restorebritain contact palette (not Win3.1-only)
        from client.ui_theme import CHROME_BG, PRIMARY

        self.assertTrue(BANNER_BG.startswith("#"))
        self.assertTrue(WINDOW_BG.startswith("#"))
        self.assertTrue(WINDOW_FG.startswith("#"))
        self.assertTrue(PRIMARY.startswith("#"))
        self.assertTrue(CHROME_BG.startswith("#"))

    def test_windows_app_manual_connect_and_theme_in_source(self):
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("PRIVACY_MESSAGE_TEXT", app)
        self.assertIn("CHROME_BG", app)
        self.assertIn("_start_connect", app)
        self.assertIn("_start_disconnect", app)
        self.assertIn("_on_close_ui_only", app)
        self.assertNotIn("def _auto_connect", app)
        self.assertIn("plain_tunnel_status", app)

    def test_flutter_sources(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        theme = (ROOT / "client_app" / "lib" / "theme.dart").read_text(encoding="utf-8")
        vpn = (ROOT / "client_app" / "lib" / "vpn_controller.dart").read_text(encoding="utf-8")
        self.assertIn(PRIVACY_MESSAGE_TEXT, theme)
        # Windows-aligned product shell tokens
        self.assertIn("kChromeBg", main)
        self.assertIn("kPrimary", theme)
        self.assertIn("0xFFF2F5F7", theme.replace(" ", ""))
        self.assertIn("0xFF2779AA", theme.replace(" ", ""))
        self.assertIn("connectButtonLabel", main)
        self.assertIn("autoConnectOnLaunch", vpn)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(encoding="utf-8")
        self.assertIn("fullTunnel = true", cfg)
        self.assertIn("0.0.0.0/0", cfg)
        self.assertIn("autoConnectOnLaunch = false", cfg)

    def test_android_vpn_service_full_tunnel(self):
        base = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
        )
        svc = (base / "RptVpnService.kt").read_text(encoding="utf-8")
        engine = (base / "RptClientEngine.kt").read_text(encoding="utf-8")
        self.assertIn('addRoute("0.0.0.0", 0)', svc)
        self.assertIn("RptVpnService", svc)
        self.assertIn("fullTunnel", svc)
        self.assertIn("engine.handshake", svc)
        self.assertIn("engine.sealPacket", svc)
        self.assertIn("inTun.read(buf)", svc)
        self.assertNotIn("inTun.available()", svc)
        self.assertIn("fun handshake", engine)
        self.assertIn("fun sealPacket", engine)

    def test_ios_mac_prep(self):
        self.assertTrue((ROOT / "client_app" / "ios" / "BUILD_ON_MAC.md").is_file())
        self.assertTrue((ROOT / "client_app" / "macos" / "BUILD_ON_MAC.md").is_file())
        self.assertTrue((ROOT / "client_app" / "ios").is_dir())
        self.assertTrue((ROOT / "client_app" / "macos").is_dir())


if __name__ == "__main__":
    unittest.main()
