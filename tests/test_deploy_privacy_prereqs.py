"""Deploy path must ship full privacy prerequisite set (0.2.3+)."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_deploy():
    path = ROOT / "scripts" / "deploy_rpt_node.py"
    spec = importlib.util.spec_from_file_location("deploy_rpt_node", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid running main; loader still executes module body (imports paramiko)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        # paramiko missing would SystemExit(2) — re-raise as skip-like fail
        raise
    return mod


class TestDeployPrivacyPrereqs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.deploy = _load_deploy()
        except SystemExit as exc:
            raise unittest.SkipTest(f"deploy module failed to load: {exc}") from exc
        except ImportError as exc:
            raise unittest.SkipTest(f"paramiko required for deploy tests: {exc}") from exc

    def test_node_extra_includes_fde_and_wipe(self):
        extra = set(self.deploy.NODE_EXTRA)
        for name in (
            "install.sh",
            "install_dns.sh",
            "install_host_privacy.sh",
            "install_disk_encryption.sh",
            "install_zram_luks.sh",
            "install_shutdown_wipe.sh",
            "rpt_shutdown_wipe.sh",
            "unbound-rpt.conf",
        ):
            self.assertIn(name, extra, f"NODE_EXTRA missing {name}")
            self.assertTrue(
                (ROOT / "node" / name).is_file(), f"local node/{name} missing"
            )

    def test_privacy_py_modules_listed_and_present(self):
        for name in self.deploy.NODE_PRIVACY_PY:
            self.assertTrue(
                (ROOT / "node" / name).is_file(), f"missing node/{name}"
            )
        # Must include nolog + wire + aggregate + disk encryption
        names = set(self.deploy.NODE_PRIVACY_PY)
        for req in (
            "nolog.py",
            "obfuscation.py",
            "traffic_shape.py",
            "pfs.py",
            "aggregate_metrics.py",
            "disk_encryption.py",
            "server.py",
        ):
            self.assertIn(req, names)

    def test_deploy_source_wires_host_privacy_and_wipe(self):
        src = (ROOT / "scripts" / "deploy_rpt_node.py").read_text(encoding="utf-8")
        self.assertIn("install_host_privacy.sh", src)
        self.assertIn("install_dns.sh", src)
        self.assertIn("install_disk_encryption.sh", src)
        self.assertIn("install_zram_luks.sh", src)
        self.assertIn("install_shutdown_wipe.sh", src)
        self.assertIn("rpt_shutdown_wipe.sh", src)
        self.assertIn("status_title_only", src)
        self.assertIn("nolog_unit", src)
        # Does not enable log sinks
        self.assertNotIn("StandardOutput=journal", src)
        self.assertNotIn("connection_log=True", src)

    def test_host_privacy_still_composes_fde_wipe(self):
        host = (ROOT / "node" / "install_host_privacy.sh").read_text(encoding="utf-8")
        self.assertIn("install_disk_encryption.sh", host)
        self.assertIn("install_zram_luks.sh", host)
        self.assertIn("install_shutdown_wipe.sh", host)

    def test_nolog_flags_still_false(self):
        from node.nolog import NO_LOG_POLICY, apply_no_log_policy

        self.assertFalse(NO_LOG_POLICY["connection_log"])
        self.assertFalse(NO_LOG_POLICY["session_log"])
        self.assertFalse(NO_LOG_POLICY["user_info_log"])
        out = apply_no_log_policy({})
        self.assertFalse(out["connection_log"])


class TestDeployAstLists(unittest.TestCase):
    """Parse NODE_EXTRA from source without importing paramiko if needed."""

    def test_ast_node_extra_complete(self):
        src = (ROOT / "scripts" / "deploy_rpt_node.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        found = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "NODE_EXTRA":
                        found = ast.literal_eval(node.value)
        self.assertIsNotNone(found)
        for name in (
            "install_disk_encryption.sh",
            "install_zram_luks.sh",
            "install_shutdown_wipe.sh",
            "rpt_shutdown_wipe.sh",
        ):
            self.assertIn(name, found)


if __name__ == "__main__":
    unittest.main()
