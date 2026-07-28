"""macOS catalog zip CFBundleShortVersionString must equal monopin always."""

from __future__ import annotations

import io
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


def _monopin() -> str:
    return (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()


def _make_macos_zip(dest: Path, *, cfbundle: str) -> Path:
    """Minimal zip with host Info.plist CFBundleShortVersionString=*cfbundle*."""
    pl = {
        "CFBundleShortVersionString": cfbundle,
        "CFBundleVersion": "1",
        "CFBundleIdentifier": "com.restoreprivacy.restorePrivacyClient",
        "CFBundleExecutable": "restore_privacy_client",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "restore_privacy_client.app/Contents/Info.plist",
            plistlib.dumps(pl),
        )
        zf.writestr(
            "restore_privacy_client.app/Contents/MacOS/restore_privacy_client",
            b"\0",
        )
    dest.write_bytes(buf.getvalue())
    return dest


class TestMacosCfbundleHelpers(unittest.TestCase):
    def test_require_matches_monopin(self):
        from apple_package_audit import (
            macos_zip_cfbundle_short_version,
            require_macos_zip_matches_monopin,
        )

        pin = _monopin()
        with tempfile.TemporaryDirectory() as td:
            ok = Path(td) / "ok.zip"
            _make_macos_zip(ok, cfbundle=pin)
            self.assertEqual(macos_zip_cfbundle_short_version(ok), pin)
            self.assertEqual(require_macos_zip_matches_monopin(ok, pin), pin)

    def test_require_rejects_stale_cfbundle(self):
        from apple_package_audit import require_macos_zip_matches_monopin

        pin = _monopin()
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "stale.zip"
            _make_macos_zip(bad, cfbundle="0.2.3")
            with self.assertRaises(RuntimeError) as ctx:
                require_macos_zip_matches_monopin(bad, pin)
            msg = str(ctx.exception)
            self.assertIn("0.2.3", msg)
            self.assertIn(pin, msg)
            self.assertIn("refuse", msg.lower())

    def test_product_pins_agree_with_monopin(self):
        pin = _monopin()
        from downloads import RELEASE_VERSION, current_catalog_version

        self.assertEqual(RELEASE_VERSION, pin)
        self.assertEqual(current_catalog_version(), pin)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn(f"version: {pin}+", pub)
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"productVersion = '{pin}'", cfg)

    def test_release_script_refuses_macos_carry_forward(self):
        """Shipped release path must not silent-rename prior zip as current monopin."""
        pin = _monopin()
        script = ROOT / "scripts" / f"build_release_{pin}.py"
        self.assertTrue(script.is_file(), msg=str(script))
        src = script.read_text(encoding="utf-8")
        self.assertIn("refuse carry-forward", src)
        self.assertIn("_require_macos_cfbundle_matches_monopin", src)
        self.assertIn("require_macos_zip_matches_monopin", src)
        # stage_macos_zip must raise, not return _stage_from_prior for success
        block = src[src.index("def stage_macos_zip") : src.index("def stage_ios_zip")]
        self.assertIn("RuntimeError", block)
        self.assertNotIn("_stage_from_prior", block)

    def test_host_paid_assets_gates_macos_cfbundle(self):
        src = (ROOT / "scripts" / "host_paid_assets_vps.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_assert_macos_cfbundle", src)
        self.assertIn("require_macos_zip_matches_monopin", src)

    def test_staged_or_release_macos_zip_matches_when_present(self):
        """Drive real inspect helper against on-disk catalog zip if staged."""
        from apple_package_audit import (
            macos_zip_cfbundle_short_version,
            require_macos_zip_matches_monopin,
        )

        pin = _monopin()
        candidates = [
            ROOT / "releases" / pin / f"restore-privacy-client-{pin}-macos.zip",
            ROOT
            / "status_page"
            / "assets"
            / pin
            / f"restore-privacy-client-{pin}-macos.zip",
        ]
        present = [p for p in candidates if p.is_file()]
        if not present:
            self.skipTest("no staged macOS zip in this checkout")
        for zpath in present:
            ver = macos_zip_cfbundle_short_version(zpath)
            self.assertEqual(
                ver,
                pin,
                msg=f"{zpath} CFBundle {ver!r} != monopin {pin}",
            )
            require_macos_zip_matches_monopin(zpath, pin)


if __name__ == "__main__":
    unittest.main()
