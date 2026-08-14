"""Shipped mineperc page: longest-string boxes + per-part copy."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "perc_chain" / "mineperc" / "public" / "index.html"


class TestMinepercPage(unittest.TestCase):
    def test_facts_copy_and_no_clip(self) -> None:
        html = PAGE.read_text(encoding="utf-8")
        self.assertIn("mineperc.restoreprivacy.online", html)
        self.assertIn("1466", html)
        self.assertIn("BeamHash III", html)
        self.assertIn("PERC_USERNAME.WORKER", html)
        self.assertIn(
            "lolMiner --algo BEAM-III --pool mineperc.restoreprivacy.online:1466",
            html,
        )
        self.assertIn("miniZ --url mineperc.restoreprivacy.online:1466", html)
        self.assertIn(
            "gminer --algo beamhashIII --server mineperc.restoreprivacy.online:1466",
            html,
        )
        for part in ("stratum", "high", "worker", "perc-mine", "lolminer", "miniz", "gminer"):
            self.assertIn(f'data-copy-part="{part}"', html)
            self.assertIn(f'data-copy-target="{part}"', html)
        self.assertEqual(html.count('class="copy-icon"'), 7)
        self.assertIn("minWidthChFromParts", html)
        self.assertIn("copyPayloadForPart", html)
        css = html[html.index(".info-value") : html.index(".copy-icon")]
        self.assertNotIn("ellipsis", css)
        self.assertNotIn("overflow: hidden", css)
        self.assertNotIn("overflow:hidden", css)


if __name__ == "__main__":
    unittest.main()
