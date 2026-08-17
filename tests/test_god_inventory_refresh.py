"""GOD installer inventory refreshes without gh and keeps the last snapshot."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


class TestGodInventoryRefresh(unittest.TestCase):
    def test_http_fetch_normalizes_github_releases(self) -> None:
        from _refresh_github_release_inventory import fetch_releases_http

        payload = json.dumps(
            [
                {
                    "tag_name": "v0.0.7",
                    "draft": False,
                    "assets": [
                        {
                            "name": "gnfp-wallet-0.0.7-macos.zip",
                            "browser_download_url": (
                                "https://github.com/rgsneddon/gnfp-wallet/"
                                "releases/download/v0.0.7/"
                                "gnfp-wallet-0.0.7-macos.zip"
                            ),
                        },
                        {"name": "checksums.sha256", "browser_download_url": "x"},
                    ],
                }
            ]
        ).encode("utf-8")

        class _Resp:
            def read(self) -> bytes:
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch(
            "_refresh_github_release_inventory.urllib.request.urlopen",
            return_value=_Resp(),
        ):
            rows = fetch_releases_http("gnfp-wallet")
        self.assertEqual(rows[0]["tag"], "v0.0.7")
        names = [a["filename"] for a in rows[0]["assets"]]
        self.assertEqual(names, ["gnfp-wallet-0.0.7-macos.zip"])

    def test_failed_fetch_keeps_previous_snapshot(self) -> None:
        from _refresh_github_release_inventory import refresh_github_release_inventory

        dest = Path(self.id().replace(".", "_") + ".json")
        dest = ROOT / "status_page" / dest.name
        self.addCleanup(lambda: dest.unlink(missing_ok=True))
        dest.write_text(
            json.dumps(
                {
                    "updated": "2026-08-17",
                    "repos": [
                        {
                            "product": "GNFP wallet",
                            "repo": "gnfp-wallet",
                            "releases": [
                                {
                                    "tag": "v0.0.6",
                                    "assets": [
                                        {
                                            "platform": "windows",
                                            "filename": "gnfp-wallet-0.0.6-windows.zip",
                                            "href": "https://example/old",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        def boom(_repo: str):
            raise HTTPError("https://api.github.com", 503, "nope", hdrs=None, fp=io.BytesIO())

        result = refresh_github_release_inventory(dest=dest, fetch_fn=boom)
        self.assertTrue(result["ok"])
        self.assertFalse(result["wrote"])
        raw = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(raw["repos"][0]["releases"][0]["tag"], "v0.0.6")

    def test_timer_unit_runs_full_refresh_script(self) -> None:
        service = (
            ROOT / "perc_chain" / "deploy" / "rpt-god-inventory.service"
        ).read_text(encoding="utf-8")
        timer = (
            ROOT / "perc_chain" / "deploy" / "rpt-god-inventory.timer"
        ).read_text(encoding="utf-8")
        self.assertIn("refresh_god_release_links.py", service)
        self.assertIn("OnUnitActiveSec=10min", timer)


if __name__ == "__main__":
    unittest.main()
