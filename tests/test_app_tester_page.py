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
            base_url="https://restoreprivacy.online",
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "not_accepted")
        self.assertFalse(self.tp.has_claimed(cid))

    def test_first_mint_returns_download_and_keygen(self) -> None:
        cid = self.tp.new_claim_id()
        out = self.tp.mint_for_tester(
            "windows",
            claim_id=cid,
            accepted=True,
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
            base_url="https://restoreprivacy.online",
        )
        self.assertTrue(first.get("ok"), first)
        second = self.tp.mint_for_tester(
            "android",
            claim_id=cid,
            accepted=True,
            base_url="https://restoreprivacy.online",
        )
        self.assertFalse(second.get("ok"))
        self.assertEqual(second.get("error"), "already_claimed")
        self.assertEqual(second.get("message"), self.tp.ALREADY_USED_MESSAGE)
        self.assertIn("testers link and keygen", second.get("message", ""))
        self.assertNotIn("trsters", second.get("message", ""))

    def test_html_has_scroll_licence_and_accept_gate(self) -> None:
        page = self.tp.render_tester_page_html()
        self.assertIn("licence-scroll", page)
        self.assertIn(self.tp.ACCEPT_FIELD, page)
        self.assertIn("read the licence", page.lower())
        self.assertIn("disclaimer", page.lower())
        self.assertIn('id="accept-box"', page)
        self.assertIn('id="generator"', page)
        self.assertIn("pointer-events:none", page.replace(" ", ""))
        self.assertIn(self.tp.TESTER_MINT_PATH, page)
        # Generator disabled until accept (radios disabled in HTML)
        self.assertIn("disabled", page)
        refuse = self.tp.render_already_used_html()
        self.assertIn(self.tp.ALREADY_USED_MESSAGE, refuse)

    def test_accept_checked_and_platform_parse(self) -> None:
        form = self.tp.parse_form_body(
            f"{self.tp.ACCEPT_FIELD}=1&{self.tp.PLATFORM_FIELD}=android"
        )
        self.assertTrue(self.tp.accept_checked(form))
        self.assertEqual(self.tp.selected_platform(form), "android")
        self.assertFalse(self.tp.accept_checked({}))
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


if __name__ == "__main__":
    unittest.main()
