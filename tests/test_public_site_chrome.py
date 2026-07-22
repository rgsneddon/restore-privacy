"""Shared public site chrome — static header, nav buttons, theme, no admin drift."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestPublicChromeModule(unittest.TestCase):
    def test_nav_home_before_licence_and_button_classes(self) -> None:
        from public_chrome import public_nav_links_html

        html = public_nav_links_html(active="home")
        self.assertIn('id="home-link"', html)
        self.assertIn('id="licence-link"', html)
        self.assertIn('id="privacy-link"', html)
        self.assertIn('id="audit-link"', html)
        self.assertIn('id="readme-link"', html)
        self.assertIn('id="settings-guide-link"', html)
        self.assertIn('id="doc-links"', html)
        self.assertIn("nav-btn", html)
        i_home = html.index('id="home-link"')
        i_lic = html.index('id="licence-link"')
        self.assertLess(i_home, i_lic, "Home must appear before Licence")
        self.assertIn('href="/"', html)
        self.assertIn('href="/LICENSE"', html)
        self.assertIn("is-active", html)

    def test_brand_header_has_theme_and_nav(self) -> None:
        from public_chrome import (
            PUBLIC_THEME_STORAGE_KEY,
            public_brand_header_html,
            public_site_css,
            public_theme_boot_script,
        )

        header = public_brand_header_html(active="licence")
        self.assertIn('id="brand-panel"', header)
        self.assertIn('id="home-link"', header)
        self.assertIn('id="theme-mode-control"', header)
        self.assertIn('name="public-theme"', header)
        self.assertIn('value="light"', header)
        self.assertIn('value="dark"', header)
        self.assertIn('value="device"', header)
        css = public_site_css()
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("--rb-btn", css)
        # No yellow palette for nav / settings banner
        self.assertNotIn("#fbbf24", css)
        self.assertNotIn("#fde68a", css)
        script = public_theme_boot_script()
        self.assertIn(PUBLIC_THEME_STORAGE_KEY, script)
        self.assertIn("localStorage", script)
        self.assertIn("data-theme", script)


class TestHomepageChrome(unittest.TestCase):
    def test_homepage_shared_header_theme_and_home_nav(self) -> None:
        from app import render_html

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn('id="brand-panel"', html)
        self.assertIn('id="home-link" href="/"', html)
        self.assertIn('id="licence-link" href="/LICENSE"', html)
        i_home = html.index('id="home-link"')
        i_lic = html.index('id="licence-link"')
        self.assertLess(i_home, i_lic)
        self.assertIn('id="theme-mode-control"', html)
        self.assertIn("public-theme-script", html)
        self.assertIn("nav-btn", html)
        self.assertIn("settings-banner", html)
        self.assertIn("settings-explainer-banner-link", html)
        # Price white callouts present
        self.assertIn('id="dl-only-price"', html)
        self.assertIn("ONLY £2.45 per month", html)
        # Admin shell markers must not leak into public homepage
        self.assertNotIn("admin-shell", html)


class TestDocsShareChrome(unittest.TestCase):
    def test_licence_privacy_audit_readme_share_header(self) -> None:
        import public_docs

        for path in ("/LICENSE", "/PRIVACY_POLICY.md", "/AUDIT.md", "/README.md"):
            got = public_docs.document_bytes_for_path(path)
            self.assertIsNotNone(got, path)
            assert got is not None
            html = got[0].decode("utf-8")
            self.assertIn('id="brand-panel"', html, path)
            self.assertIn('id="home-link"', html, path)
            self.assertIn('id="theme-mode-control"', html, path)
            self.assertIn("page-shell", html, path)
            self.assertIn("panel-card", html, path)
            self.assertIn("nav-btn", html, path)
            i_home = html.index('id="home-link"')
            i_lic = html.index('id="licence-link"')
            self.assertLess(i_home, i_lic, path)
        # Licence keeps typeform / plain body
        lic = public_docs.document_bytes_for_path("/LICENSE")
        assert lic is not None
        lhtml = lic[0].decode("utf-8")
        self.assertIn("doc-plain", lhtml)
        self.assertIn("licence-typeform", lhtml)


if __name__ == "__main__":
    unittest.main()
