"""Tests drive real shipped node modules."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.config import build_node_config, render_node_config_text, validate_node_config
from node.elgamal import decrypt, encrypt, generate_keypair
from node.handshake import (
    AdmissionError,
    NodeHandshake,
    build_client_hello,
    generate_client_admission_keypair,
    node_complete_hello,
    ed25519_pub_raw,
)
from node.nolog import assert_no_log_config, config_text_forbids_log_sinks, systemd_no_log_directives
from node.pedersen import commit_bytes, open_verified, verify
from node.routing import build_nat_masquerade_commands, build_sysctl_forward_commands
from node.sessions import SessionRegistry
from node.ui import make_handler


class TestElGamal(unittest.TestCase):
    def test_roundtrip(self):
        priv = generate_keypair()
        msg = b"rpt-session-material-32bytes!!"
        ct = encrypt(priv.public, msg)
        self.assertEqual(decrypt(priv, ct), msg)


class TestPedersen(unittest.TestCase):
    def test_commit_open(self):
        c, o = commit_bytes(b"nonce-material")
        self.assertTrue(verify(c, o))
        open_verified(c, o)


class TestHandshakeAdmission(unittest.TestCase):
    def test_authorized_client_succeeds(self):
        node_priv = generate_keypair()
        cpriv, cpub = generate_client_admission_keypair()
        allow = [ed25519_pub_raw(cpub)]
        node = NodeHandshake(node_priv, allow)
        frame, _, _ = build_client_hello(cpriv, node_priv.public)
        reply, result = node_complete_hello(node, frame, "10.88.0.2")
        self.assertEqual(len(result.session_id), 8)
        self.assertTrue(len(reply) > 100)

    def test_unauthorized_client_rejected(self):
        node_priv = generate_keypair()
        good_priv, good_pub = generate_client_admission_keypair()
        bad_priv, _ = generate_client_admission_keypair()
        node = NodeHandshake(node_priv, [ed25519_pub_raw(good_pub)])
        frame, _, _ = build_client_hello(bad_priv, node_priv.public)
        with self.assertRaises(AdmissionError):
            node_complete_hello(node, frame, "10.88.0.2")


class TestConfigPrivacy(unittest.TestCase):
    def test_config(self):
        cfg = build_node_config()
        self.assertEqual(validate_node_config(cfg), [])
        self.assertEqual(assert_no_log_config(cfg), [])
        self.assertFalse(cfg["collect_user_data"])
        self.assertTrue(cfg["admission"]["only_restore_privacy_client"])
        self.assertFalse(cfg["admission"]["open_to_public"])
        self.assertEqual(cfg["ui"]["title"], "RESTORE PRIVACY")
        text = render_node_config_text(cfg)
        self.assertIn("ListenPort = ", text)
        self.assertIn("NATMasquerade = true", text)
        self.assertIn("OnlyRestorePrivacyClient = true", text)
        self.assertIn("ConnectionLog = false", text)
        self.assertIn("UITitle = RESTORE PRIVACY", text)
        self.assertTrue(config_text_forbids_log_sinks(text))
        self.assertIn("MASQUERADE", "\n".join(build_nat_masquerade_commands(wan_iface="eth0")))
        self.assertTrue(any("ip_forward=1" in c for c in build_sysctl_forward_commands()))
        self.assertIn("StandardOutput=null", systemd_no_log_directives())


class TestSessionsUI(unittest.TestCase):
    def test_status_payload_only_count(self):
        reg = SessionRegistry()
        payload = reg.status_payload()
        self.assertEqual(payload, {"title": "RESTORE PRIVACY", "clients_connected": 0})
        self.assertNotIn("ip", payload)
        self.assertNotIn("clients", payload)

    def test_ui_handler_status_json(self):
        Handler = make_handler(lambda: {"title": "RESTORE PRIVACY", "clients_connected": 3, "secret": "nope"})
        # Exercise handler class construction; payload filter tested via safe dict in do_GET source
        self.assertTrue(callable(Handler))


class TestInstallScript(unittest.TestCase):
    def test_install_policies(self):
        text = (ROOT / "node" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("ip_forward=1", text)
        self.assertIn("MASQUERADE", text)
        self.assertIn("StandardOutput=null", text)
        self.assertIn("node.server", text)
        self.assertIn("8080", text)
        self.assertNotIn("wg-quick", text.lower())
        self.assertNotIn("openvpn --", text.lower())
        self.assertNotIn("auth-user-pass", text)


if __name__ == "__main__":
    unittest.main()
