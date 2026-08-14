"""Audit page countdown ticker under H1 + current-run Green/Amber/Red."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from audit_countdown import (  # noqa: E402
    audit_json_matches_product_monopin,
    audit_md_catalog_version,
    audit_md_matches_product_monopin,
    countdown_state,
    current_audit_rag_colour,
    format_countdown,
    load_security_audit_json_prefer_upstream,
    overlay_audit_generated_in_markdown_html,
    product_monopin_for_audit,
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

    def test_package_rag_takes_precedence_over_overall_ok(self):
        """Ticker must follow package_rag.overall (not unit-suite overall_ok alone)."""
        st = current_audit_rag_colour(
            data={
                "package_rag": {"overall": "Amber"},
                "overall_ok": True,  # unit suite can pass while package lag is Amber
            }
        )
        self.assertEqual(st["colour"], "Amber")
        st_red = current_audit_rag_colour(
            data={"package_rag": {"overall": "Red"}, "overall_ok": True}
        )
        self.assertEqual(st_red["colour"], "Red")


class TestUpstreamMonopinGuard(unittest.TestCase):
    def test_wrong_catalog_upstream_is_rejected(self):
        """Residual 0.3.6 all-Red inventory must not win over monopin 1.2.x local."""
        monopin = product_monopin_for_audit() or "1.2.1"
        self.assertTrue(monopin)
        stale = {
            "generated_at": "2099-01-01T00:00:00Z",  # newer stamp
            "catalog_version": "0.3.6",
            "package_rag": {
                "catalog_version": "0.3.6",
                "overall": "Red",
                "packages": [
                    {"platform": "windows", "state": "Red", "filename": "x-0.3.6.exe"},
                ],
            },
            "overall_ok": True,
        }
        fresh = {
            "generated_at": "2020-01-01T00:00:00Z",  # older stamp
            "catalog_version": monopin,
            "package_rag": {
                "catalog_version": monopin,
                "overall": "Amber",
                "packages": [
                    {"platform": "windows", "state": "Amber"},
                    {"platform": "android", "state": "Green"},
                ],
            },
            "overall_ok": True,
        }
        self.assertFalse(
            audit_json_matches_product_monopin(stale, monopin=monopin)
        )
        self.assertTrue(
            audit_json_matches_product_monopin(fresh, monopin=monopin)
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(json.dumps(fresh), encoding="utf-8")
            # Simulate Helsinki returning stale 0.3.6 with a newer stamp.
            import audit_countdown as ac

            with unittest.mock.patch.object(
                ac, "fetch_url_text", return_value=json.dumps(stale)
            ):
                # Default path would prefer upstream if not monopin-gated;
                # use real prefer with patched default path via explicit call.
                got = load_security_audit_json_prefer_upstream(
                    p, upstream_url="https://example.invalid/audit.json"
                )
        # Explicit non-default path returns local only (no upstream).
        self.assertEqual(got.get("catalog_version"), monopin)
        self.assertEqual((got.get("package_rag") or {}).get("overall"), "Amber")

    def test_default_path_discards_wrong_pin_upstream(self):
        """Default static path: wrong-pin upstream loses even if newer."""
        import audit_countdown as ac

        monopin = product_monopin_for_audit() or "1.2.1"
        stale = {
            "generated_at": "2099-12-31T23:59:59Z",
            "catalog_version": "0.3.6",
            "package_rag": {"catalog_version": "0.3.6", "overall": "Red"},
        }
        local = {
            "generated_at": "2026-01-01T00:00:00Z",
            "catalog_version": monopin,
            "package_rag": {"catalog_version": monopin, "overall": "Amber"},
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(json.dumps(local), encoding="utf-8")
            with unittest.mock.patch.object(ac, "_DEFAULT_JSON", p):
                with unittest.mock.patch.object(
                    ac, "fetch_url_text", return_value=json.dumps(stale)
                ):
                    with unittest.mock.patch.object(
                        ac, "product_monopin_for_audit", return_value=monopin
                    ):
                        got = load_security_audit_json_prefer_upstream(None)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got.get("catalog_version"), monopin)
        self.assertEqual((got.get("package_rag") or {}).get("overall"), "Amber")
        # Ticker colour follows monopin JSON, not residual 0.3.6 Red.
        st = current_audit_rag_colour(data=got)
        self.assertEqual(st["colour"], "Amber")

    def test_wrong_pin_local_alone_returns_none(self):
        """Wrong-pin local must not paint public ticker (false Red/Amber)."""
        import audit_countdown as ac

        monopin = product_monopin_for_audit() or "1.2.3"
        stale = {
            "generated_at": "2026-08-13T05:40:22Z",
            "catalog_version": "0.3.6",
            "package_rag": {"catalog_version": "0.3.6", "overall": "Red"},
            "overall_ok": True,
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(json.dumps(stale), encoding="utf-8")
            with unittest.mock.patch.object(ac, "_DEFAULT_JSON", p):
                with unittest.mock.patch.object(
                    ac, "fetch_url_text", return_value=None
                ):
                    with unittest.mock.patch.object(
                        ac, "product_monopin_for_audit", return_value=monopin
                    ):
                        got = load_security_audit_json_prefer_upstream(None)
        self.assertIsNone(got)

    def test_wrong_pin_rag_colour_is_unavailable(self):
        """Stale residual Red for wrong catalog pin is not public Red."""
        monopin = product_monopin_for_audit() or "1.2.3"
        stale = {
            "catalog_version": "0.3.6",
            "package_rag": {"catalog_version": "0.3.6", "overall": "Red"},
            "overall_ok": False,
        }
        with unittest.mock.patch(
            "audit_countdown.product_monopin_for_audit", return_value=monopin
        ):
            st = current_audit_rag_colour(data=stale)
        self.assertFalse(st["available"])
        self.assertIsNone(st["colour"])

    def test_audit_md_monopin_parse_and_match(self):
        monopin = product_monopin_for_audit() or "1.2.3"
        good = (
            "| **Public catalog version** | **%s** |\n"
            "## Installer package AUDIT STATE (catalog v%s)\n"
            "**Catalog overall (worst package):** 🟧\n"
        ) % (monopin, monopin)
        bad = (
            "| **Public catalog version** | **0.3.6** |\n"
            "**Catalog overall (worst package):** 🟥\n"
        )
        self.assertEqual(audit_md_catalog_version(good), monopin)
        self.assertEqual(audit_md_catalog_version(bad), "0.3.6")
        self.assertTrue(audit_md_matches_product_monopin(good, monopin=monopin))
        self.assertFalse(audit_md_matches_product_monopin(bad, monopin=monopin))


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
        self.assertIn("/static/audit_page_ticker.js", html)
        js = (ROOT / "status_page" / "static" / "audit_page_ticker.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("setInterval", js)
        self.assertIn("Time until next audit", html)
        # Unique ids (not homepage collision)
        self.assertNotIn('id="audit-countdown"', html)
        self.assertIn("rag-swatch rag-green", html)
        self.assertIn("The current audit run is", html)
        self.assertIn('id="audit-page-current-run-colour"', html)
        self.assertIn(">Green<", html)
        self.assertIn('data-rag-colour="green"', html)
        # Last-run from JSON (not stale markdown)
        self.assertIn('id="audit-page-last-run-time"', html)
        self.assertIn('datetime="2026-07-21T10:00:00Z"', html)
        # Display is Europe/London (BST in summer) or UTC fallback.
        self.assertTrue(
            "2026-07-21 10:00:00 UTC" in html or "2026-07-21 11:00:00 BST" in html,
            html,
        )

    def test_ticker_amber_when_package_rag_amber(self):
        last = datetime(2026, 7, 21, 10, 0, 0, tzinfo=timezone.utc)
        now = last + timedelta(hours=1)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-21T10:00:00Z",
                        "package_rag": {"overall": "Amber"},
                        "overall_ok": True,
                    }
                ),
                encoding="utf-8",
            )
            html = render_audit_page_ticker_html(now=now, json_path=p)
        self.assertIn("The current audit run is", html)
        self.assertIn(">Amber<", html)
        self.assertIn("rag-swatch rag-amber", html)
        self.assertIn('data-rag-colour="amber"', html)
        self.assertNotIn(">Red<", html)
        # Remaining ~23h of 1-day period (display always includes days)
        self.assertIn("0d 23:00:00", html)
        self.assertIn('data-period-seconds="86400"', html)

    def test_overlay_prefers_json_generated_at_over_stale_markdown_cell(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(
                json.dumps({"generated_at": "2026-07-29T12:00:00Z"}),
                encoding="utf-8",
            )
            stale = (
                "<tr><td><strong>Audit generated</strong></td>"
                "<td><strong>27 July 2026</strong> "
                "(<code>2026-07-27T08:27:28Z</code>)</td></tr>"
            )
            out = overlay_audit_generated_in_markdown_html(stale, json_path=p)
            self.assertIn("2026-07-29T12:00:00Z", out)
            self.assertIn("29 July 2026", out)
            self.assertNotIn("2026-07-27T08:27:28Z", out)

    def test_static_route_allows_security_audit_json(self):
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn(
            '"/static/security_audit_latest.json": "security_audit_latest.json"',
            app,
        )

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
        # Colour line is present when monopin JSON is staged; wrong-pin residual
        # inventory is honest-unavailable (not a fake Red).
        self.assertTrue(
            "The current audit run is" in page
            or "The current audit run colour is" in page,
            "ticker must expose current-run colour line",
        )
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
