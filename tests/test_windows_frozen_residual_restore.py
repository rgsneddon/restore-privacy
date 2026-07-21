"""Shipped Windows SFX frozen entry must include residual restore on Disconnect.

The product launches RestorePrivacy.exe (PyInstaller). Disconnect calls
``stop_full_tunnel`` from PYZ bytecode — pure ``client/*.py`` beside the freeze
is not enough unless the frozen module is patched. This test drives the real
catalog SFX artifact.
"""

from __future__ import annotations

import marshal
import subprocess
import sys
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


def _extract_sfx_member(sfx: Path, member: str, dest_dir: Path) -> Path:
    """Extract one member from the 7z SFX using system 7z."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["7z", "e", f"-o{dest_dir}", str(sfx), member, "-y"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"7z extract failed: {r.stderr or r.stdout}")
    name = Path(member).name
    out = dest_dir / name
    if not out.is_file():
        # 7z may preserve path
        hits = list(dest_dir.rglob(name))
        if not hits:
            raise FileNotFoundError(member)
        out = hits[0]
    return out


def _require_pyinstaller_reader():
    try:
        from PyInstaller.archive.readers import CArchiveReader  # noqa: WPS433
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest(f"PyInstaller not available: {exc}") from exc
    return CArchiveReader


class TestWindowsFrozenResidualRestore(unittest.TestCase):
    def test_catalog_sfx_frozen_stop_full_tunnel_restores_residual(self):
        """Catalog Windows SFX RestorePrivacy.exe PYZ has residual restore on stop."""
        if not SFX.is_file():
            self.skipTest(f"missing catalog SFX: {SFX}")
        if SFX.stat().st_size < 1_000_000:
            self.fail(f"SFX too small: {SFX.stat().st_size}")

        CArchiveReader = _require_pyinstaller_reader()
        with tempfile.TemporaryDirectory(prefix="rpt-win-frozen-") as td:
            tdp = Path(td)
            exe = _extract_sfx_member(SFX, "RestorePrivacy.exe", tdp)
            self.assertTrue(exe.is_file())
            reader = CArchiveReader(str(exe))
            self.assertIn("PYZ.pyz", reader.toc)
            pyz = reader.open_embedded_archive("PYZ.pyz")
            # Module key as stored in freeze
            try:
                tunnel_co = pyz.extract("client.windows.tunnel_win")
            except Exception:
                tunnel_co = pyz.extract("client/windows/tunnel_win")
            self.assertIn(
                "restore_windows_residual_path",
                tunnel_co.co_names,
                "frozen tunnel_win missing restore_windows_residual_path",
            )
            stop_co = None
            for c in tunnel_co.co_consts:
                if isinstance(c, type(tunnel_co)) and getattr(c, "co_name", "") == (
                    "stop_full_tunnel"
                ):
                    stop_co = c
                    break
            self.assertIsNotNone(stop_co, "stop_full_tunnel code object missing in freeze")
            self.assertIn(
                "restore_windows_residual_path",
                stop_co.co_names,
                "frozen stop_full_tunnel must call restore_windows_residual_path "
                "(Disconnect path)",
            )
            # Old bug: residual restore gated only on routes_were_on
            self.assertNotIn(
                "routes_were_on",
                stop_co.co_names,
                "frozen stop_full_tunnel still references routes_were_on gate",
            )

            # Entry bootstrap prefers pure sources (belt-and-suspenders)
            app_blob = reader.extract("app")
            app_co = marshal.loads(app_blob)
            consts = [c for c in (app_co.co_consts or ()) if isinstance(c, str)]
            joined = " ".join(consts).lower()
            self.assertTrue(
                "pure" in joined or "restore_windows_residual_path" in app_co.co_names,
                "frozen entry should prefer pure residual-restore sources",
            )


if __name__ == "__main__":
    unittest.main()
