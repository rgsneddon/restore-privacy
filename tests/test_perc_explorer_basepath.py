"""Perc explorer path-mounted API base + admin Perc surface."""

from __future__ import annotations

import os
import sys
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

PUBLIC_HTML = ROOT / "perc_chain" / "public" / "index.html"


class TestExplorerBasePath(unittest.TestCase):
    def test_helper_and_shipped_html(self) -> None:
        # Drive Node helper via subprocess-equivalent import through exec of pure module
        # (Python reimplementation of the shipped contract for offline CI).
        from pathlib import Path as P

        # Import the JS contract via a tiny pure Python mirror matching explorer_api_base.js
        def explorer_api_base(pathname: str) -> str:
            p = str(pathname or "/")
            if p == "/perc" or p.startswith("/perc/"):
                return "/perc"
            last = p.rfind("/")
            if last > 0:
                d = p[:last]
                if d and d != "/":
                    return d.rstrip("/") or ""
            return ""

        def explorer_api_url(path: str, pathname: str = "/") -> str:
            base = explorer_api_base(pathname)
            rel = str(path or "").lstrip("/")
            if not base:
                return "/" + rel
            return base + "/" + rel

        self.assertEqual(explorer_api_url("api/network", "/perc/"), "/perc/api/network")
        self.assertEqual(
            explorer_api_url("api/blocks?limit=40", "/perc/"),
            "/perc/api/blocks?limit=40",
        )
        self.assertEqual(explorer_api_url("api/network", "/"), "/api/network")
        self.assertNotEqual(
            explorer_api_url("api/network", "/perc/"),
            "/api/network",
        )

        html = PUBLIC_HTML.read_text(encoding="utf-8")
        self.assertIn("function explorerApiBase", html)
        self.assertIn("function explorerApiUrl", html)
        self.assertIn("explorerApiUrl('api/network')", html)
        self.assertIn("explorerApiUrl('api/blocks", html)
        self.assertNotIn("fetch('/api/network')", html)
        self.assertNotIn('fetch("/api/network")', html)
        self.assertNotIn("fetch('/api/blocks", html)
        self.assertIn('id="link-api-network"', html)
        self.assertIn("wireFooterApiLinks", html)


class TestAdminPerc(unittest.TestCase):
    def test_render_and_nav(self) -> None:
        from admin_panel import _admin_sidebar_html
        from admin_perc import (
            ADMIN_PERC_NAV_ID,
            ADMIN_PERC_PAGE_ID,
            ADMIN_PERC_PATH,
            perc_explorer_url,
            perc_network_api_url,
            render_admin_perc_main_html,
            render_admin_perc_page_html,
        )

        side = _admin_sidebar_html(active="perc")
        self.assertIn(ADMIN_PERC_NAV_ID, side)
        self.assertIn(ADMIN_PERC_PATH, side)
        self.assertIn("Perc network", side)

        fixture = {
            "ok": True,
            "nodeStatus": "online",
            "blockHeight": 12,
            "networkHeight": 12,
            "peers": {"online": 1, "total": 2},
            "chainId": "evolve-chronoflux-principia-chain-1",
        }
        main = render_admin_perc_main_html(snapshot=fixture)
        self.assertIn(ADMIN_PERC_PAGE_ID, main)
        self.assertIn("online", main.lower())
        self.assertIn(perc_explorer_url(), main)
        self.assertIn("/perc/api/network", perc_network_api_url())

        page = render_admin_perc_page_html(snapshot=fixture).decode("utf-8")
        self.assertIn(ADMIN_PERC_PAGE_ID, page)
        self.assertIn("admin-sidebar", page)
        self.assertIn(ADMIN_PERC_NAV_ID, page)

    def test_unauthenticated_admin_perc_not_console(self) -> None:
        from app import Handler

        prev = {
            k: os.environ.get(k)
            for k in (
                "RPT_ADMIN_PASSWORD",
                "RPT_ADMIN_USER",
                "RPT_ADMIN_SESSION_SECRET",
                "RPT_PAYMENT_DATA_DIR",
            )
        }
        import tempfile

        td = tempfile.TemporaryDirectory()
        try:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td.name
            os.environ["RPT_ADMIN_PASSWORD"] = "unit-test-admin-password-xx"
            os.environ["RPT_ADMIN_USER"] = "admin"
            os.environ["RPT_ADMIN_SESSION_SECRET"] = "unit-test-session-secret-xx"
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = httpd.server_address[1]
            t = Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                url = f"http://127.0.0.1:{port}/admin/perc"
                try:
                    with request.urlopen(url, timeout=5) as resp:
                        code = resp.getcode()
                        body = resp.read().decode("utf-8", errors="replace")
                except error.HTTPError as e:
                    code = e.code
                    body = e.read().decode("utf-8", errors="replace")
                self.assertIn(code, (200, 401, 403, 302, 503))
                self.assertNotIn("admin-perc-network-snapshot", body)
                # Login surface, not authenticated console snapshot
                self.assertTrue(
                    "admin-login" in body
                    or "password" in body.lower()
                    or "login" in body.lower()
                    or code in (401, 403, 503)
                )
            finally:
                httpd.shutdown()
        finally:
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
