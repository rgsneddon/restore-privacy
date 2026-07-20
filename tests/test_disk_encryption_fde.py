"""LUKS/dm-crypt FDE helpers + shutdown wipe plan + no-log composition."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.disk_encryption import (  # noqa: E402
    AGGRESSIVE_SECRETS_RELATIVE,
    HONESTY_AT_REST,
    HONESTY_NOLOG,
    HONESTY_WIPE,
    cryptsetup_check_commands,
    filter_wipe_targets,
    is_safe_wipe_path,
    luks_cryptsetup_commands_dry_run,
    plan_wipe,
    runtime_wipe_targets,
)
from node.nolog import NO_LOG_POLICY, apply_no_log_policy  # noqa: E402


class TestWipeSafety(unittest.TestCase):
    def test_rejects_root_and_system(self):
        self.assertFalse(is_safe_wipe_path("/"))
        self.assertFalse(is_safe_wipe_path("/etc/passwd"))
        self.assertFalse(is_safe_wipe_path("/boot/vmlinuz"))
        self.assertFalse(is_safe_wipe_path("/opt/restore-privacy"))  # entire root

    def test_allows_install_subtree_and_runtime(self):
        self.assertTrue(
            is_safe_wipe_path("/opt/restore-privacy/secrets/node_elgamal.priv")
        )
        self.assertTrue(is_safe_wipe_path("/run/rpt-node.ready"))
        self.assertTrue(is_safe_wipe_path("/tmp/rpt-node.tmp"))

    def test_filter_wipe_targets(self):
        candidates = [
            "/",
            "/etc/shadow",
            "/opt/restore-privacy/run/rpt-node.ready",
            "/run/rpt-node.ready",
            "/tmp/evil",
        ]
        out = filter_wipe_targets(candidates)
        self.assertNotIn("/", out)
        self.assertNotIn("/etc/shadow", out)
        self.assertNotIn("/tmp/evil", out)
        self.assertTrue(any("rpt-node.ready" in p for p in out))

    def test_plan_wipe_default_no_secrets(self):
        plan = plan_wipe(install_root="/opt/restore-privacy", aggressive_secrets=False)
        self.assertFalse(plan["aggressive_secrets"])
        joined = " ".join(plan["targets"])
        self.assertNotIn("node_elgamal.priv", joined)
        self.assertTrue(any("rpt-node.ready" in t for t in plan["targets"]))
        for t in plan["targets"]:
            self.assertTrue(is_safe_wipe_path(t), t)
        self.assertIn("best-effort", plan["honesty_wipe"].lower())

    def test_plan_wipe_aggressive_includes_priv(self):
        plan = plan_wipe(install_root="/opt/restore-privacy", aggressive_secrets=True)
        joined = " ".join(plan["targets"])
        self.assertIn("node_elgamal.priv", joined)
        for rel in AGGRESSIVE_SECRETS_RELATIVE:
            self.assertTrue(any(rel.split("/")[-1] in t for t in plan["targets"]))

    def test_runtime_wipe_idempotent_shape(self):
        a = runtime_wipe_targets()
        b = runtime_wipe_targets()
        self.assertEqual(a, b)
        self.assertGreaterEqual(len(a), 1)


class TestLuksHelpers(unittest.TestCase):
    def test_dry_run_commands_mention_luks_and_dmcrypt(self):
        cmds = luks_cryptsetup_commands_dry_run("/dev/vdb1")
        blob = "\n".join(cmds)
        self.assertIn("cryptsetup", blob)
        self.assertIn("luksFormat", blob)
        self.assertIn("luks2", blob)
        self.assertIn("open", blob)
        self.assertIn("/dev/mapper/", blob)
        with self.assertRaises(ValueError):
            luks_cryptsetup_commands_dry_run("not-a-dev")

    def test_cryptsetup_check_commands(self):
        cmds = cryptsetup_check_commands()
        self.assertTrue(any("cryptsetup" in c for c in cmds))
        self.assertTrue(any("dm_crypt" in c or "dm-crypt" in c for c in cmds))

    def test_honesty_strings(self):
        self.assertIn("at rest", HONESTY_AT_REST.lower())
        self.assertIn("LUKS", HONESTY_AT_REST)
        self.assertIn("dm-crypt", HONESTY_AT_REST.lower() + " dm-crypt")
        # HONESTY_AT_REST says LUKS/dm-crypt
        self.assertIn("dm-crypt", HONESTY_AT_REST)
        self.assertIn("provider", HONESTY_WIPE.lower())
        self.assertIn("no-log", HONESTY_NOLOG.lower())


class TestScriptsStructural(unittest.TestCase):
    def test_install_disk_encryption_script(self):
        p = ROOT / "node" / "install_disk_encryption.sh"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("LUKS", text)
        self.assertIn("dm-crypt", text)
        self.assertIn("cryptsetup", text)
        self.assertIn("luksFormat", text)
        self.assertIn("RPT_LUKS_CONFIRM", text)
        self.assertTrue(
            "no-log" in text.lower() or "nolog" in text.lower() or "no logs" in text.lower()
        )
        self.assertIn("provider", text.lower())
        self.assertIn("dry-run", text)
        self.assertIn("check", text)

    def test_wipe_scripts_and_systemd_wiring(self):
        wipe = (ROOT / "node" / "rpt_shutdown_wipe.sh").read_text(encoding="utf-8")
        inst = (ROOT / "node" / "install_shutdown_wipe.sh").read_text(encoding="utf-8")
        self.assertIn("shred", wipe)
        self.assertIn("drop_caches", wipe)
        self.assertIn("RPT_WIPE_SECRETS_ON_SHUTDOWN", wipe)
        self.assertIn("ExecStop", inst)
        self.assertIn("shutdown", inst.lower())
        self.assertIn("rpt-node-shutdown-wipe.service", inst)
        self.assertIn("rpt_shutdown_wipe.sh", inst)
        # Must not enable log sinks
        for text in (wipe, inst):
            self.assertNotIn("StandardOutput=journal", text)
            self.assertNotIn("connection_log=true", text.lower())

    def test_host_privacy_composes_fde_and_wipe(self):
        host = (ROOT / "node" / "install_host_privacy.sh").read_text(encoding="utf-8")
        self.assertIn("install_disk_encryption.sh", host)
        self.assertIn("install_shutdown_wipe.sh", host)
        self.assertIn("LUKS", host)
        self.assertTrue("nolog" in host.lower() or "no-log" in host.lower())

    def test_selfhost_mentions_luks(self):
        text = (ROOT / "scripts" / "selfhost_node.sh").read_text(encoding="utf-8")
        self.assertIn("LUKS", text)
        self.assertIn("install_disk_encryption.sh", text)
        self.assertIn("install_shutdown_wipe.sh", text)

    def test_install_sh_copies_shell_helpers(self):
        text = (ROOT / "node" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("*.sh", text)
        self.assertIn("StandardOutput=null", text)


class TestNologStillOff(unittest.TestCase):
    def test_nolog_flags_false_with_fde_module(self):
        self.assertFalse(NO_LOG_POLICY["connection_log"])
        self.assertFalse(NO_LOG_POLICY["session_log"])
        self.assertFalse(NO_LOG_POLICY["user_info_log"])
        self.assertFalse(NO_LOG_POLICY["traffic_log"])
        out = apply_no_log_policy({})
        self.assertFalse(out["connection_log"])
        self.assertFalse(out["session_log"])
        # disk_encryption must not flip policy
        from node import disk_encryption as de

        self.assertIn("no-log", de.HONESTY_NOLOG.lower())


if __name__ == "__main__":
    unittest.main()
