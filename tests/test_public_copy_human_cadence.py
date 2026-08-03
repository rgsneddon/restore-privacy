"""Public marketing copy: human cadence, no same-section double-explainers."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


def _count_ci(hay: str, needle: str) -> int:
    """Count whole-phrase matches (avoid £3 matching inside £30)."""
    return len(re.findall(rf"(?<!\w){re.escape(needle)}(?!\d)", hay, flags=re.I))


class TestPublicCopyHumanCadence(unittest.TestCase):
    def test_homepage_intro_one_product_definition_price_once(self) -> None:
        from public_chrome import (
            SUITE_HOME_INTRO_BODY,
            SUITE_HOME_CLOSING_TYPE,
            render_suite_home_intro_html,
        )

        body = SUITE_HOME_INTRO_BODY
        html = render_suite_home_intro_html()
        self.assertIn("virtual private network", body.lower())
        self.assertEqual(_count_ci(body, "KEYGEN"), 1)
        self.assertEqual(_count_ci(body, "£3"), 1)
        self.assertEqual(_count_ci(body, "£30"), 1)
        # Closing typewriter owns the tagline — body does not restate it
        self.assertNotIn("your privacy, restored", body.lower())
        self.assertIn(SUITE_HOME_CLOSING_TYPE, html)
        # No residual/tunnel jargon stack in the lead
        for jargon in ("residual traffic", "full tunnel", "monopin", "multi-hop"):
            self.assertNotIn(jargon, body.lower())
        # No multi-product Suite pitch
        for bad in ("Evolve", "Perccent", "RPSuite", "Restore Privacy Suite"):
            self.assertNotIn(bad, body)
            self.assertNotIn(bad, html)

    def test_storefront_does_not_redefine_product(self) -> None:
        from downloads import (
            SUITE_PRODUCT_SUBTITLE,
            SUITE_PAY_HINT_HTML,
            render_suite_storefront_html,
        )

        sub = SUITE_PRODUCT_SUBTITLE
        hint = SUITE_PAY_HINT_HTML
        suite = render_suite_storefront_html()
        # Action language, not a second "what is a VPN" lecture
        self.assertIn("Free download", sub)
        self.assertIn("KEYGEN", sub)
        self.assertNotIn("virtual private network", sub.lower())
        self.assertNotIn("dedicated virtual", sub.lower())
        self.assertNotIn("residual traffic", sub.lower())
        # Pay hint: KEYGEN once in the HTML block (strong tag still one concept)
        self.assertEqual(_count_ci(hint, "KEYGEN"), 1)
        self.assertNotIn("72-hour", hint.lower())
        self.assertNotIn("residual Connect", hint)
        self.assertIn("suite-blurb", suite)
        self.assertIn(sub, suite)
        # Intro-style product definition must not reappear in storefront section alone
        self.assertNotIn("virtual private network for residual", suite.lower())

    def test_how_to_buy_and_map_are_concise(self) -> None:
        from public_docs import render_how_to_buy_html
        from downloads import render_downloads_map_page_html, RELEASE_VERSION

        buy = render_how_to_buy_html().decode("utf-8")
        # One KEYGEN price story in the lead (not re-stacked residual jargon)
        lead_match = re.search(
            r'id="how-to-buy-heading".*?</p>', buy, flags=re.S | re.I
        )
        self.assertIsNotNone(lead_match)
        lead = lead_match.group(0)  # type: ignore[union-attr]
        self.assertIn("KEYGEN", lead.upper())
        self.assertNotIn("dedicated virtual private network", lead.lower())
        self.assertNotIn("residual Connect includes", lead)
        self.assertNotIn("72-hour", lead.lower())

        mhtml = render_downloads_map_page_html().decode("utf-8")
        self.assertIn(RELEASE_VERSION, mhtml)
        blurb_m = re.search(
            r'id="downloads-map-blurb"[^>]*>(.*?)</p>', mhtml, flags=re.S | re.I
        )
        self.assertIsNotNone(blurb_m)
        blurb = re.sub(r"<[^>]+>", " ", blurb_m.group(1))  # type: ignore[union-attr]
        blurb = re.sub(r"\s+", " ", blurb).strip()
        # Short map blurb: free installer + /pay once
        self.assertIn("free installer", blurb.lower())
        self.assertIn("/pay", blurb.lower())
        self.assertNotIn("monopin", blurb.lower())
        self.assertNotIn("same free path as the home", blurb.lower())
        self.assertLess(len(blurb), 160)

    def test_settings_guide_intro_not_double_trial(self) -> None:
        from settings_explainer import (
            SUITE_GUIDE_INTRO_BODY,
            SUITE_GUIDE_INTRO_FOOT,
            suite_guide_copy_is_valid,
            render_suite_guide_intro_html,
        )

        body = SUITE_GUIDE_INTRO_BODY
        foot = SUITE_GUIDE_INTRO_FOOT
        # Trial mentioned once in body; foot does not re-explain trial length
        self.assertEqual(_count_ci(body, "three days"), 1)
        self.assertNotIn("72-hour", body.lower())
        self.assertNotIn("72-hour", foot.lower())
        self.assertNotIn("3-day", foot.lower())
        self.assertNotIn("three-day", foot.lower())
        self.assertTrue(suite_guide_copy_is_valid())
        html = render_suite_guide_intro_html()
        self.assertIn("KEYGEN", html.upper())
        self.assertIn("VPN", html.upper())


if __name__ == "__main__":
    unittest.main()
