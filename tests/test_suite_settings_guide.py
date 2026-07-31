"""Suite Settings guide: human how-to for VPN / % / EVOLVE / unlock / Settings."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuiteSettingsGuideCopy(unittest.TestCase):
    def test_intro_and_howto_parts_human_suite_story(self) -> None:
        from settings_explainer import (
            SUITE_GUIDE_INTRO_BODY,
            SUITE_GUIDE_INTRO_FOOT,
            SUITE_GUIDE_INTRO_HEADING,
            suite_guide_copy_is_valid,
            suite_howto_ids,
            suite_howto_parts_catalog,
        )

        self.assertIn("Restore Privacy Suite", SUITE_GUIDE_INTRO_HEADING)
        body = SUITE_GUIDE_INTRO_BODY
        foot = SUITE_GUIDE_INTRO_FOOT
        self.assertGreater(len(body), 40)
        self.assertIn("KEYGEN", body.upper())
        self.assertTrue("free" in body.lower() or "free" in foot.lower())
        self.assertIn("VPN", body)
        self.assertIn("%", body)
        self.assertIn("EVOLVE", body.upper())
        # Lead is not residual IP laundry
        for bad in (
            "178.105.187.178",
            "82.221.101.241",
            "RPT_MULTIHOP",
            "residual-via-exit",
            "monopin",
        ):
            self.assertNotIn(bad, body)
            self.assertNotIn(bad, foot)
        self.assertNotIn("paywall", (body + foot).lower())
        self.assertTrue(suite_guide_copy_is_valid())

        parts = suite_howto_parts_catalog()
        ids = suite_howto_ids()
        for need in (
            "suite-unlock",
            "suite-vpn",
            "suite-wallet",
            "suite-evolve",
            "suite-settings-gear",
        ):
            self.assertIn(need, ids)
        for p in parts:
            self.assertGreater(len(p["what"].strip()), 20, p["id"])
            self.assertGreater(len(p["how"].strip()), 20, p["id"])
            self.assertTrue(p["default"].strip(), p["id"])
            self.assertNotIn("paywall", p["what"].lower())
            self.assertNotIn("paywall", p["how"].lower())

        unlock = next(p for p in parts if p["id"] == "suite-unlock")
        self.assertIn("KEYGEN", unlock["how"].upper())
        self.assertTrue(
            "free" in unlock["what"].lower() or "free" in unlock["how"].lower()
        )
        vpn = next(p for p in parts if p["id"] == "suite-vpn")
        self.assertIn("Connect", vpn["how"])
        wallet = next(p for p in parts if p["id"] == "suite-wallet")
        self.assertIn("%", wallet["title"])
        evolve = next(p for p in parts if p["id"] == "suite-evolve")
        self.assertIn("EVOLVE", evolve["title"].upper())

    def test_settings_catalog_includes_self_update_and_keygen(self) -> None:
        from settings_explainer import catalog_ids, settings_parts_catalog

        ids = catalog_ids()
        self.assertIn("suite-self-update", ids)
        self.assertIn("keygen", ids)
        self_update = next(p for p in settings_parts_catalog() if p["id"] == "suite-self-update")
        low = self_update["body"].lower()
        self.assertIn("unpack", low)
        self.assertIn("off", self_update["default"].lower())
        keygen = next(p for p in settings_parts_catalog() if p["id"] == "keygen")
        self.assertIn("KEYGEN", keygen["body"].upper())
        self.assertIn("free", keygen["body"].lower())


class TestSuiteSettingsGuideHtml(unittest.TestCase):
    def test_rendered_page_structure_and_suite_brand(self) -> None:
        from settings_explainer import (
            render_install_howto_box_html,
            render_settings_explainer_page_html,
            render_suite_guide_intro_html,
            render_suite_howto_parts_html,
            suite_guide_copy_is_valid,
        )

        html = render_settings_explainer_page_html().decode("utf-8")
        self.assertIn('id="settings-explainer-page"', html)
        self.assertIn('data-product="suite"', html)
        self.assertIn("Restore Privacy Suite", html)
        self.assertIn("Settings guide", html)
        self.assertIn('id="suite-guide-intro"', html)
        self.assertIn('id="suite-howto-parts"', html)
        self.assertIn('id="howto-suite-vpn"', html)
        self.assertIn('id="howto-suite-wallet"', html)
        self.assertIn('id="howto-suite-evolve"', html)
        self.assertIn('id="howto-suite-unlock"', html)
        self.assertIn('id="settings-explainers-box"', html)
        self.assertIn('id="setting-suite-self-update"', html)
        self.assertIn('id="install-run-howto-box"', html)
        self.assertIn("install-howto-steps", html)
        low = html.lower()
        self.assertIn("free", low)
        self.assertIn("keygen", low)
        self.assertIn("vpn", low)
        self.assertIn("evolve", low)
        self.assertIn("press connect", low)
        self.assertIn("unpack", low)
        self.assertNotIn("paywall", low)
        # Free download lead — not sole paid-package story
        self.assertIn("download the suite for free", low)
        self.assertNotIn("pay on the status page", low)
        self.assertTrue(suite_guide_copy_is_valid(html))

        # Order: intro → suite howto → settings catalog → install
        i_intro = html.index('id="suite-guide-intro"')
        i_parts = html.index('id="suite-howto-parts"')
        i_set = html.index('id="settings-explainers-box"')
        i_how = html.index('id="install-run-howto-box"')
        self.assertLess(i_intro, i_parts)
        self.assertLess(i_parts, i_set)
        self.assertLess(i_set, i_how)

        # Pure builders also non-empty
        self.assertIn("suite-guide-lead", render_suite_guide_intro_html())
        self.assertIn("howto-suite-vpn", render_suite_howto_parts_html())
        self.assertIn("KEYGEN", render_install_howto_box_html().upper())


class TestSuiteSettingsGuideLaunch(unittest.TestCase):
    def test_fresh_import_page_render_entry(self) -> None:
        import importlib

        mod = importlib.import_module("settings_explainer")
        raw = mod.render_settings_explainer_page_html()
        self.assertIsInstance(raw, (bytes, bytearray))
        html = raw.decode("utf-8")
        self.assertIn("settings-explainer-page", html)
        self.assertIn("Restore Privacy Suite", html)
        self.assertGreater(len(html), 500)


if __name__ == "__main__":
    unittest.main()
