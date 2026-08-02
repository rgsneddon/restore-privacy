"""FREE DOWNLOAD CTA label flash/blink animation (attention cue)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestFreeDownloadCtaBlink(unittest.TestCase):
    def test_label_css_has_blink_keyframes_and_animation(self) -> None:
        from downloads import (
            FREE_DOWNLOAD_CTA_ID,
            FREE_DOWNLOAD_CTA_LABEL,
            free_download_cta_css,
            render_free_download_cta_html,
        )

        self.assertEqual(FREE_DOWNLOAD_CTA_LABEL, "FREE DOWNLOAD")
        css = free_download_cta_css()
        self.assertIn(".free-download-cta-label", css)
        self.assertIn("@keyframes free-download-label-blink", css)
        self.assertIn("animation:", css)
        self.assertIn("free-download-label-blink", css)
        self.assertIn("infinite", css)
        # Dim half of the flash cycle
        self.assertIn("opacity:", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("animation: none", css)

        cta = render_free_download_cta_html(default_platform="macos")
        self.assertIn(FREE_DOWNLOAD_CTA_LABEL, cta)
        self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', cta)
        self.assertIn("free-download-cta-label", cta)
        self.assertIn("FREE DOWNLOAD", cta)

    def test_homepage_emits_blink_css_with_label(self) -> None:
        from app import render_html
        from downloads import FREE_DOWNLOAD_CTA_ID, FREE_DOWNLOAD_CTA_LABEL

        h1 = render_html(
            {"title": "RESTORE PRIVACY"}, default_platform="linux"
        ).decode("utf-8")
        h2 = render_html(
            {"title": "RESTORE PRIVACY"}, default_platform="linux"
        ).decode("utf-8")
        self.assertEqual(h1, h2)
        for page in (h1, h2):
            self.assertIn(FREE_DOWNLOAD_CTA_LABEL, page)
            self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', page)
            self.assertIn("free-download-cta-label", page)
            self.assertIn("@keyframes free-download-label-blink", page)
            self.assertIn("animation:", page)
            self.assertIn("free-download-label-blink", page)
            self.assertIn("infinite", page)
            # Free CTA block still present
            i = page.index(f'id="{FREE_DOWNLOAD_CTA_ID}"')
            snip = page[i : i + 500]
            self.assertIn(FREE_DOWNLOAD_CTA_LABEL, snip)


if __name__ == "__main__":
    unittest.main()
