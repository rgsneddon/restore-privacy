"""Free Suite download: Helsinki signed delivery when store has catalog installers."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class _FakeResp:
    def __init__(self, code: int = 200, body: bytes = b"X") -> None:
        self.status = code
        self._body = body
        self.headers = {"Content-Length": str(len(body))}

    def getcode(self) -> int:
        return self.status

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            out, self._body = self._body, b""
            return out
        out, self._body = self._body[:n], self._body[n:]
        return out

    def close(self) -> None:
        return None

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *a: object) -> None:
        self.close()


class TestSuiteFreeDeliveryPlan(unittest.TestCase):
    def test_soft_redirect_when_signed_url_available(self) -> None:
        from host_delivery import suite_free_delivery_plan

        signed = (
            "https://135.181.152.10.sslip.io/paid-assets/1.0.2/"
            "restore-privacy-client-1.0.2-macos.zip?exp=1&n=ab&sig=cd"
        )
        with mock.patch(
            "host_delivery.build_host_delivery_url", return_value=signed
        ):
            with mock.patch(
                "host_delivery.safe_catalog_version_and_filename",
                return_value=("1.0.2", "restore-privacy-client-1.0.2-macos.zip"),
            ):
                with mock.patch(
                    "host_delivery.host_delivery_secret", return_value="tok"
                ):
                    with mock.patch(
                        "host_delivery.browser_host_base_url",
                        return_value="https://135.181.152.10.sslip.io/paid-assets",
                    ):
                        with mock.patch(
                            "host_delivery.probe_vps_catalog_asset",
                            return_value=False,
                        ):
                            with mock.patch(
                                "host_delivery.probe_host_asset_reachable",
                                return_value=False,
                            ):
                                plan = suite_free_delivery_plan(
                                    "restore-privacy-client-1.0.2-macos.zip",
                                    probe=True,
                                    soft_redirect=True,
                                )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan["source"], "helsinki_host")
        self.assertTrue(str(plan["url"]).startswith("https://"))
        self.assertIn("macos.zip", plan["url"])

    def test_token_probe_success_returns_redirect(self) -> None:
        from host_delivery import suite_free_delivery_plan

        signed = (
            "https://135.181.152.10.sslip.io/paid-assets/1.0.2/"
            "restore-privacy-client-1.0.2-windows-x64-setup.exe?exp=1&n=ab&sig=cd"
        )
        with mock.patch(
            "host_delivery.build_host_delivery_url", return_value=signed
        ):
            with mock.patch(
                "host_delivery.safe_catalog_version_and_filename",
                return_value=(
                    "1.0.2",
                    "restore-privacy-client-1.0.2-windows-x64-setup.exe",
                ),
            ):
                with mock.patch(
                    "host_delivery.host_delivery_secret", return_value="tok"
                ):
                    with mock.patch(
                        "host_delivery.browser_host_base_url",
                        return_value="https://135.181.152.10.sslip.io/paid-assets",
                    ):
                        with mock.patch(
                            "host_delivery.probe_vps_catalog_asset",
                            return_value=True,
                        ):
                            plan = suite_free_delivery_plan(
                                "restore-privacy-client-1.0.2-windows-x64-setup.exe",
                                probe=True,
                                soft_redirect=False,
                            )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertTrue(plan.get("store_probed"))

    def test_probe_vps_catalog_asset_uses_token_header(self) -> None:
        from host_delivery import probe_vps_catalog_asset

        seen: dict[str, str] = {}

        def fake_urlopen(req, timeout=0):  # noqa: ANN001
            seen["url"] = req.full_url
            seen["token"] = req.get_header("X-rpt-asset-token") or req.headers.get(
                "X-RPT-Asset-Token", ""
            )
            return _FakeResp(200, b"MZ")

        with mock.patch(
            "payments.vps_asset_fetch_token", return_value="secret-token"
        ):
            with mock.patch(
                "payments.vps_asset_url",
                return_value=(
                    "https://135.181.152.10.sslip.io/paid-assets/1.0.2/"
                    "restore-privacy-client-1.0.2-macos.zip"
                ),
            ):
                ok = probe_vps_catalog_asset(
                    "restore-privacy-client-1.0.2-macos.zip",
                    urlopen=fake_urlopen,
                )
        self.assertTrue(ok)
        self.assertIn("1.0.2", seen.get("url", ""))
        self.assertEqual(seen.get("token"), "secret-token")

    def test_app_free_path_uses_suite_free_delivery_plan(self) -> None:
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("suite_free_delivery_plan", app_src)
        self.assertIn("soft_redirect=True", app_src)
        self.assertIn("is not on the store yet", app_src)  # still present as last resort
        # Free path should not require only hard probe failure → 502 without soft redirect
        self.assertIn("suite-free-helsinki", app_src)


if __name__ == "__main__":
    unittest.main()
