"""Suite monopin 1.0.4 alignment + companion/dapp version retention.

Drives shipped pin sources and catalog helpers (not re-implementations).
Fails if public/current surfaces still claim a pre-1.0.4 suite pin as current,
or if companion/dapp product versions were collapsed onto the suite monopin.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SUITE = "1.0.4"

# Companion / dapp product lines keep their own pins (not suite monopin).
RETAINED = {
    "rpos": "0.2.0",
    "node_installer": "1.0.0",
    "node_operator": "1.0.0",
    "rpmail_rpoffice": "0.1.0",
    "pts_apps": "0.1.0",
    "perc_chain": "0.1.0",
    "beam_dapp": "0.1.0",
}


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestSuiteMonopin104Alignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        import downloads as d

        cls.d = d
        cls.pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()

    def test_client_version_is_suite_monopin(self):
        self.assertEqual(self.pin, EXPECTED_SUITE)
        self.assertEqual(self.d.RELEASE_VERSION, EXPECTED_SUITE)
        self.assertEqual(self.d.RELEASE_TAG, EXPECTED_SUITE)
        self.assertEqual(self.d.current_catalog_version(), EXPECTED_SUITE)

    def test_flutter_suite_pubspec_pin(self):
        text = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        m = re.search(r"^version:\s*(\S+)", text, re.M)
        self.assertIsNotNone(m)
        # Flutter uses version+build; product pin is the part before '+'
        ver = m.group(1).split("+", 1)[0]
        self.assertEqual(ver, EXPECTED_SUITE)

    def test_browser_extension_version_and_suite_copy(self):
        manifest = json.loads(
            (ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest.get("version"), EXPECTED_SUITE)
        desc = str(manifest.get("description") or "")
        self.assertIn(EXPECTED_SUITE, desc)
        self.assertNotRegex(desc, r"Suite\s+1\.0\.[123]\b")
        popup = (ROOT / "browser_extension" / "popup.html").read_text(encoding="utf-8")
        self.assertIn(f"Suite {EXPECTED_SUITE}", popup)
        self.assertNotRegex(popup, r"Suite\s+1\.0\.[123]\b")

    def test_assure_current_packages_ok(self):
        result = self.d.assure_current_catalog_packages()
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(result["catalog_version"], EXPECTED_SUITE)
        self.assertEqual(len(result["platforms"]), 5)
        for p in result["platforms"]:
            self.assertIn(EXPECTED_SUITE, p["filename"])
            self.assertNotRegex(p["filename"], r"1\.0\.[123]-")

    def test_companion_product_versions_retained(self):
        rpos = _load_script("package_rpos", ROOT / "scripts" / "package_rpos.py")
        self.assertEqual(rpos.RPOS_VERSION, RETAINED["rpos"])
        self.assertNotEqual(rpos.RPOS_VERSION, EXPECTED_SUITE)

        ni = _load_script(
            "package_node_installers", ROOT / "scripts" / "package_node_installers.py"
        )
        self.assertEqual(ni.NODE_INSTALLER_VERSION, RETAINED["node_installer"])

        no = _load_script(
            "package_node_operator_linux",
            ROOT / "scripts" / "package_node_operator_linux.py",
        )
        self.assertEqual(no.NODE_OPERATOR_VERSION, RETAINED["node_operator"])

        mail = _load_script(
            "package_rpmail_rpoffice", ROOT / "scripts" / "package_rpmail_rpoffice.py"
        )
        self.assertEqual(mail.VERSION, RETAINED["rpmail_rpoffice"])

        pts = _load_script("package_pts_apps", ROOT / "scripts" / "package_pts_apps.py")
        self.assertEqual(pts.VERSION, RETAINED["pts_apps"])

        rx = _load_script(
            "package_browser_rx", ROOT / "scripts" / "package_browser_rx.py"
        )
        self.assertEqual(rx.suite_version(), EXPECTED_SUITE)

    def test_dapps_retain_product_version_and_suite_monopin_ref(self):
        beam = json.loads(
            (ROOT / "beam_privacy_dapp" / "src" / "dapp_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(beam.get("version"), RETAINED["beam_dapp"])
        self.assertEqual(beam.get("suite_monopin"), EXPECTED_SUITE)

        perc = json.loads(
            (ROOT / "perc_chain" / "package.json").read_text(encoding="utf-8")
        )
        self.assertEqual(perc.get("version"), RETAINED["perc_chain"])
        self.assertNotEqual(perc.get("version"), EXPECTED_SUITE)

    def test_public_surfaces_not_stale_suite_as_current(self):
        paths = [
            ROOT / "status_page" / "public" / "README.md",
            ROOT / "status_page" / "public" / "PRIVACY_POLICY.md",
            ROOT / "docs" / "SUITE_FREE_DOWNLOAD.md",
            ROOT / "public_site" / "README.md",
            ROOT / "public_site" / "downloads-map.html",
        ]
        stale = re.compile(
            r"(?:Suite\s+v?\s*1\.0\.[123]\b|catalog\s+(?:\*\*)?v?1\.0\.[123]\b|"
            r"monopin\s+(?:\*\*)?1\.0\.[123]\b|"
            r"restore-privacy-client-1\.0\.[123]-)",
            re.I,
        )
        for p in paths:
            self.assertTrue(p.is_file(), f"missing {p}")
            text = p.read_text(encoding="utf-8")
            self.assertIsNone(
                stale.search(text),
                f"stale suite pin-as-current in {p}: {stale.search(text) and stale.search(text).group(0)}",
            )
            # current monopin should appear on download/catalog surfaces
            if p.name in ("README.md", "downloads-map.html", "SUITE_FREE_DOWNLOAD.md", "PRIVACY_POLICY.md"):
                self.assertIn(EXPECTED_SUITE, text)


if __name__ == "__main__":
    unittest.main()
