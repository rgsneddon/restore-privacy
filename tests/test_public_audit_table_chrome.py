"""AUDIT table layout (scrollable Notes) + sleek sharp chrome / data-path."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAuditTableLayout(unittest.TestCase):
    def test_uk_ping_table_scrollable_notes_and_class(self) -> None:
        from client.uk_ping_estimates import LiveRttBase, render_audit_uk_ping_section
        from public_docs import DOC_SHELL_CSS, markdownish_to_html

        section = render_audit_uk_ping_section(
            live=LiveRttBase(entry_ms=64.0, exit_ms=67.0),
            measure=False,
        )
        html = markdownish_to_html(section)
        self.assertIn('class="doc-table uk-ping-rag"', html)
        self.assertIn("cell-scroll-notes", html)
        self.assertIn("notes-cell", html)
        self.assertIn("pkg-cell-scroll", html)
        # Notes column present as last header
        self.assertIn(">Notes</th>", html)
        # CSS balances columns + scrolls notes
        self.assertIn("uk-ping-rag", DOC_SHELL_CSS)
        self.assertIn("table-layout: fixed", DOC_SHELL_CSS)
        self.assertIn("cell-scroll-notes", DOC_SHELL_CSS)
        self.assertIn("max-height", DOC_SHELL_CSS)
        self.assertIn("overflow-y: auto", DOC_SHELL_CSS)

    def test_audit_document_html_has_uk_ping_layout(self) -> None:
        import public_docs

        got = public_docs.document_bytes_for_path("/AUDIT.md")
        self.assertIsNotNone(got)
        assert got is not None
        body = got[0].decode("utf-8")
        self.assertIn("uk-ping-rag", body)
        self.assertIn("cell-scroll-notes", body)
        self.assertIn("Privacy-scale settings", body)


class TestSleekChromeAndDataPath(unittest.TestCase):
    def test_sharp_panel_radii_not_toy_pills(self) -> None:
        from public_chrome import public_site_css

        css = public_site_css()
        self.assertIn("--rb-radius: 0px", css)
        self.assertIn("--rb-radius-sm: 0px", css)
        # Main chrome must not use large pill radii
        self.assertNotIn("border-radius: 999px", css)
        self.assertNotIn("--rb-radius: 14px", css)
        self.assertNotIn("--rb-radius: 16px", css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn('[data-theme="light"]', css)

    def test_data_path_more_prominent(self) -> None:
        from public_chrome import (
            public_data_path_layer_html,
            public_head_open,
            public_site_css,
        )

        layer = public_data_path_layer_html()
        self.assertIn("data-path-layer", layer)
        self.assertIn("data-path-prominent", layer)
        self.assertIn('aria-hidden="true"', layer)
        css = public_site_css()
        # Stronger ambient than prior soft 0.22 grid
        self.assertIn("opacity: 0.42", css)
        self.assertIn(".data-path-motif", css)
        self.assertIn("opacity: 0.58", css)
        head = public_head_open(title="t")
        self.assertIn("data-path-prominent", head)
        self.assertIn("data-path-layer", head)

    def test_homepage_and_support_share_sleek_shell(self) -> None:
        from app import render_html
        from support_tickets import render_support_page_html

        home = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        sup = render_support_page_html()
        for html in (home, sup):
            self.assertIn("--rb-radius: 0px", html)
            self.assertIn("data-path-prominent", html)
            self.assertIn("site-chrome-pro", html)


if __name__ == "__main__":
    unittest.main()
