"""Suite left box: dense world-flags strip (ISO pack) at the bottom."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

FLAGS_DIR = ROOT / "status_page" / "static" / "flags" / "w20"
# Plan: total pack ≪ 1 MB; tiny w20 PNGs
MAX_PACK_BYTES = 512_000  # 500 KiB hard cap
MIN_WORLD_FLAGS = 190


class TestSuiteBoxWorldFlags(unittest.TestCase):
    def test_flag_pack_complete_and_small(self) -> None:
        from world_flag_codes import WORLD_FLAG_CODES, WORLD_FLAG_COUNT

        self.assertGreaterEqual(WORLD_FLAG_COUNT, MIN_WORLD_FLAGS)
        self.assertEqual(len(WORLD_FLAG_CODES), WORLD_FLAG_COUNT)
        self.assertTrue(FLAGS_DIR.is_dir(), FLAGS_DIR)
        pngs = sorted(FLAGS_DIR.glob("*.png"))
        self.assertEqual(len(pngs), WORLD_FLAG_COUNT)
        total = 0
        for cc in WORLD_FLAG_CODES:
            p = FLAGS_DIR / f"{cc}.png"
            self.assertTrue(p.is_file(), f"missing {p.name}")
            size = p.stat().st_size
            self.assertGreater(size, 40, cc)
            self.assertLess(size, 4_000, f"{cc} too large for fast load")
            total += size
            # Valid tiny PNG signature
            self.assertEqual(p.read_bytes()[:8], b"\x89PNG\r\n\x1a\n", cc)
        self.assertLess(total, MAX_PACK_BYTES, f"pack {total} bytes too large")
        # Unique ISO-ish codes
        self.assertEqual(len(set(WORLD_FLAG_CODES)), WORLD_FLAG_COUNT)
        for cc in WORLD_FLAG_CODES:
            self.assertRegex(cc, r"^[a-z]{2}$")

    def test_suite_storefront_bottom_flags_region(self) -> None:
        from downloads import (
            render_download_section_html,
            render_suite_storefront_html,
            render_suite_world_flags_html,
            suite_free_download_href,
            world_flag_codes,
            world_flag_static_url,
        )
        from world_flag_codes import WORLD_FLAG_COUNT

        codes = world_flag_codes()
        self.assertGreaterEqual(len(codes), MIN_WORLD_FLAGS)

        flags_html = render_suite_world_flags_html()
        self.assertIn('id="suite-world-flags"', flags_html)
        self.assertIn('data-suite-world-flags="1"', flags_html)
        self.assertIn(f'data-flag-count="{WORLD_FLAG_COUNT}"', flags_html)
        # Many distinct flag images
        ccs = re.findall(r'data-flag-cc="([a-z]{2})"', flags_html)
        self.assertEqual(len(ccs), WORLD_FLAG_COUNT)
        self.assertEqual(len(set(ccs)), WORLD_FLAG_COUNT)
        self.assertEqual(set(ccs), set(codes))
        # Static paths for pack
        for cc in ("us", "gb", "de", "jp", "br"):
            self.assertIn(world_flag_static_url(cc), flags_html)
            self.assertIn(f'data-flag-cc="{cc}"', flags_html)

        suite = render_suite_storefront_html()
        self.assertIn('id="suite-storefront"', suite)
        self.assertIn('id="suite-world-flags"', suite)
        self.assertIn('data-suite-world-flags="1"', suite)
        # Flags after free downloads / KEYGEN (bottom of card)
        i_free = suite.index("suite-free-grid")
        i_keygen = suite.index("suite-keygen")
        i_flags = suite.index('id="suite-world-flags"')
        self.assertLess(i_free, i_flags)
        self.assertLess(i_keygen, i_flags)
        # Free Suite + KEYGEN still present
        self.assertIn(suite_free_download_href("windows"), suite)
        self.assertIn("Get KEYGEN", suite)
        self.assertIn("data-free-download", suite)

        # Right-hand client downloads box must NOT carry the world strip
        dl = render_download_section_html()
        self.assertNotIn("suite-world-flags", dl)
        self.assertNotIn("data-suite-world-flags", dl)

    def test_homepage_left_box_includes_flags_css_and_static(self) -> None:
        from app import render_html, static_file_path
        from world_flag_codes import WORLD_FLAG_CODES, WORLD_FLAG_COUNT

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        # Scope to page shell body (avoid CSS-only false positives)
        main = page[page.index('id="page-shell"') :]
        self.assertIn('id="suite-storefront"', main)
        self.assertIn('id="suite-world-flags"', main)
        self.assertIn(f'data-flag-count="{WORLD_FLAG_COUNT}"', main)
        self.assertIn("/static/flags/w20/", main)
        # CSS dense strip styles ship with homepage
        self.assertIn(".suite-world-flags", page)
        self.assertIn("img.suite-world-flag", page)
        # Static resolver serves a real pack file
        sample = WORLD_FLAG_CODES[0]
        resolved = static_file_path(f"/static/flags/w20/{sample}.png")
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertTrue(resolved.is_file())
        self.assertLess(resolved.stat().st_size, 4_000)


if __name__ == "__main__":
    unittest.main()
