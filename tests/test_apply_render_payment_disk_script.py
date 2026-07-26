"""Structural smoke: apply_render_payment_disk.ps1 is present and fail-closed without key."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_render_payment_disk.ps1"


class TestApplyRenderPaymentDiskScript(unittest.TestCase):
    def test_script_exists_and_documents_api_key(self):
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("RENDER_API_KEY", text)
        self.assertIn("RPT_PAYMENT_DATA_DIR", text)
        self.assertIn("/var/data/rpt-payment", text)
        self.assertIn("rpt-payment-data", text)
        self.assertIn("/var/data", text)
        self.assertIn("restore-privacy-status", text)
        # Correct Render disks API (not /services/{id}/disks which 404s)
        self.assertIn("https://api.render.com/v1/disks", text)
        self.assertIn("serviceId", text)

    def test_script_exits_nonzero_without_api_key(self):
        """Drive real PowerShell entry without secrets — must not claim success."""
        if sys.platform != "win32":
            self.skipTest("PowerShell apply script is Windows-oriented")
        env = dict(**{k: v for k, v in __import__("os").environ.items()})
        env.pop("RENDER_API_KEY", None)
        env.pop("RENDER_TOKEN", None)
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
            timeout=60,
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        combined = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("RENDER_API_KEY", combined)
        # Must not claim deploy success without a key
        self.assertNotIn("Deploy triggered", combined)

    def test_blueprint_still_matches_script_paths(self):
        yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("RPT_PAYMENT_DATA_DIR", yaml)
        self.assertIn("/var/data/rpt-payment", yaml)
        self.assertIn("mountPath: /var/data", yaml)
        self.assertIn("name: rpt-payment-data", yaml)


if __name__ == "__main__":
    unittest.main()
