"""mineperc.restoreprivacy.online is a Perccent PERC pool, not a Beam coin pool."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "perc_chain" / "mineperc" / "public" / "index.html"
SERVER = ROOT / "perc_chain" / "src" / "mineperc_server.js"


class TestMinepercFacing(unittest.TestCase):
    def test_page_is_perc_pool_beamhash_iii(self) -> None:
        html = PAGE.read_text(encoding="utf-8")
        self.assertIn("Perccent PERC pool", html)
        self.assertIn("BeamHash III", html)
        self.assertIn("mineperc.restoreprivacy.online:1466", html)
        self.assertIn("Ports <code>1690</code> and <code>1974</code> stay on Beam", html)
        self.assertIn("PERC_USERNAME.WORKER", html)
        self.assertNotIn("Beam mining pool", html)
        self.assertNotIn("beam.2miners.com", html)
        self.assertNotIn("--coin BEAM ", html)
        self.assertIn("Do not pass", html)

    def test_server_publishes_perc_stratum(self) -> None:
        src = SERVER.read_text(encoding="utf-8")
        self.assertIn("Perccent PERC pool", src)
        self.assertIn("beamhashIII", src)
        self.assertIn("1466", src)
        self.assertIn("BEAM_RESERVED_PORTS", src)
        self.assertIn("Do not use --coin BEAM", src)
        self.assertIn("creditAcceptedShare", src)
        self.assertNotRegex(src, r"STRATUM_PORTS\s*=\s*\[[^\]]*(1690|1974)")


if __name__ == "__main__":
    unittest.main()
