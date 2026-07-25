"""Section B Privacy probes table: STATE colour boxes + in-cell Notes scroll."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from public_docs import (  # noqa: E402
    DOC_SHELL_CSS,
    markdownish_to_html,
    rag_swatch_html,
    repair_audit_emoji_mojibake,
    render_document_html,
)


SECTION_B_MD = """
## Privacy probes (section B — audit timer)

| Probe | State | Notes |
|-------|-------|-------|
| **nolog_journald** | **SKIP** | short skip note |
| **no_priv_public_trees** | **PASS** | scanned_roots=6; hits=0 |
| **title_only_status** | **FAIL** | title_only=False; body has clients_connected leak |
| **host_privacy_drift** | SKIP | lengthy note that should scroll in-cell: """ + (
    "journald drop-in 99-rpt-privacy.conf absent; " * 8
) + """|
"""


class TestRagSwatchWordStates(unittest.TestCase):
    def test_pass_skip_fail_map_to_green_amber_red(self):
        for raw, css, label in (
            ("**PASS**", "rag-green", "PASS"),
            ("PASS", "rag-green", "PASS"),
            ("**SKIP**", "rag-amber", "SKIP"),
            ("skip", "rag-amber", "SKIP"),
            ("**FAIL**", "rag-red", "FAIL"),
            ("FAIL", "rag-red", "FAIL"),
            ("🟩", "rag-green", "Green"),
            ("🟧", "rag-amber", "Amber"),
            ("🟥", "rag-red", "Red"),
        ):
            with self.subTest(raw=raw):
                html = rag_swatch_html(raw)
                self.assertIsNotNone(html)
                assert html is not None
                self.assertIn(f"rag-swatch {css}", html)
                self.assertIn(f'aria-label="{label}"', html)

    def test_non_state_returns_none(self):
        self.assertIsNone(rag_swatch_html("nolog_journald"))
        self.assertIsNone(rag_swatch_html("**probe_name**"))
        self.assertIsNone(rag_swatch_html(""))

    def test_cp1252_mojibake_colour_squares_map_to_swatches(self):
        """UTF-8 RAG squares mis-decoded as cp1252 must still become solid boxes."""
        for good, css, label in (
            ("🟩", "rag-green", "Green"),
            ("🟧", "rag-amber", "Amber"),
            ("🟥", "rag-red", "Red"),
        ):
            moj = good.encode("utf-8").decode("cp1252")
            self.assertNotEqual(moj, good)
            repaired = repair_audit_emoji_mojibake(moj)
            self.assertEqual(repaired, good)
            html = rag_swatch_html(moj)
            self.assertIsNotNone(html)
            assert html is not None
            self.assertIn(f"rag-swatch {css}", html)
            self.assertIn(f'aria-label="{label}"', html)
            # Swatch path must not leave the wonky mojibake glyph as cell content
            self.assertNotIn(moj, html)


class TestSectionBProbeTableHtml(unittest.TestCase):
    def test_state_boxes_and_notes_scroll_not_probe(self):
        html = markdownish_to_html(SECTION_B_MD)
        self.assertIn('class="doc-table section-b-probes"', html)
        # All three state colours present as solid swatches
        self.assertIn("rag-swatch rag-green", html)
        self.assertIn("rag-swatch rag-amber", html)
        self.assertIn("rag-swatch rag-red", html)
        self.assertIn('aria-label="PASS"', html)
        self.assertIn('aria-label="SKIP"', html)
        self.assertIn('aria-label="FAIL"', html)
        # Probe identity still present as text (not scrolled away)
        self.assertIn("nolog_journald", html)
        self.assertIn("no_priv_public_trees", html)
        # Notes column uses in-cell scroll; probe column must not get scroll wrapper
        self.assertIn('class="pkg-cell-scroll"', html)
        self.assertIn('class="cell-scroll"', html)
        # State cells use rag-cell solid fill (not bare **PASS** text alone)
        self.assertIn('class="rag-cell"', html)
        # Must not leave bold-only PASS as the only STATE cue without swatch
        # (raw **PASS** should be upgraded; no plain markdown asterisks in state cells)
        self.assertNotIn("**PASS**", html)
        self.assertNotIn("**SKIP**", html)
        self.assertNotIn("**FAIL**", html)

    def test_css_section_b_scroll_and_swatches(self):
        css = DOC_SHELL_CSS
        self.assertIn("section-b-probes", css)
        self.assertIn("rag-swatch", css)
        self.assertIn("rag-green", css)
        self.assertIn("rag-amber", css)
        self.assertIn("rag-red", css)
        self.assertIn("cell-scroll", css)
        # Section B Notes scroll; Probe column not given cell-scroll treatment in CSS nth-child(1)
        self.assertIn("table.doc-table.section-b-probes", css)
        self.assertIn("overflow-x: auto", css)

    def test_shipped_audit_md_section_b_renders_boxes(self):
        audit = ROOT / "AUDIT.md"
        if not audit.is_file():
            self.skipTest("AUDIT.md missing")
        text = audit.read_text(encoding="utf-8")
        if "Privacy probes (section B" not in text:
            self.skipTest("section B heading missing from AUDIT.md")
        html = markdownish_to_html(text)
        self.assertIn("section-b-probes", html)
        # At least one of pass/skip/fail swatches from live audit content
        self.assertTrue(
            "rag-swatch rag-green" in html
            or "rag-swatch rag-amber" in html
            or "rag-swatch rag-red" in html,
            "section B table should map State to colour boxes",
        )
        self.assertIn("nolog_journald", html)

    def test_full_document_shell_includes_section_b_css(self):
        page = render_document_html(
            title="Security audit",
            raw=SECTION_B_MD.encode("utf-8"),
        ).decode("utf-8")
        self.assertIn("section-b-probes", page)
        self.assertIn("rag-swatch rag-green", page)
        self.assertIn("rag-swatch rag-amber", page)
        self.assertIn("rag-swatch rag-red", page)
        self.assertIn("cell-scroll", page)


class TestPkgRagRegressionWithSectionB(unittest.TestCase):
    def test_package_state_table_still_solid_boxes_and_scroll(self):
        md = """
