"""Native residual engines dual-wire X25519 PFS (product require_pfs compatible)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KT = (
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
    / "RptClientEngine.kt"
)
SWIFT = (
    ROOT
    / "client_app"
    / "apple_shared"
    / "Rpt2"
    / "Sources"
    / "Rpt2"
    / "RptClientEngine.swift"
)
SWIFT_TEST = (
    ROOT
    / "client_app"
    / "apple_shared"
    / "Rpt2"
    / "Tests"
    / "Rpt2Tests"
    / "Rpt2Tests.swift"
)


class TestAndroidPfsWire(unittest.TestCase):
    def test_engine_sends_eph_and_derives_pfs_ikm(self):
        self.assertTrue(KT.is_file(), f"missing {KT}")
        text = KT.read_text(encoding="utf-8")
        # HELLO payload includes eph public
        self.assertIn("generateX25519", text)
        self.assertIn("clientNonce + opening + eph.publicKey", text)
        # Session IKM matches Python derive_pfs_session_shared
        self.assertIn("|pfs-x25519|", text)
        self.assertIn("x25519Shared", text)
        self.assertIn("serverEphPub", text)
        # Must not use legacy-only session shared as sole product path
        self.assertNotIn(
            "val sessionShared = sha256(clientNonce + serverNonce + sid + clientPub)",
            text,
        )
        self.assertIn("product requires PFS", text)
        self.assertIn("scalarMultBase", text)


class TestApplePfsWire(unittest.TestCase):
    def test_engine_sends_eph_and_derives_pfs_ikm(self):
        self.assertTrue(SWIFT.is_file(), f"missing {SWIFT}")
        text = SWIFT.read_text(encoding="utf-8")
        self.assertIn("Curve25519.KeyAgreement.PrivateKey", text)
        self.assertIn("pendingClientEph", text)
        self.assertIn("opening.export() + ephPub", text)
        self.assertIn("|pfs-x25519|", text)
        self.assertIn("sharedSecretFromKeyAgreement", text)
        self.assertIn("product requires PFS", text)
        self.assertIn("pfs: true", text)
        # Legacy-only materialization should not be the sole path
        self.assertNotIn(
            "sessionSharedMaterial.append(clientPub)\n        let sessionShared = Data(SHA256.hash(data: sessionSharedMaterial))",
            text,
        )

    def test_mock_node_hello_includes_server_eph(self):
        self.assertTrue(SWIFT_TEST.is_file())
        text = SWIFT_TEST.read_text(encoding="utf-8")
        self.assertIn("serverEphPub", text)
        self.assertIn("clientEphPub", text)
        self.assertIn("session.pfs", text)


if __name__ == "__main__":
    unittest.main()
