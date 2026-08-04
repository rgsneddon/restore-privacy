"""Gatekeeper / Developer ID honesty for catalog macOS packages.

Drives pure codesign parsers and (on Darwin) the real assess helper against
the monopin zip when present.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestCodesignDvParser(unittest.TestCase):
    def test_developer_id_leaf_ok(self) -> None:
        from apple_package_audit import (
            distribution_seal_ok_from_codesign,
            parse_codesign_dv_output,
        )

        sample = """
Executable=/tmp/restore_privacy_client.app/Contents/MacOS/restore_privacy_client
Identifier=com.restoreprivacy.restorePrivacyClient
Authority=Developer ID Application: Russell Sneddon (SFCBP95595)
Authority=Developer ID Certification Authority
Authority=Apple Root CA
TeamIdentifier=SFCBP95595
Notarization Ticket=stapled
Runtime Version=26.5.0
"""
        p = parse_codesign_dv_output(sample)
        self.assertTrue(p["is_developer_id_application"])
        self.assertFalse(p["is_apple_development"])
        self.assertTrue(p["ticket_stapled"])
        seal = distribution_seal_ok_from_codesign(sample)
        self.assertTrue(seal["ok"])
        self.assertEqual(seal["reason"], "developer_id_application")

    def test_apple_development_fails_closed(self) -> None:
        from apple_package_audit import distribution_seal_ok_from_codesign

        sample = """
Authority=Apple Development: Russell Sneddon (U37S5938B4)
Authority=Apple Worldwide Developer Relations Certification Authority
Authority=Apple Root CA
TeamIdentifier=SFCBP95595
Notarization Ticket=stapled
"""
        seal = distribution_seal_ok_from_codesign(sample)
        self.assertFalse(seal["ok"])
        self.assertEqual(seal["reason"], "apple_development_not_distribution")
        self.assertTrue(seal["is_apple_development"])

    def test_adhoc_fails_closed(self) -> None:
        from apple_package_audit import distribution_seal_ok_from_codesign

        seal = distribution_seal_ok_from_codesign("Signature=adhoc\n")
        self.assertFalse(seal["ok"])


class TestSignScriptFailClosed(unittest.TestCase):
    def test_sign_script_requires_developer_id_not_development(self) -> None:
        text = (ROOT / "scripts" / "sign_and_notarize_macos.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Developer ID Application", text)
        self.assertIn("notarytool", text)
        self.assertIn("stapler", text)
        # Must refuse non-DevID leaf after sign (Gatekeeper "could not verify")
        self.assertIn('if "Developer ID Application" not in cs:', text)
        self.assertIn("Apple Development", text)


class TestLiveMonopinZipDistribution(unittest.TestCase):
    def test_monopin_macos_zip_is_developer_id_when_present(self) -> None:
        """Catalog monopin is Notarized Developer ID (Gatekeeper-openable)."""
        from apple_package_audit import (
            assess_macos_catalog_zip_codesign,
            require_macos_zip_matches_monopin,
        )
        from downloads import RELEASE_VERSION

        pin = RELEASE_VERSION
        candidates = [
            ROOT / "releases" / pin / f"restore-privacy-client-{pin}-macos.zip",
            ROOT / "status_page" / "assets" / pin / f"restore-privacy-client-{pin}-macos.zip",
        ]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            self.skipTest("monopin macOS zip not staged on this host")
        require_macos_zip_matches_monopin(path, pin)
        if sys.platform != "darwin":
            self.skipTest("codesign assess requires Darwin")
        report = assess_macos_catalog_zip_codesign(path)
        self.assertTrue(
            report.get("ok"),
            msg=f"catalog monopin must be Notarized Developer ID: {report}",
        )
        self.assertTrue(report.get("is_developer_id_application"))
        self.assertFalse(report.get("is_apple_development"))
        self.assertTrue(
            report.get("spctl_notarized_developer_id"),
            msg=report.get("spctl_text"),
        )

    def test_build_suite_monopin_requires_devid_not_residual(self) -> None:
        """Ship recipe must fail-closed for DevID monopin (not residual-team)."""
        script = ROOT / "scripts" / "build_suite_1.1.10.py"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn("require_macos_zip_developer_id_distribution", text)
        self.assertIn("sign_and_notarize_macos.py", text)
        # Free monopin prefers residual host NE for first-use System VPN registration.
        self.assertIn('RPT_MACOS_HOST_NE"] = "1"', text)
        # Residual re-sign is best-effort side path only
        self.assertIn("require=False", text)
        self.assertNotIn(
            "require_macos_zip_residual_capable(dest)",
            text,
        )

    def test_residual_seal_helpers_still_exported(self) -> None:
        from apple_package_audit import (
            assess_macos_zip_residual_capable,
            host_app_has_packet_tunnel_provider,
            launch_probe_app_alive,
            require_macos_zip_residual_capable,
        )

        self.assertTrue(callable(host_app_has_packet_tunnel_provider))
        self.assertTrue(callable(launch_probe_app_alive))
        self.assertTrue(callable(assess_macos_zip_residual_capable))
        self.assertTrue(callable(require_macos_zip_residual_capable))
        missing = assess_macos_zip_residual_capable("/no/such/macos.zip")
        self.assertFalse(missing.get("ok"))
        self.assertEqual(missing.get("reason"), "missing_zip")


if __name__ == "__main__":
    unittest.main()
