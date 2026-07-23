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
        # Top brand nav no longer includes Settings Guide
        self.assertNotIn('id="settings-guide-link"', html)
        self.assertNotIn("SETTINGS GUIDE", html)
        self.assertIn('id="doc-links"', html)
        self.assertIn("nav-btn", html)
        i_home = html.index('id="home-link"')
        i_lic = html.index('id="licence-link"')
        self.assertLess(i_home, i_lic, "Home must appear before Licence")
        self.assertIn('href="/"', html)
        self.assertIn('href="/LICENSE"', html)
        self.assertIn("is-active", html)

    def test_nav_active_exactly_one_per_key(self) -> None:
        import re

        from public_chrome import public_nav_links_html

        keys = ("home", "licence", "privacy", "audit", "readme")
        expected = {
            "home": "home-link",
            "licence": "licence-link",
            "privacy": "privacy-link",
            "audit": "audit-link",
            "readme": "readme-link",
        }
        for key in keys:
            html = public_nav_links_html(active=key)
            # Only anchor class attributes (ignore CSS selectors)
            active_anchors = re.findall(
                r'<a class="([^"]*is-active[^"]*)" id="([^"]+)"',
                html,
            )
            self.assertEqual(
                len(active_anchors),
                1,
                msg=f"active={key!r} should mark exactly one control: {active_anchors}",
            )
            self.assertEqual(active_anchors[0][1], expected[key])
            self.assertNotIn("settings-guide-link", html)
        bare = public_nav_links_html(active=None)
        self.assertEqual(
            len(re.findall(r'<a class="[^"]*is-active', bare)),
            0,
        )
        self.assertNotIn("settings-guide-link", bare)

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
            self.assertNotIn("settings-guide-link", html, path)
            i_home = html.index('id="home-link"')
            i_lic = html.index('id="licence-link"')
            self.assertLess(i_home, i_lic, path)
        # Licence keeps typeform / plain body
        lic = public_docs.document_bytes_for_path("/LICENSE")
        assert lic is not None
        lhtml = lic[0].decode("utf-8")
        self.assertIn("doc-plain", lhtml)
        self.assertIn("licence-typeform", lhtml)

    def test_audit_and_readme_highlight_correct_nav_not_privacy(self) -> None:
        """Titles end with product name 'Restore Privacy' — must not activate Privacy."""
        import public_docs
        from public_docs import _active_nav_for_title

        # Title helper: product suffix must not force privacy
        self.assertEqual(
            _active_nav_for_title("Security audit — Restore Privacy"),
            "audit",
        )
        self.assertEqual(
            _active_nav_for_title("README — Restore Privacy"),
            "readme",
        )
        self.assertEqual(
            _active_nav_for_title("Privacy Policy — Restore Privacy"),
            "privacy",
        )
        self.assertEqual(
            _active_nav_for_title("End User Licence — Restore Privacy", plain=True),
            "licence",
        )

        for path, link_id, not_id in (
            ("/AUDIT.md", "audit-link", "privacy-link"),
            ("/README.md", "readme-link", "privacy-link"),
            ("/PRIVACY_POLICY.md", "privacy-link", "audit-link"),
            ("/LICENSE", "licence-link", "privacy-link"),
        ):
            got = public_docs.document_bytes_for_path(path)
            self.assertIsNotNone(got, path)
            assert got is not None
            html = got[0].decode("utf-8")
            import re

            # Active class on the correct control (ignore CSS rule text)
            active_anchors = re.findall(
                r'<a class="([^"]*is-active[^"]*)" id="([^"]+)"',
                html,
            )
            self.assertEqual(
                len(active_anchors),
                1,
                msg=f"{path} active anchors={active_anchors}",
            )
            self.assertEqual(
                active_anchors[0][1],
                link_id,
                msg=f"{path} should activate {link_id}",
            )
            if link_id != "privacy-link":
                m = re.search(
                    r'<a class="([^"]*)" id="privacy-link"',
                    html,
                )
                self.assertIsNotNone(m, path)
                assert m is not None
                self.assertNotIn("is-active", m.group(1), msg=path)
            self.assertNotIn("settings-guide-link", html)


if __name__ == "__main__":
    unittest.main()
