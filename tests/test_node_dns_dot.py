"""Node Unbound config: DoT / privacy upstream; tunnel-only listen."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestNodeUnboundDot(unittest.TestCase):
    def test_unbound_conf_has_dot_forward(self):
        conf = (ROOT / "node" / "unbound-rpt.conf").read_text(encoding="utf-8")
        self.assertIn("interface: 10.88.0.1", conf)
        self.assertIn("access-control: 0.0.0.0/0 refuse", conf)
        self.assertIn("forward-tls-upstream: yes", conf)
        self.assertIn("@853#", conf)
        self.assertIn("dns.quad9.net", conf)
        # Not open recursion comment
        self.assertIn("DoT", conf)
        # Must not listen on all interfaces as product default
        self.assertNotIn("interface: 0.0.0.0", conf)

    def test_install_dns_mentions_dot(self):
        sh = (ROOT / "node" / "install_dns.sh").read_text(encoding="utf-8")
        self.assertIn("unbound-rpt.conf", sh)
        self.assertIn("DoT", sh)
        self.assertIn("ca-certificates", sh)
        self.assertIn("Do not open port 53 on the public WAN", sh)


if __name__ == "__main__":
    unittest.main()
