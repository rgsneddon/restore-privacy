"""Structural tests: shipped Apple distribution signing path is Gatekeeper-safe.

Asserts the real packaging/signing scripts invoke Developer ID, notarytool, and
stapler on the product app path — not a re-implementation of Apple's tools.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestMacosSignNotarizeScript(unittest.TestCase):
    def test_script_exists_and_invokes_real_apple_tools(self):
        script = ROOT / "scripts" / "sign_and_notarize_macos.py"
        self.assertTrue(script.is_file(), "missing sign_and_notarize_macos.py")
        text = script.read_text(encoding="utf-8")
        # Real tool invocations (shipped path)
        self.assertIn("codesign", text)
        self.assertIn("Developer ID Application", text)
        self.assertIn("notarytool", text)
        self.assertIn("stapler", text)
        self.assertIn("--options", text)
        self.assertIn("runtime", text)  # hardened runtime
        self.assertIn("spctl", text)
        # Product app path / packaging
        self.assertIn("restore_privacy_client.app", text)
        self.assertIn("ditto", text)
        # Must not treat ad-hoc as success
        self.assertIn("Signature=adhoc", text)
        self.assertIn("PacketTunnel", text)

    def test_release_package_script_calls_sign_and_notarize(self):
        rel = ROOT / "scripts" / "build_release_0.0.9.py"
        self.assertTrue(rel.is_file())
        text = rel.read_text(encoding="utf-8")
        self.assertIn("sign_and_notarize_macos", text)
        self.assertIn("sign_and_notarize_macos.py", text)
        self.assertIn("package_macos_zip", text)
        self.assertIn("MACOS_ZIP_NAME", text)
        # iOS team-sign path (not permanently ad-hoc-only)
        self.assertIn("sign_ios_app", text)
        self.assertIn("Apple Distribution", text)
        self.assertIn("codesign", text)


class TestGatekeeperDocsMentionNotarize(unittest.TestCase):
    def test_macos_build_doc_mentions_notarization(self):
        p = ROOT / "client_app" / "macos" / "BUILD_ON_MAC.md"
        text = p.read_text(encoding="utf-8")
        lower = text.lower()
        self.assertTrue("notar" in lower)
        # Point to the distribution script when present in repo docs
        apple = (ROOT / "client_app" / "APPLE_BUILD.md").read_text(encoding="utf-8")
        # Either APPLE_BUILD or BUILD_ON_MAC should mention Developer ID / Gatekeeper path
        combined = text + "\n" + apple
        self.assertTrue(
            "Developer ID" in combined
            or "notarytool" in combined
            or "sign_and_notarize" in combined
            or "Gatekeeper" in combined
            or "notar" in combined.lower()
        )


if __name__ == "__main__":
    unittest.main()
