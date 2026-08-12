"""Suite monopin 1.2.1 catalog + handoff pins (shipped sources)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()


class TestSuiteMonopin121(unittest.TestCase):
    def test_version_file_is_1_2_1(self) -> None:
        self.assertEqual(VERSION, "1.2.1")

    def test_downloads_catalog_pin(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            RELEASE_TAG,
            list_catalog_platform_packages,
        )

        self.assertEqual(RELEASE_VERSION, "1.2.1")
        self.assertEqual(RELEASE_TAG, "1.2.1")
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], "1.2.1")
            self.assertIn("1.2.1", p["filename"])
            self.assertTrue(
                p["filename"].startswith("restore-privacy-client-1.2.1-")
            )

    def test_suite_version_dart_pin(self) -> None:
        dart = (ROOT / "client_app" / "lib" / "suite_version.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kSuiteVersion = '1.2.1'", dart)

    def test_pubspec_pin(self) -> None:
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 1.2.1+", pub)

    def test_rpt_config_product_version(self) -> None:
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("productVersion = '1.2.1'", cfg)

    def test_windows_handoff_1_2_1_exists(self) -> None:
        h = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.2.1.md"
        self.assertTrue(h.is_file(), f"missing {h}")
        text = h.read_text(encoding="utf-8")
        self.assertIn("1.2.1", text)
        self.assertIn(
            "restore-privacy-client-1.2.1-windows-x64-setup.exe", text
        )

    def test_build_suite_1_2_1_exists(self) -> None:
        script = ROOT / "scripts" / "build_suite_1.2.1.py"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn('VERSION = "1.2.1"', text)
        self.assertIn("1.2.0", text)  # carry-forward prior
        # iOS IPA + fail-closed provision path retained
        self.assertIn("ios_sideload_package", text)
        self.assertIn("embedded.mobileprovision", text)

    def test_ios_sideload_package_helper_present(self) -> None:
        helper = ROOT / "scripts" / "ios_sideload_package.py"
        self.assertTrue(helper.is_file())
        text = helper.read_text(encoding="utf-8")
        self.assertIn("package_ios_ipa_zip", text)
        self.assertIn("require_installable_ios_zip", text)
        self.assertIn("Payload", text)

    def test_residual_trial_claim_and_post_attach_in_tree(self) -> None:
        """1.2.1 product path must include residual honesty fixes."""
        trial = (ROOT / "client" / "device_trial.py").read_text(encoding="utf-8")
        self.assertIn("claim_remote_device_trial", trial)
        self.assertIn("ensure_remote_trial_for_node_hello", trial)
        tun = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("residual_tunnel_dns_smoke", tun)
        self.assertIn("residual_post_attach_ready", tun)


if __name__ == "__main__":
    unittest.main()
