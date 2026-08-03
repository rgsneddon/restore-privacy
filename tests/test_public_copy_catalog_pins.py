"""Public copy must match shipped catalog monopin, GBP price, and 3-day trial."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestPublicCopyCatalogPins(unittest.TestCase):
    def test_truth_pins_from_shipped_constants(self) -> None:
        from downloads import PRICE_LABEL, PRICE_YEARLY_LABEL, RELEASE_VERSION
        from public_chrome import PUBLIC_BRAND_VERSION

        self.assertEqual(RELEASE_VERSION, PUBLIC_BRAND_VERSION)
        client_ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(client_ver, RELEASE_VERSION)
        self.assertEqual(PRICE_LABEL, "£3.00")
        self.assertEqual(PRICE_YEARLY_LABEL, "£30.00")

    def test_public_pack_and_public_site_match_release_version(self) -> None:
        from downloads import PRICE_LABEL, RELEASE_VERSION

        # Public pack product docs (not historical RELEASE_NOTES_*)
        public_dir = ROOT / "status_page" / "public"
        stale_ver = re.compile(rf"\b(?!{re.escape(RELEASE_VERSION)})1\.0\.[0-6]\b")
        # Files that claim current catalog
        for name in ("AUDIT.md", "RX.md", "README.md"):
            path = public_dir / name
            self.assertTrue(path.is_file(), name)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("£2.45", text)
            self.assertNotIn("£ 2.45", text)
            # AUDIT public catalog line must show truth pin + £3 not £2.45
            if name == "AUDIT.md":
                self.assertIn(RELEASE_VERSION, text)
                self.assertIn("£3.00", text)
            if name == "RX.md":
                self.assertIn(RELEASE_VERSION, text)
                self.assertNotRegex(text, r"catalog \*\*1\.0\.[0-6]\*\*")

        # Root README current catalog claims
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"v{RELEASE_VERSION}", root_readme)
        self.assertIn(PRICE_LABEL, root_readme)
        self.assertNotIn("£2.45", root_readme)
        self.assertNotIn("restore-privacy-client-1.0.1-", root_readme)
        self.assertIn(f"restore-privacy-client-{RELEASE_VERSION}-", root_readme)

        # public_site export
        idx = (ROOT / "public_site" / "index.html").read_text(encoding="utf-8")
        self.assertIn(RELEASE_VERSION, idx)
        self.assertIn(PRICE_LABEL, idx)
        self.assertNotIn("suite-free-grid", idx)
        self.assertNotIn("Get Suite Windows", idx)
        self.assertNotIn("Device for KEYGEN", idx)
        self.assertNotIn("£2.45", idx)

        # Browser extension companion catalog label
        popup = (ROOT / "browser_extension" / "popup.html").read_text(encoding="utf-8")
        self.assertIn(f"{RELEASE_VERSION}", popup)
        manifest = (ROOT / "browser_extension" / "manifest.json").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'"version": "{RELEASE_VERSION}"', manifest)
        self.assertIn(f"{RELEASE_VERSION}", manifest)

    def test_homepage_render_has_current_price_and_trial_not_stale(self) -> None:
        from app import render_html
        from downloads import PRICE_LABEL, RELEASE_VERSION, render_download_section_html
        from public_chrome import SUITE_HOME_INTRO_BODY

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn(RELEASE_VERSION, page)
        self.assertIn(PRICE_LABEL, page)
        self.assertNotIn("£2.45", page)
        self.assertNotIn("7 day trial", page.lower())
        self.assertNotIn("7-day trial", page.lower())
        # Intro / KEYGEN copy uses three-day trial language
        self.assertTrue(
            "three days" in SUITE_HOME_INTRO_BODY.lower()
            or "3-day" in page.lower()
            or "3 day" in page.lower()
        )
        self.assertIn("3-day", page.lower())

        dl = render_download_section_html(coming_soon=False)
        self.assertIn(RELEASE_VERSION, dl)
        self.assertNotIn("£2.45", dl)
        self.assertNotIn('id="dl-only-price"', dl)
        self.assertNotIn('id="dl-price-box"', dl)
        self.assertIn('id="dl-local-price"', dl)

    def test_public_docs_loader_readme_not_stale_price(self) -> None:
        from downloads import RELEASE_VERSION
        from public_docs import load_public_document_bytes

        raw = load_public_document_bytes("AUDIT.md", min_size=100)
        self.assertIsNotNone(raw)
        assert raw is not None
        text = raw.decode("utf-8")
        self.assertIn(RELEASE_VERSION, text)
        self.assertNotIn("£2.45", text)
        self.assertIn("£3.00", text)

    def test_audit_generator_and_mirrors_reject_stale_live_price(self) -> None:
        """Generator template + AUDIT mirrors must not reintroduce £2.45 as live price."""
        from downloads import PRICE_LABEL, PRICE_YEARLY_LABEL, RELEASE_VERSION

        gen = (ROOT / "scripts" / "run_security_audit.py").read_text(encoding="utf-8")
        # No live catalog price hardcoded as retired monthly amount in emitted row
        self.assertNotIn(
            "paid installers on [status host](https://restoreprivacy.online/) (£2.45",
            gen,
        )
        self.assertNotRegex(
            gen,
            r"Public catalog\s*\|[^\n]*£2\.45",
        )
        # Template must use shipped price constants (or equivalent current wording)
        self.assertIn("PRICE_LABEL", gen)
        self.assertIn("PRICE_YEARLY_LABEL", gen)
        self.assertIn("catalog_price_note", gen)
        self.assertIn("{catalog_price_note}", gen)

        for rel in (
            "AUDIT.md",
            "status_page/AUDIT.md",
            "status_page/public/AUDIT.md",
        ):
            path = ROOT / rel
            self.assertTrue(path.is_file(), rel)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("£2.45", text, msg=rel)
            self.assertIn(RELEASE_VERSION, text)
            # Live catalog credibility row must state current KEYGEN GBP anchors
            self.assertIn(PRICE_LABEL, text, msg=rel)
            self.assertIn(PRICE_YEARLY_LABEL, text, msg=rel)
            self.assertRegex(
                text,
                rf"Public catalog\s*\|\s*\*\*{re.escape(RELEASE_VERSION)}\*\*.*{re.escape(PRICE_LABEL)}",
                msg=f"{rel}: public catalog row must pin version + monthly price",
            )


if __name__ == "__main__":
    unittest.main()
