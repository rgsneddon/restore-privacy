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
        self.assertEqual(NODE_PREFERENCE_HEADING, "Full business package?")
        self.assertNotEqual(NODE_PREFERENCE_HEADING, "Prefer to run a residual node?")
        self.assertEqual(NODE_PREFERENCE_DEPOSIT_LABEL, COMMERCIAL_SUITE_NODE_PRICE_LABEL)
        self.assertEqual(NODE_PREFERENCE_COMMERCIAL_CHECKOUT, COMMERCIAL_SUITE_CHECKOUT_PATH)

        frag = render_node_preference_html()
        self.assertIn(f'id="{NODE_PREFERENCE_SECTION_ID}"', frag)
        self.assertIn('data-node-preference="1"', frag)
        self.assertIn('data-business-package="1"', frag)
        self.assertIn('data-commercial-deposit="1"', frag)
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

        suite = render_suite_storefront_html()
        self.assertIn(NODE_PREFERENCE_SECTION_ID, suite)
        self.assertIn("Full business package?", suite)
        self.assertIn(COMMERCIAL_SUITE_CHECKOUT_PATH, suite)
        self.assertNotIn("Prefer to run a residual node?", suite)
        # Node preference only on Suite (left) box — not the client downloads card
        dl = render_download_section_html()
        self.assertNotIn("download-node-preference", dl)

    def test_suite_client_downloads_still_present(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            render_suite_storefront_html,
            render_download_section_html,
            suite_free_download_href,
        )

        suite = render_suite_storefront_html()
        self.assertIn('id="suite-storefront"', suite)
        self.assertIn('data-free-download="1"', suite)
        self.assertIn("suite-free-grid", suite)
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(suite_free_download_href(plat), suite)
            self.assertIn(f'data-platform="{plat}"', suite)
        self.assertIn("KEYGEN", suite)
        self.assertIn("/pay/checkout", suite)
        dl = render_download_section_html()
        self.assertIn('id="downloads"', dl)
        self.assertIn(f"Download Suite client v{RELEASE_VERSION}", dl)
        self.assertIn("dl-buy-now", dl)
        pref = re.search(
            r'id="download-node-preference".*?</aside>',
            suite,
            re.DOTALL,
        )
        self.assertIsNotNone(pref)
        assert pref is not None
        block = pref.group(0).lower()
        self.assertIn("deposit", block)
        self.assertIn("3000", block)
        self.assertIn("business package", block)

    def test_public_site_mirror_suite_downloads_1_0_0(self) -> None:
        """Static public_site export: Suite brand + live host 1.0.0 free downloads."""
        html = (ROOT / "public_site" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Restore Privacy Suite", html)
        self.assertIn("1.0.0", html)
        self.assertNotIn("Restore Privacy VPN", html)
        self.assertNotIn("RESTORE PRIVACY VPN", html)
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(
                f"https://restoreprivacy.online/suite/download?platform={plat}",
                html,
            )
        self.assertIn("suite/download?platform=windows", html)
        self.assertIn("restoreprivacy.online", html)


if __name__ == "__main__":
    unittest.main()
