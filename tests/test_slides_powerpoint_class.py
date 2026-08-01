"""Slides PowerPoint-class core: multi-slide content, structure, undo, entry."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rpos" / "apps"))


class TestSlidesDeckRoundTrip(unittest.TestCase):
    def test_multi_slide_content_round_trip(self) -> None:
        from rpoffice.deck import Presentation, create_presentation

        p = create_presentation("Pitch")
        # replace seed content
        p.set_slide_title(0, "Welcome")
        p.set_slide_body(0, "Hello suite")
        p.set_slide_notes(0, "Say residual privacy")
        p.set_slide_bullets(0, ["One", "Two"])
        p.add_slide(
            "Agenda",
            "What ships",
            notes="Walk bullets",
            bullets=["Pens", "Tables", "Slides"],
        )
        p.add_slide("End", "Thanks", notes="Q&A")
        again = Presentation.loads(p.dumps())
        self.assertEqual(again.title, "Pitch")
        self.assertEqual(len(again.slides), 3)
        self.assertEqual(again.slides[0].title, "Welcome")
        self.assertEqual(again.slides[0].body, "Hello suite")
        self.assertEqual(again.slides[0].notes, "Say residual privacy")
        self.assertEqual(again.slides[0].bullets, ["One", "Two"])
        self.assertEqual(again.slides[1].title, "Agenda")
        self.assertEqual(again.slides[1].bullets, ["Pens", "Tables", "Slides"])
        self.assertEqual(again.slides[2].title, "End")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "deck.slides.json"
            again.save(path)
            loaded = Presentation.load(path)
            self.assertEqual(loaded.slide_titles(), ["Welcome", "Agenda", "End"])
            self.assertEqual(loaded.slides[1].notes, "Walk bullets")
            self.assertEqual(loaded.to_dict().get("product"), "Slides")
            self.assertEqual(loaded.to_dict().get("maker"), "Raskul")


class TestSlidesStructureEdit(unittest.TestCase):
    def test_add_delete_duplicate_reorder_undo(self) -> None:
        from rpoffice.deck import PresentationEditor, create_presentation

        p = create_presentation("WB")
        ed = PresentationEditor(p)
        self.assertIs(ed.presentation, p)
        ed.set_title(0, "A")
        ed.add_slide("B", "body-b", notes="nb", bullets=["b1"])
        ed.add_slide("C", "body-c")
        self.assertEqual(p.slide_titles(), ["A", "B", "C"])
        ed.duplicate_slide(0)
        self.assertEqual(p.slide_titles()[0], "A")
        self.assertEqual(p.slide_titles()[1], "A")
        self.assertNotEqual(p.slides[0].slide_id, p.slides[1].slide_id)
        ed.reorder_slide(3, 0)  # C to front if last is C after dup → titles A,A,B,C
        self.assertEqual(p.slides[0].title, "C")
        ed.delete_slide(0)
        self.assertNotEqual(p.slides[0].title, "C")
        # undo delete restores C at front
        self.assertTrue(ed.undo())
        self.assertIs(ed.presentation, p)
        self.assertEqual(p.slides[0].title, "C")
        # undo reorder
        self.assertTrue(ed.undo())
        self.assertEqual(p.slides[0].title, "A")
        # shared identity after content undo
        ed.set_notes(0, "temp")
        self.assertTrue(ed.undo())
        self.assertNotEqual(p.slides[0].notes, "temp")
        # redo notes
        self.assertTrue(ed.redo())
        self.assertEqual(p.slides[0].notes, "temp")


class TestSlidesEntry(unittest.TestCase):
    def test_smoke_and_cli_twice(self) -> None:
        from rpoffice.apps.slides import main, smoke
        from rpoffice.brand import SLIDES
        from rpoffice.parity_scope import matrix_as_dict, slides_powerpoint_class_core_rows

        for _ in range(2):
            r = smoke()
            self.assertTrue(r["ok"])
            self.assertEqual(r["product"], SLIDES)
            self.assertEqual(r["maker"], "Raskul")
            self.assertGreaterEqual(r["slide_count"], 2)
            self.assertTrue(r["round_trip"])
            self.assertTrue(r["first_bullets"])
            self.assertTrue(r["first_notes"])
            self.assertIn("not full microsoft powerpoint", r["honesty"].lower())

        self.assertEqual(main(["--version"]), 0)
        self.assertEqual(main(["--smoke"]), 0)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "demo.slides.json"
            self.assertEqual(main(["--demo", "-o", str(path)]), 0)
            self.assertTrue(path.is_file())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("product"), "Slides")
            self.assertEqual(data.get("kind"), "slides_presentation")
            self.assertGreaterEqual(len(data.get("slides") or []), 1)

        m = matrix_as_dict()
        self.assertIn(SLIDES, m["implemented_pillars"])
        core = slides_powerpoint_class_core_rows()
        self.assertGreaterEqual(len(core), 3)
        out = [
            r
            for r in m["matrix"]
            if r["pillar"] == SLIDES and r["status"] == "out_of_scope"
        ]
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()
