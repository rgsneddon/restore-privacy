"""Native residual pad/cover + outer obfuscation parity with Python wire."""

from __future__ import annotations

import hashlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from node.obfuscation import (  # noqa: E402
    OBFS_VERSION,
    looks_like_bare_rpt,
    looks_like_obfs,
    unwrap_frame,
    wrap_frame,
)
from node.traffic_shape import (  # noqa: E402
    COVER_MAGIC,
    PAD_MAGIC,
    make_cover_payload,
    pad_payload,
    unpad_payload,
)

KT_ENGINE = (
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
KT_SHAPE = (
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
    / "RptTrafficShape.kt"
)
KT_OBFS = (
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
    / "RptObfuscation.kt"
)
KT_VPN = (
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
    / "RptVpnService.kt"
)
SWIFT_SHARED = ROOT / "client_app" / "apple_shared" / "Rpt2" / "Sources" / "Rpt2"
SWIFT_IOS = ROOT / "client_app" / "ios" / "NativePrep" / "Rpt2" / "RptClientEngine.swift"
SWIFT_MAC = ROOT / "client_app" / "macos" / "NativePrep" / "Rpt2" / "RptClientEngine.swift"


def _assert_shape_source(text: str, case: unittest.TestCase, label: str) -> None:
    case.assertIn("RPTP", text, label)
    case.assertIn("RPTC", text, label)
    case.assertIn("padPayload", text, label)
    case.assertIn("makeCoverPayload", text, label)
    case.assertIn("unpadPayload", text, label)
    case.assertIn("128", text, label)  # product bucket


def _assert_obfs_source(text: str, case: unittest.TestCase, label: str) -> None:
    case.assertIn("0x52505431", text.replace("_", ""), label)  # RPT1 version
    case.assertIn("RPT-OBFS-LAYER-v1", text, label)
    case.assertIn("wrapFrame", text, label)
    case.assertIn("unwrapFrame", text, label)
    case.assertIn("maybeWrap", text, label)
    case.assertIn("maybeUnwrap", text, label)


class TestAndroidTrafficShapeAndObfs(unittest.TestCase):
    def test_helpers_exist_and_engine_wires(self):
        self.assertTrue(KT_SHAPE.is_file())
        self.assertTrue(KT_OBFS.is_file())
        shape = KT_SHAPE.read_text(encoding="utf-8")
        obfs = KT_OBFS.read_text(encoding="utf-8")
        eng = KT_ENGINE.read_text(encoding="utf-8")
        vpn = KT_VPN.read_text(encoding="utf-8")
        _assert_shape_source(shape, self, "android shape")
        _assert_obfs_source(obfs, self, "android obfs")
        self.assertIn("RptTrafficShape.prepareOutbound", eng)
        self.assertIn("sealCoverFrame", eng)
        self.assertIn("sealAndWrapPacket", eng)
        self.assertIn("unwrapAndOpen", eng)
        self.assertIn("RptObfuscation.maybeWrap", eng)
        # VPN dataplane uses wrap + cover timer
        self.assertIn("sealAndWrapPacket", vpn)
        self.assertIn("unwrapAndOpen", vpn)
        self.assertIn("sealAndWrapCover", vpn)
        self.assertIn("PRODUCT_COVER_INTERVAL_MS", vpn)

    def test_python_pad_cover_wire_contract(self):
        """Shipped Python pad/cover (what native mirrors) round-trips."""
        ip = b"\x45" + b"\x00" * 40
        padded = pad_payload(ip, bucket=128)
        self.assertTrue(padded.startswith(PAD_MAGIC))
        self.assertGreater(len(padded), len(ip))
        plain, is_cover = unpad_payload(padded)
        self.assertFalse(is_cover)
        self.assertEqual(plain, ip)
        cover = make_cover_payload(128)
        self.assertTrue(cover.startswith(COVER_MAGIC))
        p2, is_c = unpad_payload(cover)
        self.assertTrue(is_c)
        self.assertEqual(p2, b"")

    def test_python_obfs_wire_contract(self):
        inner = b"RPT2" + bytes([0x03]) + b"\xab" * 40
        outer = wrap_frame(inner)
        self.assertFalse(looks_like_bare_rpt(outer))
        self.assertTrue(looks_like_obfs(outer))
        self.assertEqual(struct.unpack("!I", outer[1:5])[0], OBFS_VERSION)
        self.assertEqual(unwrap_frame(outer), inner)
        # bare still accepted
        self.assertEqual(unwrap_frame(inner, allow_bare=True), inner)


class TestAppleTrafficShapeAndObfs(unittest.TestCase):
    def test_apple_shared_helpers(self):
        shape = (SWIFT_SHARED / "RptTrafficShape.swift").read_text(encoding="utf-8")
        obfs = (SWIFT_SHARED / "RptObfuscation.swift").read_text(encoding="utf-8")
        eng = (SWIFT_SHARED / "RptClientEngine.swift").read_text(encoding="utf-8")
        _assert_shape_source(shape, self, "apple_shared shape")
        _assert_obfs_source(obfs, self, "apple_shared obfs")
        self.assertIn("RptTrafficShape.prepareOutbound", eng)
        self.assertIn("RptObfuscation.maybeWrap", eng)
        self.assertIn("sealCoverFrame", eng)
        self.assertIn("sendCoverFrame", eng)
        self.assertIn("openPacketAllowCover", eng)

    def test_ios_nativeprep_product_wired(self):
        self.assertTrue(SWIFT_IOS.is_file())
        text = SWIFT_IOS.read_text(encoding="utf-8")
        _assert_shape_source(text, self, "ios NativePrep")
        _assert_obfs_source(text, self, "ios NativePrep")
        self.assertIn("|pfs-x25519|", text)
        self.assertIn("RptTrafficShape.prepareOutbound", text)
        self.assertIn("RptObfuscation.maybeWrap", text)
        # Must not be legacy-only session IKM
        self.assertNotIn(
            "sessionSharedMaterial.append(clientPub)\n"
            "        let sessionShared = Data(SHA256.hash(data: sessionSharedMaterial))",
            text,
        )

    def test_macos_nativeprep_product_wired(self):
        self.assertTrue(SWIFT_MAC.is_file())
        text = SWIFT_MAC.read_text(encoding="utf-8")
        _assert_shape_source(text, self, "macos NativePrep")
        _assert_obfs_source(text, self, "macos NativePrep")
        self.assertIn("|pfs-x25519|", text)
        self.assertIn("RptTrafficShape.prepareOutbound", text)
        self.assertIn("RptObfuscation.maybeWrap", text)

    def test_ios_macos_nativeprep_engines_match(self):
        ios = SWIFT_IOS.read_bytes()
        mac = SWIFT_MAC.read_bytes()
        self.assertEqual(
            hashlib.sha256(ios).hexdigest(),
            hashlib.sha256(mac).hexdigest(),
            "iOS and macOS NativePrep residual engines must stay aligned",
        )


class TestNativeObfsKeyMatchesPython(unittest.TestCase):
    def test_product_obfs_key_constant_in_native(self):
        """Native sources embed the same public product obfs key material as Python."""
        from node import obfuscation as obfs_mod

        py_key = obfs_mod._PRODUCT_OBFS_KEY
        self.assertGreaterEqual(len(py_key), 24)
        self.assertTrue(py_key.startswith(b"RPT-OBFS-LAYER-v1"))
        for path in (KT_OBFS, SWIFT_SHARED / "RptObfuscation.swift", SWIFT_IOS):
            text = path.read_text(encoding="utf-8")
            self.assertIn("RPT-OBFS-LAYER-v1", text, str(path))
            # Trailing key bytes present (Kotlin 0x9a / Swift 0x9a)
            self.assertTrue(
                "0x9a" in text.lower() or "0X9A" in text,
                f"missing key tail bytes in {path}",
            )


if __name__ == "__main__":
    unittest.main()
