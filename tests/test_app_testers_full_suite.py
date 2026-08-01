"""App-testers mint grants full Suite brand downloadables (not VPN client only).

Drives shipped ``tester_page`` helpers and payments mint path with a fresh
payment-data dir. Asserts success HTML / mint payload includes multiple brand
product families beyond ``restore-privacy-client-*``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAppTestersFullSuite(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments
        import tester_page as tp
        from downloads import RELEASE_VERSION

        self.pay = payments
        self.tp = tp
        self.pin = RELEASE_VERSION
        self.pay.init_db()
        self.tp.init_tester_claim_db()

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_inventory_lists_suite_and_companions(self) -> None:
        rows = self.tp.list_tester_full_suite_downloadables()
        self.assertGreaterEqual(len(rows), 10)
        kinds = {r["kind"] for r in rows}
        self.assertIn("suite_client", kinds)
        # Companions from downloads-map brand inventory
        companion_kinds = kinds - {"suite_client"}
        self.assertTrue(
            companion_kinds,
            f"expected companion product kinds, got only {kinds}",
        )
        expected_any = {
            "browser",
            "rpos",
            "node_installer",
            "node_operator",
            "rpmail",
            "rpoffice",
            "rpos_app",
        }
        self.assertTrue(
            companion_kinds & expected_any,
            f"missing brand families in {companion_kinds}",
        )
        # No docs/scaffold-only rows
        for r in rows:
            self.assertNotEqual(r["kind"], "beam_dapp")
            self.assertNotIn("/", r["filename"])
            self.assertFalse(r["filename"].lower().endswith(".md"))
        suite = [r for r in rows if r["kind"] == "suite_client"]
        self.assertEqual(len(suite), 5)
        for r in suite:
            self.assertIn(self.pin, r["filename"])
            self.assertTrue(r["filename"].startswith("restore-privacy-client-"))

    def test_mint_returns_full_suite_downloads_not_vpn_only(self) -> None:
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
        self.assertTrue(out.get("full_suite"), out)
        self.assertTrue(str(out.get("keygen") or "").startswith(self.pay.KEYGEN_PREFIX))
        downloads = out.get("downloads") or []
        self.assertIsInstance(downloads, list)
        self.assertGreaterEqual(len(downloads), 10, downloads[:3])

        kinds = {str(d.get("kind") or "") for d in downloads}
        self.assertIn("suite_client", kinds)
        companion = kinds - {"suite_client"}
        self.assertTrue(companion, f"only VPN kinds: {kinds}")

        filenames = [str(d.get("filename") or "") for d in downloads]
        client_names = [f for f in filenames if f.startswith("restore-privacy-client-")]
        self.assertGreaterEqual(len(client_names), 5)
        non_client = [
            f
            for f in filenames
            if f and not f.startswith("restore-privacy-client-")
        ]
        self.assertTrue(non_client, "expected companion basenames")
        # Representative companions from inventory
        joined = "\n".join(filenames)
        self.assertTrue(
            any(
                x in joined
                for x in (
                    "browser-extension",
                    "rx-browser",
                    "rpos-",
                    "node-installer",
                    "rpmail-",
                    "rpoffice-",
                    "pens-",
                )
            ),
            joined[:500],
        )
        # Every row has a download URL
        for d in downloads:
            url = str(d.get("download_url") or "")
            self.assertTrue(url.startswith("https://"), d)
            self.assertTrue(
                "/download?token=" in url or "/assets/" in url,
                url,
            )
            # Companions stage under suite monopin free-open path (not product pin).
            if str(d.get("kind") or "") != "suite_client":
                self.assertIn(f"/assets/{self.pin}/", url, url)

    def test_success_html_lists_multiple_brand_families(self) -> None:
        cid = self.tp.new_claim_id()
        out = self.tp.mint_for_tester(
            "linux",
            claim_id=cid,
            accepted=True,
            reports_consent=True,
            base_url="https://restoreprivacy.online",
        )
        self.assertTrue(out.get("ok"), out)
        raw = self.tp.render_success_html(out)
        self.assertIsInstance(raw, (bytes, bytearray))
        html = raw.decode("utf-8")
        self.assertIn("data-full-suite", html)
        self.assertIn("full-suite-downloads", html)
        self.assertIn("KEYGEN", html.upper())
        self.assertIn("/download?token=", html)
        # Companions via /assets/ with keygen
        self.assertIn("/assets/", html)
        self.assertIn(self.pin, html)
        # Not VPN-only: multiple product labels / non-client filenames
        self.assertGreater(html.count("data-filename="), 5)
        self.assertTrue(
            any(
                s in html
                for s in (
                    "browser-extension",
                    "rx-browser",
                    "rpos-",
                    "node-installer",
                    "rpmail-",
                    "rpoffice-",
                    "pens-",
                    "tables-",
                    "slides-",
                )
            ),
            html[:1200],
        )
        # Primary residual platform still named
        self.assertIn("linux", html.lower())

    def test_main_page_copy_promises_full_suite(self) -> None:
        page = self.tp.render_tester_page_html().decode("utf-8")
        self.assertIn("data-full-suite-grant", page)
        self.assertIn("full Suite", page)
        self.assertIn("Primary residual client platform", page)
        # Disclaimer no longer claims one-package-only
        lic = self.tp.licence_and_disclaimer_text()
        self.assertIn("full brand", lic.lower())
        self.assertNotIn(
            "one** device package\n   platform only",
            lic,
        )

    def test_gates_and_second_claim_still_hold(self) -> None:
        cid = self.tp.new_claim_id()
        denied = self.tp.mint_for_tester(
            "windows", claim_id=cid, accepted=False, reports_consent=True
        )
        self.assertFalse(denied.get("ok"))
        first = self.tp.mint_for_tester(
            "windows",
            claim_id=cid,
            accepted=True,
            reports_consent=True,
            base_url="https://restoreprivacy.online",
        )
        self.assertTrue(first.get("ok"), first)
        self.assertGreaterEqual(len(first.get("downloads") or []), 10)
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


if __name__ == "__main__":
    unittest.main()
