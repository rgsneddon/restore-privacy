"""Docs + helpers for RPT_CAPACITY_TOKEN enable path (no real secrets)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.capacity_probe import probe_peer_capacity_map  # noqa: E402
from node.private_capacity import authorize_capacity_request  # noqa: E402


class TestCapacityTokenHelpers(unittest.TestCase):
    def test_authorize_requires_token(self):
        ok, msg = authorize_capacity_request(
            authorization_header="Bearer x",
            env={},
        )
        self.assertFalse(ok)
        ok2, _ = authorize_capacity_request(
            authorization_header="Bearer secret-token-value",
            env={"RPT_CAPACITY_TOKEN": "secret-token-value"},
        )
        self.assertTrue(ok2)

    def test_probe_empty_without_token(self):
        m = probe_peer_capacity_map(env={}, catalog_hosts=["82.221.101.241"])
        self.assertEqual(m, {})


class TestCapacityTokenDocs(unittest.TestCase):
    def test_operator_docs_mention_token_and_privacy(self):
        files = [
            ROOT / "README.md",
            ROOT / "scripts" / "hop_env.example",
            ROOT / "docs" / "CAPACITY_PROBES.md",
            ROOT / "docs" / "NODE_WIPE_REINSTALL.md",
            ROOT / "scripts" / "MULTIHOP_EXIT_HOP_PREP.md",
            ROOT / "scripts" / "install_capacity_token_env.sh",
        ]
        for p in files:
            self.assertTrue(p.is_file(), f"missing {p}")
            text = p.read_text(encoding="utf-8")
            self.assertIn("RPT_CAPACITY_TOKEN", text, f"{p.name} missing token")
            # No committed real-looking 48-char hex secrets in docs
            # (generated tokens are openssl rand -hex 24 → 48 hex chars)
            if p.suffix in (".md", ".example"):
                # Placeholder language
                low = text.lower()
                self.assertTrue(
                    "private" in low or "title-only" in low or "no live client" in low
                    or "not publish" in low or "do not commit" in low,
                    f"{p.name} should state private/no-public-count honesty",
                )

    def test_docs_list_optional_probe_keys(self):
        cap = (ROOT / "docs" / "CAPACITY_PROBES.md").read_text(encoding="utf-8")
        for key in (
            "RPT_CAPACITY_TOKEN",
            "RPT_CAPACITY_PROBE_URLS",
            "RPT_CAPACITY_PROBE_TIMEOUT",
            "RPT_NODE_MAX_SESSIONS",
            "RPT_NODE_BANDWIDTH_CAP_BPS",
            "RPT_BANDWIDTH_CAP_BPS_MAP",
        ):
            self.assertIn(key, cap)
        self.assertIn("title-only", cap.lower().replace("title only", "title-only") or cap.lower())
        # Accept either phrasing
        self.assertTrue(
            "title-only" in cap.lower() or "title only" in cap.lower()
            or "no live client" in cap.lower()
        )

    def test_hop_env_example_has_placeholder_not_live_secret(self):
        text = (ROOT / "scripts" / "hop_env.example").read_text(encoding="utf-8")
        self.assertIn("RPT_CAPACITY_TOKEN", text)
        self.assertIn("replace-with-long-random-secret", text)
        # Must not look like a committed production token assignment with hex
        for line in text.splitlines():
            if line.strip().startswith("RPT_CAPACITY_TOKEN=") and not line.strip().startswith("#"):
                val = line.split("=", 1)[1].strip()
                self.assertFalse(
                    bool(re.fullmatch(r"[0-9a-fA-F]{32,}", val)),
                    "hop_env.example must not commit a real hex token",
                )

    def test_install_script_writes_env_file_not_repo(self):
        src = (ROOT / "scripts" / "install_capacity_token_env.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("capacity.env", src)
        self.assertIn("/etc/restore-privacy", src)
        self.assertIn("EnvironmentFile", src)
        self.assertIn("do not commit", src.lower())
        self.assertIn("RPT_NODE_BANDWIDTH_CAP_BPS", src)
        self.assertIn("RPT_NODE_MAX_SESSIONS", src)

    def test_render_blueprint_has_capacity_env_placeholders(self):
        text = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("RPT_CAPACITY_TOKEN", text)
        self.assertIn("RPT_BANDWIDTH_CAP_BPS_MAP", text)
        # Token must be dashboard-only (sync: false), not a committed secret value
        # Find the RPT_CAPACITY_TOKEN block and ensure sync: false nearby
        idx = text.index("RPT_CAPACITY_TOKEN")
        window = text[idx : idx + 80]
        self.assertIn("sync: false", window)

    def test_ro_mac_finalize_handoff_is_committed_and_secret_free(self):
        """RO operator handoff for Mac SSH: host, unlimited-class bw, sessions 256, no live token."""
        handoff = ROOT / "docs" / "RO_CAPACITY_MAC_FINALIZE.md"
        self.assertTrue(handoff.is_file(), "missing docs/RO_CAPACITY_MAC_FINALIZE.md")
        text = handoff.read_text(encoding="utf-8")
        self.assertIn("185.146.232.107", text)
        # Product: RO unlimited-class bandwidth (extendable at cost) — not fixed 100 Mbps
        self.assertIn("unlimited-class", text.lower())
        self.assertIn("RPT_NODE_MAX_SESSIONS=256", text)
        self.assertNotIn("RPT_NODE_BANDWIDTH_CAP_BPS=100000000", text)
        self.assertNotIn("**100 Mbps**", text)
        self.assertIn("RPT_CAPACITY_TOKEN", text)
        self.assertIn("install_capacity_token_env.sh", text)
        self.assertIn("capacity_token.txt", text)
        self.assertIn("/api/private/capacity", text)
        self.assertIn("do not commit", text.lower())
        # Align with product maps (private_capacity / CAPACITY_PROBES)
        from node.private_capacity import (
            product_bandwidth_unlimited,
            product_session_soft_max,
        )

        self.assertTrue(product_bandwidth_unlimited(code="RO"))
        self.assertTrue(product_bandwidth_unlimited(code="IS"))
        self.assertEqual(product_session_soft_max(code="RO"), 256)
        self.assertGreater(product_session_soft_max(code="IS") or 0, 256)
        # Discoverable from primary capacity doc
        cap = (ROOT / "docs" / "CAPACITY_PROBES.md").read_text(encoding="utf-8")
        self.assertIn("RO_CAPACITY_MAC_FINALIZE.md", cap)
        self.assertIn("unlimited-class", cap.lower())
        wipe = (ROOT / "docs" / "NODE_WIPE_REINSTALL.md").read_text(encoding="utf-8")
        self.assertIn("RO_CAPACITY_MAC_FINALIZE.md", wipe)
        # No live 32+ hex token assignment in handoff (placeholders / env expansion only)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Reject RPT_CAPACITY_TOKEN=<long hex> as a real secret commit
            m = re.search(
                r"RPT_CAPACITY_TOKEN\s*=\s*['\"]?([0-9a-fA-F]{32,})['\"]?",
                stripped,
            )
            self.assertIsNone(
                m,
                f"RO handoff must not embed a live hex token: {stripped[:60]!r}",
            )


if __name__ == "__main__":
    unittest.main()
