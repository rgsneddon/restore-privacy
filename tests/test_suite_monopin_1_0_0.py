"""Suite monopin 1.0.0 is the project-wide current catalog pin."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

SUITE_PIN = "1.0.0"


class TestSuiteMonopin100(unittest.TestCase):
    def test_client_version_file_is_1_0_0(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(pin, SUITE_PIN)

    def test_downloads_release_and_current_catalog_are_1_0_0(self) -> None:
        from downloads import (
            RELEASE_TAG,
            RELEASE_VERSION,
            current_catalog_version,
            list_catalog_platform_packages,
            render_download_section_html,
        )

        self.assertEqual(RELEASE_VERSION, SUITE_PIN)
        self.assertEqual(RELEASE_TAG, SUITE_PIN)
        self.assertEqual(current_catalog_version(), SUITE_PIN)
        pkgs = list_catalog_platform_packages(version=SUITE_PIN)
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], SUITE_PIN)
            self.assertIn(f"-{SUITE_PIN}-", p["filename"])
        html = render_download_section_html()
        for ver in re.findall(
            r"restore-privacy-client-([0-9.]+)-[A-Za-z0-9._-]+", html
        ):
            self.assertEqual(ver, SUITE_PIN)

    def test_public_chrome_and_operator_default_are_1_0_0(self) -> None:
        from public_chrome import PUBLIC_BRAND_DISPLAY, PUBLIC_BRAND_VERSION
        from node.operator_admin import NodeOperatorController

        self.assertEqual(PUBLIC_BRAND_VERSION, SUITE_PIN)
        self.assertIn(SUITE_PIN, PUBLIC_BRAND_DISPLAY)
        ctrl = NodeOperatorController(repo_root=ROOT)
        self.assertEqual(ctrl.catalog_version_default(), SUITE_PIN)

    def test_flutter_and_installer_embed_1_0_0(self) -> None:
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        m = re.search(r"(?m)^version:\s*([0-9.]+)", pub)
        self.assertIsNotNone(m)
        assert m is not None
        self.assertEqual(m.group(1), SUITE_PIN)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"productVersion = '{SUITE_PIN}'", cfg)
        suite = (ROOT / "client_app" / "lib" / "suite_version.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"kSuiteVersion = '{SUITE_PIN}'", suite)
        inst = (ROOT / "client" / "windows" / "installer.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'PRODUCT_VERSION_EMBEDDED = "{SUITE_PIN}"', inst)

    def test_audit_mirrors_and_docs_report_1_0_0_catalog(self) -> None:
        for rel in (
            "AUDIT.md",
            "status_page/AUDIT.md",
            "status_page/public/AUDIT.md",
            "README.md",
            "PRIVACY_POLICY.md",
            "status_page/public/README.md",
            "status_page/public/PRIVACY_POLICY.md",
        ):
            path = ROOT / rel
            self.assertTrue(path.is_file(), rel)
            text = path.read_text(encoding="utf-8")
            if rel.endswith("AUDIT.md"):
                self.assertIn(
                    f"| **Public catalog version** | **{SUITE_PIN}** |",
                    text,
                    rel,
                )
                for ver in re.findall(
                    r"restore-privacy-client-([0-9.]+)-[A-Za-z0-9._-]+", text
                ):
                    self.assertEqual(ver, SUITE_PIN, f"{rel} package {ver}")
                self.assertNotIn("catalog **0.5.9**", text)
                self.assertNotIn("catalog **0.6.0**", text)
                self.assertNotIn("Public catalog version** | **0.5.9**", text)
            else:
                self.assertIn(SUITE_PIN, text, rel)
                # Active catalog lines must not advertise older monopin as current
                self.assertNotRegex(
                    text,
                    r"(?i)catalog\s+(?:v)?0\.5\.9\b",
                    msg=f"{rel} still names 0.5.9 as catalog",
                )
                self.assertNotRegex(
                    text,
                    r"(?i)catalog\s+(?:v)?0\.6\.0\b",
                    msg=f"{rel} still names 0.6.0 as catalog",
                )

        sundries = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        self.assertIn("Public download catalog: 1.0.0", sundries)
        self.assertNotIn("Public download catalog: 0.2.1", sundries)
        self.assertNotIn("Public download catalog: 0.5.9", sundries)


if __name__ == "__main__":
    unittest.main()
