"""Admin package SSH upload: host key check; missing keys → app-testers."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))

APP_TESTERS = "https://restoreprivacy.online/app-testers"


class TestHostSshAccessKeyProbe(unittest.TestCase):
    def test_missing_keys_preflight_redirects_to_app_testers(self) -> None:
        from host_paid_assets_vps import (
            APP_TESTERS_FORCE_URL,
            host_ssh_access_keys_present,
            resolve_ssh_access_key_path,
            ssh_upload_preflight,
        )

        self.assertEqual(APP_TESTERS_FORCE_URL, APP_TESTERS)
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / ".ssh").mkdir()
            env = {
                "RPT_SSH_KEY": "",
                "RPT_SSH_PASSWORD": "",
            }
            self.assertFalse(
                host_ssh_access_keys_present(env=env, home=home)
            )
            self.assertIsNone(
                resolve_ssh_access_key_path(key_env="", home=home)
            )
            pre = ssh_upload_preflight(upload=True, env=env, home=home)
            self.assertFalse(pre["ok"])
            self.assertTrue(pre["missing_ssh_keys"])
            self.assertEqual(pre["redirect"], APP_TESTERS)
            self.assertIn("app-testers", str(pre["error"]))

            # Stage-only / upload off: no gate
            pre2 = ssh_upload_preflight(upload=False, env=env, home=home)
            self.assertTrue(pre2["ok"])
            self.assertFalse(pre2["missing_ssh_keys"])
            self.assertEqual(pre2["redirect"], "")

    def test_present_key_file_allows_upload_preflight(self) -> None:
        from host_paid_assets_vps import (
            host_ssh_access_keys_present,
            resolve_ssh_access_key_path,
            ssh_upload_preflight,
        )

        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            ssh = home / ".ssh"
            ssh.mkdir()
            key = ssh / "id_ed25519_restore_privacy_eu"
            key.write_text("fake-private-key-material\n", encoding="utf-8")
            env = {"RPT_SSH_KEY": "", "RPT_SSH_PASSWORD": ""}
            self.assertTrue(host_ssh_access_keys_present(env=env, home=home))
            resolved = resolve_ssh_access_key_path(key_env="", home=home)
            self.assertEqual(resolved, key)
            pre = ssh_upload_preflight(upload=True, env=env, home=home)
            self.assertTrue(pre["ok"])
            self.assertFalse(pre["missing_ssh_keys"])
            self.assertEqual(pre["redirect"], "")
            self.assertEqual(pre["key_path"], str(key))

            # Explicit RPT_SSH_KEY env path
            env2 = {"RPT_SSH_KEY": str(key), "RPT_SSH_PASSWORD": ""}
            pre3 = ssh_upload_preflight(upload=True, env=env2, home=home)
            self.assertTrue(pre3["ok"])
            self.assertEqual(pre3["key_path"], str(key))

            # Password alone counts as credentials
            env3 = {"RPT_SSH_KEY": "", "RPT_SSH_PASSWORD": "secret"}
            empty_home = Path(td) / "empty_home"
            empty_home.mkdir()
            (empty_home / ".ssh").mkdir()
            self.assertTrue(
                host_ssh_access_keys_present(env=env3, home=empty_home)
            )

    def test_key_dir_and_private_key_material_resolve(self) -> None:
        from host_paid_assets_vps import (
            resolve_ssh_access_key_path,
            ssh_upload_preflight,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            key_dir = root / "rpt-ssh"
            key_dir.mkdir()
            key = key_dir / "id_ed25519_restore_privacy_eu"
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n", encoding="utf-8")
            empty_home = root / "nohome"
            empty_home.mkdir()
            (empty_home / ".ssh").mkdir()
            env = {
                "RPT_SSH_KEY": "",
                "RPT_SSH_PASSWORD": "",
                "RPT_SSH_KEY_DIR": str(key_dir),
            }
            pre = ssh_upload_preflight(upload=True, env=env, home=empty_home)
            self.assertTrue(pre["ok"], pre)
            self.assertFalse(pre["missing_ssh_keys"])
            self.assertEqual(pre["key_path"], str(key))

            # PEM secret materializes to a key file when no path candidates exist
            mat_home = root / "mat_home"
            mat_home.mkdir()
            (mat_home / ".ssh").mkdir()
            dest = root / "from-secret" / "id_ed25519_restore_privacy_eu"
            env2 = {
                "RPT_SSH_KEY": str(dest),
                "RPT_SSH_PASSWORD": "",
                "RPT_SSH_PRIVATE_KEY": "-----BEGIN OPENSSH PRIVATE KEY-----\\nfake-material\\n-----END-----",
            }
            pre2 = ssh_upload_preflight(upload=True, env=env2, home=mat_home)
            self.assertTrue(pre2["ok"], pre2)
            self.assertTrue(Path(str(pre2["key_path"])).is_file())
            body = Path(str(pre2["key_path"])).read_text(encoding="utf-8")
            self.assertIn("BEGIN OPENSSH", body)
            self.assertIn("\n", body)


class TestOperatorUploadMissingKeys(unittest.TestCase):
    def test_upload_catalog_blocks_ssh_when_keys_missing(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / ".ssh").mkdir()
            empty_env = {
                "RPT_SSH_KEY": "",
                "RPT_SSH_PASSWORD": "",
                "HOME": str(home),
                "PATH": os.environ.get("PATH", ""),
            }
            with mock.patch.dict(os.environ, empty_env, clear=True):
                with mock.patch.object(
                    ctrl,
                    "ssh_upload_access_preflight",
                    return_value={
                        "ok": False,
                        "missing_ssh_keys": True,
                        "redirect": APP_TESTERS,
                        "error": f"keys missing → {APP_TESTERS}",
                        "key_path": "",
                    },
                ):
                    r = ctrl.upload_catalog_packages(
                        version=ver,
                        stage=False,
                        upload=True,
                        dry_run=False,
                        allow_missing=True,
                    )
            self.assertFalse(r.get("ok"))
            self.assertTrue(r.get("missing_ssh_keys"))
            self.assertEqual(r.get("redirect"), APP_TESTERS)
            self.assertIn("app-testers", str(r.get("error") or ""))
            # Must not invent a successful SSH upload
            self.assertIsNone(r.get("upload_code"))

    def test_dry_run_upload_skips_key_gate(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        # dry_run does not force app-testers even without keys
        r = ctrl.upload_catalog_packages(
            version=ver,
            stage=False,
            upload=True,
            dry_run=True,
            allow_missing=True,
        )
        self.assertTrue(r.get("dry_run"))
        self.assertNotEqual(r.get("redirect"), APP_TESTERS)
        # missing_ssh_keys should not force-open on dry-run
        self.assertFalse(r.get("missing_ssh_keys"))

    def test_handle_action_returns_redirect_fourth(self) -> None:
        from admin_node_operator import (
            ADMIN_UPLOAD_MISSING_SSH_KEYS_URL,
            handle_admin_node_operator_action,
        )
        from node.operator_admin import NodeOperatorController

        self.assertEqual(ADMIN_UPLOAD_MISSING_SSH_KEYS_URL, APP_TESTERS)
        ctrl = NodeOperatorController(repo_root=ROOT)
        with mock.patch(
            "admin_node_operator.get_operator_controller",
            return_value=ctrl,
        ):
            with mock.patch.object(
                ctrl,
                "upload_catalog_packages",
                return_value={
                    "ok": False,
                    "missing_ssh_keys": True,
                    "redirect": APP_TESTERS,
                    "error": "SSH access keys missing",
                    "version": "1.0.0",
                },
            ):
                result = handle_admin_node_operator_action(
                    {
                        "node": "helsinki-store",
                        "action": "upload_packages",
                        "version": "1.0.0",
                        "upload": "1",
                        "dry_run": "0",
                        "stage": "0",
                    }
                )
        self.assertEqual(len(result), 4)
        ok, msg, node_id, redirect = result
        self.assertFalse(ok)
        self.assertEqual(redirect, APP_TESTERS)
        self.assertEqual(node_id, "helsinki-store")
        self.assertIn("SSH", msg)

    def test_present_keys_continues_to_upload_call(self) -> None:
        from node.operator_admin import NodeOperatorController

        ctrl = NodeOperatorController(repo_root=ROOT)
        ver = ctrl.catalog_version_default()
        called: list[dict] = []

        def fake_upload_packages(**kwargs):
            called.append(kwargs)
            return 0

        class FakeMod:
            def stage_packages(self, **kwargs):
                return []

            def upload_packages(self, **kwargs):
                return fake_upload_packages(**kwargs)

            def list_packages(self, ver):
                return []

        with mock.patch.object(ctrl, "_load_host_paid_assets", return_value=FakeMod()):
            with mock.patch.object(
                ctrl,
                "ssh_upload_access_preflight",
                return_value={
                    "ok": True,
                    "missing_ssh_keys": False,
                    "redirect": "",
                    "error": "",
                    "key_path": "/tmp/fake_key",
                },
            ):
                r = ctrl.upload_catalog_packages(
                    version=ver,
                    stage=False,
                    upload=True,
                    dry_run=False,
                    allow_missing=True,
                )
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(r.get("missing_ssh_keys"))
        self.assertEqual(r.get("redirect") or "", "")
        self.assertEqual(len(called), 1)
        self.assertEqual(r.get("upload_code"), 0)
        self.assertEqual(r.get("ssh_key_path"), "/tmp/fake_key")


class TestAsyncPushJobSshGate(unittest.TestCase):
    def test_start_push_job_missing_keys_returns_redirect(self) -> None:
        from node.operator_admin import NodeOperatorController
        from suite_push_progress import start_push_job

        ctrl = NodeOperatorController(repo_root=ROOT)
        with mock.patch.object(
            ctrl,
            "ssh_upload_access_preflight",
            return_value={
                "ok": False,
                "missing_ssh_keys": True,
                "redirect": APP_TESTERS,
                "error": f"Package host SSH access keys were not found. Open {APP_TESTERS}",
                "key_path": "",
            },
        ):
            started = start_push_job(
                ctrl,
                stage=False,
                upload=True,
                dry_run=False,
                allow_missing=True,
            )
        self.assertFalse(started.get("ok"))
        self.assertTrue(started.get("missing_ssh_keys"))
        self.assertEqual(started.get("redirect"), APP_TESTERS)
        self.assertIn("SSH", str(started.get("error") or ""))
        job = started.get("job") or {}
        self.assertEqual(job.get("state"), "failed")
        self.assertEqual(job.get("message"), "missing_ssh_keys")
        self.assertTrue(job.get("missing_ssh_keys"))

    def test_start_push_job_dry_run_skips_ssh_gate(self) -> None:
        from node.operator_admin import NodeOperatorController
        from suite_push_progress import job_snapshot, start_push_job
        import time

        ctrl = NodeOperatorController(repo_root=ROOT)
        with mock.patch.object(
            ctrl,
            "ssh_upload_access_preflight",
            side_effect=AssertionError("preflight must not run on dry_run"),
        ):
            started = start_push_job(
                ctrl,
                stage=True,
                upload=True,
                dry_run=True,
                allow_missing=True,
            )
        self.assertTrue(started.get("ok"), started)
        jid = started["job_id"]
        deadline = time.time() + 60
        while time.time() < deadline:
            snap = job_snapshot(jid)
            if snap and snap.get("state") in ("complete", "failed"):
                break
            time.sleep(0.05)
        snap = job_snapshot(jid)
        self.assertIsNotNone(snap)
        assert snap is not None
        # dry-run should not be missing_ssh_keys
        self.assertNotEqual(snap.get("message"), "missing_ssh_keys")


if __name__ == "__main__":
    unittest.main()
