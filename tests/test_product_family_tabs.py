"""Product family tabs + Browser/Vault landings (paths; style not VPN structure)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestProductTabsChrome(unittest.TestCase):
    def test_three_tabs_link_vpn_browser_vault(self) -> None:
        from public_chrome import (
            PRODUCT_BROWSER_PATH,
            PRODUCT_TAB_BROWSER_ID,
            PRODUCT_TAB_VAULT_ID,
            PRODUCT_TAB_VPN_ID,
            PRODUCT_TABS_ID,
            PRODUCT_VAULT_PATH,
            PRODUCT_VPN_PATH,
            public_product_tabs_html,
            public_brand_header_html,
            public_site_css,
        )

        html = public_product_tabs_html(active="vpn")
        self.assertIn(f'id="{PRODUCT_TABS_ID}"', html)
        self.assertIn(f'id="{PRODUCT_TAB_VPN_ID}"', html)
        self.assertIn(f'id="{PRODUCT_TAB_BROWSER_ID}"', html)
        self.assertIn(f'id="{PRODUCT_TAB_VAULT_ID}"', html)
        self.assertIn(f'href="{PRODUCT_VPN_PATH}"', html)
        self.assertIn(f'href="{PRODUCT_BROWSER_PATH}"', html)
        self.assertIn(f'href="{PRODUCT_VAULT_PATH}"', html)
        self.assertIn("Restore Privacy VPN", html)
        self.assertIn("Restore Privacy Browser", html)
        self.assertIn("Restore Privacy Vault", html)
        # VPN active
        self.assertIn('id="product-tab-vpn"', html)
        self.assertIn("product-tab is-active", html)
        self.assertIn('data-product="vpn"', html)
        # CSS: equal full-shell width (no narrow max-width cap on tabs)
        css = public_site_css()
        self.assertIn(".product-tab", css)
        self.assertIn("product-tabs", css)
        self.assertIn("flex: 1 1 0", css)
        self.assertIn("max-width: none", css)
        self.assertIn("width: 100%", css)
        # Must not re-introduce a short cluster cap on tabs
        self.assertNotIn("max-width: 15rem", css)
        # Injected at top of brand header chrome
        header = public_brand_header_html(product_active="browser")
        self.assertLess(header.index("product-tabs"), header.index("brand-panel"))
        self.assertIn('id="product-tab-browser"', header)
        self.assertIn("is-active", header)


class TestBrowserVaultBodies(unittest.TestCase):
    def test_browser_three_lines_no_vpn_structure(self) -> None:
        from product_family import (
            BROWSER_LINE_1,
            BROWSER_LINE_2,
            BROWSER_LINE_3,
            render_browser_page_html,
        )

        html = render_browser_page_html().decode("utf-8")
        self.assertIn(BROWSER_LINE_1, html)
        self.assertIn(BROWSER_LINE_2, html)
        self.assertIn(BROWSER_LINE_3, html)
        self.assertIn("Q3 2026", html)
        self.assertIn("product-tabs", html)
        self.assertIn('data-product="browser"', html)
        # No VPN homepage structure
        self.assertNotIn("dl-buy-form", html)
        self.assertNotIn("audit-countdown", html)
        self.assertNotIn("node-wipe-countdown", html)
        self.assertNotIn("settings-explainer-banner", html)
        self.assertNotIn("admin-node-usage", html)
        # No site menu buttons (Home / Licence / Privacy / Audit / README)
        self.assertNotIn('id="doc-links"', html)
        self.assertNotIn('id="home-link"', html)
        self.assertNotIn('id="licence-link"', html)
        self.assertNotIn('id="privacy-link"', html)
        self.assertNotIn('id="audit-link"', html)
        self.assertNotIn('id="readme-link"', html)

    def test_vault_three_lines_no_vpn_structure(self) -> None:
        from product_family import (
            VAULT_LINE_1,
            VAULT_LINE_2,
            VAULT_LINE_3,
            render_vault_page_html,
        )

        html = render_vault_page_html().decode("utf-8")
        self.assertIn(VAULT_LINE_1, html)
        self.assertIn(VAULT_LINE_2, html)
        self.assertIn(VAULT_LINE_3, html)
        self.assertIn("Q3 2027", html)
        self.assertIn("product-tabs", html)
        self.assertNotIn("dl-buy-form", html)
        self.assertNotIn("audit-countdown", html)
        self.assertNotIn("node-wipe-countdown", html)
        self.assertNotIn('id="doc-links"', html)
        self.assertNotIn('id="home-link"', html)
        self.assertNotIn('id="licence-link"', html)
        self.assertNotIn('id="privacy-link"', html)
        self.assertNotIn('id="audit-link"', html)
        self.assertNotIn('id="readme-link"', html)


class TestHomepageStillVpn(unittest.TestCase):
    def test_render_html_is_vpn_with_tabs(self) -> None:
        from app import render_html
        from public_chrome import PUBLIC_BRAND_TITLE

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn(PUBLIC_BRAND_TITLE, html)
        self.assertIn("RESTORE PRIVACY VPN", html)
        self.assertIn("product-tabs", html)
        self.assertIn('id="product-tab-vpn"', html)
        self.assertIn("dl-buy-form", html)  # VPN shop still present
        self.assertIn("audit-countdown", html)
        # VPN retains site menu buttons
        self.assertIn('id="doc-links"', html)
        self.assertIn('id="home-link"', html)
        self.assertIn('id="licence-link"', html)
        self.assertIn('id="privacy-link"', html)
        self.assertIn('id="audit-link"', html)
        self.assertIn('id="readme-link"', html)


class TestAppEntryRoutes(unittest.TestCase):
    def test_handler_serves_browser_vault_and_home(self) -> None:
        """Drive real shipped handlers/renderers (not a re-implementation)."""
        import app as app_mod

        src = Path(app_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("/browser", src)
        self.assertIn("/vault", src)
        self.assertIn("render_browser_page_html", src)
        self.assertIn("render_vault_page_html", src)
        self.assertIn("product_key_from_host", src)

        from product_family import (
            render_browser_page_html,
            render_vault_page_html,
            product_key_from_host,
        )
        from app import render_html, Handler

        # Real Handler.do_GET for /browser and /vault
        from io import BytesIO

        def invoke(path: str, host: str = "restoreprivacy.online") -> bytes:
            body = BytesIO()
            h = Handler.__new__(Handler)
            h.path = path
            h.headers = {"Host": host}  # type: ignore[assignment]
            h.rfile = BytesIO(b"")
            h.wfile = body
            h.client_address = ("127.0.0.1", 0)
            h.request_version = "HTTP/1.1"
            h.command = "GET"
            h.requestline = f"GET {path} HTTP/1.1"
            h.send_response = lambda *a, **k: None  # type: ignore[method-assign]
            h.send_header = lambda *a, **k: None  # type: ignore[method-assign]
            h.end_headers = lambda *a, **k: None  # type: ignore[method-assign]
            h.do_GET()
            return body.getvalue()

        browser_body = invoke("/browser")
        vault_body = invoke("/vault")
        self.assertIn(b"RESTORE PRIVACY BROWSER", browser_body)
        self.assertIn(b"scheduled for Q3 2026", browser_body)
        self.assertIn(b"RESTORE PRIVACY VAULT", vault_body)
        self.assertIn(b"scheduled for Q3 2027", vault_body)
        # Host alias
        host_browser = invoke("/", host="browser.restoreprivacy.online")
        self.assertIn(b"RESTORE PRIVACY BROWSER", host_browser)
        host_vault = invoke("/", host="vault.restoreprivacy.online")
        self.assertIn(b"RESTORE PRIVACY VAULT", host_vault)

        home = render_html({"title": "RESTORE PRIVACY"}).decode()
        browser = render_browser_page_html().decode()
        vault = render_vault_page_html().decode()
        for page, active in (
            (home, "vpn"),
            (browser, "browser"),
            (vault, "vault"),
        ):
            self.assertIn("product-tabs", page)
            self.assertIn(f'data-product="{active}"', page)
        self.assertIn("RESTORE PRIVACY VPN", home)
        self.assertIn("dl-buy-form", home)
        self.assertNotIn("dl-buy-form", browser)
        self.assertNotIn("dl-buy-form", vault)
        self.assertEqual(product_key_from_host("browser.restoreprivacy.online"), "browser")
        self.assertEqual(product_key_from_host("vault.example.com:443"), "vault")
        self.assertIsNone(product_key_from_host("restoreprivacy.online"))
        self.assertIsNone(product_key_from_host("www.restoreprivacy.online"))


if __name__ == "__main__":
    unittest.main()