## Installer package AUDIT STATE

| Platform | Package | STATE | Notes |
|----------|---------|-------|-------|
| 🪟 **Windows** | `restore-privacy-client-0.3.4-windows-x64-setup.exe` | 🟩 | pin ok; lengthy package note for scroll test |
"""
        html = markdownish_to_html(md)
        self.assertIn("pkg-rag", html)
        self.assertIn("rag-swatch rag-green", html)
        self.assertIn("pkg-cell-scroll", html)
        self.assertIn("cell-scroll", html)
        self.assertIn("restore-privacy-client-0.3.4-windows-x64-setup.exe", html)
        # Package table must not be misclassified as section B
        self.assertNotIn("section-b-probes", html)

    def test_mojibake_package_state_and_platform_render_clean(self):
        """Package table with cp1252-mojibaked STATE/platform must not show tofu."""
        green_moj = "🟩".encode("utf-8").decode("cp1252")
        # Mixed platform corruption observed on shipped macOS/Linux AUDIT rows
        mac_moj = "\u00f0\u0178\u008d\u017d"
        md = f"""
## Installer package AUDIT STATE

| Platform | Package | STATE | Notes |
|----------|---------|-------|-------|
| {mac_moj} **macOS** | `restore-privacy-client-0.4.0-macos.zip` | {green_moj} | pin ok |
| 🪟 **Windows** | `restore-privacy-client-0.4.0-windows-x64-setup.exe` | 🟩 | pin ok |
"""
        html = markdownish_to_html(md)
        self.assertIn("pkg-rag", html)
        self.assertIn("rag-swatch rag-green", html)
        self.assertIn("rag-cell", html)
        self.assertIn("plat-icon", html)
        self.assertIn("macOS", html)
        # Wonky mojibake must not remain as visible STATE/platform glyph content
        self.assertNotIn(green_moj, html)
        self.assertNotIn(mac_moj, html)

    def test_shipped_audit_package_state_cells_are_swatches_not_raw_squares(self):
        audit = ROOT / "AUDIT.md"
        if not audit.is_file():
            self.skipTest("AUDIT.md missing")
        text = audit.read_text(encoding="utf-8")
        if "Installer package AUDIT STATE" not in text:
            self.skipTest("package RAG section missing")
        html = markdownish_to_html(text)
        self.assertIn("pkg-rag", html)
        self.assertIn("rag-swatch", html)
        # No residual cp1252 mojibake of green/amber squares in HTML body
        for good in ("🟩", "🟧", "🟥"):
            moj = good.encode("utf-8").decode("cp1252")
            self.assertNotIn(moj, html)
        # Canonical colour-square emoji should not remain as bare STATE cell text
        # (swatch replaces pure cells; legend may still mention colours as words)
        self.assertNotIn("ðŸŸ", html)


if __name__ == "__main__":
    unittest.main()
