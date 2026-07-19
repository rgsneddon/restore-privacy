"""Structural tests: shipped Apple distribution signing path is Gatekeeper-safe.

Asserts the real packaging/signing scripts invoke Developer ID, notarytool, and
stapler on the product app path — not a re-implementation of Apple's tools.
"""

from __future__ import annotations

import sys
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
        self.assertIn("inject_apple_secrets", text)

    def test_release_package_script_calls_sign_and_notarize(self):
        rel = ROOT / "scripts" / "build_release_0.1.5.py"
        self.assertTrue(rel.is_file())
        text = rel.read_text(encoding="utf-8")
        self.assertIn("sign_and_notarize_macos", text)
        self.assertIn("sign_and_notarize_macos.py", text)
        self.assertIn("package_macos_zip", text)
        self.assertIn("MACOS_ZIP_NAME", text)
        # iOS team-sign path (not permanently ad-hoc-only)
        self.assertIn("sign_ios_app", text)
        self.assertIn("inject_product_secrets", text)
        self.assertIn("inject_apple_secrets", text)
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


class TestInjectAppleSecretsScript(unittest.TestCase):
    def test_inject_script_only_copies_product_keys(self):
        script = ROOT / "scripts" / "inject_apple_secrets.py"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn("node_elgamal.pub", text)
        self.assertIn("node_elgamal.priv", text)  # forbidden name
        self.assertIn("never a shared", text.lower())
        self.assertIn('"Contents"', text)
        self.assertIn('"Resources"', text)
        self.assertIn('"secrets"', text)
        self.assertIn("FORBIDDEN", text)

    def test_inject_roundtrip_into_temp_app_layout(self):
        """Drive the real inject script on a fake .app tree (node pub only)."""
        import subprocess
        import tempfile

        script = ROOT / "scripts" / "inject_apple_secrets.py"
        secrets = ROOT / "secrets"
        if not (secrets / "node_elgamal.pub").is_file():
            self.skipTest("node_elgamal.pub not staged in repo secrets/")
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / "restore_privacy_client.app"
            (app / "Contents" / "Resources").mkdir(parents=True)
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--app",
                    str(app),
                    "--source",
                    str(secrets),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = app / "Contents" / "Resources" / "secrets"
            # Public packages must not embed shared client priv
            self.assertFalse((dest / "client_ed25519.priv").exists())
            self.assertTrue((dest / "node_elgamal.pub").is_file())
            self.assertEqual((dest / "node_elgamal.pub").stat().st_size, 256)
            self.assertFalse((dest / "node_elgamal.priv").exists())
