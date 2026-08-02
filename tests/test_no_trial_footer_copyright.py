"""Customer surfaces: 3-day free trial copy; public footer is Raskul copyright.

(Formerly asserted *no* trial; catalog policy is now a 3-day free trial.)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

_LEGACY_TRIAL_PHRASES = (
    "7 day trial",
    "7-day trial",
    "begins after your 7 day trial",
)


class TestCatalogThreeDayTrialOnPublicHtml(unittest.TestCase):
    def _assert_no_legacy_seven_day(self, html: str, label: str) -> None:
        low = html.lower()
        for phrase in _LEGACY_TRIAL_PHRASES:
            self.assertNotIn(phrase, low, msg=f"{label} still has legacy {phrase!r}")

    def _assert_three_day_trial(self, html: str, label: str) -> None:
        low = html.lower()
        self.assertTrue(
            "3-day free trial" in low or "3 day free trial" in low or "3-day trial" in low,
            msg=f"{label} missing 3-day free trial wording",
        )
        self.assertTrue(
            "no money is taken until after the trial ends" in low
            or "no charge until trial ends" in low
            or "no money taken until after" in low
            or "not charged until" in low,
            msg=f"{label} missing no-charge-until-trial-ends wording",
        )
        self._assert_no_legacy_seven_day(html, label)

    def test_homepage_and_pay_plan_and_keygen_instruction(self):
        from app import render_html
        from coffee_link import SITE_COPYRIGHT_TEXT
        from payments import KEYGEN_UNLOCK_INSTRUCTION, render_pay_plan_page_html

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self._assert_three_day_trial(home, "homepage")
        self.assertIn(SITE_COPYRIGHT_TEXT, home)
        self.assertIn("Raskul", home)
        self.assertNotIn("buymeacoffee.com", home.lower())
        # Live catalog must not claim pay-immediate as the sole policy
        self.assertNotIn("subscription starts when you pay", home.lower())

        pay = render_pay_plan_page_html("windows", interval="month").decode("utf-8")
        self._assert_three_day_trial(pay, "pay_plan")
        self.assertIn("3-day free trial", pay.lower())

        self.assertNotIn("TRIAL", KEYGEN_UNLOCK_INSTRUCTION)
        self.assertEqual(
            KEYGEN_UNLOCK_INSTRUCTION,
            "USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY",
        )

    def test_settings_explainer_and_public_docs_shell(self):
        from public_docs import render_how_to_buy_html
        from settings_explainer import render_settings_explainer_page_html

        expl = render_settings_explainer_page_html().decode("utf-8")
        self._assert_three_day_trial(expl, "settings_explainer")
        how = render_how_to_buy_html().decode("utf-8")
        self._assert_three_day_trial(how, "how_to_buy")


class TestFooterCopyright(unittest.TestCase):
    def test_footer_helper_and_homepage_placement(self):
        from app import render_html
        from coffee_link import SITE_COPYRIGHT_TEXT, render_site_copyright_footer_html
        from public_chrome import public_page_close

        # Site footer is copyright left + downloads-map link right (not BMC tip).
        frag = render_site_copyright_footer_html()
        self.assertIn(SITE_COPYRIGHT_TEXT, frag)
        self.assertIn('id="site-footer"', frag)
        self.assertIn("download map", frag)
        self.assertIn("site-footer-downloads-map", frag)
        self.assertIn("site-footer", public_page_close())
        self.assertNotIn("buymeacoffee.com", frag)

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        foot_at = page.find('id="site-footer"')
        self.assertGreater(foot_at, 0)
        self.assertGreater(foot_at, page.find('id="downloads"'))
        self.assertIn(SITE_COPYRIGHT_TEXT, page)
        self.assertIn("download map", page)


if __name__ == "__main__":
    unittest.main()
