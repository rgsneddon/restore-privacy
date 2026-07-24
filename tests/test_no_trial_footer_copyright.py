"""Customer surfaces: no free-trial copy; public footer is Raskul copyright."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

_TRIAL_PHRASES = (
    "free trial",
    "7 day trial",
    "7-day trial",
    "no free trial",
    "restore privacy trial",
)


class TestNoTrialOnPublicHtml(unittest.TestCase):
    def _assert_no_trial(self, html: str, label: str) -> None:
        low = html.lower()
        for phrase in _TRIAL_PHRASES:
            self.assertNotIn(phrase, low, msg=f"{label} still has {phrase!r}")
        # Bare word "trial" as product marketing (allow trial_period in scripts only)
        self.assertIsNone(
            re.search(r"\bfree\s+trial\b", low),
            msg=f"{label} free trial",
        )

    def test_homepage_and_pay_plan_and_keygen_instruction(self):
        from app import render_html
        from coffee_link import SITE_COPYRIGHT_TEXT
        from payments import KEYGEN_UNLOCK_INSTRUCTION, render_pay_plan_page_html

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self._assert_no_trial(home, "homepage")
        self.assertIn(SITE_COPYRIGHT_TEXT, home)
        self.assertIn("Raskul", home)
        self.assertNotIn("buymeacoffee.com", home.lower())

        pay = render_pay_plan_page_html("windows", interval="month").decode("utf-8")
        self._assert_no_trial(pay, "pay_plan")
        self.assertNotIn("trial", pay.lower())

        self.assertNotIn("TRIAL", KEYGEN_UNLOCK_INSTRUCTION)
        self.assertNotIn("trial", KEYGEN_UNLOCK_INSTRUCTION.lower())
        self.assertEqual(
            KEYGEN_UNLOCK_INSTRUCTION,
            "USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY",
        )

    def test_settings_explainer_and_public_docs_shell(self):
        from public_docs import render_how_to_buy_html
        from settings_explainer import render_settings_explainer_page_html

        expl = render_settings_explainer_page_html().decode("utf-8")
        self._assert_no_trial(expl, "settings_explainer")
        how = render_how_to_buy_html().decode("utf-8")
        self._assert_no_trial(how, "how_to_buy")


class TestFooterCopyright(unittest.TestCase):
    def test_footer_helper_and_homepage_placement(self):
        from app import render_html
        from coffee_link import SITE_COPYRIGHT_TEXT, render_site_copyright_footer_html
        from downloads import render_bmc_tip_html

        frag = render_site_copyright_footer_html()
        self.assertEqual(frag, render_bmc_tip_html())
        self.assertIn(SITE_COPYRIGHT_TEXT, frag)
        self.assertIn('id="site-footer"', frag)
        self.assertNotIn("href=", frag)  # plain text copyright, no tip link

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        foot_at = page.find('id="site-footer"')
        self.assertGreater(foot_at, 0)
        self.assertGreater(foot_at, page.find('id="downloads"'))


if __name__ == "__main__":
    unittest.main()
