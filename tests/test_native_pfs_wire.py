"""Native residual engines dual-wire X25519 PFS (product require_pfs compatible).

Covers product-wired paths:
- Android Kotlin engine
- apple_shared package sources
- iOS NativePrep (Xcode compiles this for residual Packet Tunnel)
- macOS NativePrep (same for macOS residual)
"""

from __future__ import annotations

import hashlib
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
SWIFT_SHARED = (
    ROOT
    / "client_app"
    / "apple_shared"
    / "Rpt2"
    / "Sources"
    / "Rpt2"
    / "RptClientEngine.swift"
)
SWIFT_IOS_NATIVEPREP = (
    ROOT
    / "client_app"
    / "ios"
    / "NativePrep"
    / "Rpt2"
    / "RptClientEngine.swift"
)
SWIFT_MACOS_NATIVEPREP = (
    ROOT
    / "client_app"
    / "macos"
    / "NativePrep"
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

# Legacy-only session IKM line that must not be the product path
_LEGACY_SWIFT_SESSION = (
    "sessionSharedMaterial.append(clientPub)\n"
    "        let sessionShared = Data(SHA256.hash(data: sessionSharedMaterial))"
)
_LEGACY_KT_SESSION = (
    "val sessionShared = sha256(clientNonce + serverNonce + sid + clientPub)"
)


def _assert_swift_pfs_engine(path: Path, case: unittest.TestCase) -> None:
    case.assertTrue(path.is_file(), f"missing product-wired engine: {path}")
    text = path.read_text(encoding="utf-8")
    case.assertIn("Curve25519.KeyAgreement.PrivateKey", text)
    case.assertIn("pendingClientEph", text)
    case.assertIn("opening.export() + ephPub", text)
    case.assertIn("|pfs-x25519|", text)
    case.assertIn("sharedSecretFromKeyAgreement", text)
    case.assertIn("product requires PFS", text)
    case.assertIn("pfs: true", text)
    case.assertNotIn(_LEGACY_SWIFT_SESSION, text)
    # Must not build hybrid as nonce+opening only without eph
    case.assertNotIn(
        "let payload = clientNonce + opening.export()\n        let hybrid",
        text,
    )


class TestAndroidPfsWire(unittest.TestCase):
    def test_engine_sends_eph_and_derives_pfs_ikm(self):
        self.assertTrue(KT.is_file(), f"missing {KT}")
        text = KT.read_text(encoding="utf-8")
        self.assertIn("generateX25519", text)
        self.assertIn("clientNonce + opening + eph.publicKey", text)
        self.assertIn("|pfs-x25519|", text)
        self.assertIn("x25519Shared", text)
        self.assertIn("serverEphPub", text)
        self.assertNotIn(_LEGACY_KT_SESSION, text)
        self.assertIn("product requires PFS", text)
        self.assertIn("scalarMultBase", text)


class TestAppleSharedPfsWire(unittest.TestCase):
    def test_engine_sends_eph_and_derives_pfs_ikm(self):
        _assert_swift_pfs_engine(SWIFT_SHARED, self)

    def test_mock_node_hello_includes_server_eph(self):
        self.assertTrue(SWIFT_TEST.is_file())
        text = SWIFT_TEST.read_text(encoding="utf-8")
        self.assertIn("serverEphPub", text)
        self.assertIn("clientEphPub", text)
        self.assertIn("session.pfs", text)


class TestIosNativePrepPfsWire(unittest.TestCase):
    """Product-wired iOS residual engine (Xcode compiles NativePrep, not only apple_shared)."""

    def test_ios_nativeprep_has_pfs_dual_wire(self):
        _assert_swift_pfs_engine(SWIFT_IOS_NATIVEPREP, self)

    def test_ios_nativeprep_includes_pad_cover_obfs(self):
        """NativePrep embeds pad/cover/obfs (merged into engine for Xcode compile)."""
        text = SWIFT_IOS_NATIVEPREP.read_text(encoding="utf-8")
        self.assertIn("RPTP", text)
        self.assertIn("RPTC", text)
        self.assertIn("RptObfuscation", text)
        self.assertIn("maybeWrap", text)


class TestMacosNativePrepPfsWire(unittest.TestCase):
    """Product-wired macOS residual engine (Xcode compiles NativePrep)."""

    def test_macos_nativeprep_has_pfs_dual_wire(self):
        _assert_swift_pfs_engine(SWIFT_MACOS_NATIVEPREP, self)

    def test_macos_nativeprep_matches_ios_nativeprep(self):
        ios = SWIFT_IOS_NATIVEPREP.read_bytes()
        mac = SWIFT_MACOS_NATIVEPREP.read_bytes()
        self.assertEqual(
            hashlib.sha256(ios).hexdigest(),
            hashlib.sha256(mac).hexdigest(),
            "iOS and macOS NativePrep residual engines must stay aligned",
        )


if __name__ == "__main__":
    unittest.main()
