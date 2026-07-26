"""Browser extension MV3: structure + shipped vpn_core enable/disable via Node.

Drives browser_extension/lib/vpn_core.js (and proxy_adapter) through the
real Node test runner — not a re-implementation of Connect routing.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "browser_extension"


class TestBrowserExtensionStructure(unittest.TestCase):
    def test_mv3_manifest_connect_disconnect_and_proxy(self) -> None:
        manifest_path = EXT / "manifest.json"
        self.assertTrue(manifest_path.is_file(), "manifest.json missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("manifest_version"), 3)
        self.assertEqual(manifest.get("version"), "0.4.8")
        self.assertIn("proxy", manifest.get("permissions", []))
        self.assertIn("storage", manifest.get("permissions", []))
        bg = manifest.get("background") or {}
        self.assertIn("service_worker", bg)
        self.assertTrue((EXT / bg["service_worker"]).is_file())
        action = manifest.get("action") or {}
        self.assertIn("default_popup", action)
        popup = (EXT / action["default_popup"]).read_text(encoding="utf-8")
        self.assertIn("Connect", popup)
        self.assertIn("Disconnect", popup)
        self.assertIn('id="btn-connect"', popup)
        self.assertIn('id="btn-disconnect"', popup)
        # Honest browser-scope (not OS residual TUN claim as the product residual)
        popup_js = (EXT / "popup.js").read_text(encoding="utf-8")
        readme = (EXT / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("browser", readme)
        self.assertTrue(
            "not os residual" in readme
            or "does not create" in readme
            or "browser-scoped" in readme
            or "browser only" in readme
        )
        # Core modules present
        self.assertTrue((EXT / "lib" / "vpn_core.js").is_file())
        self.assertTrue((EXT / "lib" / "proxy_adapter.js").is_file())
        self.assertTrue((EXT / "background.js").is_file())
        # No false system residual claim in popup chrome title path
        self.assertNotIn("system residual TUN", popup_js.lower())


class TestBrowserExtensionCoreViaNode(unittest.TestCase):
    def test_shipped_node_suite_passes(self) -> None:
        runner = EXT / "test" / "vpn_core.test.js"
        self.assertTrue(runner.is_file())
        proc = subprocess.run(
            ["node", str(runner)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(
            proc.returncode,
            0,
            f"node suite failed:\n{out}",
        )
        self.assertIn("ALL PASS", out)
        self.assertIn("enableVpn sets connected", out)
        self.assertIn("disableVpn clears proxy", out)

    def test_enable_disable_via_node_eval_shipped_module(self) -> None:
        """Direct require of shipped vpn_core.js — enable applies, disable clears."""
        script = r"""
const core = require('./browser_extension/lib/vpn_core.js');
const on = core.enableVpn(null, {host:'127.0.0.1', port:1080, scheme:'socks5'});
if (on.status !== 'connected') process.exit(2);
if (!on.proxyConfig || on.proxyConfig.mode !== 'fixed_servers') process.exit(3);
if (on.proxyConfig.rules.singleProxy.port !== 1080) process.exit(4);
const off = core.disableVpn(on);
if (off.status !== 'disconnected') process.exit(5);
if (off.proxyConfig !== null) process.exit(6);
if (core.isConnected(off)) process.exit(7);
console.log(JSON.stringify({
  enabled_status: on.status,
  enabled_mode: on.proxyConfig.mode,
  disabled_status: off.status,
  disabled_proxy: off.proxyConfig,
  disclaimer_browser: core.browserScopeDisclaimer().toLowerCase().includes('browser'),
}));
"""
        proc = subprocess.run(
            ["node", "-e", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(data["enabled_status"], "connected")
        self.assertEqual(data["enabled_mode"], "fixed_servers")
        self.assertEqual(data["disabled_status"], "disconnected")
        self.assertIsNone(data["disabled_proxy"])
        self.assertTrue(data["disclaimer_browser"])


if __name__ == "__main__":
    unittest.main()
