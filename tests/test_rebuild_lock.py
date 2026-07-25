"""Exclusive rebuild lock — never two node wipe instances at once."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.rebuild_lock import (  # noqa: E402
    acquire_rebuild_lock,
    entry_is_draining_for_clients,
    is_locked,
    read_lock,
    release_rebuild_lock,
    update_rebuild_lock_state,
)


class TestExclusiveRebuildLock(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def test_acquire_entry_and_second_fails_closed(self):
        ok1, msg1, st1 = acquire_rebuild_lock(
            "entry", install_root=self.root, state="draining"
        )
        self.assertTrue(ok1, msg1)
        self.assertIsNotNone(st1)
        self.assertEqual(st1.role, "entry")
        self.assertTrue(is_locked(self.root))
        self.assertTrue(entry_is_draining_for_clients(self.root))

        ok2, msg2, st2 = acquire_rebuild_lock(
            "entry", install_root=self.root, state="rebuilding"
        )
        self.assertFalse(ok2)
        self.assertIn("already active", msg2.lower())
        self.assertIsNotNone(st2)
        # First lock still held
        cur = read_lock(self.root)
        self.assertEqual(cur.pid, st1.pid)
        self.assertEqual(cur.state, "draining")

    def test_refuse_exit_and_both_roles(self):
        for role in ("exit", "both", "all"):
            ok, msg, st = acquire_rebuild_lock(role, install_root=self.root)
            self.assertFalse(ok, role)
            self.assertIsNone(st)
            self.assertTrue(
                "never" in msg.lower() or "refuse" in msg.lower() or "concurrent" in msg.lower(),
                msg,
            )
        self.assertFalse(is_locked(self.root))

    def test_allow_country_roles_sequentially(self):
        ok, msg, st = acquire_rebuild_lock("is", install_root=self.root, state="draining")
        self.assertTrue(ok, msg)
        self.assertEqual(st.role, "is")
        # Concurrent second peer refused
        ok2, msg2, _ = acquire_rebuild_lock("ro", install_root=self.root)
        self.assertFalse(ok2)
        self.assertIn("already active", msg2.lower())

    def test_update_state_and_release(self):
        ok, _, st = acquire_rebuild_lock(
            "entry", install_root=self.root, state="held"
        )
        self.assertTrue(ok)
        ok_u, msg_u = update_rebuild_lock_state(
            "rebuilding", install_root=self.root
        )
        self.assertTrue(ok_u, msg_u)
        cur = read_lock(self.root)
        self.assertEqual(cur.state, "rebuilding")
        self.assertTrue(entry_is_draining_for_clients(self.root))

        ok_r, msg_r = release_rebuild_lock(
            install_root=self.root, expected_pid=st.pid
        )
        self.assertTrue(ok_r, msg_r)
        self.assertFalse(is_locked(self.root))
        self.assertFalse(entry_is_draining_for_clients(self.root))

    def test_release_wrong_pid_refused(self):
        ok, _, st = acquire_rebuild_lock("entry", install_root=self.root)
        self.assertTrue(ok)
        bad, msg = release_rebuild_lock(
            install_root=self.root, expected_pid=st.pid + 99999
        )
        self.assertFalse(bad)
        self.assertIn("refusing release", msg.lower())
        self.assertTrue(is_locked(self.root))
        release_rebuild_lock(install_root=self.root, expected_pid=st.pid)


if __name__ == "__main__":
    unittest.main()
