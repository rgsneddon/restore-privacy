"""Grok / host-statement test: relay FlokiNET public privacy claims + docs.

Drives the real ``client.host_privacy`` helper (live fetch preferred, offline
fixture fallback) so user docs stay aligned with host-published wording.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from client.host_privacy import (  # noqa: E402
    FLOKINET_PRIVACY_URL,
    FLOKINET_VPS_URL,
    PRODUCT_NODE_COUNTRY,
    PRODUCT_NODE_HOST,
    PRODUCT_VPS_HOST_NAME,
    assert_docs_host_assurance,
    docs_paths_requiring_host_assurance,
    host_statement_claim_markers,
    offline_host_statements,
    relay_flokinet_host_statements,
    relay_summary_json,
    user_doc_host_assurance_markers,
)


class TestHostPrivacyConstants(unittest.TestCase):
    def test_product_placement(self):
        self.assertEqual(PRODUCT_NODE_HOST, "82.221.101.241")
        self.assertEqual(PRODUCT_NODE_COUNTRY, "Iceland")
        self.assertEqual(PRODUCT_VPS_HOST_NAME, "FlokiNET")
        self.assertTrue(FLOKINET_PRIVACY_URL.startswith("https://flokinet.is/"))
        self.assertTrue(FLOKINET_VPS_URL.startswith("https://flokinet.is/"))


class TestRelayFlokiNETHostStatements(unittest.TestCase):
    def test_offline_fixture_relays_public_claims(self):
        relay = offline_host_statements()
        self.assertEqual(relay.source, "offline_fixture")
        self.assertFalse(relay.live_ok)
        for m in host_statement_claim_markers():
            self.assertTrue(
                m.lower() in relay.text.lower(),
                msg=f"offline fixture missing host claim {m!r}",
            )
        # Explicit FlokiNET VPS no-traffic-sharing / resource-usage-only wording
        self.assertIn("resource usage", relay.text.lower())
        self.assertIn("third parties", relay.text.lower())
        self.assertIn("No invasive logs", relay.text)

    def test_relay_prefers_live_or_falls_back(self):
        """Drive real relay entry point (live HTTPS or offline fixture)."""
        relay = relay_flokinet_host_statements(allow_live=True, timeout=15.0)
        self.assertIn(relay.source, ("live", "live+offline_fixture", "offline_fixture"))
        self.assertTrue(
            relay.contains_all(host_statement_claim_markers()),
            msg=f"relay missing claims; source={relay.source} errors={relay.errors}",
        )
        # Summary is real JSON from helper (for scratch capture)
        summary = relay_summary_json(relay)
        self.assertIn('"claim_markers_ok": true', summary)
        self.assertIn(PRODUCT_VPS_HOST_NAME, summary)
        self.assertIn("Iceland", summary)

    def test_force_offline_path(self):
        relay = relay_flokinet_host_statements(allow_live=False)
        self.assertEqual(relay.source, "offline_fixture")
        self.assertTrue(relay.contains_all(host_statement_claim_markers()))


class TestDocsCarryHostAssurance(unittest.TestCase):
    def test_user_docs_include_iceland_flokinet_assurance(self):
        markers = user_doc_host_assurance_markers()
        self.assertIn("Iceland", markers)
        self.assertIn("FlokiNET", markers)
        failures = assert_docs_host_assurance(ROOT)
        self.assertEqual(failures, [], msg=f"docs missing host assurance: {failures}")
        for path in docs_paths_requiring_host_assurance(ROOT):
            text = path.read_text(encoding="utf-8", errors="replace")
            low = (
                text.replace("\u201c", '"')
                .replace("\u201d", '"')
                .replace("\u2018", "'")
                .replace("\u2019", "'")
                .lower()
            )
            self.assertIn("iceland", low)
            self.assertIn("flokinet", low)
            self.assertIn("as far as we can be assured", low)
            # Host does not retain invasive connection logs (assurance language)
            self.assertTrue(
                "no invasive logs" in low
                or ("does not retain" in low and "log" in low)
                or ("not retain" in low and "log" in low),
                msg=f"{path.name} must state host no-connection-logs assurance",
            )


if __name__ == "__main__":
    unittest.main()
