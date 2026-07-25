"""Tests read shipped privacy policy, LICENSE, CREDITS, and README how-to."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    path = ROOT / name
    assert path.is_file(), f"missing shipped file: {name}"
    text = path.read_text(encoding="utf-8")
    assert len(text) > 200, f"{name} is too short to be a full document"
    return text


class TestPrivacyPolicy(unittest.TestCase):
    def test_policy_exists_and_covers_no_collection_themes(self):
        text = _read("PRIVACY_POLICY.md")
        lower = text.lower()
        self.assertIn("privacy policy", lower)
        # No user-info / session activity logging themes
        self.assertTrue(
            "no user-info" in lower
            or "user-info logs" in lower
            or "session" in lower and "log" in lower
        )
        self.assertIn("not", lower)
        self.assertTrue(
            "connection log" in lower
            or "session log" in lower
            or "traffic log" in lower
            or "activity log" in lower
        )
        # Public page no longer advertises a live client count
        self.assertTrue(
            "no public" in lower
            or "not" in lower
            and ("count" in lower or "session" in lower)
            or "status" in lower
        )
        # Operational limits section
        self.assertTrue("limit" in lower or "limits" in lower)
        # Multi-platform client apps (shipped wording)
        self.assertIn("Windows", text)
        self.assertIn("Android", text)
        self.assertIn("iOS", text)
        self.assertIn("macOS", text)
        self.assertNotIn("iOS/macOS prep", text)
        # Pointers to related docs
        self.assertIn("LICENSE", text)
        self.assertIn("README", text)

    def test_policy_public_catalog_is_current_monopin(self):
        """User-facing policy must advertise catalog v0.4.5 as current paid ship."""
        text = _read("PRIVACY_POLICY.md")
        self.assertIn("Current packages (catalog v0.4.5)", text)
        self.assertNotIn("Current packages (catalog v0.4.1)", text)
        self.assertNotIn("Current packages (catalog v0.4.0)", text)
        self.assertIn("0.4.5", text)
        self.assertIn("restoreprivacy.online", text)
        self.assertIn("Developer ID", text)
        self.assertIn("Team-signed", text)
        self.assertIn("private", text.lower())
        self.assertIn("£2.45", text)
        # Paid-only distribution — no free permanent public installer CDN claim
        self.assertIn("one-time", text.lower())
        self.assertNotIn(
            "download links to public GitHub release packages",
            text,
        )
        # Must not claim RUST-IN-PRIVACY v1.0.0 as the current public packages line
        self.assertNotIn(
            "Current public packages:** [RUST-IN-PRIVACY v1.0.0]",
            text,
        )
        # Public mirror stays in sync
        pub = _read("status_page/public/PRIVACY_POLICY.md")
        self.assertIn("Current packages (catalog v0.4.5)", pub)


class TestLicenseAndCredits(unittest.TestCase):
    def test_license_full_copyright_not_mit_product_grant(self):
        text = _read("LICENSE")
        # Not MIT product grant
        self.assertNotIn("MIT License", text)
        self.assertNotIn("Permission is hereby granted, free of charge", text)
        self.assertIn("FULL COPYRIGHT", text.upper())
        self.assertIn("Copyright", text)
        self.assertIn("All rights reserved", text)
        # Architecture lock
        up = text.upper()
        self.assertIn("ARCHITECTURE", up)
        self.assertTrue(
            "NO COPY" in up or "NOT COPY" in up or "MAY NOT" in up and "ARCHITECTURE" in up
        )
        self.assertIn("transmission", text.lower())
        # No warranty + VPN-only client use
        self.assertIn("AS IS", text)
        self.assertIn("WITHOUT WARRANTY", text.upper())
        self.assertIn("VPN", text)
        self.assertIn("Client Package", text)
        # Credits / third-party acknowledgment in license
        self.assertTrue(
            "THIRD-PARTY" in text.upper() or "Wintun" in text or "CREDITS" in text
        )
        # Apple stack utilised components (aligned with CREDITS.md)
        self.assertIn("CryptoKit", text)
        self.assertIn("BigInt", text)
        # Public mirror must match
        pub = _read("status_page/public/LICENSE")
        self.assertEqual(text, pub)

    def test_credits_name_utilised_components(self):
        text = _read("CREDITS.md")
        # Must credit real utilised parts
        for name in ("Wintun", "cryptography", "Bouncy", "Flutter", "CryptoKit", "BigInt"):
            self.assertIn(name, text, f"missing credit for {name}")
        self.assertIn("wintun", text.lower())
        self.assertIn("virtual NIC", text)
        # Public Credits must not use competitor “not WireGuard/OpenVPNâ€ disclaimers
        self.assertNotIn("wireguard", text.lower())
        self.assertNotIn("openvpn", text.lower())
        # Distribution services (private source + paid status host)
        self.assertIn("Stripe", text)
        self.assertIn("restoreprivacy.online", text)
        self.assertIn("private", text.lower())
        # Product grant is full copyright, not MIT
        self.assertIn("full copyright", text.lower())
        self.assertNotIn("Project license for original code: **MIT**", text)

    def test_license_notes_paid_catalog_distribution(self):
        text = _read("LICENSE")
        self.assertIn("FULL COPYRIGHT", text.upper())
        self.assertIn("Stripe", text)
        self.assertIn("catalog v0.4.5", text)
        self.assertNotIn("catalog v0.4.0", text)
        self.assertNotIn("catalog v0.4.1", text)
        self.assertIn("private", text.lower())
        self.assertIn("PAYMENT REQUIRED", text.upper())
        pub = _read("status_page/public/LICENSE")
        self.assertEqual(text, pub)
        self.assertIn("catalog v0.4.5", pub)


class TestReadmeHowto(unittest.TestCase):
    def test_readme_howto_and_legal_links(self):
        """Public README: client-user how-to + legal links (operator detail in sundries)."""
        text = _read("README.md")
        lower = text.lower()
        self.assertTrue("how to" in lower or "install" in lower)
        # End-user client path Ã¢â‚¬â€ all published platforms
        self.assertIn("download", lower)
        self.assertIn("windows", lower)
        self.assertIn("android", lower)
        self.assertIn("macos", lower)
        self.assertIn("ios", lower)
        # Catalog ship is 0.4.5 (signed packages via paid VPN APP Shop)
        self.assertIn("0.4.5", text)
        self.assertIn("restoreprivacy.online", text)
        self.assertIn("Developer ID", text)
        self.assertIn("Team-signed", text)
        self.assertIn("private", lower)
        self.assertIn("£2.45", text)
        self.assertNotIn("prep stubs", lower)
        self.assertNotIn("prep packages only", lower)
        # Buyer path is paid status host — not free GH releases/download
        self.assertNotIn("releases/download/", text)
        # Package basenames from the public release catalog monopin
        self.assertIn(
            "restore-privacy-client-0.4.5-windows-x64-setup.exe",
            text,
        )
        self.assertIn("restore-privacy-client-0.4.5-android.apk", text)
        self.assertIn("restore-privacy-client-0.4.5-macos.zip", text)
        self.assertIn("restore-privacy-client-0.4.5-ios.zip", text)
        self.assertIn("restore-privacy-client-0.4.5-linux-x64.tar.gz", text)
        # Must not advertise older monopin filenames as the current catalog
        self.assertNotIn(
            "restore-privacy-client-0.4.0-windows-x64-setup.exe",
            text,
        )
        self.assertNotIn(
            "restore-privacy-client-0.4.1-windows-x64-setup.exe",
            text,
        )
        # Links / names to legal docs
        self.assertIn("PRIVACY_POLICY", text)
        self.assertIn("LICENSE", text)
        self.assertTrue("CREDITS" in text or "credit" in lower)
        # User-facing status/downloads OK; operator deploy is not required here
        self.assertTrue(
            "restoreprivacy.online" in text
            or "VPN APP Shop" in lower
            or "download" in lower
        )
        # Operator material lives in sundries
        self.assertTrue(
            (ROOT / "sundries.txt").is_file()
            or "sundries" in lower
        )


if __name__ == "__main__":
    unittest.main()
