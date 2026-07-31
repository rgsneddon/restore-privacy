"""Public download box: node/operator preference links + Suite client still present."""

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
        # Alias short path
        self.assertIsNotNone(public_doc_by_path("/node-operator"))

        raw = load_public_document_bytes("NODE_OPERATOR.md", min_size=100)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        low = text.lower()
        # Must be node/operator oriented — not Suite KEYGEN client README only
        self.assertIn("residual node", low)
        self.assertIn("operator", low)
        self.assertIn("node_operator", low)
        self.assertIn("self-host", low)
        self.assertIn("selfhost_node", low)
        self.assertIn("suite client", low)
        self.assertIn("keygen", low)
        # Honest separation: not Suite client installers / not KEYGEN-unlocked node
        self.assertRegex(text, r"(?i)\*\*not\*\*\s+the suite client")
        self.assertRegex(text, r"(?i)does \*\*not\*\*.*keygen|keygen.*does \*\*not\*\*|not unlocked by keygen")

        # On-disk public pack
        pack = ROOT / "status_page" / "public" / "NODE_OPERATOR.md"
        self.assertTrue(pack.is_file())
        pack_text = pack.read_text(encoding="utf-8")
        self.assertIn("node_operator", pack_text)
        self.assertIn("selfhost_node", pack_text)

    def test_node_preference_block_points_at_node_operator_doc(self) -> None:
        from downloads import (
            NODE_OPERATOR_DOCS_HREF,
            NODE_OPERATOR_DOCS_ALIAS_HREF,
            NODE_PREFERENCE_SECTION_ID,
            NODE_PUBLIC_SUITE_PAGES_HREF,
            NODE_PUBLIC_SUITE_SOURCE_HREF,
            render_node_preference_html,
            render_suite_storefront_html,
            render_download_section_html,
        )
        from public_docs import load_public_document_bytes, public_doc_by_path

        self.assertEqual(NODE_OPERATOR_DOCS_HREF, "/NODE_OPERATOR.md")
        self.assertNotEqual(NODE_OPERATOR_DOCS_HREF, "/README.md")

        frag = render_node_preference_html()
        self.assertIn(f'id="{NODE_PREFERENCE_SECTION_ID}"', frag)
        self.assertIn('data-node-preference="1"', frag)
        self.assertIn("Prefer to run a residual node", frag)
        self.assertIn(f'href="{NODE_OPERATOR_DOCS_HREF}"', frag)
        self.assertIn(f'href="{NODE_OPERATOR_DOCS_ALIAS_HREF}"', frag)
        self.assertIn(f'href="{NODE_PUBLIC_SUITE_PAGES_HREF}"', frag)
        self.assertIn(f'href="{NODE_PUBLIC_SUITE_SOURCE_HREF}"', frag)
        # Primary node-docs link resolves via shipped public_docs registry
        resolved = public_doc_by_path(NODE_OPERATOR_DOCS_HREF)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        body = load_public_document_bytes(resolved.filename, min_size=100)
        self.assertIsNotNone(body)
        assert body is not None
        self.assertIn(b"residual node", body.lower())
        self.assertIn(b"node_operator", body.lower())

        suite = render_suite_storefront_html()
        self.assertIn(NODE_OPERATOR_DOCS_HREF, suite)
        self.assertNotIn('href="/README.md"', frag)
        # Node preference only on Suite (left) box — not the client downloads card
        dl = render_download_section_html()
        self.assertNotIn("download-node-preference", dl)
        self.assertNotIn(NODE_OPERATOR_DOCS_HREF, dl)

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
        self.assertIn(f"Download client v{RELEASE_VERSION}", dl)
        self.assertIn("dl-buy-now", dl)
        pref = re.search(
            r'id="download-node-preference".*?</aside>',
            suite,
            re.DOTALL,
        )
        self.assertIsNotNone(pref)
        assert pref is not None
        block = pref.group(0).lower()
        self.assertIn("not", block)
        self.assertIn("keygen", block)

    def test_public_site_mirror_has_node_preference(self) -> None:
        html = (ROOT / "public_site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="download-node-preference"', html)
        self.assertIn("data-node-preference", html)
        self.assertIn("https://restoreprivacy.online/NODE_OPERATOR.md", html)
        self.assertIn("https://restoreprivacy.online/node-operator", html)
        self.assertNotIn(
            'href="https://restoreprivacy.online/README.md"',
            html,
        )
        self.assertIn("https://rgsneddon.github.io/restore-privacy-suite/", html)
        self.assertIn("suite/download?platform=windows", html)


if __name__ == "__main__":
    unittest.main()
