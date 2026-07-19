"""UK public-IP security gate — drives shipped client.uk_gate + RptClient.connect."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ConnectState, RptClient  # noqa: E402
from client.uk_gate import (  # noqa: E402
    DEFAULT_GEO_URLS,
    UK_GATE_DENIED_MESSAGE,
    UK_GATE_LOOKUP_FAILED_MESSAGE,
    check_uk_public_ip,
    default_geo_fetcher,
    evaluate_geo_payload,
    is_uk_country,
    normalize_country_code,
)


class TestUkGatePure(unittest.TestCase):
    def test_normalize_and_is_uk(self):
        self.assertEqual(normalize_country_code("gb"), "GB")
        self.assertEqual(normalize_country_code("United Kingdom"), "GB")
        self.assertTrue(is_uk_country("GB"))
        self.assertTrue(is_uk_country("UK"))
        self.assertFalse(is_uk_country("US"))
        self.assertFalse(is_uk_country("DE"))

    def test_evaluate_uk_payload_allows(self):
        r = evaluate_geo_payload({"ip": "1.2.3.4", "country_code": "GB"})
        self.assertTrue(r.allowed)
        self.assertEqual(r.country_code, "GB")
        self.assertEqual(r.public_ip, "1.2.3.4")

    def test_evaluate_non_uk_denies_with_notice(self):
        r = evaluate_geo_payload({"ip": "8.8.8.8", "country_code": "US"})
        self.assertFalse(r.allowed)
        self.assertEqual(r.message, UK_GATE_DENIED_MESSAGE)
        self.assertIn("United Kingdom", r.message)
        self.assertIn("not UK", r.message)

    def test_evaluate_missing_country_fails_closed(self):
        r = evaluate_geo_payload({"ip": "1.1.1.1"})
        self.assertFalse(r.allowed)
        self.assertEqual(r.message, UK_GATE_LOOKUP_FAILED_MESSAGE)

    def test_check_uk_public_ip_uses_fetcher_seam(self):
        uk = check_uk_public_ip(fetcher=lambda: {"country_code": "GB", "ip": "9.9.9.9"})
        self.assertTrue(uk.allowed)
        non = check_uk_public_ip(fetcher=lambda: {"countryCode": "FR", "ip": "1.1.1.1"})
        self.assertFalse(non.allowed)
        self.assertEqual(non.message, UK_GATE_DENIED_MESSAGE)

    def test_check_uk_public_ip_fail_closed_on_fetcher_error(self):
        def boom():
            raise TimeoutError("network down")

        r = check_uk_public_ip(fetcher=boom)
        self.assertFalse(r.allowed)
        self.assertEqual(r.message, UK_GATE_LOOKUP_FAILED_MESSAGE)

    def test_ipinfo_and_country_is_payload_shapes(self):
        r = evaluate_geo_payload({"ip": "1.2.3.4", "country": "GB", "city": "London"})
        self.assertTrue(r.allowed)
        r2 = evaluate_geo_payload({"ip": "2a00::1", "country": "GB"})
        self.assertTrue(r2.allowed)

    def test_default_geo_fetcher_falls_back_after_primary_failure(self):
        """When first provider fails (e.g. 429), second success must be used."""
        import urllib.error

        calls: list[str] = []

        def fake_fetch(url: str, timeout: float = 8.0) -> dict:
            calls.append(url)
            if "ipapi.co" in url:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)
            if "ipinfo.io" in url:
                return {"ip": "9.9.9.9", "country": "GB"}
            raise TimeoutError("skip")

        with mock.patch("client.uk_gate.fetch_geo_url", side_effect=fake_fetch):
            data = default_geo_fetcher()
        self.assertEqual(data["country"], "GB")
        self.assertTrue(any("ipapi.co" in u for u in calls))
        self.assertTrue(any("ipinfo.io" in u for u in calls))
        r = evaluate_geo_payload(data)
        self.assertTrue(r.allowed)

    def test_default_geo_urls_have_fallbacks(self):
        self.assertGreaterEqual(len(DEFAULT_GEO_URLS), 2)
        self.assertIn("ipapi.co", DEFAULT_GEO_URLS[0])


class TestRptClientUkGate(unittest.TestCase):
    def test_connect_blocked_for_non_uk_before_handshake(self):
        client = RptClient(
            uk_gate_fetcher=lambda: {"country_code": "US", "ip": "8.8.8.8"},
        )
        # Must not reach secrets/handshake — gate fails first
        with mock.patch(
            "client.connect.load_client_private_key",
            side_effect=AssertionError("must not load secrets when non-UK"),
        ):
            result = client.connect(timeout=1.0)
        self.assertFalse(result.ok)
        self.assertEqual(result.state, ConnectState.ERROR)
        self.assertEqual(result.message, UK_GATE_DENIED_MESSAGE)
        self.assertIsNotNone(client.last_uk_gate)
        self.assertFalse(client.last_uk_gate.allowed)

    def test_connect_uk_gate_passes_then_may_fail_on_secrets(self):
        """UK result does not block at the gate; further connect may fail for other reasons."""
        client = RptClient(
            uk_gate_fetcher=lambda: {"country_code": "GB", "ip": "81.2.69.142"},
            secrets_dir=Path("/nonexistent/secrets/path-for-test"),
        )
        result = client.connect(timeout=1.0)
        # Gate allowed — failure is from secrets/network, not UK denial
        self.assertTrue(client.last_uk_gate.allowed)
        self.assertNotEqual(result.message, UK_GATE_DENIED_MESSAGE)
        self.assertNotIn("not UK", result.message)

    def test_auto_connect_on_launch_uses_gate(self):
        client = RptClient(
            uk_gate_fetcher=lambda: {"country": "DE"},
        )
        result = client.auto_connect_on_launch(timeout=1.0)
        self.assertFalse(result.ok)
        self.assertIn("United Kingdom", result.message)

    def test_run_uk_gate_entry_point(self):
        client = RptClient(uk_gate_fetcher=lambda: {"country_code": "GB"})
        g = client.run_uk_gate()
        self.assertTrue(g.allowed)
        client2 = RptClient(uk_gate_fetcher=lambda: {"country_code": "CA"})
        g2 = client2.run_uk_gate()
        self.assertFalse(g2.allowed)
        self.assertEqual(g2.message, UK_GATE_DENIED_MESSAGE)


if __name__ == "__main__":
    unittest.main()
