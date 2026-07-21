"""Node LUKS2 + zram ram-only volume planners (node-only; not client)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.disk_encryption import (  # noqa: E402
    HONESTY_NODE_ONLY,
    HONESTY_ZRAM_LUKS,
    is_safe_format_device,
    plan_zram_luks2_volume,
    zram_luks2_commands_dry_run,
    zram_luks_docs_markers,
    zram_setup_commands_dry_run,
)


class TestZramLuks2Plan(unittest.TestCase):
    def test_dry_run_sequence_mentions_zram_and_luks2(self):
        cmds = zram_luks2_commands_dry_run(size_mib=256)
        blob = "\n".join(cmds)
        self.assertIn("zram", blob.lower())
        self.assertIn("luks2", blob.lower())
        self.assertIn("cryptsetup luksFormat", blob)
        self.assertIn("/dev/zram0", blob)
        self.assertIn("modprobe zram", blob)

    def test_plan_is_node_only_and_confirm_gated(self):
        plan = plan_zram_luks2_volume(size_mib=512)
        self.assertTrue(plan["node_only"])
        self.assertFalse(plan["client_encryption"])
        self.assertEqual(plan["luks_type"], "luks2")
        self.assertEqual(plan["confirm_env"], "RPT_ZRAM_LUKS_CONFIRM")
        self.assertEqual(plan["confirm_required"], "yes")
        self.assertTrue(plan["safe_device"])
        self.assertIn("luksFormat", "\n".join(plan["commands_dry_run"]))
        self.assertIn("node-only", plan["honesty_node_only"].lower().replace(" ", "-") or "node")
        self.assertIn("node", plan["honesty_node_only"].lower())
        self.assertIn("not", plan["honesty_node_only"].lower())
        self.assertIn("client", plan["honesty_node_only"].lower())
        self.assertIn("RAM", plan["honesty_zram_luks"] or HONESTY_ZRAM_LUKS)

    def test_rejects_root_disk_names(self):
        self.assertFalse(is_safe_format_device("/dev/sda"))
        self.assertFalse(is_safe_format_device("/dev/vda"))
        self.assertFalse(is_safe_format_device("not-a-dev"))
        self.assertTrue(is_safe_format_device("/dev/zram0"))
        self.assertTrue(is_safe_format_device("/dev/sdb1"))

    def test_unsafe_zram_device_raises(self):
        with self.assertRaises(ValueError):
            zram_setup_commands_dry_run(zram_device="/dev/sda")

    def test_install_script_modes(self):
        p = ROOT / "node" / "install_zram_luks.sh"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        for needle in (
            "luks2",
            "zram",
            "RPT_ZRAM_LUKS_CONFIRM",
            "check",
            "dry-run",
            "format",
            "node host only",
            "Clients do NOT",
        ):
            self.assertIn(needle, text)

    def test_host_privacy_and_selfhost_wire(self):
        host = (ROOT / "node" / "install_host_privacy.sh").read_text(encoding="utf-8")
        self.assertIn("install_zram_luks.sh", host)
        selfhost = (ROOT / "scripts" / "selfhost_node.sh").read_text(encoding="utf-8")
        self.assertIn("install_zram_luks.sh", selfhost)
        self.assertIn("RPT_ZRAM_LUKS_CONFIRM", selfhost)
        deploy = (ROOT / "scripts" / "deploy_rpt_node.py").read_text(encoding="utf-8")
        self.assertIn("install_zram_luks.sh", deploy)
        self.assertIn("zram_luks_script=ok", deploy)

    def test_docs_markers(self):
        m = zram_luks_docs_markers()
        self.assertEqual(m["luks2"], "luks2")
        self.assertIn("zram", m["zram"])


class TestClientNoLuksRequirement(unittest.TestCase):
    def test_client_apps_do_not_require_luks(self):
        for rel in (
            "client/windows/app.py",
            "client/linux/app.py",
            "client_app/lib/main.dart",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("install_zram_luks", src)
            self.assertNotIn("cryptsetup luksFormat", src)
            # Connect still residual
            self.assertTrue(
                "assert_may_connect" in src or "assertMayConnect" in src
            )


if __name__ == "__main__":
    unittest.main()
