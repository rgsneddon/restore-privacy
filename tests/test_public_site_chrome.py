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
            PUBLIC_BRAND_LOGO_PATH,
            PUBLIC_BRAND_LOGO_SIZE_DEFAULT,
            PUBLIC_BRAND_LOGO_SIZE_MAX_CSS,
            PUBLIC_BRAND_LOGO_SIZE_MIN_CSS,
            PUBLIC_BRAND_TITLE,
            PUBLIC_THEME_STORAGE_KEY,
            public_brand_header_html,
            public_site_css,
            public_theme_boot_script,
        )

        header = public_brand_header_html(active="licence")
        self.assertIn('id="brand-panel"', header)
        self.assertIn('id="brand-mark"', header)
        self.assertIn('class="brand-mark"', header)
        self.assertIn("<h1>", header)
        self.assertEqual(PUBLIC_BRAND_TITLE, "RESTORE PRIVACY VPN")
        self.assertIn(f"<h1>{PUBLIC_BRAND_TITLE}</h1>", header)
        # Borderless transparent mark left of title (logo before h1)
        mark_start = header.index('id="brand-mark"')
        mark_end = header.index("</div>", mark_start)
        mark = header[mark_start:mark_end]
        i_logo = mark.index("brand-logo")
        i_h1 = mark.index("<h1>")
        self.assertLess(i_logo, i_h1, "logo must sit left of title in brand-mark")
        self.assertIn(PUBLIC_BRAND_LOGO_PATH, mark)
        self.assertIn("logo_transparent", mark)
        self.assertNotIn('src="/logo.png"', mark)
        self.assertNotIn('src="/logo.png?', mark)
        self.assertIn(f'width="{PUBLIC_BRAND_LOGO_SIZE_DEFAULT}"', header)
        # Nav remains below the logo+title band
        i_mark = header.index('id="brand-mark"')
        i_nav = header.index('id="doc-links"')
        self.assertLess(i_mark, i_nav)
        # Short historical title upgrades to brand title with VPN
        short = public_brand_header_html(title="RESTORE PRIVACY")
        self.assertIn(f"<h1>{PUBLIC_BRAND_TITLE}</h1>", short)
        self.assertNotRegex(short, r"<h1>RESTORE PRIVACY</h1>")
        # No under-title slogan in the top brand box
        self.assertNotIn("brand-tagline", header)
        self.assertNotIn("lightweight vpn to restore", header.lower())
        self.assertNotIn("your privacy is restored", header.lower())
        self.assertIn('id="home-link"', header)
        self.assertIn('id="theme-mode-control"', header)
        self.assertIn('name="public-theme"', header)
        self.assertIn('value="light"', header)
        self.assertIn('value="dark"', header)
        self.assertIn('value="device"', header)
        # Explicit empty tagline still omits the element
        bare = public_brand_header_html(tagline="")
        self.assertNotIn("brand-tagline", bare)
        # Non-empty override still allowed for callers that need a subtitle
        with_tag = public_brand_header_html(tagline="custom subtitle only")
        self.assertIn('class="brand-tagline"', with_tag)
        self.assertIn("custom subtitle only", with_tag)
        css = public_site_css()
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("--rb-btn", css)
        # Logo data-artifact neon borders (cyan/blue + green) on panel boxes
        self.assertIn("--rb-neon-cyan", css)
        self.assertIn("--rb-neon-green", css)
        self.assertIn("--rb-neon-blue", css)
        self.assertIn("--rb-neon-border", css)
        self.assertIn("#00e5ff", css)  # dark-theme neon cyan
        self.assertIn("#39ff6a", css)  # dark-theme neon green
        self.assertIn(".panel-card", css)
        self.assertIn("var(--rb-neon-border)", css)
        self.assertIn("var(--rb-neon-glow-cyan)", css)
        self.assertIn("var(--rb-neon-glow-green)", css)
        # Dual-tone border technique: padding-box fill + border-box gradient
        self.assertIn("padding-box", css)
        self.assertIn("border-box", css)
        # Brand logo: larger clamp, no border/frame, transparent plate
        self.assertIn(".brand-mark", css)
        self.assertIn("flex-direction: row", css)
        self.assertIn(f"{PUBLIC_BRAND_LOGO_SIZE_MIN_CSS}px", css)
        self.assertIn(f"{PUBLIC_BRAND_LOGO_SIZE_MAX_CSS}px", css)
        self.assertGreater(PUBLIC_BRAND_LOGO_SIZE_MIN_CSS, 72)
        self.assertGreater(PUBLIC_BRAND_LOGO_SIZE_MAX_CSS, 104)
        self.assertGreater(PUBLIC_BRAND_LOGO_SIZE_DEFAULT, 96)
        logo_css_i = css.index(".brand-logo")
        logo_css = css[logo_css_i : logo_css_i + 450]
        self.assertIn("border: none", logo_css)
        self.assertIn("background: transparent", logo_css)
        self.assertIn("box-shadow: none", logo_css)
        self.assertIn("object-fit: contain", logo_css)
        self.assertNotIn("var(--rb-neon-border)", logo_css)
        # Light theme still defines both neon tones (softer values)
        light_i = css.index('[data-theme="light"]')
        light_css = css[light_i : light_i + 1800]
        self.assertIn("--rb-neon-cyan", light_css)
        self.assertIn("--rb-neon-green", light_css)
        # No yellow palette for nav / settings banner
        self.assertNotIn("#fbbf24", css)
        self.assertNotIn("#fde68a", css)
        script = public_theme_boot_script()
        self.assertIn(PUBLIC_THEME_STORAGE_KEY, script)
        self.assertIn("/static/public_theme.js", script)
        self.assertIn("public-theme-script", script)
        js = (ROOT / "status_page" / "static" / "public_theme.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("localStorage", js)
        self.assertIn("data-theme", js)

    def test_brand_logo_static_is_borderless_transparent_mark(self) -> None:
        """Header logo: outer transparent; no enclosed holes inside the shield."""
        from pathlib import Path

        from public_chrome import PUBLIC_BRAND_LOGO_STATIC_NAME

        path = ROOT / "status_page" / "static" / PUBLIC_BRAND_LOGO_STATIC_NAME
        self.assertEqual(PUBLIC_BRAND_LOGO_STATIC_NAME, "logo_transparent.png")
        self.assertTrue(path.is_file(), msg=f"missing {path}")
        data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        try:
            from PIL import Image, ImageDraw

            im = Image.open(path).convert("RGBA")
            w, h = im.size
            corners = [
                im.getpixel((0, 0))[3],
                im.getpixel((w - 1, 0))[3],
                im.getpixel((0, h - 1))[3],
                im.getpixel((w - 1, h - 1))[3],
            ]
            self.assertTrue(
                all(a < 16 for a in corners),
                msg=f"corners must be transparent: {corners}",
            )
            px = im.load()
            outer = Image.new("L", (w, h), 0)
            op = outer.load()
            for y in range(h):
                for x in range(w):
                    if px[x, y][3] == 0:
                        op[x, y] = 255
            for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
                if outer.getpixel(seed) == 255:
                    ImageDraw.floodfill(outer, seed, 128, thresh=0)
            outer_t = holes = 0
            for y in range(h):
                for x in range(w):
                    if px[x, y][3] != 0:
                        continue
                    if outer.getpixel((x, y)) == 128:
                        outer_t += 1
                    else:
                        holes += 1
            self.assertEqual(holes, 0, "shield interior holes must be filled")
            self.assertGreater(outer_t, w * h // 2, "outer area must stay transparent")
            solid = ROOT / "status_page" / "static" / "logo.png"
            self.assertTrue(solid.is_file())
            self.assertNotEqual(solid.read_bytes(), path.read_bytes())
            return
        except ImportError:
            self.fail("Pillow required to assert transparent logo alpha")


class TestHomepageChrome(unittest.TestCase):
    def test_homepage_shared_header_theme_and_home_nav(self) -> None:
        from app import render_html

        from public_chrome import PUBLIC_BRAND_TITLE

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn('id="brand-panel"', html)
        brand_start = html.index('id="brand-panel"')
        brand_end = html.index("</header>", brand_start)
        brand_box = html[brand_start:brand_end]
        self.assertIn(f"<h1>{PUBLIC_BRAND_TITLE}</h1>", brand_box)
        self.assertNotRegex(brand_box, r"<h1>RESTORE PRIVACY</h1>")
        self.assertIn(f"<title>{PUBLIC_BRAND_TITLE}</title>", html)
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
        # Top brand box has no lightweight-vpn (or any) tagline line
        brand_start = html.index('id="brand-panel"')
        brand_end = html.index("</header>", brand_start)
        brand_box = html[brand_start:brand_end]
        self.assertNotIn("brand-tagline", brand_box)
        self.assertNotIn('class="tagline"', brand_box)
        self.assertNotIn("lightweight vpn to restore", brand_box.lower())
        self.assertNotIn("your privacy is restored", brand_box.lower())
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
            brand_start = html.index('id="brand-panel"')
            brand_end = html.index("</header>", brand_start)
            brand_box = html[brand_start:brand_end]
            self.assertNotIn("brand-tagline", brand_box, path)
            self.assertNotIn('class="tagline"', brand_box, path)
            self.assertNotIn("lightweight vpn to restore", brand_box.lower(), path)
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

            # Active class on site nav only (product-family tabs also use is-active)
            active_anchors = re.findall(
                r'<a class="([^"]*nav-btn[^"]*is-active[^"]*)" id="([^"]+)"',
                html,
            )
            self.assertEqual(
                len(active_anchors),
                1,
                msg=f"{path} active nav anchors={active_anchors}",
            )
            self.assertEqual(
                active_anchors[0][1],
                link_id,
                msg=f"{path} should activate {link_id}",
            )
            # Product tabs present on public docs
            self.assertIn("product-tabs", html)
            self.assertIn("product-tab-vpn", html)
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
