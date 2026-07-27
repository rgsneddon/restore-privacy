"""Audit page countdown ticker under H1 + current-run Green/Amber/Red."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from audit_countdown import (  # noqa: E402
    countdown_state,
    current_audit_rag_colour,
    format_countdown,
    remaining_seconds_until,
    render_audit_page_ticker_html,
)
from public_docs import render_document_html  # noqa: E402


class TestCurrentAuditRagColour(unittest.TestCase):
    def test_package_rag_overall_green_amber_red(self):
        for colour, css in (
            ("Green", "rag-green"),
            ("Amber", "rag-amber"),
            ("Red", "rag-red"),
        ):
            with self.subTest(colour=colour):
                st = current_audit_rag_colour(
                    data={
                        "package_rag": {"overall": colour},
                        "overall_ok": colour == "Green",
                    }
                )
                self.assertTrue(st["available"])
                self.assertEqual(st["colour"], colour)
                self.assertEqual(st["css"], css)
                self.assertEqual(st["label"], colour)

    def test_overall_ok_fallback(self):
        self.assertEqual(
            current_audit_rag_colour(data={"overall_ok": True})["colour"],
            "Green",
        )
        self.assertEqual(
            current_audit_rag_colour(data={"overall_ok": False})["colour"],
            "Red",
        )

    def test_missing_is_unavailable_not_fake_green(self):
        st = current_audit_rag_colour(data={})
        self.assertFalse(st["available"])
        self.assertIsNone(st["colour"])
        self.assertIsNone(st["css"])


class TestAuditPageTickerHtml(unittest.TestCase):
    def test_ticker_has_countdown_and_unique_ids(self):
        last = datetime(2026, 7, 21, 10, 0, 0, tzinfo=timezone.utc)
        now = last + timedelta(hours=1)
        # Fixed remaining via countdown_state path with last from temp json
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-21T10:00:00Z",
                        "package_rag": {"overall": "Green"},
                        "overall_ok": True,
                    }
                ),
                encoding="utf-8",
            )
            html = render_audit_page_ticker_html(now=now, json_path=p)
        self.assertIn('id="audit-page-ticker"', html)
        self.assertIn('id="audit-page-countdown-value"', html)
        self.assertIn("data-next-audit", html)
        self.assertIn("setInterval", html)
        self.assertIn("Time until next audit", html)
        # Unique ids (not homepage collision)
        self.assertNotIn('id="audit-countdown"', html)
        self.assertIn("rag-swatch rag-green", html)
        self.assertIn("The current audit run is", html)
        self.assertIn('id="audit-page-current-run-colour"', html)
        self.assertIn(">Green<", html)
        self.assertIn('data-rag-colour="green"', html)
        # Remaining ~23h of 1-day period (display always includes days)
        self.assertIn("0d 23:00:00", html)
        self.assertIn('data-period-seconds="86400"', html)

    def test_amber_and_red_discrete_text(self):
        for colour, css in (("Amber", "rag-amber"), ("Red", "rag-red")):
            html = render_audit_page_ticker_html(
                rag={
                    "available": True,
                    "colour": colour,
                    "css": css,
                    "label": colour,
                },
            )
            self.assertIn(f"rag-swatch {css}", html)
            self.assertIn(f"The current audit run is", html)
            self.assertIn(f">{colour}<", html)
            self.assertIn(f'data-rag-colour="{colour.lower()}"', html)

    def test_unavailable_deadline_shows_em_dash_display(self):
        missing = Path("/nonexistent/security_audit_latest.json")
        st = countdown_state(json_path=missing)
        self.assertFalse(st["available"])
        self.assertEqual(st["display"], "—")
        html = render_audit_page_ticker_html(
            json_path=missing,
            rag={"available": False, "colour": None, "css": None, "label": "unavailable"},
        )
        self.assertIn("—", html)
        self.assertIn("unavailable", html.lower())


class TestAuditDocumentInjectsTicker(unittest.TestCase):
    def test_under_h1_code_and_policy_audit(self):
        md = b"""# Restore Privacy \xe2\x80\x94 Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy |
"""
        page = render_document_html(
            title="Security audit — Restore Privacy",
            raw=md,
            plain=False,
            include_audit_ticker=True,
        ).decode("utf-8")
        self.assertIn("Restore Privacy", page)
        self.assertIn("Code &amp; Policy Audit", page)
        # H1 then ticker
        h1_end = page.find("</h1>")
        ticker_at = page.find('id="audit-page-ticker"')
        self.assertGreater(h1_end, 0)
        self.assertGreater(ticker_at, h1_end)
        self.assertIn("audit-page-countdown-value", page)
        self.assertIn("The current audit run is", page)
        # CSS present
        self.assertIn("audit-page-ticker", page)
        self.assertIn("rag-green", page)  # CSS classes in shell

    def test_non_audit_doc_skips_ticker(self):
        md = b"# Privacy Policy\n\nNo collection.\n"
        page = render_document_html(
            title="Privacy policy — Restore Privacy",
            raw=md,
            plain=False,
            include_audit_ticker=False,
        ).decode("utf-8")
        # Shared CSS may mention the class; the live widget must not inject
        self.assertNotIn('id="audit-page-ticker"', page)
        self.assertNotIn('id="audit-page-countdown-value"', page)

    def test_shipped_audit_md_path(self):
        audit = ROOT / "AUDIT.md"
        if not audit.is_file():
            self.skipTest("AUDIT.md missing")
        page = render_document_html(
            title="Security audit — Restore Privacy",
            raw=audit.read_bytes(),
            plain=False,
        ).decode("utf-8")
        self.assertIn("Code &amp; Policy Audit", page)
        self.assertIn("audit-page-ticker", page)
        self.assertIn("audit-page-countdown-value", page)


class TestCountdownMathStillHonest(unittest.TestCase):
    def test_remaining_matches_fixed_now(self):
        last = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 7, 21, 13, 30, 0, tzinfo=timezone.utc)
        st = countdown_state(now=now, last_generated_at=last)
        # 1d - 1h30m = 22h30m
        self.assertEqual(st["remaining_seconds"], 22 * 3600 + 30 * 60)
        self.assertEqual(st["display"], format_countdown(st["remaining_seconds"]))
        self.assertEqual(st["display"], "0d 22:30:00")
        self.assertEqual(st["period_seconds"], 86400)


if __name__ == "__main__":
    unittest.main()
