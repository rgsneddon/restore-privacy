"""Pens Word-class core: format, structure, find/replace, undo, entry smoke."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rpos" / "apps"))


class TestPensDocumentRoundTrip(unittest.TestCase):
    def test_format_and_round_trip(self) -> None:
        from rpoffice.word import (
            Document,
            DocumentEditor,
            STYLE_HEADING1,
            create_document,
        )

        doc = create_document("Essay", "Intro paragraph.")
        ed = DocumentEditor(doc)
        ed.add_heading("Section A", level=1)
        ed.add_paragraph(
            "Bold italic underline body.",
            bold=True,
            italic=True,
            underline=True,
            font_size=14,
            align="center",
        )
        ed.add_paragraph("Left body.", align="left", font_size=11)
        raw = ed.document.dumps()
        again = Document.loads(raw)
        self.assertEqual(again.title, "Essay")
        self.assertEqual(again.schema_version, 2)
        self.assertGreaterEqual(len(again.paragraphs), 3)
        h = [p for p in again.paragraphs if p.style == STYLE_HEADING1]
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0].text, "Section A")
        body = [p for p in again.paragraphs if "Bold italic" in p.text][0]
        self.assertTrue(body.runs[0].format.bold)
        self.assertTrue(body.runs[0].format.italic)
        self.assertTrue(body.runs[0].format.underline)
        self.assertEqual(body.runs[0].format.font_size, 14)
        self.assertEqual(body.align, "center")
        # file round-trip
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "essay.pens.json"
            again.save(path)
            loaded = Document.load(path)
            self.assertEqual(loaded.title, again.title)
            self.assertEqual(loaded.plain_text(), again.plain_text())


class TestPensStructure(unittest.TestCase):
    def test_headings_lists_tables(self) -> None:
        from rpoffice.word import Document, DocumentEditor, create_document

        doc = create_document("Struct")
        ed = DocumentEditor(doc)
        ed.add_heading("H1", level=1)
        ed.add_heading("H2", level=2)
        ed.add_bullet("b1")
        ed.add_bullet("b2")
        ed.add_numbered("n1")
        ed.add_numbered("n2")
        t = ed.add_table(2, 3, fill="x")
        t.set_cell_text(0, 0, "Name")
        t.set_cell_text(1, 2, "corner")
        ed.document.add_image_placeholder("photo.png", alt="a photo")
        again = Document.loads(ed.document.dumps())
        styles = {p.style for p in again.paragraphs}
        self.assertIn("Heading1", styles)
        self.assertIn("Heading2", styles)
        bullets = [p for p in again.paragraphs if p.list_type == "bullet"]
        numbers = [p for p in again.paragraphs if p.list_type == "number"]
        self.assertEqual(len(bullets), 2)
        self.assertEqual(len(numbers), 2)
        tables = [b for b in again.blocks if b.kind == "table"]
        self.assertEqual(len(tables), 1)
        assert tables[0].table is not None
        self.assertEqual(tables[0].table.nrows, 2)
        self.assertEqual(tables[0].table.ncols, 3)
        self.assertEqual(tables[0].table.cell(0, 0).text, "Name")
        self.assertEqual(tables[0].table.cell(1, 2).text, "corner")
        images = [b for b in again.blocks if b.kind == "image"]
        self.assertEqual(len(images), 1)
        assert images[0].image is not None
        self.assertEqual(images[0].image.name, "photo.png")


class TestPensEditOps(unittest.TestCase):
    def test_find_replace_undo_redo(self) -> None:
        from rpoffice.word import DocumentEditor, create_document

        doc = create_document("Edit", "alpha beta alpha")
        ed = DocumentEditor(doc)
        ed.add_paragraph("alpha gamma")
        hits = ed.document.find_all("alpha")
        self.assertEqual(len(hits), 3)
        n = ed.replace_all("alpha", "ALPHA")
        self.assertEqual(n, 3)
        self.assertNotIn("alpha", ed.document.plain_text())
        self.assertIn("ALPHA", ed.document.plain_text())
        self.assertTrue(ed.undo())
        self.assertIn("alpha", ed.document.plain_text())
        self.assertTrue(ed.redo())
        self.assertIn("ALPHA", ed.document.plain_text())
        # insert / delete / reorder
        ed.add_paragraph("tail")
        self.assertIn("tail", ed.document.plain_text())
        idx = len(ed.document.blocks) - 1
        ed.move_block(idx, 0)
        self.assertEqual(ed.document.blocks[0].paragraph.text, "tail")
        ed.delete_block(0)
        self.assertNotIn("tail", ed.document.plain_text())
        self.assertTrue(ed.undo())  # undo delete

    def test_undo_mutates_shared_document_instance(self) -> None:
        """Caller-held Document must reflect undo (no rebind to new object)."""
        from rpoffice.word import DocumentEditor, create_document

        doc = create_document("Shared", "before")
        ed = DocumentEditor(doc)
        self.assertIs(ed.document, doc)
        ed.add_paragraph("after-edit")
        self.assertIn("after-edit", doc.plain_text())
        self.assertIs(ed.document, doc)
        self.assertTrue(ed.undo())
        self.assertIs(ed.document, doc)
        self.assertNotIn("after-edit", doc.plain_text())
        self.assertNotIn("after-edit", ed.document.plain_text())
        # save on original ref matches editor view
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "shared.pens.json"
            doc.save(path)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("after-edit", text)
        self.assertTrue(ed.redo())
        self.assertIs(ed.document, doc)
        self.assertIn("after-edit", doc.plain_text())

    def test_replace_preserves_multi_run_formatting(self) -> None:
        """replace_all must not collapse runs or drop bold/italic on neighbors."""
        from rpoffice.word import (
            Block,
            CharFormat,
            DocumentEditor,
            Paragraph,
            Run,
            create_document,
        )

        doc = create_document("Fmt")
        para = Paragraph(
            runs=[
                Run("Hello ", format=CharFormat(bold=True)),
                Run("world", format=CharFormat(italic=True)),
                Run(" end", format=CharFormat(underline=True)),
            ]
        )
        doc.blocks = [Block.paragraph_block(para)]
        ed = DocumentEditor(doc)
        n = ed.replace_all("world", "Earth")
        self.assertEqual(n, 1)
        runs = ed.document.paragraphs[0].runs
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0].text, "Hello ")
        self.assertTrue(runs[0].format.bold)
        self.assertFalse(runs[0].format.italic)
        self.assertEqual(runs[1].text, "Earth")
        self.assertTrue(runs[1].format.italic)
        self.assertFalse(runs[1].format.bold)
        self.assertEqual(runs[2].text, " end")
        self.assertTrue(runs[2].format.underline)


class TestPensEntry(unittest.TestCase):
    def test_smoke_and_cli(self) -> None:
        from rpoffice.apps.pens import main, smoke
        from rpoffice.brand import PENS
        from rpoffice.parity_scope import matrix_as_dict, pens_word_class_core_rows

        r = smoke()
        self.assertTrue(r["ok"])
        self.assertEqual(r["product"], PENS)
        self.assertEqual(r["maker"], "Raskul")
        self.assertGreaterEqual(r["headings"], 1)
        self.assertGreaterEqual(r["list_items"], 1)
        self.assertGreaterEqual(r["tables"], 1)
        self.assertTrue(r["round_trip"])
        self.assertIn("not full microsoft word", r["honesty"].lower())

        self.assertEqual(main(["--version"]), 0)
        self.assertEqual(main(["--smoke"]), 0)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "demo.pens.json"
            self.assertEqual(main(["--demo", "-o", str(path)]), 0)
            self.assertTrue(path.is_file())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("product"), "Pens")
            self.assertEqual(data.get("kind"), "pens_document")

        m = matrix_as_dict()
        self.assertIn(PENS, m["implemented_pillars"])
        core = pens_word_class_core_rows()
        self.assertGreaterEqual(len(core), 5)
        self.assertTrue(all(r["status"] == "implemented" for r in core))
        # Explicit non-claim
        out = [r for r in m["matrix"] if r["status"] == "out_of_scope"]
        self.assertTrue(any("Word" in r["feature"] or "OOXML" in r["feature"] for r in out))


if __name__ == "__main__":
    unittest.main()
