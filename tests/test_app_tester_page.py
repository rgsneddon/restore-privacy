"""Public unlinked app-tester page: licence gate, one mint, refuse second."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAppTesterPage(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments
        import tester_page as tp

        self.pay = payments
        self.tp = tp
        self.pay.init_db()
        self.tp.init_tester_claim_db()

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_unaccepted_does_not_mint(self) -> None:
        cid = self.tp.new_claim_id()
        out = self.tp.mint_for_tester(
            "windows",
            claim_id=cid,
            accepted=False,
            reports_consent=True,
            base_url="https://restoreprivacy.online",
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "not_accepted")
        self.assertFalse(self.tp.has_claimed(cid))

    def test_missing_reports_consent_does_not_mint(self) -> None:
        cid = self.tp.new_claim_id()
        out = self.tp.mint_for_tester(
            "windows",
            claim_id=cid,
            accepted=True,
            reports_consent=False,
            base_url="https://restoreprivacy.online",
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "reports_required")
        self.assertIn(self.tp.REPORTS_EMAIL, out.get("message", ""))
        self.assertFalse(self.tp.has_claimed(cid))

    def test_first_mint_returns_download_and_keygen(self) -> None:
        cid = self.tp.new_claim_id()
        out = self.tp.mint_for_tester(
            "windows",
            claim_id=cid,
            accepted=True,
            reports_consent=True,
            base_url="https://restoreprivacy.online",
            now=1_700_000_000.0,
        )
        self.assertTrue(out.get("ok"), out)
        self.assertTrue(str(out.get("keygen") or "").startswith(self.pay.KEYGEN_PREFIX))
        self.assertTrue(str(out.get("download_url") or "").startswith("https://"))
        self.assertIn("/download?token=", str(out.get("download_url") or ""))
        self.assertEqual(out.get("platform"), "windows")
        self.assertTrue(self.tp.has_claimed(cid))

    def test_second_mint_refused_with_message(self) -> None:
        cid = self.tp.new_claim_id()
        first = self.tp.mint_for_tester(
            "windows",
            claim_id=cid,
            accepted=True,
            reports_consent=True,
            base_url="https://restoreprivacy.online",
        )
        self.assertTrue(first.get("ok"), first)
        second = self.tp.mint_for_tester(
            "android",
            claim_id=cid,
            accepted=True,
            reports_consent=True,
            base_url="https://restoreprivacy.online",
        )
        self.assertFalse(second.get("ok"))
        self.assertEqual(second.get("error"), "already_claimed")
        self.assertEqual(second.get("message"), self.tp.ALREADY_USED_MESSAGE)
        self.assertIn("testers link and keygen", second.get("message", ""))
        self.assertNotIn("trsters", second.get("message", ""))

    def test_html_has_scroll_licence_and_accept_gate(self) -> None:
        raw = self.tp.render_tester_page_html()
        self.assertIsInstance(raw, (bytes, bytearray))
        page = raw.decode("utf-8")
        self.assertIn("licence-scroll", page)
        self.assertIn("data-scroll-gate", page)
        self.assertIn(self.tp.ACCEPT_FIELD, page)
        self.assertIn(self.tp.REPORTS_FIELD, page)
        self.assertIn(self.tp.DO_NOT_SHARE_NOTICE, page)
        self.assertIn("do-not-share", page)
        self.assertIn(self.tp.REPORTS_EMAIL, page)
        # CSP-safe: external gate script (not blocked inline)
        self.assertIn(self.tp.TESTER_GATE_SCRIPT_PATH, page)
        self.assertIn('src="/static/tester_page_gate.js"', page)
        self.assertNotIn("scrolledToBottom", page)  # logic lives in external JS
        self.assertIn("read and understand", page.lower())
        self.assertIn("disclaimer", page.lower())
        self.assertIn('id="accept-box"', page)
        self.assertIn('id="reports-box"', page)
        self.assertIn('id="generator"', page)
        self.assertIn("pointer-events:none", page.replace(" ", ""))
        self.assertIn(self.tp.TESTER_MINT_PATH, page)
        # Generator + both checkboxes start disabled until gates open
        self.assertIn("disabled", page)
        refuse = self.tp.render_already_used_html()
        self.assertIsInstance(refuse, (bytes, bytearray))
        self.assertIn(self.tp.ALREADY_USED_MESSAGE, refuse.decode("utf-8"))
        # Pure client-gate mirror
        self.assertFalse(
            self.tp.package_ui_enabled(
                scrolled_to_bottom=False, read_accepted=True, reports_accepted=True
            )
        )
        self.assertFalse(
            self.tp.package_ui_enabled(
                scrolled_to_bottom=True, read_accepted=True, reports_accepted=False
            )
        )
        self.assertTrue(
            self.tp.package_ui_enabled(
                scrolled_to_bottom=True, read_accepted=True, reports_accepted=True
            )
        )
        # Scroll metrics (mirrors JS): not at bottom / at bottom / short content
        self.assertFalse(self.tp.at_bottom_metrics(0, 100, 500, slack=16))
        self.assertTrue(self.tp.at_bottom_metrics(400, 100, 500, slack=16))
        self.assertTrue(self.tp.at_bottom_metrics(0, 200, 180, slack=16))  # no overflow

    def test_accept_checked_and_platform_parse(self) -> None:
        form = self.tp.parse_form_body(
            f"{self.tp.ACCEPT_FIELD}=1&{self.tp.REPORTS_FIELD}=1"
            f"&{self.tp.PLATFORM_FIELD}=android"
        )
        self.assertTrue(self.tp.accept_checked(form))
        self.assertTrue(self.tp.reports_consent_checked(form))
        self.assertTrue(self.tp.consents_ok(form))
        self.assertEqual(self.tp.selected_platform(form), "android")
        self.assertFalse(self.tp.accept_checked({}))
        self.assertFalse(self.tp.reports_consent_checked({}))
        self.assertFalse(
            self.tp.consents_ok(self.tp.parse_form_body(f"{self.tp.ACCEPT_FIELD}=1"))
        )
        self.assertEqual(self.tp.selected_platform({"platform": ["commodore"]}), "")

    def test_public_pages_do_not_link_tester(self) -> None:
        """Homepage / downloads / settings explainer must not href app-testers."""
        # Drive real HTML renderers where possible
        from downloads import render_download_section_html

        chunks: list[str] = [render_download_section_html()]
        try:
            from settings_explainer import (
                render_settings_explainer_banner_html,
                render_settings_explainer_page_html,
            )

            chunks.append(render_settings_explainer_banner_html())
            chunks.append(render_settings_explainer_page_html())
        except Exception:  # noqa: BLE001
            pass
        try:
            import app as status_app

            # render_html if available
            if hasattr(status_app, "render_html"):
                chunks.append(
                    status_app.render_html(
                        {"title": "RESTORE PRIVACY", "ok": True}
                    )
                )
        except Exception:  # noqa: BLE001
            pass
        # Public link-producing modules (not route handlers — those may name the path)
        for rel in (
            "status_page/downloads.py",
            "status_page/coffee_link.py",
            "status_page/settings_explainer.py",
            "status_page/public_docs.py",
        ):
            p = ROOT / rel
            if p.is_file():
                chunks.append(p.read_text(encoding="utf-8", errors="replace"))
        for src in chunks:
            self.assertTrue(
                self.tp.public_html_must_not_link_tester(src),
                f"found app-testers href in public surface (len={len(src)})",
            )
        # Route exists for direct access (handler source may mention path)
        self.assertTrue(self.tp.is_tester_page_path("/app-testers"))
        self.assertIn("mint_for_tester", (ROOT / "status_page" / "app.py").read_text(
            encoding="utf-8"
        ))

    def test_app_routes_wired(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("mint_for_tester", src)
        self.assertIn("render_tester_page_html", src)
        self.assertIn("TESTER_MINT_PATH", src)
        self.assertIn("tester_page_gate.js", src)
        js = (ROOT / "status_page" / "static" / "tester_page_gate.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("atBottomMetrics", js)
        self.assertIn("scrolledToBottom", js)
        self.assertIn("packageEnabled", js)
        self.assertIn("accept-box", js)
        self.assertIn("reports-box", js)


class _RealSendHandler:
    """In-process status Handler stub that uses the real _send (bytes-only)."""

    def __init__(self, path: str, *, method: str = "GET", body: bytes = b"") -> None:
        import app as status_app

        self._Handler = status_app.Handler
        self.path = path
        self.command = method
        self.headers: dict[str, str] = {"Host": "localhost"}
        self.wfile = __import__("io").BytesIO()
        self.rfile = __import__("io").BytesIO(body)
        self.code: int | None = None
        self.sent_headers: dict[str, str] = {}
        self._extra_cookies: list[str] = []

    def send_response(self, code: int, message: str | None = None) -> None:
        self.code = code

    def send_header(self, key: str, value: str) -> None:
        k = str(key)
        if k.lower() == "set-cookie":
            self._extra_cookies.append(str(value))
            # Keep last cookie visible for Content-Type etc. overwrites
            self.sent_headers[k] = str(value)
            return
        self.sent_headers[k] = str(value)

    def end_headers(self) -> None:
        return

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _security_headers(self, allow_framing: bool = False) -> None:
        return

    def body_bytes(self) -> bytes:
        return self.wfile.getvalue()

    def body_text(self) -> str:
        return self.body_bytes().decode("utf-8", errors="replace")

    def claim_cookie(self) -> str | None:
        for c in self._extra_cookies:
            if c.startswith("rpt_app_tester_claim="):
                return c.split(";", 1)[0].split("=", 1)[1]
        # also from headers Cookie we set
        return None

    def do_GET(self) -> None:
        # Bind real methods from status Handler onto this instance
        import app as status_app

        self._send = status_app.Handler._send.__get__(self, type(self))  # type: ignore[attr-defined]
        self._redirect = status_app.Handler._redirect.__get__(self, type(self))  # type: ignore[attr-defined]
        status_app.Handler.do_GET(self)  # type: ignore[arg-type]

    def do_POST(self) -> None:
        import app as status_app

        self._send = status_app.Handler._send.__get__(self, type(self))  # type: ignore[attr-defined]
        self._redirect = status_app.Handler._redirect.__get__(self, type(self))  # type: ignore[attr-defined]
        self._read_body = lambda: self.rfile.getvalue()  # type: ignore[method-assign]
        status_app.Handler.do_POST(self)  # type: ignore[arg-type]


class TestAppTesterHttpHandler(unittest.TestCase):
    """Drive real Handler.do_GET / do_POST — catches str-vs-bytes _send crashes."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments
        import tester_page as tp

        self.pay = payments
        self.tp = tp
        self.pay.init_db()
        self.tp.init_tester_claim_db()

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_get_app_testers_returns_200_bytes_with_licence_gate(self) -> None:
        h = _RealSendHandler("/app-testers")
        h.do_GET()
        self.assertEqual(h.code, 200)
        body = h.body_bytes()
        self.assertIsInstance(body, (bytes, bytearray))
        self.assertGreater(len(body), 100)
        text = h.body_text()
        self.assertIn("licence-scroll", text)
        self.assertIn(self.tp.ACCEPT_FIELD, text)
        self.assertIn(self.tp.REPORTS_FIELD, text)
        self.assertIn(self.tp.DO_NOT_SHARE_NOTICE, text)
        self.assertIn("accept-box", text)
        self.assertIn("reports-box", text)
        self.assertIn("/static/tester_page_gate.js", text)
        # Cookie issued for claim identity
        self.assertTrue(
            any("rpt_app_tester_claim=" in c for c in h._extra_cookies)
            or "rpt_app_tester_claim=" in (h.sent_headers.get("Set-Cookie") or ""),
            h.sent_headers,
        )

    def test_post_mint_then_second_claim_refused_via_handler(self) -> None:
        # First GET to mint claim cookie
        g = _RealSendHandler("/app-testers")
        g.do_GET()
        self.assertEqual(g.code, 200)
        claim = None
        for c in g._extra_cookies:
            if "rpt_app_tester_claim=" in c:
                claim = c.split(";", 1)[0].replace("rpt_app_tester_claim=", "", 1)
                break
        if not claim:
            raw = g.sent_headers.get("Set-Cookie") or ""
            if raw.startswith("rpt_app_tester_claim="):
                claim = raw.split(";", 1)[0].split("=", 1)[1]
        self.assertTrue(claim, "expected claim cookie from GET")

        form = (
            f"{self.tp.ACCEPT_FIELD}=1&{self.tp.REPORTS_FIELD}=1"
            f"&{self.tp.PLATFORM_FIELD}=windows"
        ).encode("utf-8")
        p1 = _RealSendHandler("/app-testers/mint", method="POST", body=form)
        p1.headers["Cookie"] = f"rpt_app_tester_claim={claim}"
        p1.headers["Content-Type"] = "application/x-www-form-urlencoded"
        p1.headers["Content-Length"] = str(len(form))
        p1.do_POST()
        self.assertEqual(p1.code, 200, p1.body_text()[:500])
        t1 = p1.body_text()
        self.assertIn("KEYGEN", t1.upper())
        self.assertIn("/download?token=", t1)
        self.assertTrue(
            any(x in t1 for x in ("RPT-KEY", "product-keygen", "keygen")),
            t1[:800],
        )

        form2 = (
            f"{self.tp.ACCEPT_FIELD}=1&{self.tp.REPORTS_FIELD}=1"
            f"&{self.tp.PLATFORM_FIELD}=android"
        ).encode("utf-8")
        p2 = _RealSendHandler("/app-testers/mint", method="POST", body=form2)
        p2.headers["Cookie"] = f"rpt_app_tester_claim={claim}"
        p2.headers["Content-Type"] = "application/x-www-form-urlencoded"
        p2.headers["Content-Length"] = str(len(form2))
        p2.do_POST()
        self.assertEqual(p2.code, 200)
        t2 = p2.body_text()
        self.assertIn(self.tp.ALREADY_USED_MESSAGE, t2)
        self.assertNotIn("trsters", t2)

    def test_post_without_accept_does_not_mint(self) -> None:
        g = _RealSendHandler("/app-testers")
        g.do_GET()
        claim = None
        for c in g._extra_cookies:
            if "rpt_app_tester_claim=" in c:
                claim = c.split(";", 1)[0].split("=", 1)[1]
                break
        form = (
            f"{self.tp.REPORTS_FIELD}=1&{self.tp.PLATFORM_FIELD}=windows"
        ).encode("utf-8")
        p = _RealSendHandler("/app-testers/mint", method="POST", body=form)
        if claim:
            p.headers["Cookie"] = f"rpt_app_tester_claim={claim}"
        p.headers["Content-Type"] = "application/x-www-form-urlencoded"
        p.do_POST()
        self.assertEqual(p.code, 200)
        text = p.body_text()
        self.assertNotIn("Your one-month tester grant", text)
        self.assertTrue(
            "read" in text.lower() or "understand" in text.lower() or "agreements" in text.lower(),
            text[:600],
        )

    def test_static_gate_js_served_as_javascript(self) -> None:
        """CSP script-src 'self' requires /static/tester_page_gate.js to be served."""
        h = _RealSendHandler("/static/tester_page_gate.js")
        h.do_GET()
        self.assertEqual(h.code, 200, h.body_text()[:200])
        body = h.body_bytes()
        self.assertGreater(len(body), 100)
        text = body.decode("utf-8", errors="replace")
        self.assertIn("atBottomMetrics", text)
        self.assertIn("scrolledToBottom", text)
        ctype = (h.sent_headers.get("Content-Type") or "").lower()
        self.assertTrue(
            "javascript" in ctype or "ecmascript" in ctype or "text/" in ctype,
            h.sent_headers,
        )

    def test_post_without_reports_consent_does_not_mint(self) -> None:
        g = _RealSendHandler("/app-testers")
        g.do_GET()
        claim = None
        for c in g._extra_cookies:
            if "rpt_app_tester_claim=" in c:
                claim = c.split(";", 1)[0].split("=", 1)[1]
                break
        form = (
            f"{self.tp.ACCEPT_FIELD}=1&{self.tp.PLATFORM_FIELD}=windows"
        ).encode("utf-8")
        p = _RealSendHandler("/app-testers/mint", method="POST", body=form)
        if claim:
            p.headers["Cookie"] = f"rpt_app_tester_claim={claim}"
        p.headers["Content-Type"] = "application/x-www-form-urlencoded"
        p.do_POST()
        self.assertEqual(p.code, 200)
        text = p.body_text()
        self.assertNotIn("Your one-month tester grant", text)
        self.assertIn(self.tp.REPORTS_EMAIL, text)


if __name__ == "__main__":
    unittest.main()
