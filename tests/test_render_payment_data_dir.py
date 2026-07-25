"""Render durable payment path: blueprint + env-driven db_path helpers."""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestRenderPaymentDiskBlueprint(unittest.TestCase):
    def test_render_yaml_declares_disk_and_payment_data_dir(self):
        text = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("RPT_PAYMENT_DATA_DIR", text)
        self.assertIn("/var/data/rpt-payment", text)
        self.assertIn("mountPath", text)
        self.assertIn("/var/data", text)
        self.assertIn("rpt-payment-data", text)
        self.assertIn("sizeGB", text)
        # Free cannot attach disks — blueprint must not pin free for this disk setup
        # (allow comment mentions of free)
        plan_lines = [
            ln.strip()
            for ln in text.splitlines()
            if re.match(r"^\s*plan:\s*", ln)
        ]
        self.assertTrue(plan_lines, "expected plan: in render.yaml")
        self.assertTrue(
            any("starter" in ln or "standard" in ln or "pro" in ln for ln in plan_lines),
            f"persistent disk needs paid plan, got {plan_lines}",
        )
        # Disk block present
        self.assertRegex(text, r"disk:\s*\n\s+name:\s*rpt-payment-data")


class TestPaymentDataDirEnv(unittest.TestCase):
    def test_env_override_places_db_under_configured_dir(self):
        import payments

        with tempfile.TemporaryDirectory() as td:
            durable = Path(td) / "rpt-payment"
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = str(durable)
            try:
                d = payments.payment_data_dir()
                self.assertEqual(d.resolve(), durable.resolve())
                db = payments.db_path()
                self.assertEqual(db.parent.resolve(), durable.resolve())
                self.assertEqual(db.name, payments.PAYMENT_DB_FILENAME)
                # Real store open under durable path
                payments.init_db()
                self.assertTrue(db.is_file())
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

    def test_resolve_payment_data_dir_pure_env(self):
        import payments

        custom = payments.resolve_payment_data_dir(
            {"RPT_PAYMENT_DATA_DIR": "/var/data/rpt-payment"}
        )
        self.assertEqual(custom.as_posix(), "/var/data/rpt-payment")
        default = payments.resolve_payment_data_dir({})
        self.assertTrue(str(default).endswith("status_page") or "data" in str(default))
        self.assertEqual(default.name, "data")

    def test_payment_store_paths_document_render_mount(self):
        import payments

        paths = payments.payment_store_paths()
        self.assertEqual(paths["render_disk_mount"], payments.RENDER_PAYMENT_DISK_MOUNT)
        self.assertEqual(paths["render_data_dir"], payments.RENDER_PAYMENT_DATA_DIR)
        self.assertEqual(paths["env_override"], "RPT_PAYMENT_DATA_DIR")

    def test_admin_mentions_render_disk_path(self):
        import admin_panel

        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            try:
                html = admin_panel.render_admin_html(grants=[]).decode("utf-8")
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev
        self.assertIn("RPT_PAYMENT_DATA_DIR", html)
        self.assertIn("/var/data/rpt-payment", html)
        self.assertIn("rpt-payment-data", html)


if __name__ == "__main__":
    unittest.main()
