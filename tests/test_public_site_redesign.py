"""Public website redesign (site-chrome-pro + data-path) — structural gates."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestPublicChromeRedesign(unittest.TestCase):
    def test_dual_theme_tokens_and_data_path_styles(self) -> None:
        from public_chrome import (
            SITE_BRAND_HEADER_ID,
            SITE_CHROME_PRO_CLASS,
            DATA_PATH_LAYER_CLASS,
            THEME_MODE_CONTROL_ID,
            public_data_path_layer_html,
            public_site_css,
            public_brand_header_html,
            public_head_open,
        )

        css = public_site_css()
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn('[data-theme="light"]', css)
        self.assertIn("--rb-neon-cyan", css)
        self.assertIn("--rb-neon-blue", css)
        self.assertIn("--rb-neon-green", css)
        self.assertIn("--rb-neon-border", css)
        self.assertIn("#00e5ff", css)
        self.assertIn("#39ff6a", css)
        # Redesign markers
        self.assertIn(SITE_CHROME_PRO_CLASS, css)
        self.assertIn("data-path", css)
        self.assertIn(".data-path-grid", css)
        self.assertIn(".data-path-motif", css)
        self.assertIn("site-chrome-pro", css)
        # Responsive shells
        self.assertIn("@media (max-width: 520px)", css)
        self.assertIn("@media (max-width: 820px)", css)
        # Refined type / spacing tokens
        self.assertIn("--rb-font", css)
        self.assertIn("--rb-max", css)
        self.assertIn("64rem", css)
        # Dual-tone panel technique preserved
        self.assertIn("padding-box", css)
        self.assertIn("border-box", css)
        self.assertIn(".panel-card", css)
        self.assertIn("var(--rb-neon-glow-cyan)", css)

        layer = public_data_path_layer_html()
        self.assertIn(DATA_PATH_LAYER_CLASS, layer)
        self.assertIn('id="data-path-layer"', layer)
        self.assertIn("data-path-motif", layer)
        self.assertIn("data_path_motif.svg", layer)
        self.assertIn('aria-hidden="true"', layer)

        head = public_head_open(title="t")
        self.assertIn(SITE_CHROME_PRO_CLASS, head)
        self.assertIn("site-public", head)
        self.assertIn('data-chrome="pro"', head)
        self.assertIn("data-path-layer", head)
        self.assertIn('id="theme-mode-control"', public_brand_header_html())
        self.assertIn(f'id="{SITE_BRAND_HEADER_ID}"', public_brand_header_html())
        self.assertIn(f'id="{THEME_MODE_CONTROL_ID}"', public_brand_header_html())

        motif = ROOT / "status_page" / "static" / "data_path_motif.svg"
        self.assertTrue(motif.is_file(), "data-path SVG must ship under static/")
        self.assertIn(b"<svg", motif.read_bytes()[:80])

    def test_stable_nav_and_support_ids_remain(self) -> None:
        from public_chrome import public_nav_links_html, public_brand_header_html

        nav = public_nav_links_html(active="support")
        for el in (
            "home-link",
            "licence-link",
            "privacy-link",
            "audit-link",
            "support-link",
            "settings-guide-link",
            "doc-links",
        ):
            self.assertIn(f'id="{el}"', nav)
        self.assertNotIn("readme-link", nav)
        self.assertIn('href="/support"', nav)
        self.assertIn("is-active", nav)
        # Order: Home → Settings Guide → Licence → Audit → Privacy → Support
        order_ids = (
            "home-link",
            "settings-guide-link",
            "licence-link",
            "audit-link",
            "privacy-link",
            "support-link",
        )
        positions = [nav.index(f'id="{eid}"') for eid in order_ids]
        for i in range(len(positions) - 1):
            self.assertLess(positions[i], positions[i + 1], order_ids[i : i + 2])
        header = public_brand_header_html(active="home")
        self.assertIn('id="brand-panel"', header)
        self.assertIn('id="brand-mark"', header)
        self.assertIn('data-chrome="pro"', header)


class TestPublicPagesShareRedesign(unittest.TestCase):
    def test_homepage_shell_markers(self) -> None:
        from app import render_html

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("site-chrome-pro", html)
        self.assertIn("data-path-layer", html)
        self.assertIn('id="page-shell"', html)
        self.assertIn('data-chrome="pro"', html)
        self.assertIn('id="brand-panel"', html)
        self.assertIn('id="theme-mode-control"', html)
        self.assertIn('id="support-link"', html)
        self.assertIn('href="/support"', html)
        self.assertIn("data_path_motif.svg", html)
        # Buy / primary CTA surface still present
        self.assertIn("dl-buy-now", html)
        self.assertIn('id="home-link"', html)

    def test_support_page_shell_and_form(self) -> None:
        from support_tickets import render_support_page_html

        html = render_support_page_html()
        self.assertIn("site-chrome-pro", html)
        self.assertIn("data-path-layer", html)
        self.assertIn('id="support-page-shell"', html)
        self.assertIn('id="support-form"', html)
        self.assertIn('action="/support"', html)
        self.assertIn('id="support-submit"', html)
        self.assertIn('id="support-link"', html)
        self.assertIn("is-active", html)
        order_ids = (
            "home-link",
            "settings-guide-link",
            "licence-link",
            "audit-link",
            "privacy-link",
            "support-link",
        )
        positions = [html.index(f'id="{eid}"') for eid in order_ids]
        for i in range(len(positions) - 1):
            self.assertLess(
                positions[i],
                positions[i + 1],
                f"support page: {order_ids[i]} before {order_ids[i + 1]}",
            )
        # Theme-aware field tokens (not broken --rb-panel / --rb-primary)
        self.assertNotIn("var(--rb-panel)", html)
        self.assertNotIn("var(--rb-primary)", html)
        self.assertIn("support-form", html)
        self.assertIn("panel-card", html)

    def test_public_doc_shell_markers(self) -> None:
        import public_docs

        got = public_docs.document_bytes_for_path("/README.md")
        self.assertIsNotNone(got)
        assert got is not None
        html = got[0].decode("utf-8")
        self.assertIn("site-chrome-pro", html)
        self.assertIn("data-path-layer", html)
        self.assertIn('id="doc-page-shell"', html)
        self.assertIn('data-chrome="pro"', html)
        self.assertIn('id="brand-panel"', html)
        self.assertIn('id="support-link"', html)
        self.assertIn("page-shell", html)
        self.assertIn("panel-card", html)

    def test_both_theme_blocks_present_on_rendered_home(self) -> None:
        from app import render_html

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn('[data-theme="dark"]', html)
        self.assertIn('[data-theme="light"]', html)
        # Radio theme controls
        self.assertRegex(html, re.compile(r'value="light"'))
        self.assertRegex(html, re.compile(r'value="dark"'))
        self.assertRegex(html, re.compile(r'value="device"'))


if __name__ == "__main__":
    unittest.main()
