"""Windows residual privilege gates — real shipped helpers (no residual without privilege)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestResidualPrivilegeHelpers(unittest.TestCase):
    def test_residual_requires_os_privilege_honest(self) -> None:
        from client.windows.residual_privilege import (
            gui_may_run_as_standard_user,
            residual_requires_os_privilege,
        )

        self.assertTrue(residual_requires_os_privilege())
        self.assertTrue(gui_may_run_as_standard_user())

    def test_status_elevate_disabled_message(self) -> None:
        from client.windows.residual_privilege import (
            MSG_ELEVATE_DISABLED,
            residual_connect_block_message,
            residual_privilege_status,
        )

        with mock.patch.dict(os.environ, {"RPT_NO_AUTO_ELEVATE": "1"}, clear=False):
            with mock.patch(
                "client.windows.residual_privilege.is_process_admin",
                return_value=False,
            ):
                with mock.patch(
                    "client.windows.residual_privilege.residual_helper_installed",
                    return_value=False,
                ):
                    st = residual_privilege_status()
        self.assertEqual(st["mode"], "elevate_disabled")
        self.assertFalse(st["may_connect_without_gui_elevation"])
        self.assertIn("RPT_NO_AUTO_ELEVATE", st["message"])
        msg = residual_connect_block_message(st)
        self.assertEqual(msg, MSG_ELEVATE_DISABLED)
        self.assertIn("residual helper", msg.lower())

    def test_status_helper_installed_allows_gui_non_admin_connect(self) -> None:
        from client.windows.residual_privilege import (
            MSG_HELPER_READY,
            product_connect_requires_admin_process,
            residual_privilege_status,
        )

        with mock.patch.dict(os.environ, {"RPT_NO_AUTO_ELEVATE": "0"}, clear=False):
            os.environ.pop("RPT_NO_AUTO_ELEVATE", None)
            with mock.patch(
                "client.windows.residual_privilege.is_process_admin",
                return_value=False,
            ):
                with mock.patch(
                    "client.windows.residual_privilege.residual_helper_installed",
                    return_value=True,
                ):
                    st = residual_privilege_status()
                    needs = product_connect_requires_admin_process()
        self.assertEqual(st["mode"], "helper_installed")
        self.assertTrue(st["may_connect_without_gui_elevation"])
        self.assertIn("helper", st["message"].lower())
        self.assertFalse(needs)
        self.assertIn("Run as administrator", MSG_HELPER_READY)

    def test_elevation_result_user_message_uac_cancelled(self) -> None:
        from client.windows.residual_privilege import (
            MSG_UAC_CANCELLED,
            elevation_result_user_message,
        )

        self.assertEqual(
            elevation_result_user_message("failed:uac_cancelled"),
            MSG_UAC_CANCELLED,
        )
        self.assertIn("RPT_NO_AUTO_ELEVATE", elevation_result_user_message("skipped"))

    def test_install_helper_dry_run_and_admin_gate(self) -> None:
        from client.windows.residual_privilege import (
            RESIDUAL_HELPER_TASK,
            build_install_residual_helper_command,
            install_residual_helper,
        )

        cmd = build_install_residual_helper_command()
        self.assertEqual(cmd[0], "schtasks")
        self.assertIn("/Create", cmd)
        self.assertIn(RESIDUAL_HELPER_TASK, cmd)
        self.assertIn("/RL", cmd)
        self.assertIn("HIGHEST", cmd)

        dry = install_residual_helper(dry_run=True)
        self.assertTrue(dry.get("ok"))
        self.assertTrue(dry.get("dry_run"))

        with mock.patch(
            "client.windows.residual_privilege.is_process_admin",
            return_value=False,
        ):
            res = install_residual_helper(dry_run=False)
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("error"), "admin_required")

    def test_app_product_connect_requires_admin_delegates(self) -> None:
        from client.windows import app as win_app

        with mock.patch(
            "client.windows.residual_privilege.product_connect_requires_admin_process",
            return_value=False,
        ):
            self.assertFalse(win_app.product_connect_requires_admin())
        with mock.patch(
            "client.windows.residual_privilege.product_connect_requires_admin_process",
            return_value=True,
        ):
            self.assertTrue(win_app.product_connect_requires_admin())
        self.assertTrue(win_app.non_admin_connect_allowed())

    def test_shortcut_default_not_run_as_admin(self) -> None:
        import inspect

        from client.windows import installer as inst

        src = inspect.getsource(inst._create_shortcut)
        self.assertIn("run_as_admin: bool = False", src)
        self.assertIn("run_as_admin", src)


class TestResidualPrivilegeBoundaryStructural(unittest.TestCase):
    def test_tunnel_still_requires_admin_for_system_capture(self) -> None:
        """Residual system capture path still gates on is_admin in tunnel_win."""
        src = (
            ROOT / "client" / "windows" / "tunnel_win.py"
        ).read_text(encoding="utf-8")
        self.assertIn("require_system_capture", src)
        self.assertIn("is_admin()", src)
        self.assertIn("Wintun", src)
        self.assertIn("dual /1", src)

    def test_main_does_not_force_launch_elevate(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("RPT_ELEVATE_ON_LAUNCH", src)
        self.assertIn("residual_helper", src.lower() or "residual helper")


if __name__ == "__main__":
    unittest.main()
