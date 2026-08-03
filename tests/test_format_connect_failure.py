"""format_connect_failure — preferred entry + multi-peer timeout reporting."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import format_connect_failure  # noqa: E402


class TestFormatConnectFailure(unittest.TestCase):
    def test_timeout_names_preferred_not_only_last_failover(self) -> None:
        msg = format_connect_failure(
            socket.timeout("timed out"),
            host="82.221.101.241",  # last failover (IS)
            port=44044,
            timeout_s=20.0,
            preferred_host="178.105.187.178",  # entry DE
            tried_hosts=["178.105.187.178", "82.221.101.241"],
        )
        self.assertIn("178.105.187.178:44044", msg)
        self.assertIn("No reply from VPN node", msg)
        self.assertIn("82.221.101.241:44044", msg)
        self.assertIn("failover", msg.lower())
        self.assertIn("20", msg)

    def test_timeout_single_peer_no_spurious_failover_clause(self) -> None:
        msg = format_connect_failure(
            TimeoutError("timed out"),
            host="178.105.187.178",
            port=44044,
            timeout_s=20,
            preferred_host="178.105.187.178",
            tried_hosts=["178.105.187.178"],
        )
        self.assertIn("178.105.187.178:44044", msg)
        self.assertNotIn("Also tried failover", msg)


if __name__ == "__main__":
    unittest.main()
