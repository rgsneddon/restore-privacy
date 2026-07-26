"""Native NE permission gate must not open Settings for residual re-sign / non-auth NE errors.

Shipped classifiers live in macOS RptVpnChannel.swift:
  isTeamResidualOrMissingHostNeDetail
  isNePermissionFailure
  isNePermissionFailureDetail
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWIFT = ROOT / "client_app" / "macos" / "NativePrep" / "RptVpnChannel.swift"
DART = ROOT / "client_app" / "lib" / "connect_status.dart"


def _extract_func_body(text: str, name: str) -> str:
    """Extract Swift static func body by name (brace-matched)."""
    m = re.search(rf"static func {name}\b[^{{]*\{{", text)
    assert m, f"missing func {name}"
    start = m.end() - 1
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unclosed func {name}")


class TestNePermissionSettingsGate(unittest.TestCase):
    def setUp(self):
        self.swift = SWIFT.read_text(encoding="utf-8")

    def test_residual_classifier_exists_and_is_used_first(self):
        body = _extract_func_body(self.swift, "isNePermissionFailureDetail")
        self.assertIn("isTeamResidualOrMissingHostNeDetail", body)
        # Residual check must return false before broad matching
        residual_pos = body.find("isTeamResidualOrMissingHostNeDetail")
        nevpn_pos = body.find("nevpnerrordomain")
        self.assertGreater(residual_pos, 0)
        self.assertGreater(nevpn_pos, residual_pos)

    def test_host_missing_message_not_classified_as_permission(self):
        """hostMissingNeEntitlementMessage must not trip permission detail matcher."""
        body = _extract_func_body(self.swift, "hostMissingNeEntitlementMessage")
        # User-facing string literals only (ignore // comments)
        literals = " ".join(re.findall(r'"([^"]*)"', body)).lower()
        self.assertNotIn("allow vpn", literals)
        # Residual markers present so isTeamResidualOrMissingHostNeDetail matches
        self.assertIn("packet-tunnel-provider", body)
        self.assertIn("sign_macos_residual_team", body)
        # Permission detail gate must exclude residual before any "allow" matching
        detail = _extract_func_body(self.swift, "isNePermissionFailureDetail")
        self.assertIn("isTeamResidualOrMissingHostNeDetail", detail)
        self.assertIn("return false", detail)

    def test_permission_detail_does_not_match_generic_ne_preferences_failed(self):
        body = _extract_func_body(self.swift, "isNePermissionFailureDetail")
        # Must not return true solely for "ne preferences failed"
        self.assertNotIn('d.contains("ne preferences failed")', body)
        self.assertNotIn('d.contains("allow vpn")', body)
        # Must require auth language or code 5 for NEVPNErrorDomain
        self.assertIn("code 5", body.lower().replace(" ", "") + body)  # flexible
        self.assertTrue(
            "code 5" in body.lower()
            or " 5)" in body
            or "errordomain 5" in body.lower()
            or 'ns.code == 5' in body.replace(" ", "")
            or "code5" in body.lower().replace(" ", "")
            or 'contains(" 5)")' in body
            or 'contains(" 5:")' in body
        )

    def test_is_ne_permission_failure_not_all_domain_errors(self):
        body = _extract_func_body(self.swift, "isNePermissionFailure")
        # Must not return true for entire NEVPNErrorDomain without code/auth check
        self.assertNotRegex(
            body.replace(" ", ""),
            r'ifns\.domain==NEVPNErrorDomain\{returntrue\}',
        )
        self.assertIn("ns.code == 5", body.replace(" ", "") + body)
        # code == 5 appears
        self.assertTrue("code == 5" in body or "code==5" in body.replace(" ", ""))

    def test_connect_enable_failure_sets_residual_flags(self):
        body = _extract_func_body(self.swift, "enableProductVpnAndStartTunnel")
        self.assertIn("needsTeamResidualSign", body)
        self.assertIn("hostHasPacketTunnelEntitlement", body)
        self.assertIn("isTeamResidualOrMissingHostNeDetail", body)
        self.assertIn("hostMissingNeEntitlementMessage", body)

    def test_dart_auto_open_excludes_residual_and_host_missing(self):
        dart = DART.read_text(encoding="utf-8")
        self.assertIn("isStrictVpnPermissionDenialMessage", dart)
        strict = _extract_func_body_dart(dart, "isStrictVpnPermissionDenialMessage")
        self.assertIn("team residual", strict.lower())
        self.assertIn("packet-tunnel-provider", strict)
        self.assertIn("return false", strict)


def _extract_func_body_dart(text: str, name: str) -> str:
    m = re.search(rf"bool {name}\b[^{{]*\{{", text)
    assert m, f"missing dart func {name}"
    start = m.end() - 1
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unclosed {name}")


if __name__ == "__main__":
    unittest.main()
