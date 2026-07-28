"""Admin multi-page shell: ^top links on multi-section pages."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminSectionTopLinks(unittest.TestCase):
    def _render_link_gen(self, *, seed: bool = False) -> str:
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
                return admin_panel.render_admin_link_generation_html().decode(
                    "utf-8"
                )
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

    def test_link_generation_page_has_top_links_on_cards(self):
        import admin_panel

        html = self._render_link_gen(seed=False)
        self.assertIn(f'id="{admin_panel.ADMIN_TOP_ANCHOR_ID}"', html)
        n_top = html.count('class="admin-top-link-a"')
        # reissue + ondemand + keygen + tester = 4 section cards
        self.assertGreaterEqual(n_top, 4, html[:500])
        self.assertIn("^top", html)
        self.assertIn("Link Generation", html)

    def test_seed_section_also_gets_top_link_when_enabled(self):
        html = self._render_link_gen(seed=True)
        self.assertIn('id="admin-seed-purchase"', html)
        idx = html.find('id="admin-seed-purchase"')
        self.assertGreater(idx, 0)
        tail = html[idx : idx + 4000]
        self.assertIn("admin-top-link-a", tail)
        self.assertIn("^top", tail)

    def test_home_architecture_card_present(self):
        import admin_panel

        html = admin_panel.render_admin_home_html().decode("utf-8")
        self.assertIn('id="admin-architecture"', html)
        self.assertIn("admin-sidebar", html)


if __name__ == "__main__":
    unittest.main()
