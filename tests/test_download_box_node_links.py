"""Public download box: full business package + £3000 deposit + Suite client still present."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestDownloadBoxNodeLinks(unittest.TestCase):
    def test_node_docs_destination_is_residual_node_operator_content(self) -> None:
        """Shipped public NODE_OPERATOR.md is about residual node/operator path."""
        from public_docs import (
            NODE_OPERATOR_PATH,
            load_public_document_bytes,
            public_doc_by_path,
        )

        doc = public_doc_by_path(NODE_OPERATOR_PATH)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.filename, "NODE_OPERATOR.md")
        self.assertEqual(doc.path, "/NODE_OPERATOR.md")
        self.assertIsNotNone(public_doc_by_path("/node-operator"))

        raw = load_public_document_bytes("NODE_OPERATOR.md", min_size=100)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        low = text.lower()
        self.assertIn("residual node", low)
        self.assertIn("operator", low)
        self.assertIn("node_operator", low)
        self.assertIn("self-host", low)
        self.assertIn("selfhost_node", low)
        self.assertIn("suite client", low)
        self.assertIn("keygen", low)
        self.assertRegex(text, r"(?i)\*\*not\*\*\s+the suite client")
        self.assertRegex(
            text,
            r"(?i)does \*\*not\*\*.*keygen|keygen.*does \*\*not\*\*|not unlocked by keygen",
        )

        pack = ROOT / "status_page" / "public" / "NODE_OPERATOR.md"
        self.assertTrue(pack.is_file())
        pack_text = pack.read_text(encoding="utf-8")
        self.assertIn("node_operator", pack_text)
        self.assertIn("selfhost_node", pack_text)

    def test_business_package_block_deposit_and_stripe_path(self) -> None:
        from downloads import (
            NODE_OPERATOR_DOCS_HREF,
            NODE_OPERATOR_DOCS_ALIAS_HREF,
            NODE_PREFERENCE_COMMERCIAL_CHECKOUT,
            NODE_PREFERENCE_COMMERCIAL_HREF,
            NODE_PREFERENCE_DEPOSIT_LABEL,
            NODE_PREFERENCE_HEADING,
            NODE_PREFERENCE_SECTION_ID,
            NODE_PUBLIC_SUITE_PAGES_HREF,
            NODE_PUBLIC_SUITE_SOURCE_HREF,
            render_download_section_html,
            render_node_preference_html,
            render_suite_storefront_html,
        )
        from payments import (
            COMMERCIAL_SUITE_CHECKOUT_PATH,
            COMMERCIAL_SUITE_NODE_PRICE_LABEL,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
        )

        self.assertEqual(NODE_OPERATOR_DOCS_HREF, "/NODE_OPERATOR.md")
        # Heading always carries Full business package + £3000 deposit framing.
        self.assertIn("Full business package?", NODE_PREFERENCE_HEADING)
        self.assertIn("3000", NODE_PREFERENCE_HEADING.replace("£", ""))
        self.assertNotEqual(NODE_PREFERENCE_HEADING, "Prefer to run a residual node?")
        self.assertEqual(NODE_PREFERENCE_DEPOSIT_LABEL, COMMERCIAL_SUITE_NODE_PRICE_LABEL)
        self.assertEqual(NODE_PREFERENCE_COMMERCIAL_CHECKOUT, COMMERCIAL_SUITE_CHECKOUT_PATH)

        frag = render_node_preference_html()
        self.assertIn(f'id="{NODE_PREFERENCE_SECTION_ID}"', frag)
        self.assertIn('data-node-preference="1"', frag)
        self.assertIn('data-business-package="1"', frag)
        self.assertIn('data-commercial-deposit="1"', frag)
        self.assertIn(NODE_PREFERENCE_HEADING, frag)
        self.assertIn("Full business package?", frag)
        self.assertNotIn("Prefer to run a residual node?", frag)
        # Old KEYGEN-not-unlock framing must not be primary blurb
        self.assertNotIn("not a fifth Suite client platform", frag)
        self.assertNotIn("not unlocked by the monthly KEYGEN", frag)
        # New substance
        low = frag.lower()
        for needle in (
            "business package",
            "residual node",
            "raskul",
            "deposit",
            "3000",
            "costs may be higher",
            "restore privacy operating system",
            "rpos",
            "user-friendly",
        ):
            self.assertIn(needle, low, msg=needle)
        # £3000 deposit control → commercial Stripe checkout
        self.assertIn(f'action="{COMMERCIAL_SUITE_CHECKOUT_PATH}"', frag)
        self.assertIn(f'value="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"', frag)
        self.assertIn('id="node-pref-deposit-btn"', frag)
        self.assertIn("deposit", frag.lower())
        self.assertIn(f'href="{NODE_PREFERENCE_COMMERCIAL_HREF}"', frag)
        self.assertIn(f'href="{NODE_OPERATOR_DOCS_HREF}"', frag)
        self.assertIn(f'href="{NODE_OPERATOR_DOCS_ALIAS_HREF}"', frag)
        self.assertIn(f'href="{NODE_PUBLIC_SUITE_PAGES_HREF}"', frag)
        self.assertIn(f'href="{NODE_PUBLIC_SUITE_SOURCE_HREF}"', frag)

        # Business package is standalone on home (above node wipe) — not nested in Suite.
        suite = render_suite_storefront_html()
        self.assertNotIn(NODE_PREFERENCE_SECTION_ID, suite)
        self.assertNotIn("Full business package?", suite)
        self.assertNotIn("download-node-preference", suite)
        self.assertNotIn('data-business-package="1"', suite)
        # Client downloads card also does not host it
        dl = render_download_section_html()
        self.assertNotIn("download-node-preference", dl)

        # Standalone fragment marks home-business-package (dotted transparent box).
        stand = render_node_preference_html(standalone=True)
        self.assertIn("home-business-package", stand)
        self.assertIn('data-home-business-package="1"', stand)
        self.assertIn("Full business package?", stand)
        self.assertIn("deposit", stand.lower())
        self.assertIn("3000", stand)

        # Home page: shop row → business package → node wipe timer.
        from app import render_html
        from downloads import suite_storefront_css

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main_i = page.find('id="page-shell"')
        main = page[main_i:] if main_i >= 0 else page
        i_row = main.index('id="home-shop-row"')
        i_biz = main.index(f'id="{NODE_PREFERENCE_SECTION_ID}"')
        i_nw = main.index("node-wipe")
        self.assertLess(i_row, i_biz, "business package must follow shop row")
        self.assertLess(i_biz, i_nw, "business package must sit above node wipe")
        self.assertIn('data-home-business-package="1"', main)
        self.assertIn("home-business-package", main)
        # Dotted transparent style lives in suite_storefront_css (injected on home).
        css = suite_storefront_css()
        self.assertIn("border: 1px dashed", css)
        self.assertIn("rgba(8, 18, 32, 0.18)", css)
        self.assertIn(".download-node-preference.home-business-package", css)
        self.assertIn("border: 1px dashed", page)
        self.assertIn("rgba(8, 18, 32, 0.18)", page)

        # Homepage/standalone box spans full content width (not narrow 42rem-only card).
        self.assertRegex(
            css,
            r"\.download-node-preference\.home-business-package\s*\{[^}]*width:\s*100%",
        )
        self.assertRegex(
            css,
            r"\.download-node-preference\.home-business-package\s*\{[^}]*max-width:\s*100%",
        )
        # Base card may still use min(42rem, 100%); home override must not re-apply that cap.
        home_rule = re.search(
            r"\.download-node-preference\.home-business-package\s*\{([^}]*)\}",
            css,
            re.S,
        )
        self.assertIsNotNone(home_rule, "home-business-package CSS rule required")
        assert home_rule is not None
        home_body = home_rule.group(1)
        home_compact = re.sub(r"\s+", "", home_body)
        self.assertNotIn("42rem", home_body)
        self.assertIn("width:100%", home_compact)
        self.assertIn("max-width:100%", home_compact)

    def test_suite_client_downloads_still_present(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            render_suite_storefront_html,
            render_download_section_html,
            suite_pay_href,
        )

        suite = render_suite_storefront_html()
        self.assertIn('id="suite-storefront"', suite)
        self.assertNotIn('id="suite-free-grid"', suite)
        self.assertNotIn("Device for KEYGEN", suite)
        self.assertNotIn("Get Suite", suite)
        self.assertIn("KEYGEN", suite)
        self.assertIn("/pay", suite)
        self.assertIn("suite-keygen-buy", suite)
        self.assertNotIn("download-node-preference", suite)
        self.assertNotIn("Full business package?", suite)
        dl = render_download_section_html()
        self.assertIn('id="downloads"', dl)
        self.assertIn(f"Download Suite client v{RELEASE_VERSION}", dl)
        self.assertIn("dl-buy-now", dl)

    def test_public_site_mirror_suite_downloads_current(self) -> None:
        """Static public_site export still brands Suite (live host is source of truth)."""
        from downloads import RELEASE_VERSION

        html = (ROOT / "public_site" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Restore Privacy Suite", html)
        self.assertIn(RELEASE_VERSION, html)
        self.assertNotIn("RESTORE PRIVACY VPN", html)
        self.assertIn("restoreprivacy.online", html)


if __name__ == "__main__":
    unittest.main()
