"""World-flags pack + helper; homepage no longer mounts the flag strip."""

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
        from world_flag_codes import (
            UK_HOME_NATION_CODES,
            WORLD_FLAG_CODES,
            WORLD_FLAG_COUNT,
        )

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
        # Unique codes (ISO 2-letter + home-nation 3-letter extras)
        self.assertEqual(len(set(WORLD_FLAG_CODES)), WORLD_FLAG_COUNT)
        for cc in WORLD_FLAG_CODES:
            self.assertRegex(cc, r"^[a-z]{2,3}$")
        # UK home nations present with dedicated codes (not sc/ni ISO collisions)
        for cc in UK_HOME_NATION_CODES:
            self.assertIn(cc, WORLD_FLAG_CODES)
        self.assertIn("gb", WORLD_FLAG_CODES)
        self.assertNotEqual(
            set(UK_HOME_NATION_CODES) & {"sc", "ni"},
            set(UK_HOME_NATION_CODES),
        )

    def test_uk_home_nations_distinct_assets_and_labels(self) -> None:
        from downloads import render_suite_world_flags_html, world_flag_static_url
        from world_flag_codes import (
            UK_HOME_NATION_CODES,
            UK_HOME_NATION_FLAGS,
            UK_HOME_NATION_TITLES,
        )

        for code, title in UK_HOME_NATION_FLAGS:
            self.assertEqual(UK_HOME_NATION_TITLES[code], title)
            p = FLAGS_DIR / f"{code}.png"
            self.assertTrue(p.is_file(), f"missing home-nation asset {p}")
            self.assertEqual(p.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(p.stat().st_size, 40)

        # Must not use ISO sc (Seychelles) / ni (Nicaragua) as stand-ins
        self.assertEqual(UK_HOME_NATION_CODES, ("sct", "eng", "nir", "wls"))
        # Pure helper still builds valid strip markup when called directly
        html = render_suite_world_flags_html()
        for code, title in UK_HOME_NATION_FLAGS:
            self.assertIn(f'data-flag-cc="{code}"', html)
            self.assertIn(f'data-flag-nation="{title}"', html)
            self.assertIn(f'title="{title}"', html)
            self.assertIn(f'alt="{title}"', html)
            self.assertIn(world_flag_static_url(code), html)
            self.assertIn('data-flag-home-nation="1"', html)

    def test_homepage_and_downloads_omit_world_flags_strip(self) -> None:
        from downloads import (
            render_download_section_html,
            render_suite_storefront_html,
            render_suite_world_flags_html,
            world_flag_codes,
            world_flag_static_url,
        )
        from world_flag_codes import WORLD_FLAG_COUNT

        codes = world_flag_codes()
        self.assertGreaterEqual(len(codes), MIN_WORLD_FLAGS)

        # Helper still valid
        flags_html = render_suite_world_flags_html()
        self.assertIn('id="suite-world-flags"', flags_html)
        self.assertIn(f'data-flag-count="{WORLD_FLAG_COUNT}"', flags_html)
        ccs = re.findall(r'data-flag-cc="([a-z]{2,3})"', flags_html)
        self.assertEqual(len(ccs), WORLD_FLAG_COUNT)
        for cc in ("us", "gb", "de", "jp", "br", "sct", "eng", "nir", "wls"):
            self.assertIn(world_flag_static_url(cc), flags_html)

        # Suite storefront: no flags strip
        suite = render_suite_storefront_html()
        self.assertIn('id="suite-storefront"', suite)
        self.assertNotIn('id="suite-world-flags"', suite)
        self.assertNotIn("data-suite-world-flags", suite)
        self.assertIn("Get KEYGEN", suite)

        # Downloads right box: still present, no flags strip
        dl = render_download_section_html()
        self.assertIn('id="downloads"', dl)
        self.assertIn("Download Suite client", dl)
        self.assertIn('id="dl-local-price"', dl)
        self.assertIn("dl-buy-form", dl)
        self.assertNotIn('id="dl-price-box"', dl)
        self.assertNotIn('id="dl-only-price"', dl)
        self.assertNotIn('id="suite-world-flags"', dl)
        self.assertNotIn("data-downloads-world-flags", dl)
        self.assertNotIn("data-suite-world-flags", dl)
        self.assertNotIn("suite-world-flag", dl)
        self.assertNotIn("/static/flags/w20/", dl)

    def test_homepage_omits_flags_strip_downloads_still_present(self) -> None:
        from app import render_html, static_file_path
        from world_flag_codes import WORLD_FLAG_CODES

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = page[page.index('id="page-shell"') :]
        self.assertIn('id="suite-storefront"', main)
        self.assertIn('id="downloads"', main)
        self.assertNotIn('id="suite-world-flags"', main)
        self.assertNotIn("data-suite-world-flags", main)
        self.assertNotIn("data-downloads-world-flags", main)
        self.assertNotIn("/static/flags/w20/", main)

        dl_at = main.index('id="downloads"')
        dl_end = main.index("</section>", dl_at)
        dl_block = main[dl_at:dl_end]
        self.assertIn("Download Suite client", dl_block)
        self.assertIn('id="dl-local-price"', dl_block)
        self.assertIn("dl-buttons", dl_block)
        self.assertNotIn('id="dl-price-box"', dl_block)
        self.assertNotIn('id="suite-world-flags"', dl_block)

        # Flag assets still on disk / static resolver for other uses
        for sample in (WORLD_FLAG_CODES[0], "sct", "eng", "nir", "wls"):
            resolved = static_file_path(f"/static/flags/w20/{sample}.png")
            self.assertIsNotNone(resolved, sample)
            assert resolved is not None
            self.assertTrue(resolved.is_file(), sample)
            self.assertLess(resolved.stat().st_size, 4_000)


if __name__ == "__main__":
    unittest.main()
