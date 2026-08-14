"""GOD support box + two-hour FRED/GOD scenario cadence."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


class TestGodSupport(unittest.TestCase):
    def test_local_product_answer_and_learn(self) -> None:
        from god_support import (
            GOD_BOX_ID,
            SCENARIO_INTERVAL_SEC,
            answer_god_question,
            render_god_support_box_html,
            scenario_due,
            tick_scenario,
        )

        with tempfile.TemporaryDirectory() as td:
            import god_support as gs

            gs._data_dir = lambda: Path(td)  # type: ignore[method-assign]
            result = answer_god_question("What is GOD?")
            self.assertTrue(result["ok"])
            self.assertIn("GOD", result["answer"])
            self.assertGreaterEqual(result["learned"], 1)
            self.assertEqual(SCENARIO_INTERVAL_SEC, 7200)
            self.assertTrue(scenario_due(0, 1))
            first = tick_scenario("FRED", now=1000, force=True, question="Helsinki check")
            self.assertTrue(first["grew"])
            html = render_god_support_box_html()
            self.assertIn(GOD_BOX_ID, html)
            self.assertIn("god-question", html)

    def test_refuses_secrets(self) -> None:
        from god_support import answer_god_question

        with tempfile.TemporaryDirectory() as td:
            import god_support as gs

            gs._data_dir = lambda: Path(td)  # type: ignore[method-assign]
            bad = answer_god_question("here is RPT-KEY-secret")
            self.assertFalse(bad["ok"])


class TestGodSupportRoute(unittest.TestCase):
    def test_app_mentions_god_ask_route(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/support/god-ask", src)
        self.assertIn("god_support.js", src)
        js = (ROOT / "status_page" / "static" / "god_support.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("/support/god-ask", js)


if __name__ == "__main__":
    unittest.main()
