"""macOS Debug/first-run residual pin packaging: DE monopin on Connect search path.

Drives the real inject_apple_secrets script and asserts the shipped Xcode
Runner path always injects public pins (never node_elgamal.priv).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INJECT = ROOT / "scripts" / "inject_apple_secrets.py"
PRODUCT = ROOT / "product"
DE_HOST = "178.105.187.178"
DE_PUB = "de_node_elgamal.pub"
NODE_PUB = "node_elgamal.pub"
EXIT_PUB = "exit_node_elgamal.pub"
US_PUB = "us_node_elgamal.pub"  # retired — must not stage/inject
FORBIDDEN = "node_elgamal.priv"
# Live catalog residual public pins only (matches inject_apple_secrets.PUBLIC_PUBS).
PUBLICS = (NODE_PUB, DE_PUB, EXIT_PUB)


class TestMacosResidualPinPath(unittest.TestCase):
    def test_product_monopin_has_de_and_entry_pubs(self):
        for name in (NODE_PUB, DE_PUB):
            p = PRODUCT / name
            self.assertTrue(p.is_file(), name)
            self.assertGreaterEqual(p.stat().st_size, 32, name)
            self.assertEqual(p.stat().st_size, 256, f"{name} product size")
        self.assertFalse((PRODUCT / FORBIDDEN).is_file())

    def test_runner_secrets_stage_public_only(self):
        staged = ROOT / "client_app" / "macos" / "Runner" / "secrets"
        self.assertTrue(staged.is_dir(), "macos/Runner/secrets must be staged")
        for name in PUBLICS:
            p = staged / name
            self.assertTrue(p.is_file(), name)
            self.assertGreaterEqual(p.stat().st_size, 32, name)
        self.assertFalse((staged / FORBIDDEN).exists())
        # Retired US monopin must not be staged as package material
        self.assertFalse(
            (staged / US_PUB).exists(),
            f"retired {US_PUB} must not be in macos/Runner/secrets",
        )
        # Match product DE pin bytes (no stale pin)
        self.assertEqual(
            (staged / DE_PUB).read_bytes(),
            (PRODUCT / DE_PUB).read_bytes(),
        )

    def test_xcode_runner_has_inject_residual_pubs_phase(self):
        pbx = (
            ROOT
            / "client_app"
            / "macos"
            / "Runner.xcodeproj"
            / "project.pbxproj"
        ).read_text(encoding="utf-8")
        self.assertIn("Inject residual public pins", pbx)
        self.assertIn("inject_residual_pubs.sh", pbx)
        self.assertIn("de_node_elgamal.pub", pbx)
        sh = ROOT / "client_app" / "macos" / "scripts" / "inject_residual_pubs.sh"
        self.assertTrue(sh.is_file())
        body = sh.read_text(encoding="utf-8")
        self.assertIn("inject_apple_secrets.py", body)
        self.assertIn("node_elgamal.priv", body)  # forbidden check
        self.assertIn("de_node_elgamal.pub", body)

    def test_inject_from_product_places_de_pin_on_search_path(self):
        """Real inject entry point → Contents/Resources/secrets/de_node_elgamal.pub."""
        self.assertTrue(INJECT.is_file())
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / "restore_privacy_client.app"
            (app / "Contents" / "Resources").mkdir(parents=True)
            # Fake PacketTunnel layout (inject also targets PlugIns)
            ape = (
                app
                / "Contents"
                / "PlugIns"
                / "PacketTunnel.appex"
                / "Contents"
                / "Resources"
            )
            ape.mkdir(parents=True)
            r = subprocess.run(
                [
                    sys.executable,
                    str(INJECT),
                    "--app",
                    str(app),
                    "--source",
                    str(PRODUCT),
                ],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = app / "Contents" / "Resources" / "secrets"
            for name in PUBLICS:
                pin = dest / name
                self.assertTrue(pin.is_file(), f"missing {name}\n{r.stdout}")
                self.assertGreaterEqual(pin.stat().st_size, 32, name)
            self.assertFalse(
                (dest / US_PUB).exists(),
                f"retired {US_PUB} must not be injected\n{r.stdout}",
            )
            self.assertFalse((dest / FORBIDDEN).exists())
            self.assertFalse((dest / "client_ed25519.priv").exists())
            # DE pin matches product monopin (Connect default residual host)
            self.assertEqual(
                (dest / DE_PUB).read_bytes(),
                (PRODUCT / DE_PUB).read_bytes(),
            )
            # PacketTunnel also receives DE pin; no US
            ape_sec = (
                app
                / "Contents"
                / "PlugIns"
                / "PacketTunnel.appex"
                / "Contents"
                / "Resources"
                / "secrets"
            )
            ape_pin = ape_sec / DE_PUB
            self.assertTrue(ape_pin.is_file(), "PacketTunnel missing de pin")
            self.assertFalse(
                (ape_sec / US_PUB).exists(),
                "PacketTunnel must not get retired US pin",
            )

    def test_dart_and_swift_map_de_host_to_de_pub(self):
        dart = (
            ROOT / "client_app" / "lib" / "country_select.dart"
        ).read_text(encoding="utf-8")
        self.assertIn(DE_HOST, dart)
        self.assertIn(DE_PUB, dart)
        # residualNodePubNameForHost(DE host) → de_node_elgamal.pub in shipped Dart
        # (exercised by client_app/test/country_select_pub_test.dart).
        self.assertIn("residualNodePubNameForHost", dart)
        self.assertRegex(
            dart,
            r"residualNodePubNameForHost[\s\S]{0,1200}de_node_elgamal\.pub",
        )
        for rel in (
            "client_app/macos/NativePrep/RptSecrets.swift",
            "client_app/apple_shared/Rpt2/Sources/Rpt2/RptSecrets.swift",
        ):
            sw = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(f'"{DE_PUB}"', sw, rel)
            self.assertIn(DE_HOST, sw, rel)
            self.assertIn("deNodePubName", sw, rel)


if __name__ == "__main__":
    unittest.main()
