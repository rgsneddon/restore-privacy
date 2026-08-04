"""Refuse Windows residual carry-forward PE that still freezes 0.5.8."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from host_paid_assets_vps import assert_windows_setup_matches_monopin  # noqa: E402


class TestWindowsSetupMonopinGate(unittest.TestCase):
    def test_rejects_size_of_historical_carry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "restore-privacy-client-1.1.7-windows-x64-setup.exe"
            # Exact historical CF size that kept replacing paid 1.1.x
            p.write_bytes(b"x" * 38_631_642)
            with self.assertRaises(RuntimeError) as ctx:
                assert_windows_setup_matches_monopin(p, "1.1.7")
            self.assertIn("0.5.8 carry-forward", str(ctx.exception))

    def test_rejects_embedded_0_5_8_when_monopin_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "setup.exe"
            # Large enough to avoid size gate; embeds stale pin only
            body = b"header\x00" + b"0.5.8" + b"\x00trailer" + (b"z" * 1000)
            p.write_bytes(body)
            with self.assertRaises(RuntimeError) as ctx:
                assert_windows_setup_matches_monopin(p, "1.1.7")
            self.assertIn("0.5.8", str(ctx.exception))

    def test_accepts_native_monopin_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "setup.exe"
            p.write_bytes(b"Restore Privacy monopin 1.1.7 residual seal\n" + b"q" * 2000)
            assert_windows_setup_matches_monopin(p, "1.1.7")

    def test_local_release_1_1_7_when_present(self) -> None:
        rel = (
            ROOT
            / "releases"
            / "1.1.7"
            / "restore-privacy-client-1.1.7-windows-x64-setup.exe"
        )
        if not rel.is_file():
            self.skipTest("local 1.1.7 setup not built in this workspace")
        assert_windows_setup_matches_monopin(rel, "1.1.7")
        data = rel.read_bytes()
        self.assertNotIn(b"0.5.8", data)
        self.assertIn(b"1.1.7", data)


if __name__ == "__main__":
    unittest.main()
