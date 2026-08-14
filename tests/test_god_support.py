"""GOD support box: research-before-reply, no placeholder learning."""

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
            result = answer_god_question(
                "What is GOD?",
                fetch_public=False,
                xai_fn=lambda *a, **k: None,
            )
            self.assertTrue(result["ok"])
            self.assertIn("GOD", result["answer"])
            self.assertGreaterEqual(result["learned"], 1)
            self.assertNotIn("I do not have that part yet", result["answer"])
            self.assertEqual(SCENARIO_INTERVAL_SEC, 7200)
            self.assertTrue(scenario_due(0, 1))
            first = tick_scenario("FRED", now=1000, force=True, question="Helsinki check")
            self.assertTrue(first["grew"])
            html = render_god_support_box_html()
            self.assertIn(GOD_BOX_ID, html)
            self.assertIn("god-question", html)
            self.assertIn("finds", html.lower())

    def test_refuses_secrets(self) -> None:
        from god_support import answer_god_question

        with tempfile.TemporaryDirectory() as td:
            import god_support as gs

            gs._data_dir = lambda: Path(td)  # type: ignore[method-assign]
            bad = answer_god_question(
                "here is RPT-KEY-secret",
                fetch_public=False,
                xai_fn=lambda *a, **k: None,
            )
            self.assertFalse(bad["ok"])

    def test_researches_docs_instead_of_grow_placeholder(self) -> None:
        from god_support import GROW_MARKERS, answer_god_question, learned_count

        with tempfile.TemporaryDirectory() as td:
            import god_support as gs

            gs._data_dir = lambda: Path(td)  # type: ignore[method-assign]
            result = answer_god_question(
                "What BeamHash difficulty is the perc pool?",
                fetch_public=False,
                xai_fn=lambda *a, **k: None,
            )
            self.assertTrue(result["ok"], result)
            low = result["answer"].lower()
            self.assertTrue(
                "beamhash" in low or "1466" in low or "3334" in low, result["answer"]
            )
            for marker in GROW_MARKERS:
                self.assertNotIn(marker, low)
            self.assertEqual(learned_count(), 1)

    def test_grow_placeholder_is_never_stored_or_replayed(self) -> None:
        from god_support import (
            answer_god_question,
            is_real_answer,
            learned_count,
            local_answer,
            record_learn,
        )

        with tempfile.TemporaryDirectory() as td:
            import god_support as gs

            gs._data_dir = lambda: Path(td)  # type: ignore[method-assign]
            fake = (
                "I do not have that part yet — and I am thrilled to learn it. "
                "Use the ticket form below."
            )
            self.assertFalse(is_real_answer(fake))
            refused = record_learn("obscure widget flux", fake, "grow")
            self.assertFalse(refused["ok"])
            self.assertEqual(learned_count(), 0)
            self.assertIsNone(local_answer("obscure widget flux"))

            result = answer_god_question(
                "zzqx vrml qwertyuiop asdfghjkl",
                fetch_public=False,
                xai_fn=lambda *a, **k: None,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result.get("source"), "researching")
            self.assertEqual(learned_count(), 0)
            self.assertNotIn("answer", result)

    def test_works_hard_every_time_via_research_fn(self) -> None:
        from god_support import answer_god_question, learned_count

        with tempfile.TemporaryDirectory() as td:
            import god_support as gs

            gs._data_dir = lambda: Path(td)  # type: ignore[method-assign]
            calls: list[str] = []

            def finder(question: str, context: str = "") -> str:
                calls.append(question)
                return (
                    "Residual DE pin is the live catalog peer; Suite nav is "
                    "vpn, wallet, backup, analysis, voting, credit, rpai."
                )

            first = answer_god_question(
                "Where is the live residual catalog peer?",
                fetch_public=False,
                xai_fn=finder,
            )
            self.assertTrue(first["ok"])
            self.assertEqual(first["source"], "web")
            self.assertGreaterEqual(learned_count(), 1)
            second = answer_god_question(
                "Where is the live residual catalog peer?",
                fetch_public=False,
                xai_fn=finder,
            )
            self.assertTrue(second["ok"])
            # Research runs on every ask — users never supply the answer.
            self.assertGreaterEqual(len(calls), 2)


class TestGodSupportRoute(unittest.TestCase):
    def test_app_mentions_god_ask_route(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/support/god-ask", src)
        self.assertIn("god_support.js", src)
        js = (ROOT / "status_page" / "static" / "god_support.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("/support/god-ask", js)
        self.assertIn("finding the answer", js)

    def test_support_page_includes_god_box(self) -> None:
        from support_tickets import render_support_page_html

        page = render_support_page_html()
        self.assertIn("god-support-box", page)
        self.assertIn("god-question", page)
        self.assertIn("/static/god_support.js", page)


if __name__ == "__main__":
    unittest.main()
