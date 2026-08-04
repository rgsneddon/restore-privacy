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
        self.assertIn("personal use", body.lower())
        self.assertIn("no obligation to pay", body.lower())
        self.assertIn("subscription", body.lower())
        # Price once (subscription wording may omit KEYGEN in the lead)
        self.assertEqual(_count_ci(body, "£3"), 1)
        self.assertEqual(_count_ci(body, "£30"), 1)
        self.assertLessEqual(_count_ci(body, "KEYGEN"), 1)
        # Closing typewriter owns the tagline — body does not restate it
        # (lead may say "privacy restored" as product phrase; full tagline is typewriter)
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
        import re

        sub = SUITE_PRODUCT_SUBTITLE
        hint = SUITE_PAY_HINT_HTML
        suite = render_suite_storefront_html()
        # Blurb = download action only; pay-hint = KEYGEN price only (not two journeys).
        self.assertIn("Free download", sub)
        self.assertNotIn("KEYGEN", sub)
        self.assertNotIn("trial", sub.lower())
        self.assertNotIn("virtual private network", sub.lower())
        self.assertNotIn("dedicated virtual", sub.lower())
        self.assertNotIn("residual traffic", sub.lower())
        self.assertEqual(_count_ci(hint, "KEYGEN"), 1)
        self.assertNotIn("trial", hint.lower())
        self.assertNotIn("free", hint.lower())
        self.assertNotIn("72-hour", hint.lower())
        self.assertNotIn("residual", hint.lower())
        self.assertIn("suite-blurb", suite)
        self.assertIn(sub, suite)
        # Adjacent blurb + pay-hint together: trial journey at most once (prefer zero —
        # homepage intro owns free/trial/KEYGEN path).
        blurb_m = re.search(
            r'id="suite-blurb"[^>]*>([^<]+)', suite, flags=re.I
        )
        hint_m = re.search(
            r'id="suite-pay-hint"[^>]*>(.*?)</p>', suite, flags=re.S | re.I
        )
        self.assertIsNotNone(blurb_m)
        self.assertIsNotNone(hint_m)
        pair = (blurb_m.group(1) + " " + hint_m.group(1)).lower()  # type: ignore[union-attr]
        self.assertNotIn("three-day", pair)
        self.assertNotIn("3-day", pair)
        self.assertNotIn("72-hour", pair)
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

    def test_settings_page_html_forbids_residual_trial_stacks(self) -> None:
        """Drive shipped full-page renderer — install box + unlock must not re-stack."""
        from settings_explainer import (
            render_install_howto_box_html,
            render_settings_explainer_page_html,
            suite_howto_parts_catalog,
        )

        install = render_install_howto_box_html()
        page = render_settings_explainer_page_html().decode("utf-8")
        for blob, label in ((install, "install_box"), (page, "full_page")):
            low = blob.lower()
            for banned in (
                "72-hour",
                "72 hours",
                "free residual trial",
                "residual connect",
                "residual public ip",
                "residual hello",
                "monopin",
            ):
                self.assertNotIn(
                    banned,
                    low,
                    msg=f"{label} still has mechanical stack: {banned!r}",
                )
        # Unlock part is paste-focused, not a second free-install lecture
        unlock = next(p for p in suite_howto_parts_catalog() if p["id"] == "suite-unlock")
        self.assertIn("KEYGEN", unlock["title"].upper())
        unlock_blob = f"{unlock['title']} {unlock['what']} {unlock['how']} {unlock['default']}"
        self.assertNotIn("Install free", unlock_blob)
        self.assertNotIn("3-day trial", unlock_blob.lower())
        self.assertNotIn("three free days", unlock_blob.lower())
        # Intro owns the free/trial journey once; install still mentions KEYGEN once
        self.assertIn("KEYGEN", install.upper())
        self.assertIn("Press Connect", install)
        self.assertIn("install-run-howto-box", page)
        self.assertIn("suite-guide-intro", page)

    def test_settings_catalog_includes_auto_connect_if_idle_and_kill_switch(self) -> None:
        """Drive shipped settings_parts_catalog — v1.2.0 controls must be documented."""
        from settings_explainer import settings_parts_catalog

        parts = settings_parts_catalog()
        by_id = {p["id"]: p for p in parts}
        self.assertIn("auto-connect-if-idle", by_id)
        idle = by_id["auto-connect-if-idle"]
        self.assertEqual(idle["default"].lower(), "off")
        low = f"{idle['title']} {idle['body']}".lower()
        self.assertTrue(
            "re-open" in low or "reconnect" in low or "reopen" in low,
            msg=f"idle entry must describe reconnect: {idle!r}",
        )
        self.assertTrue(
            "drop" in low or "idle" in low or "blip" in low,
            msg=f"idle body should explain drop/reconnect: {idle['body']!r}",
        )
        self.assertIn("disconnect", low)
        self.assertIn("kill-switch-opt-in", by_id)
        ks = by_id["kill-switch-opt-in"]
        self.assertEqual(ks["default"].lower(), "off")
        self.assertIn("confirm", ks["body"].lower())

if __name__ == "__main__":
    unittest.main()
