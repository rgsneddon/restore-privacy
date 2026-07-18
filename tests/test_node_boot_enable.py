"""Node must auto-start after VPS reboot: systemd enable + restart policy in install recipe."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INSTALL = ROOT / "node" / "install.sh"
DEPLOY = ROOT / "scripts" / "deploy_rpt_node.py"


class TestInstallSystemdBootEnable(unittest.TestCase):
    def test_install_sh_exists(self):
        self.assertTrue(INSTALL.is_file(), "node/install.sh missing")

    def test_unit_wanted_by_multi_user(self):
        src = INSTALL.read_text(encoding="utf-8")
        self.assertIn("[Install]", src)
        self.assertIn("WantedBy=multi-user.target", src)

    def test_unit_after_network_online(self):
        src = INSTALL.read_text(encoding="utf-8")
        self.assertIn("After=network-online.target", src)
        self.assertIn("Wants=network-online.target", src)

    def test_restart_always_or_on_failure(self):
        src = INSTALL.read_text(encoding="utf-8")
        # Prefer always so crash + unexpected exit recover; on-failure alone is weaker
        self.assertRegex(src, r"Restart=(always|on-failure)")
        self.assertIn("RestartSec=", src)

    def test_systemctl_enable_on_install(self):
        src = INSTALL.read_text(encoding="utf-8")
        self.assertIn('systemctl enable "${SERVICE_NAME}.service"', src)
        # Must fail install if not enabled (prevents silent "running now, dead after reboot")
        self.assertIn("is-enabled", src)
        self.assertIn("not enabled for boot", src)

    def test_service_name_rpt_node(self):
        src = INSTALL.read_text(encoding="utf-8")
        self.assertIn('SERVICE_NAME="rpt-node"', src)
        self.assertIn("ExecStart=", src)
        self.assertIn("node.server", src)

    def test_deploy_checks_enabled(self):
        src = DEPLOY.read_text(encoding="utf-8")
        self.assertIn("systemctl enable rpt-node.service", src)
        self.assertIn("is-enabled rpt-node.service", src)


if __name__ == "__main__":
    unittest.main()
