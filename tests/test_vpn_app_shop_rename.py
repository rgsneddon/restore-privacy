"""Product storefront name is VPN APP Shop (not Status page)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Primary user-facing / mirrored / operator-doc surfaces that must use the new name.
PRIMARY_SURFACES = (
    "README.md",
    "PRIVACY_POLICY.md",
    "LICENSE",
    "CREDITS.md",
    "AUDIT.md",
    "sundries.txt",
    "status_page/public/README.md",
    "status_page/public/PRIVACY_POLICY.md",
    "status_page/public/LICENSE",
    "status_page/public/CREDITS.md",
    "status_page/public/AUDIT.md",
    "status_page/admin_panel.py",
    "status_page/public_docs.py",
)

# Product-name phrases that must not remain as the storefront label.
OLD_PRODUCT_NAME = re.compile(r"(?i)\bstatus page\b")


class TestVpnAppShopRename(unittest.TestCase):
    def test_primary_surfaces_use_vpn_app_shop(self):
        for rel in PRIMARY_SURFACES:
            path = ROOT / rel
            self.assertTrue(path.is_file(), f"missing {rel}")
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "VPN APP Shop",
                text,
                msg=f"{rel} must name the storefront VPN APP Shop",
            )

    def test_primary_surfaces_drop_status_page_product_name(self):
        for rel in PRIMARY_SURFACES:
            path = ROOT / rel
            text = path.read_text(encoding="utf-8")
            # Allow technical status_page path / module identifiers only
            cleaned = text.replace("status_page", "")
            hits = OLD_PRODUCT_NAME.findall(cleaned)
            self.assertEqual(
                hits,
                [],
                msg=f"{rel} still has product-name 'status page': {hits}",
            )

    def test_admin_home_link_label(self):
        src = (ROOT / "status_page" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn('href="/">VPN APP Shop</a>', src)
        self.assertNotIn('href="/">Status page</a>', src)

    def test_readme_section_heading(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("### VPN APP Shop", readme)
        self.assertNotIn("### Status page", readme)

    def test_public_docs_howto_copy(self):
        src = (ROOT / "status_page" / "public_docs.py").read_text(encoding="utf-8")
        self.assertIn("Open the VPN APP Shop:", src)
        self.assertNotIn("Open the status page:", src)

    def test_sundries_storefront_section(self):
        text = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        self.assertIn("PUBLIC VPN APP Shop", text)
        self.assertNotIn("PUBLIC STATUS PAGE", text)
        cleaned = text.replace("status_page", "")
        self.assertEqual(OLD_PRODUCT_NAME.findall(cleaned), [])


if __name__ == "__main__":
    unittest.main()
