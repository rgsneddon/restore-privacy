"""rpOffice Corel-historical independent suite design + reveal + seamless pillars."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rpos" / "apps"))


class TestCorelHistoricalIdentity(unittest.TestCase):
    def test_suite_status_independent_not_ms_workalike(self) -> None:
        from rpoffice.brand import (
            DESIGN_LINEAGE,
            PENS,
            SLIDES,
            TABLES,
            suite_identity,
        )
        from rpoffice.parity_scope import matrix_as_dict
        from rpoffice.shell import suite_status

        st = suite_status()
        self.assertEqual(st["brands"], [PENS, TABLES, SLIDES])
        self.assertEqual(st["product"], "rpOffice")
        self.assertEqual(st["design_lineage"], DESIGN_LINEAGE)
        self.assertIn("Corel-historical", st["design_lineage"])
        self.assertFalse(st["microsoft_workalike"])
        self.assertFalse(st["corel_trademark_claimed"])
        self.assertTrue(st["seamless"])
        self.assertEqual(st["suite_order"], [PENS, TABLES, SLIDES])
        for bad in ("Word", "Excel", "PowerPoint"):
            self.assertNotIn(bad, st["brands"])
        # identity helper matches shell
        ident = suite_identity()
        self.assertFalse(ident["microsoft_workalike"])
        self.assertIn("independent", str(ident["design_lineage"]).lower())
        # parity framing
        m = matrix_as_dict()
        self.assertFalse(m["microsoft_workalike"])
        self.assertFalse(m["corel_trademark_claimed"])
        self.assertIn("Corel-historical", m["variant"])
        note = m["note"].lower()
        self.assertIn("pens", note)
        self.assertIn("independent", note)
        # must deny MS workalike positioning (honesty), not claim to be a clone
        self.assertTrue(
            "not a microsoft" in note
            or "not microsoft" in note
            or "microsoft office parity" in note
        )
        self.assertFalse(m.get("microsoft_workalike"))
        # primary analogue language is independent, not "Word-class core" only
        pens_impl = [
            r for r in m["matrix"] if r["pillar"] == PENS and r["status"] == "implemented"
        ]
        self.assertTrue(any("structure" in r["analogue"].lower() for r in pens_impl))
        # out of scope includes Corel trademarks and MS
        oos = [r for r in m["matrix"] if r["status"] == "out_of_scope"]
        self.assertTrue(any("WordPerfect" in r["analogue"] or "WordPerfect" in r["feature"] for r in oos))
        self.assertTrue(any("Microsoft" in r["analogue"] for r in oos))


class TestPensRevealStructure(unittest.TestCase):
    def test_structure_tokens_match_and_update_after_edit(self) -> None:
        from rpoffice.word import DocumentEditor, create_document

        doc = create_document("Reveal Demo", "Opening")
        ed = DocumentEditor(doc)
        ed.add_heading("Chapter", level=1)
        ed.add_paragraph("Body text", bold=True)
        ed.add_bullet("Item one")
        t = ed.add_table(2, 2, fill="")
        t.set_cell_text(0, 0, "cell")
        tokens = ed.structure_tokens()
        reveal = ed.reveal_structure()
        # Doc header
        self.assertEqual(tokens[0].get("code"), "Doc")
        self.assertEqual(tokens[0].get("title"), "Reveal Demo")
        kinds = [t.get("kind") for t in tokens if "kind" in t]
        self.assertIn("paragraph", kinds)
        self.assertIn("table", kinds)
        # structure codes present
        self.assertIn("[Style:Heading1]", reveal)
        self.assertIn("[List:bullet]", reveal)
        self.assertIn("[Table:", reveal)
        self.assertIn("Chapter", reveal)
        self.assertIn("Item one", reveal)
        before_count = len(tokens)
        before_reveal = reveal
        # real edit on shipped path
        ed.add_heading("After Edit", level=2)
        tokens2 = ed.structure_tokens()
        reveal2 = ed.reveal_structure()
        self.assertGreater(len(tokens2), before_count)
        self.assertNotEqual(reveal2, before_reveal)
        self.assertIn("After Edit", reveal2)
        self.assertIn("[Style:Heading2]", reveal2)
        # shared identity
        self.assertIs(ed.document, doc)
        self.assertIn("After Edit", doc.plain_text())


class TestSeamlessSuiteSmoke(unittest.TestCase):
    def test_suite_smoke_twice_all_pillars(self) -> None:
        from rpoffice.__main__ import main, smoke
        from rpoffice.apps import pens, slides, tables
        from rpoffice.brand import DESIGN_LINEAGE, PENS, SLIDES, TABLES

        for _ in range(2):
            r = smoke()
            self.assertTrue(r["ok"])
            self.assertTrue(r["smoke"])
            self.assertEqual(r["brands"], [PENS, TABLES, SLIDES])
            self.assertTrue(r["brands_ok"])
            self.assertTrue(r["apps_ok"])
            self.assertTrue(r["suite_consistent"])
            self.assertEqual(r["design_lineage"], DESIGN_LINEAGE)
            self.assertFalse(r["microsoft_workalike"])
            for brand in (PENS, TABLES, SLIDES):
                app = r["apps"][brand]
                self.assertTrue(app["ok"], brand)
                self.assertEqual(app["product"], brand)
                self.assertEqual(app.get("family"), r["family"])
                self.assertIn("design_lineage", app)
            # pens reveal exercised
            self.assertTrue(r["apps"][PENS].get("reveal_ok"))

        self.assertEqual(main(["--version"]), 0)
        self.assertEqual(main(["--smoke"]), 0)
        self.assertEqual(main(["--parity"]), 0)
        # pillar entries
        self.assertTrue(pens.smoke()["ok"])
        self.assertTrue(tables.smoke()["ok"])
        self.assertTrue(slides.smoke()["ok"])


class TestFunctionRegression(unittest.TestCase):
    def test_pillar_cores_still_work(self) -> None:
        from rpoffice.apps import pens, slides, tables
        from rpoffice.deck import PresentationEditor, create_presentation
        from rpoffice.sheet import WorkbookEditor, create_workbook
        from rpoffice.word import DocumentEditor, create_document

        p = pens.smoke()
        self.assertTrue(p["ok"])
        self.assertGreaterEqual(p["paragraphs"], 1)
        self.assertTrue(p["round_trip"])

        t = tables.smoke()
        self.assertTrue(t["ok"])
        self.assertEqual(t["formula_A1_plus_B1"], 15.0)
        self.assertEqual(t["formula_after_recalc"], 25.0)
        self.assertEqual(t["sum_A2_A4"], 6.0)
        self.assertTrue(t["round_trip"])

        s = slides.smoke()
        self.assertTrue(s["ok"])
        self.assertGreaterEqual(s["slide_count"], 2)
        self.assertTrue(s["round_trip"])

        # direct model paths
        doc = create_document("X", "y")
        DocumentEditor(doc).add_bullet("z")
        self.assertIn("z", doc.plain_text())
        wb = create_workbook("W", "S")
        ed = WorkbookEditor(wb)
        ed.set_ref("A1", 2)
        ed.set_ref("B1", 3)
        self.assertEqual(ed.evaluate("=A1+B1"), 5)
        pr = create_presentation("D")
        ped = PresentationEditor(pr)
        ped.add_slide("Two")
        self.assertEqual(len(pr.slides), 2)


if __name__ == "__main__":
    unittest.main()
