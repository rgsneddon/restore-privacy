"""Admin page: each major section ends with a ^top link to page heading."""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminSectionTopLinks(unittest.TestCase):
    def _render(self, *, seed: bool = False) -> str:
        import admin_panel

        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            prev_seed = os.environ.get("RPT_ADMIN_SEED_PURCHASE")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            if seed:
                os.environ["RPT_ADMIN_SEED_PURCHASE"] = "1"
            else:
                os.environ.pop("RPT_ADMIN_SEED_PURCHASE", None)
            try:
                return admin_panel.render_admin_html(grants=[]).decode("utf-8")
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev
                if prev_seed is None:
                    os.environ.pop("RPT_ADMIN_SEED_PURCHASE", None)
                else:
                    os.environ["RPT_ADMIN_SEED_PURCHASE"] = prev_seed

    def test_helper_emits_label_and_heading_href(self):
        import admin_panel

        frag = admin_panel.admin_section_top_link_html()
        self.assertIn("^top", frag)
        self.assertIn(f'href="#{admin_panel.ADMIN_TOP_ANCHOR_ID}"', frag)
        self.assertIn("admin-top-link", frag)

    def test_render_admin_html_has_top_link_per_section_card(self):
        import admin_panel

        html = self._render(seed=False)
        self.assertIn(f'id="{admin_panel.ADMIN_TOP_ANCHOR_ID}"', html)
        # Major section cards
        section_ids = re.findall(
            r'<section\s+[^>]*\bid="(admin-[^"]+)"[^>]*class="[^"]*card',
            html,
        )
        # Also match class="card" before id
        if not section_ids:
            section_ids = re.findall(
                r'<section\s+[^>]*class="[^"]*card[^"]*"[^>]*\bid="(admin-[^"]+)"',
                html,
            )
        # Fallback: any section with id starting admin- that is a card
        cards = re.findall(
            r"<section\b[^>]*\bid=\"(admin-[^\"]+)\"[^>]*>",
            html,
        )
        # Prefer cards that close with top link pattern
        top_links = re.findall(
            r'class="admin-top-link-a"[^>]*>\s*\^top\s*<',
            html,
            flags=re.I,
        )
        hrefs = re.findall(
            r'class="admin-top-link-a"[^>]*href="([^"]+)"',
            html,
        )
        if not hrefs:
            hrefs = re.findall(
                r'href="(#[^"]+)"[^>]*class="admin-top-link-a"',
                html,
            )
        # Count via helper class (stable)
        n_top = html.count('class="admin-top-link-a"')
        n_cards = html.count('class="card"')
        # Sections use class="card" on major blocks
        self.assertGreaterEqual(n_cards, 6, f"expected several section cards, html sample={html[:400]!r}")
        self.assertGreaterEqual(
            n_top,
            n_cards,
            f"top links ({n_top}) should cover section cards ({n_cards}); "
            f"section ids={cards}",
        )
        self.assertIn("^top", html)
        self.assertIn(f'href="#{admin_panel.ADMIN_TOP_ANCHOR_ID}"', html)
        # Login page must not be confused — authenticated page has heading
        self.assertIn("Payment administration", html)

    def test_seed_section_also_gets_top_link_when_enabled(self):
        html = self._render(seed=True)
        self.assertIn('id="admin-seed-purchase"', html)
        # At least one top link after seed section content
        idx = html.find('id="admin-seed-purchase"')
        self.assertGreater(idx, 0)
        tail = html[idx : idx + 4000]
        self.assertIn("admin-top-link-a", tail)
        self.assertIn("^top", tail)


if __name__ == "__main__":
    unittest.main()
