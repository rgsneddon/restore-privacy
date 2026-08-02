"""Drive shipped cut_render_upstream artifacts (env + nginx one-liners)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "perc_chain" / "deploy"
SCRIPT = DEPLOY / "cut_render_upstream.sh"
DOC = DEPLOY / "CUT_RENDER_UPSTREAM.md"

# Shape of live Helsinki env (pre-cut) — must match operator reality.
LIVE_SHAPED_ENV = """\
# Restore Privacy Suite v1.0.1
# evolve-perc-internet.onrender.com is paused to save money.
PORT=9478
PERC_RENDEZVOUS_PORT=9478
PERC_BIND_HOST=127.0.0.1
PERC_DATA_DIR=/opt/restore-privacy/perc_chain/data
PERC_PUBLIC_ENDPOINT=https://135.181.152.10.sslip.io/perc
PERC_UPSTREAM_RENDEZVOUS_URL=https://evolve-perc-internet.onrender.com
PERC_SEED_USERNAME=evolve_seed_node
PERC_CHAIN_GENESIS_REVISION=2
NODE_ENV=production
"""

LIVE_SHAPED_NGINX = """\
# Restore Privacy Suite perc_chain (evolve-perc-internet paused — Helsinki default)
location = /perc {
    return 301 /perc/;
}
location /perc/ {
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_pass http://127.0.0.1:9478/;
}
"""


class TestCutRenderUpstream(unittest.TestCase):
    def test_shipped_artifacts_exist_and_target_live_paths(self) -> None:
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")
        self.assertTrue(DOC.is_file(), f"missing {DOC}")
        sh = SCRIPT.read_text(encoding="utf-8")
        md = DOC.read_text(encoding="utf-8")
        for blob in (sh, md):
            self.assertIn("/opt/restore-privacy/perc_chain/helsinki.env", blob)
            self.assertIn("rpt-perc-chain", blob)
            self.assertIn("/etc/nginx/snippets/rpt-perc-chain.conf", blob)
            self.assertIn("proxy_pass http://127.0.0.1:9478/", blob)
            self.assertIn("https://135.181.152.10.sslip.io/perc/health", blob)
            self.assertIn("PERC_UPSTREAM_RENDEZVOUS_URL", blob)
            self.assertIn("evolve-perc-internet.onrender.com", blob)
        # Doc must document client Helsinki rendezvous + re-deploy residual
        self.assertIn("rendezvousUrl", md)
        self.assertIn("deploy_perc_chain_helsinki.py", md)
        self.assertIn("restore-privacy-status", md)
        # Runnable SSH one-liners, not prose-only
        self.assertIn(
            "ssh -i ~/.ssh/id_ed25519_restore_privacy_eu root@135.181.152.10",
            md,
        )
        self.assertIn("systemctl restart rpt-perc-chain", md)
        self.assertIn("nginx -t", md)
        # Script must force explicit disable (none), not merely drop the key
        self.assertIn("PERC_UPSTREAM_RENDEZVOUS_URL=none", sh)
        self.assertIn("grep -vE", sh)
        # Node must not hard-default to paid Render
        node = (ROOT / "perc_chain" / "src" / "internet_node.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("isDisabledUpstream", node)
        self.assertNotIn(
            "return 'https://evolve-perc-internet.onrender.com'",
            node,
        )

    def test_script_cuts_upstream_on_live_shaped_env(self) -> None:
        """Run the real shipped script against temp files (no host systemctl)."""
        self.assertTrue(SCRIPT.is_file())
        with tempfile.TemporaryDirectory(prefix="rpt-cut-render-") as tmp:
            t = Path(tmp)
            env_path = t / "helsinki.env"
            snip_path = t / "rpt-perc-chain.conf"
            nginx_root = t / "nginx"
            nginx_root.mkdir()
            env_path.write_text(LIVE_SHAPED_ENV, encoding="utf-8")
            snip_path.write_text(LIVE_SHAPED_NGINX, encoding="utf-8")
            # Precondition: umbilical present
            self.assertIn(
                "https://evolve-perc-internet.onrender.com",
                env_path.read_text(encoding="utf-8"),
            )
            env = os.environ.copy()
            env.update(
                {
                    "RPT_PERC_ENV": str(env_path),
                    "RPT_NGINX_SNIP": str(snip_path),
                    "RPT_NGINX_ROOT": str(nginx_root),
                    "RPT_CUT_RENDER_SKIP_SERVICE": "1",
                }
            )
            proc = subprocess.run(
                ["bash", str(SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}",
            )
            self.assertIn("CUT_RENDER_UPSTREAM_DONE", proc.stdout)
            after = env_path.read_text(encoding="utf-8")
            self.assertIn("PERC_UPSTREAM_RENDEZVOUS_URL=none", after)
            self.assertNotRegex(after, r"https?://\S*onrender\.com")
            for line in after.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                self.assertNotIn("onrender.com", stripped, msg=line)
                if stripped.startswith("PERC_UPSTREAM_RENDEZVOUS_URL="):
                    self.assertEqual(stripped, "PERC_UPSTREAM_RENDEZVOUS_URL=none")
            # Required keys preserved
            self.assertIn("PORT=9478", after)
            self.assertIn(
                "PERC_PUBLIC_ENDPOINT=https://135.181.152.10.sslip.io/perc",
                after,
            )
            self.assertIn(
                "PERC_DATA_DIR=/opt/restore-privacy/perc_chain/data",
                after,
            )
            self.assertIn("PERC_SEED_USERNAME=evolve_seed_node", after)
            # Backup created next to env
            backups = list(t.glob("helsinki.env.bak.*"))
            self.assertTrue(backups, "expected helsinki.env.bak.* backup")
            # nginx snippet still local-only
            snip = snip_path.read_text(encoding="utf-8")
            self.assertIn("proxy_pass http://127.0.0.1:9478/", snip)

    def test_script_fails_if_nginx_has_live_onrender_url(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rpt-cut-nginx-") as tmp:
            t = Path(tmp)
            env_path = t / "helsinki.env"
            snip_path = t / "rpt-perc-chain.conf"
            nginx_root = t / "nginx"
            nginx_root.mkdir()
            bad = nginx_root / "evil.conf"
            bad.write_text(
                "proxy_pass https://evolve-perc-internet.onrender.com;\n",
                encoding="utf-8",
            )
            env_path.write_text(LIVE_SHAPED_ENV, encoding="utf-8")
            snip_path.write_text(LIVE_SHAPED_NGINX, encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "RPT_PERC_ENV": str(env_path),
                    "RPT_NGINX_SNIP": str(snip_path),
                    "RPT_NGINX_ROOT": str(nginx_root),
                    "RPT_CUT_RENDER_SKIP_SERVICE": "1",
                }
            )
            proc = subprocess.run(
                ["bash", str(SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("onrender", (proc.stdout + proc.stderr).lower())


if __name__ == "__main__":
    unittest.main()
