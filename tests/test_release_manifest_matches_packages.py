"""Catalog release manifest sha256/bytes must match on-disk packages.

When ``releases/<catalog>/`` is staged with monopin packages, ``manifest.json``
must not lag prior carry-forward digests (skeptic gap on 1.0.7).
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _catalog_version() -> str:
    ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
    if not ver:
        raise AssertionError("client/VERSION empty")
    return ver


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ReleaseManifestMatchesPackages(unittest.TestCase):
    def test_catalog_manifest_matches_staged_packages(self) -> None:
        ver = _catalog_version()
        out = ROOT / "releases" / ver
        man_path = out / "manifest.json"
        if not man_path.is_file():
            self.skipTest(f"no staged releases/{ver}/manifest.json")

        man = json.loads(man_path.read_text(encoding="utf-8"))
        self.assertEqual(man.get("version"), ver)
        packages = man.get("packages") or []
        self.assertGreaterEqual(len(packages), 1, "manifest packages empty")

        for pkg in packages:
            with self.subTest(platform=pkg.get("platform")):
                name = pkg.get("filename")
                self.assertTrue(name, "package missing filename")
                path = out / name
                self.assertTrue(path.is_file(), f"missing package {path}")
                self.assertEqual(
                    path.stat().st_size,
                    int(pkg["bytes"]),
                    f"{name} bytes mismatch man={pkg['bytes']} act={path.stat().st_size}",
                )
                dig = _sha256(path)
                self.assertEqual(
                    dig,
                    pkg["sha256"],
                    f"{name} sha256 mismatch man={pkg['sha256'][:16]}… act={dig[:16]}…",
                )

    def test_status_assets_manifest_matches_when_present(self) -> None:
        ver = _catalog_version()
        assets = ROOT / "status_page" / "assets" / ver
        man_path = assets / "manifest.json"
        if not man_path.is_file():
            self.skipTest(f"no status_page/assets/{ver}/manifest.json")

        man = json.loads(man_path.read_text(encoding="utf-8"))
        self.assertEqual(man.get("version"), ver)
        for pkg in man.get("packages") or []:
            path = assets / pkg["filename"]
            if not path.is_file():
                # status tree may hold subset; only assert when file present
                continue
            self.assertEqual(path.stat().st_size, int(pkg["bytes"]), pkg["filename"])
            self.assertEqual(_sha256(path), pkg["sha256"], pkg["filename"])


if __name__ == "__main__":
    unittest.main()
