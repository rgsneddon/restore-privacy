"""Lean residual + C++ residual_core continue (low-ping product defaults).

Drives shipped ProductSettings / product_policy defaults and structural rules:
C++ residual_core owns pure crypto; no Dart residual AEAD dataplane.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestLeanResidualDefaults(unittest.TestCase):
    def test_flutter_product_settings_lean_off(self) -> None:
        src = (ROOT / "client_app" / "lib" / "settings_store.dart").read_text(
            encoding="utf-8"
        )
        # Constructor defaults in ProductSettings
        self.assertIn("this.privacyTrafficShape = false", src)
        self.assertIn("this.privacyOuterObfuscation = false", src)
        self.assertIn("this.privacyMultihop = false", src)
        from pathlib import Path as P

        # Load defaults via pure structural parse is not enough — also drive
        # Python product_policy which shares the lean contract.
        from client.product_policy import PrivacyScalePrefs, resolve_privacy_policy

        d = PrivacyScalePrefs()
        self.assertFalse(d.traffic_shape)
        self.assertFalse(d.outer_obfuscation)
        self.assertFalse(d.multihop)
        scale = resolve_privacy_policy(prefs=d)
        self.assertFalse(scale.traffic_shape_enabled)
        self.assertFalse(scale.outer_obfuscation_enabled)
        self.assertFalse(scale.multihop_enabled)

    def test_rpt_config_default_residual_udp_port(self) -> None:
        src = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("static const int port = 44044", src)
        self.assertNotIn("static const int port = 443", src)


class TestNoDartDataplane(unittest.TestCase):
    def test_vpn_controller_is_method_channel_bridge_only(self) -> None:
        src = (ROOT / "client_app" / "lib" / "vpn_controller.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("MethodChannel", src)
        self.assertIn("restore_privacy/vpn", src)
        # No residual wire AEAD in Dart controller
        low = src.lower()
        self.assertNotIn("chacha20", low)
        self.assertNotIn("poly1305", low)
        self.assertNotIn("rawdatagramsocket", low)
        self.assertNotIn("x25519", low)

    def test_client_app_lib_has_no_residual_udp_aead_loop(self) -> None:
        lib = ROOT / "client_app" / "lib"
        hits: list[str] = []
        for p in lib.rglob("*.dart"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(
                r"RawDatagramSocket|InternetAddress\.lookup.*44044",
                text,
            ):
                hits.append(str(p.relative_to(ROOT)))
            if "ChaCha20Poly1305" in text or "chacha20_poly1305" in text:
                # Licence/docs may mention AEAD by name; disallow seal loops
                if "seal" in text.lower() and "session" in text.lower():
                    if "full_end_user_licence" not in str(p):
                        hits.append(f"aead:{p.relative_to(ROOT)}")
        self.assertEqual(hits, [], f"unexpected Dart residual dataplane: {hits}")


class TestResidualCoreCppPresent(unittest.TestCase):
    def test_shipped_cpp_primitives_exist(self) -> None:
        core = ROOT / "residual_core"
        for rel in (
            "include/residual_core/x25519.hpp",
            "include/residual_core/aead.hpp",
            "include/residual_core/pfs.hpp",
            "include/residual_core/protocol.hpp",
            "include/residual_core/lean_residual.hpp",
            "src/x25519.cpp",
            "src/aead.cpp",
            "src/c_api.cpp",
        ):
            self.assertTrue((core / rel).is_file(), rel)

    def test_lean_residual_header_defaults(self) -> None:
        text = (
            ROOT / "residual_core" / "include" / "residual_core" / "lean_residual.hpp"
        ).read_text(encoding="utf-8")
        self.assertIn("traffic_shape = false", text)
        self.assertIn("outer_obfuscation = false", text)
        self.assertIn("multihop = false", text)
        self.assertIn("kResidualUdpPort = 44044", text)
        self.assertIn("kNoDartDataplaneRule", text)

    def test_residual_core_tests_binary_pass(self) -> None:
        exe = ROOT / "residual_core" / "build" / "residual_core_tests"
        if not exe.is_file():
            self.skipTest("residual_core_tests not built")
        r = subprocess.run(
            [str(exe)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ALL_PASS residual_core", r.stdout)
        self.assertIn("lean default traffic_shape off", r.stdout)
        self.assertIn("C ABI seal length", r.stdout)


if __name__ == "__main__":
    unittest.main()
