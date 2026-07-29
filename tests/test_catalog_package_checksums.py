"""Catalog monopin package manifests must match on-disk installer bytes.

When ``status_page/assets/{RELEASE_VERSION}/`` holds the current catalog
packages, ``manifest.json`` / ``SHA256SUMS.json`` sha256+size must equal a
fresh hash of each listed file (prevents stale checksums after rebuilds).
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestCatalogPackageChecksums(unittest.TestCase):
    def test_current_monopin_manifest_matches_disk_when_staged(self) -> None:
        from downloads import RELEASE_VERSION

        asset_dir = ROOT / "status_page" / "assets" / RELEASE_VERSION
        man_path = asset_dir / "manifest.json"
        sums_path = asset_dir / "SHA256SUMS.json"
        if not man_path.is_file():
            self.skipTest(f"no staged catalog assets at {asset_dir}")

        man = json.loads(man_path.read_text(encoding="utf-8"))
        self.assertEqual(str(man.get("version") or ""), RELEASE_VERSION)
        assets = man.get("assets") or []
        self.assertGreaterEqual(len(assets), 1)

        if sums_path.is_file():
            sums = json.loads(sums_path.read_text(encoding="utf-8"))
            self.assertEqual(sums.get("assets"), assets)

        for entry in assets:
            name = str(entry.get("filename") or "")
            want_sha = str(entry.get("sha256") or "")
            want_bytes = int(entry.get("bytes") or 0)
            path = asset_dir / name
            # Apple may be missing until Mac seal; only assert present files
            if not path.is_file():
                continue
            got_sha = _sha256_file(path)
            got_bytes = path.stat().st_size
            self.assertEqual(
                got_bytes,
                want_bytes,
                f"{name}: size mismatch disk={got_bytes} manifest={want_bytes}",
            )
            self.assertEqual(
                got_sha,
                want_sha,
                f"{name}: sha256 mismatch disk={got_sha} manifest={want_sha}",
            )

    def test_android_apk_if_present_is_not_stale_residual_wire_size(self) -> None:
        """Flutter release APK for 0.5.2+ is ~52MB; refuse known stale 48142726 CF size."""
        from downloads import RELEASE_VERSION

        apk = (
            ROOT
            / "status_page"
            / "assets"
            / RELEASE_VERSION
            / f"restore-privacy-client-{RELEASE_VERSION}-android.apk"
        )
        if not apk.is_file():
            self.skipTest("android apk not staged")
        size = apk.stat().st_size
        # Known stale residual-wire CF size from 0.3.0 carry-forward
        self.assertNotEqual(
            size,
            48142726,
            "android apk still looks like pre-Flutter residual-wire CF size",
        )
        man_path = apk.parent / "manifest.json"
        if man_path.is_file():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            entry = next(
                (
                    a
                    for a in (man.get("assets") or [])
                    if str(a.get("filename") or "").endswith("android.apk")
                ),
                None,
            )
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(int(entry["bytes"]), size)
            self.assertEqual(str(entry["sha256"]), _sha256_file(apk))


if __name__ == "__main__":
    unittest.main()
