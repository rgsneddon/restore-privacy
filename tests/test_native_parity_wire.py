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
        # VPN dataplane uses wrap + cover timer + product jitter
        self.assertIn("sealAndWrapPacket", vpn)
        self.assertIn("unwrapAndOpen", vpn)
        self.assertIn("sealAndWrapCover", vpn)
        self.assertIn("PRODUCT_COVER_INTERVAL_MS", vpn)
        self.assertIn("PRODUCT_COVER", vpn)
        self.assertIn("applySendJitter", eng)
        self.assertIn("PRODUCT_JITTER_MS_MAX", shape)
        self.assertIn("PRODUCT_PADDING: Boolean = true", shape)
        self.assertIn("PRODUCT_COVER: Boolean = true", shape)

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
        self.assertIn("applySendJitter", eng)
        self.assertIn("productJitterMsMax", shape)

    def test_ios_nativeprep_product_wired(self):
        self.assertTrue(SWIFT_IOS.is_file())
        text = SWIFT_IOS.read_text(encoding="utf-8")
        _assert_shape_source(text, self, "ios NativePrep")
        _assert_obfs_source(text, self, "ios NativePrep")
        self.assertIn("|pfs-x25519|", text)
        self.assertIn("RptTrafficShape.prepareOutbound", text)
        self.assertIn("RptObfuscation.maybeWrap", text)
        self.assertIn("applySendJitter", text)
        self.assertIn("productJitterMsMax", text)
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
        self.assertIn("applySendJitter", text)
        self.assertIn("productJitterMsMax", text)

    def test_ios_macos_nativeprep_engines_match(self):
        ios = SWIFT_IOS.read_bytes()
        mac = SWIFT_MAC.read_bytes()
        self.assertEqual(
            hashlib.sha256(ios).hexdigest(),
            hashlib.sha256(mac).hexdigest(),
            "iOS and macOS NativePrep residual engines must stay aligned",
        )

    def test_apple_packet_tunnel_residual_defaults(self):
        """Packet Tunnel residual loops use pad/wrap/cover + cover-tolerant open."""
        for rel in (
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("sendSealedPacket", text, rel)
            self.assertIn("openPacketAllowCover", text, rel)
            self.assertIn("startCoverTraffic", text, rel)
            self.assertIn("sendCoverFrame", text, rel)
            self.assertIn("productCover", text, rel)
            self.assertIn("productCoverIntervalS", text, rel)
            # Must not hard-open cover as IP (throws / tears tunnel)
            self.assertNotIn(
                "let plain = try engine.openPacket(data)",
                text,
                msg=f"{rel} must use openPacketAllowCover on residual inbound",
            )


class TestNativeObfsKeyMatchesPython(unittest.TestCase):
    def test_product_obfs_key_constant_in_native(self):
        """Native sources embed the *exact* product obfs key as Python (len + pad)."""
        from node import obfuscation as obfs_mod

        py_key = obfs_mod._PRODUCT_OBFS_KEY
        # Contract: RPT-OBFS-LAYER-v1 (17) + 8 NUL + 8 tail = 33
        self.assertEqual(len(py_key), 33, "Python product obfs key length")
        self.assertTrue(py_key.startswith(b"RPT-OBFS-LAYER-v1"))
        self.assertEqual(py_key[17:25], b"\x00" * 8)
        self.assertEqual(py_key[25:], bytes([0x9A, 0x3C, 0x7E, 0x11, 0xD4, 0x55, 0x88, 0x02]))

        # Kotlin: 8 explicit \\u0000 after prefix in string literal
        kt = KT_OBFS.read_text(encoding="utf-8")
        self.assertIn("RPT-OBFS-LAYER-v1", kt)
        # Count consecutive \u0000 in the key string (must be 8, not 7)
        import re

        m = re.search(
            r'RPT-OBFS-LAYER-v1((?:\\u0000)+)',
            kt,
        )
        self.assertIsNotNone(m, "Kotlin PRODUCT_OBFS_KEY missing NUL pad sequence")
        nuls = m.group(1).count("\\u0000")
        self.assertEqual(nuls, 8, f"Kotlin NUL pad must be 8 (got {nuls}) to match Python key len 33")
        self.assertIn("0x9a", kt.lower())

        # Swift apple_shared + NativePrep: Data(repeating: 0, count: 8)
        for path in (
            SWIFT_SHARED / "RptObfuscation.swift",
            SWIFT_IOS,
            SWIFT_MAC,
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("RPT-OBFS-LAYER-v1", text, str(path))
            self.assertIn(
                "Data(repeating: 0, count: 8)",
                text,
                f"{path} must pad with 8 NULs (not 7) for Python interop",
            )
            self.assertNotIn(
                "Data(repeating: 0, count: 7)",
                text,
                f"{path} must not use 7-NUL pad (breaks obfs interop)",
            )
            self.assertIn("0x9a", text.lower(), str(path))
            # Explicit length contract comment or assert where present
            if "assert(k.count" in text:
                self.assertIn("assert(k.count == 33)", text, str(path))


if __name__ == "__main__":
    unittest.main()
