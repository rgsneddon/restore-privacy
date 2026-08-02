"""Suite homepage intro: one-shot neon typewriters + amended copy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestTypewriterPure(unittest.TestCase):
    def test_prefix_and_done_once(self) -> None:
        from public_chrome import (
            SUITE_HOME_CLOSING_TYPE,
            SUITE_HOME_WELCOME_TYPE,
            typewriter_done,
            typewriter_prefix,
            typewriter_sequence,
        )

        full = SUITE_HOME_WELCOME_TYPE
        self.assertEqual(typewriter_prefix(full, 0), "")
        self.assertEqual(typewriter_prefix(full, 1), full[0])
        self.assertEqual(typewriter_prefix(full, len(full)), full)
        self.assertEqual(typewriter_prefix(full, len(full) + 50), full)
        self.assertFalse(typewriter_done(full, 0))
        self.assertFalse(typewriter_done(full, len(full) - 1))
        self.assertTrue(typewriter_done(full, len(full)))
        self.assertTrue(typewriter_done(full, len(full) + 9))
        # Two completed sequences — consistent finals
        for _ in range(2):
            seq = typewriter_sequence(full)
            self.assertEqual(seq[0], "")
            self.assertEqual(seq[-1], full)
            self.assertEqual(len(seq), len(full) + 1)
            for i, prefix in enumerate(seq):
                self.assertEqual(prefix, full[:i])
                self.assertEqual(typewriter_done(full, i), i >= len(full))
        close = SUITE_HOME_CLOSING_TYPE
        self.assertEqual(typewriter_sequence(close)[-1], close)
        self.assertTrue(typewriter_done(close, len(close)))


class TestSuiteIntroRenderer(unittest.TestCase):
    def test_markup_order_and_copy(self) -> None:
        from public_chrome import (
            SUITE_HOME_CLOSING_TYPE,
            SUITE_HOME_INTRO_BODY,
            SUITE_HOME_INTRO_HEADING,
            SUITE_HOME_INTRO_ID,
            SUITE_HOME_WELCOME_TYPE,
            render_suite_home_intro_html,
            suite_home_intro_css,
            suite_home_intro_script_tag,
        )

        html = render_suite_home_intro_html()
        self.assertIn(f'id="{SUITE_HOME_INTRO_ID}"', html)
        self.assertIn(SUITE_HOME_WELCOME_TYPE, html)
        self.assertIn(SUITE_HOME_INTRO_HEADING, html)
        self.assertIn(SUITE_HOME_CLOSING_TYPE, html)
        self.assertIn("residual VPN protection", html)
        self.assertIn("Evolve analysis engine", html)
        self.assertIn("fun rewards token wallet", html)
        self.assertIn("convenient app", html)
        self.assertIn("three days", html)
        self.assertIn("£3 per month", html)
        self.assertIn("£30 annually", html)
        self.assertIn("RPSuite extras", html)
        self.assertIn(SUITE_HOME_INTRO_BODY[:40], html)

        # Order by unique element ids (not aria-labelledby which may cite title early)
        i_w = html.index('id="suite-welcome-type"')
        i_h = html.index('id="suite-home-intro-title"')
        i_b = html.index('id="suite-home-lead"')
        i_c = html.index('id="suite-closing-type"')
        self.assertLess(i_w, i_h)
        self.assertLess(i_h, i_b)
        self.assertLess(i_b, i_c)

        self.assertIn('data-typewriter="1"', html)
        self.assertIn('data-typewriter-once="1"', html)
        self.assertIn("neon-type", html)
        self.assertIn(f'data-typewriter-text="{SUITE_HOME_WELCOME_TYPE}"', html)
        self.assertIn(f'data-typewriter-text="{SUITE_HOME_CLOSING_TYPE}"', html)

        css = suite_home_intro_css()
        self.assertIn("Courier New", css)
        self.assertIn("neon", css.lower() or "suite-typewriter")
        self.assertIn(".suite-typewriter", css)
        self.assertIn("#7dffe8", css)
        self.assertIn("39ff88", css)

        tag = suite_home_intro_script_tag()
        self.assertIn("/static/suite_home_typewriter.js", tag)

    def test_homepage_path_includes_intro_and_script(self) -> None:
        from app import render_html

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("suite-home-intro", page)
        self.assertIn("WELCOME, ANON...", page)
        self.assertIn("...privacy you can actually use...", page)
        self.assertIn("YOUR PRIVACY, RESTORED", page)
        self.assertIn("£3 per month", page)
        self.assertIn("£30 annually", page)
        self.assertIn("suite_home_typewriter.js", page)
        self.assertIn("suite-typewriter", page)
        # Layer order in main content
        i0 = page.index("suite-welcome-type")
        i1 = page.index("...privacy you can actually use...")
        i2 = page.index("residual VPN")
        i3 = page.index("suite-closing-type")
        self.assertLess(i0, i1)
        self.assertLess(i1, i2)
        self.assertLess(i2, i3)
        # Static JS file exists
        js = ROOT / "status_page" / "static" / "suite_home_typewriter.js"
        self.assertTrue(js.is_file())
        src = js.read_text(encoding="utf-8")
        self.assertIn("typewriterPrefix", src)
        self.assertIn("data-typewriter-complete", src)
        self.assertIn("suite-home-intro", src)
        self.assertIn("data-typewriter", src)


if __name__ == "__main__":
    unittest.main()
