"""Admin mutators mint ChronoFlux blocks and confirm pending relays."""

from __future__ import annotations

import io
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
            empty_ledger,
            load_ledger,
            mint_admin_action_block,
            queue_pending_relayed_transfer,
            save_ledger,
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


class _FakeHandler:
    """Minimal stand-in that uses real Handler methods with controlled I/O."""

    def __init__(self, path: str, body: bytes = b"", headers: dict | None = None):
        import app as status_app

        self.path = path
        self.headers = headers or {}
        self._body = body
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self._code = None
        self._sent: list[tuple[str, str]] = []
        # Bind real methods
        self._read_body = status_app.Handler._read_body.__get__(self, status_app.Handler)
        self._admin_chronoflux_ok = status_app.Handler._admin_chronoflux_ok.__get__(
            self, status_app.Handler
        )
        self.do_POST = status_app.Handler.do_POST.__get__(self, status_app.Handler)
        self.do_GET = status_app.Handler.do_GET.__get__(self, status_app.Handler)
        self._security_headers = lambda **kw: None

    def send_response(self, code: int) -> None:
        self._code = code

    def send_header(self, k: str, v: str) -> None:
        self._sent.append((k, v))

    def end_headers(self) -> None:
        pass

    def _send(
        self,
        code: int,
        content_type: str,
        data: bytes,
        *,
        extra_headers: list | None = None,
        allow_framing: bool = False,
    ) -> None:
        self._code = code
        self._body_out = data
        self._content_type = content_type


class TestAdminChronofluxHandlerNegative(unittest.TestCase):
    """Drive real Handler do_POST/do_GET — failed/unauth must not mint."""

    def test_unauth_mint_keygen_post_does_not_mint(self) -> None:
        from admin_chronoflux import list_admin_chronoflux_blocks

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            with mock.patch(
                "admin_chronoflux.admin_chronoflux_ledger_path", return_value=lp
            ), mock.patch(
                "status_page.admin_chronoflux.admin_chronoflux_ledger_path",
                return_value=lp,
            ), mock.patch(
                "admin_panel.admin_enabled", return_value=True
            ), mock.patch(
                "admin_panel.is_authenticated", return_value=False
            ):
                # Import after patches so app uses same modules
                import app as status_app

                with mock.patch.object(
                    status_app, "admin_enabled", return_value=True
                ), mock.patch.object(
                    status_app, "is_authenticated", return_value=False
                ), mock.patch.object(
                    status_app, "render_login_html", return_value=b"login"
                ):
                    h = _FakeHandler(
                        "/admin/mint-keygen",
                        body=b"platform=windows&note=test",
                        headers={"Content-Length": "24"},
                    )
                    # Content-Length must match body for _read_body
                    h.headers = {
                        "Content-Length": str(len(h._body)),
                    }
                    h.do_POST()
            blocks = list_admin_chronoflux_blocks(ledger_path=lp)
            self.assertEqual(
                blocks, [], "unauthenticated mint-keygen must not mint a block"
            )
            self.assertEqual(h._code, 200)  # login page

    def test_bad_form_clear_licences_does_not_mint(self) -> None:
        from admin_chronoflux import list_admin_chronoflux_blocks

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            import app as status_app

            with mock.patch.object(
                status_app, "admin_enabled", return_value=True
            ), mock.patch.object(
                status_app, "is_authenticated", return_value=True
            ), mock.patch(
                "payments.clear_all_licences_for_admin",
                side_effect=ValueError("confirm token mismatch"),
            ), mock.patch(
                "admin_panel.render_admin_licences_page_html",
                return_value=b"err",
            ), mock.patch(
                "admin_chronoflux.admin_chronoflux_ledger_path", return_value=lp
            ):
                body = b"confirm=WRONG"
                h = _FakeHandler(
                    "/admin/clear-licences",
                    body=body,
                    headers={"Content-Length": str(len(body))},
                )
                h.headers = {"Content-Length": str(len(body))}
                h.do_POST()
            self.assertEqual(list_admin_chronoflux_blocks(ledger_path=lp), [])
            self.assertEqual(h._code, 400)

    def test_admin_get_does_not_mint(self) -> None:
        from admin_chronoflux import list_admin_chronoflux_blocks

        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "ledger.json"
            import app as status_app

            with mock.patch.object(
                status_app, "admin_enabled", return_value=True
            ), mock.patch.object(
                status_app, "is_authenticated", return_value=True
            ), mock.patch.object(
                status_app, "render_admin_html", return_value=b"admin-home"
            ), mock.patch(
                "admin_chronoflux.admin_chronoflux_ledger_path", return_value=lp
            ):
                h = _FakeHandler("/admin", body=b"", headers={})
                h.headers = {"Content-Length": "0"}
                h.do_GET()
            self.assertEqual(
                list_admin_chronoflux_blocks(ledger_path=lp),
                [],
                "admin GET must not mint ChronoFlux blocks",
            )


class TestAdminHandlerHookExists(unittest.TestCase):
    def test_handler_has_chronoflux_ok_method(self) -> None:
        import app as status_app

        self.assertTrue(hasattr(status_app.Handler, "_admin_chronoflux_ok"))
        src = Path(status_app.__file__).read_text(encoding="utf-8")
        for needle in (
            '"mint_keygen"',
            '"mint_download"',
            '"clear_licences"',
            '"push_suite_packages"',
            '"support_ticket_close"',
            '"reissue_download"',
            '"resend_fulfilment_email"',
            '"seed_test_purchase"',
            '"processors_apply"',
            '"upload_package_path"',
            "_admin_chronoflux_ok",
        ):
            self.assertIn(needle, src, msg=f"missing hook for {needle!r}")
        self.assertGreaterEqual(src.count("_admin_chronoflux_ok"), 12)


if __name__ == "__main__":
    unittest.main()
