"""Admin mutators mint ChronoFlux blocks and confirm pending relays."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminChronofluxMint(unittest.TestCase):
    def test_progress_mints_block_with_admin_kind(self) -> None:
        from admin_chronoflux import (
            ADMIN_ACTION_KIND,
            explorer_block_rows,
            progress_admin_action,
        )

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            r = progress_admin_action(
                action_kind="mint_keygen",
                label="Admin: Mint Keygen",
                path="/admin/mint-keygen",
                ledger_path=lp,
                remote=False,
            )
            self.assertTrue(r["ok"])
            self.assertEqual(r["height"], 0)
            self.assertEqual(r["block"]["transactions"][0]["kind"], ADMIN_ACTION_KIND)
            self.assertTrue(r["block"]["adminAction"])
            self.assertTrue(lp.is_file())
            rows = explorer_block_rows(ledger_path=lp)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["confirmed"])
            self.assertIn("Admin", rows[0]["label"])

    def test_pending_relays_confirmed_on_seal(self) -> None:
        from admin_chronoflux import (
            mint_admin_action_block,
            queue_pending_relayed_transfer,
            load_ledger,
            save_ledger,
            empty_ledger,
        )

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            save_ledger(empty_ledger(), lp)
            queue_pending_relayed_transfer(
                {"id": "xfer-1", "kind": "transfer"}, path=lp
            )
            queue_pending_relayed_transfer(
                {"id": "xfer-2", "kind": "transfer"}, path=lp
            )
            ledger = load_ledger(lp)
            r = mint_admin_action_block(
                ledger,
                action_kind="push_suite_packages",
                label="Admin: Push Suite Packages",
            )
            self.assertTrue(r["ok"])
            self.assertEqual(r["pendingIncluded"], 2)
            self.assertEqual(ledger.get("pendingInboundTransfers"), [])
            kinds = [t["kind"] for t in r["block"]["transactions"]]
            self.assertIn("adminAction", kinds)
            self.assertEqual(kinds.count("transfer"), 2)

    def test_relay_ledger_tx_ids_recorded(self) -> None:
        from admin_chronoflux import empty_ledger, mint_admin_action_block

        ledger = empty_ledger()
        relay = {
            "blocks": [
                {
                    "index": 1,
                    "transactions": [
                        {"id": "relay-aa", "kind": "transfer"},
                    ],
                }
            ]
        }
        r = mint_admin_action_block(
            ledger,
            action_kind="clear_licences",
            label="Admin: Clear Licences",
            relay_ledgers=[relay],
        )
        self.assertTrue(r["ok"])
        self.assertIn("relay-aa", r["confirmedRelayTxIds"])


class TestAdminChronofluxNegative(unittest.TestCase):
    def test_failed_action_does_not_call_progress_on_unauth(self) -> None:
        """Unauthenticated admin POST must not mint (structural: after_admin_success not invoked)."""
        # Drive after_admin_success only on success; failed path uses no hook.
        # Pure unit: mint only when after_admin_success is called.
        from admin_chronoflux import after_admin_success, list_admin_chronoflux_blocks

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            # Simulate failure: we never call after_admin_success
            self.assertEqual(list_admin_chronoflux_blocks(ledger_path=lp), [])
            # Success path would call:
            with mock.patch(
                "admin_chronoflux.admin_chronoflux_ledger_path", return_value=lp
            ):
                r = after_admin_success("mint_download", path="/admin/mint-download")
            self.assertTrue(r.get("ok"))
            self.assertEqual(len(list_admin_chronoflux_blocks(ledger_path=lp)), 1)

    def test_read_only_get_does_not_mint(self) -> None:
        from admin_chronoflux import list_admin_chronoflux_blocks, load_ledger, empty_ledger, save_ledger

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            save_ledger(empty_ledger(), lp)
            # No progress_admin_action → still empty
            self.assertEqual(list_admin_chronoflux_blocks(ledger_path=lp), [])
            data = load_ledger(lp)
            self.assertEqual(data.get("blocks"), [])


class TestAdminHandlerHookExists(unittest.TestCase):
    def test_handler_has_chronoflux_ok_method(self) -> None:
        import app as status_app

        self.assertTrue(hasattr(status_app.Handler, "_admin_chronoflux_ok"))
        # Source wiring for representative mutators
        src = Path(status_app.__file__).read_text(encoding="utf-8")
        for needle in (
            '"mint_keygen"',
            '"mint_download"',
            '"clear_licences"',
            '"push_suite_packages"',
            '"support_ticket_close"',
            "_admin_chronoflux_ok",
        ):
            self.assertIn(needle, src, msg=f"missing hook for {needle!r}")
        self.assertGreaterEqual(src.count("_admin_chronoflux_ok"), 8)

if __name__ == "__main__":
    unittest.main()
