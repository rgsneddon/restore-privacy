"""Catalog Windows SFX must be PE and apply Defender allows on the real launch path.

Guards against Mach-O 7zCon.sfx mistakes (unrunnable on Windows) and ensures
AllowFirewall.bat runs before RestorePrivacy.exe via run.bat / SFX bootstrap.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
SFX = (
    ROOT
    / "releases"
    / VERSION
    / f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
)


def _7z_list(sfx: Path) -> str:
    r = subprocess.run(
        ["7z", "l", str(sfx)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "7z l failed")
    return r.stdout


def _7z_extract(sfx: Path, member: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["7z", "e", f"-o{dest}", str(sfx), member, "-y"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "7z e failed")
    name = Path(member).name
    hits = list(dest.rglob(name))
    if not hits:
        raise FileNotFoundError(member)
    return hits[0]


class TestWindowsCatalogSfxPe(unittest.TestCase):
    def test_catalog_sfx_is_pe_not_mach_o(self):
        self.assertTrue(SFX.is_file(), f"missing catalog SFX: {SFX}")
        self.assertGreater(SFX.stat().st_size, 1_000_000)
        magic = SFX.read_bytes()[:4]
        self.assertEqual(magic[:2], b"MZ", f"not PE/MZ: {magic.hex()}")
        # Mach-O 64-bit magic (arm64) from accidental macOS 7zCon.sfx
        self.assertNotEqual(magic, bytes.fromhex("cffaedfe"))
        self.assertNotEqual(magic, bytes.fromhex("feedfacf"))

    def test_catalog_sfx_ships_allowfirewall_and_run_order(self):
        listing = _7z_list(SFX)
        self.assertIn("AllowFirewall.bat", listing)
        self.assertIn("run.bat", listing)
        self.assertIn("RestorePrivacy.exe", listing)
        self.assertIn("firewall_allow.py", listing)
        with tempfile.TemporaryDirectory(prefix="rpt-pe-sfx-") as td:
            tdp = Path(td)
            run_bat = _7z_extract(SFX, "run.bat", tdp)
            allow = _7z_extract(SFX, "AllowFirewall.bat", tdp)
            text = run_bat.read_text(encoding="utf-8", errors="replace")
            allow_text = allow.read_text(encoding="utf-8", errors="replace")
            self.assertIn("AllowFirewall.bat", text)
            self.assertIn("RestorePrivacy.exe", text)
            # Allow before product launch
            self.assertLess(
                text.lower().index("allowfirewall"),
                text.lower().index("restoreprivacy.exe"),
            )
            self.assertIn("RPT-FW", allow_text)
            self.assertIn("allow-node-udp", allow_text)
            self.assertIn("82.221.101.241", allow_text)

    def test_catalog_frozen_has_firewall_allow_module(self):
        """Frozen Disconnect/Connect path includes RPT-FW apply (not pure-tree only)."""
        try:
            from PyInstaller.archive.readers import CArchiveReader  # noqa: WPS433
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"PyInstaller required for freeze audit: {exc}")
        with tempfile.TemporaryDirectory(prefix="rpt-pe-frozen-") as td:
            tdp = Path(td)
            exe = _7z_extract(SFX, "RestorePrivacy.exe", tdp)
            self.assertEqual(exe.read_bytes()[:2], b"MZ")
            reader = CArchiveReader(str(exe))
            pyz = reader.open_embedded_archive("PYZ.pyz")
            fa = pyz.extract("client.windows.firewall_allow")
            self.assertIn("windows_fw_allow_script", fa.co_names)
            self.assertIn("apply_windows_fw_allows", fa.co_names)
            tw = pyz.extract("client.windows.tunnel_win")
            rest = None
            for c in tw.co_consts:
                if isinstance(c, type(tw)) and getattr(c, "co_name", "") == (
                    "restore_windows_residual_path"
                ):
                    rest = c
                    break
            self.assertIsNotNone(rest)
            self.assertIn("apply_windows_fw_allows", rest.co_names)


if __name__ == "__main__":
    unittest.main()
