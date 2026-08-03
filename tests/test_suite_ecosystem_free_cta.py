"""Suite ecosystem rpOS/Rx Browser/VPN links, neon underline menus, free CTA 1.0.1."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuiteEcosystemNewLinks(unittest.TestCase):
    """Product docs submenu: About / Settings / How to buy / Rx Browser."""

    def test_submenu_links_are_vpn_docs_not_multi_product_pitch(self) -> None:
        from downloads import (
            SUITE_ECOSYSTEM_VPN_HREF,
            SUITE_ECOSYSTEM_VPN_KEY,
            SUITE_RX_BROWSER_HREF,
            SUITE_RX_BROWSER_KEY,
            SUITE_RX_BROWSER_LABEL,
            render_suite_product_submenu_html,
            suite_product_submenu_links,
        )

        links = suite_product_submenu_links()
        # (href, label, key, title)
        by_key = {row[2]: row for row in links}
        self.assertIn(SUITE_ECOSYSTEM_VPN_KEY, by_key)
        self.assertIn(SUITE_RX_BROWSER_KEY, by_key)
        self.assertIn("settings-guide", by_key)
        self.assertIn("how-to-buy", by_key)
        # No Evolve / Perccent product pitch on the storefront
        self.assertNotIn("evolve-docs", by_key)
        self.assertNotIn("perccent-wallet", by_key)
        self.assertNotIn("perc-explorer", by_key)

        href_v, label_v, _, _ = by_key[SUITE_ECOSYSTEM_VPN_KEY]
        self.assertEqual(href_v, SUITE_ECOSYSTEM_VPN_HREF)
        self.assertIn("About", label_v)

        href_b, label_b, _, _ = by_key[SUITE_RX_BROWSER_KEY]
        self.assertEqual(label_b, SUITE_RX_BROWSER_LABEL)
        self.assertEqual(href_b, SUITE_RX_BROWSER_HREF)

        html = render_suite_product_submenu_html()
        for key in (
            SUITE_ECOSYSTEM_VPN_KEY,
            SUITE_RX_BROWSER_KEY,
            "settings-guide",
            "how-to-buy",
        ):
            self.assertIn(f'data-suite-sub="{key}"', html)
            self.assertIn(f'id="suite-sub-{key}"', html)
            self.assertRegex(
                html,
                rf'<a[^>]*data-suite-sub="{re.escape(key)}"[^>]*>',
            )
        self.assertIn("Learn more", html)
        self.assertNotIn("Suite ecosystem", html)
        self.assertNotIn("Evolve docs", html)
        self.assertNotIn("Perccent wallet", html)

class TestSuiteEcosystemNeonUnderline(unittest.TestCase):
    """Menu items use neon-gradient underline, not filled pill/box chrome."""

    def test_suite_submenu_css_neon_underline_not_pills(self) -> None:
        from downloads import suite_storefront_css

        css = suite_storefront_css()
        # Neon gradient brand treatment (cyan → blue → green)
        self.assertIn("border-image", css)
        self.assertIn("linear-gradient", css)
        self.assertIn("#00e5ff", css)  # cyan
        self.assertIn("#2694e8", css)  # blue
        self.assertIn("#39ff6a", css)  # green
        self.assertIn("border-bottom", css)
        # Submenu anchors: transparent / no filled chip
        self.assertIn("background: transparent", css)
        self.assertIn("Neon-gradient underline", css)
        # Must not style suite-sub links as filled rounded pills
        # (old chrome used solid background + border-radius chips on anchors)
        block = re.search(
            r"\.suite-product-submenu a(?:[^{]|\{[^{]*\})*?\{([^}]+)\}",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(block, "suite-product-submenu a rule present")
        rule = block.group(0) if block else ""
        self.assertIn("background: transparent", rule)
        self.assertNotRegex(
            rule.replace(" ", ""),
            r"background:(?!transparent)(?!none)(?!image)",
        )
        # border-radius: 0 (not pill 999px) on submenu links
        self.assertIn("border-radius: 0", rule)

    def test_public_nav_active_is_neon_underline(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        self.assertIn(".nav-btn.is-active", css)
        self.assertIn("border-image", css)
        self.assertIn("linear-gradient", css)
        # Active nav is not a filled box
        active = re.search(
            r"\.nav-btn\.is-active[^{]*\{([^}]+)\}",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(active)
        body = active.group(1) if active else ""
        self.assertIn("background: transparent", body)
        self.assertIn("border-image", body)


class TestFreeDownloadFace101Platform(unittest.TestCase):
    """Free-download bar: full art, FREE DOWNLOAD face, platform detect hrefs."""

    def test_cta_face_version_1_0_1_and_full_image_css(self) -> None:
        from downloads import (
            DOWNLOADS_MAP_PATH,
            FREE_DOWNLOAD_FACE_VERSION,
            RELEASE_VERSION,
            free_download_cta_css,
            render_free_download_cta_html,
        )

        # Catalog version tracks RELEASE_VERSION; CTA is rectangular typewriter text.
        self.assertEqual(FREE_DOWNLOAD_FACE_VERSION, RELEASE_VERSION)
        css = free_download_cta_css()
        self.assertIn("width: 100%", css)
        self.assertIn("Courier New", css)
        self.assertIn("data_path_motif", css)
        self.assertIn("display: none", css)  # non-logo faces hidden
        self.assertIn("free-download-cta-logo", css)
        self.assertIn("display: block !important", css)  # logo flanks shown
        self.assertNotIn("aspect-ratio: 1 / 1", css)
        # FREE DOWNLOAD label continuously flashes for attention
        self.assertIn("@keyframes free-download-label-blink", css)
        self.assertIn("free-download-label-blink", css)
        self.assertIn("animation:", css)
        self.assertIn("infinite", css)
        self.assertIn("prefers-reduced-motion", css)

        cta = render_free_download_cta_html()
        self.assertIn(RELEASE_VERSION, cta)
        self.assertIn(f'data-face-version="{RELEASE_VERSION}"', cta)
        # No detected platform → Downloads Map fallback (not /pay, not KEYGEN gate)
        self.assertIn("FREE DOWNLOAD", cta)
        self.assertIn(DOWNLOADS_MAP_PATH, cta)
        self.assertIn('data-pay="0"', cta)
        self.assertNotIn('href="/pay', cta)
        self.assertNotIn("v1.0.0", cta)
        self.assertEqual(cta.count("logo_transparent.png"), 2)
        self.assertIn("free-download-cta-logo-left", cta)
        self.assertIn("free-download-cta-logo-right", cta)
        self.assertNotIn("freebie.jpg", cta)
        self.assertIn('data-cta-shape="rectangle"', cta)
        self.assertIn("free-download-cta-label", cta)

    def test_cta_platform_detect_names_brand_and_href(self) -> None:
        from downloads import (
            DOWNLOADS_MAP_PATH,
            render_free_download_cta_html,
        )

        for plat, face in (
            ("macos", "macOS"),
            ("windows", "Windows"),
            ("android", "Android"),
            ("ios", "iOS"),
            ("linux", "Linux"),
        ):
            cta = render_free_download_cta_html(default_platform=plat)
            self.assertIn("free_direct=1", cta, msg=plat)
            self.assertIn(f"platform={plat}", cta, msg=plat)
            self.assertIn("DOWNLOAD", cta, msg=plat)
            self.assertIn(face, cta, msg=plat)
            self.assertIn(f'data-detected-platform="{plat}"', cta, msg=plat)
            self.assertNotIn(f'href="{DOWNLOADS_MAP_PATH}"', cta, msg=plat)
            self.assertNotIn('href="/pay', cta, msg=plat)

        # Unknown / empty → Downloads Map
        chooser = render_free_download_cta_html(default_platform="")
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', chooser)
        self.assertIn("DOWNLOAD", chooser)
        self.assertNotIn("data-detected-platform", chooser)

        unknown = render_free_download_cta_html(default_platform="not-a-platform")
        self.assertIn(f'href="{DOWNLOADS_MAP_PATH}"', unknown)
        self.assertNotIn("data-detected-platform", unknown)


if __name__ == "__main__":
    unittest.main()
