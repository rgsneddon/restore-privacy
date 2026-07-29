"""Helsinki breadcrumbs vault — layout, Mac check outcomes, GH deprecation."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))


def _load_vault():
    path = ROOT / "scripts" / "breadcrumbs_vault.py"
    spec = importlib.util.spec_from_file_location("breadcrumbs_vault", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_serve():
    path = ROOT / "node" / "serve_paid_assets.py"
    spec = importlib.util.spec_from_file_location("serve_paid_assets", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVaultLayout(unittest.TestCase):
    def test_stage_writes_well_formed_vault(self):
        mod = _load_vault()
        pin = mod.current_monopin()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            ver_dir = mod.stage_vault(monopin=pin, out_root=out)
            self.assertTrue((ver_dir / "manifest.json").is_file())
            self.assertTrue((out / "current" / "manifest.json").is_file())
            self.assertTrue((out / "current" / "honesty.json").is_file())
            self.assertTrue((out / "current" / "checklist.md").is_file())
            self.assertTrue((out / "current" / "APPLE_HANDOFF.md").is_file())
            man = json.loads((out / "current" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(man["schema"], "rpt.breadcrumbs.v1")
            self.assertEqual(man["monopin"], pin)
            self.assertEqual(man["source_of_truth"], "helsinki_breadcrumbs_vault")
            self.assertEqual(man["github_breadcrumb_flow"], "deprecated")
            self.assertIn("macos", man["platforms"])
            self.assertIn("ios", man["platforms"])
            # No installer blob filenames as free public assets
            text = (out / "current" / "APPLE_HANDOFF.md").read_text(encoding="utf-8")
            self.assertIn("Breadcrumbs vault (Helsinki)", text)
            self.assertNotIn("github.com/releases/download", text.lower() or text)


class TestMacCheckOutcomes(unittest.TestCase):
    def test_evaluate_up_to_date_when_no_work(self):
        mod = _load_vault()
        man = {
            "monopin": "9.9.9",
            "needs_any_apple_work": False,
            "macbook_actions": ["none_apple_up_to_date"],
            "platforms": {
                "macos": {"needs_work": False, "status": "native_monopin"},
                "ios": {"needs_work": False, "status": "native_monopin"},
            },
            "source_of_truth": "helsinki_breadcrumbs_vault",
            "github_breadcrumb_flow": "deprecated",
        }
        r = mod.evaluate_manifest(man)
        self.assertTrue(r["up_to_date"])
        self.assertFalse(r["macos_needs_work"])
        self.assertFalse(r["ios_needs_work"])

    def test_evaluate_needs_work_flags(self):
        mod = _load_vault()
        man = {
            "monopin": "9.9.9",
            "needs_any_apple_work": True,
            "macbook_actions": ["rebuild_ios_team_sign"],
            "platforms": {
                "macos": {"needs_work": False, "status": "native_monopin"},
                "ios": {"needs_work": True, "status": "carry_forward_or_lag"},
            },
            "source_of_truth": "helsinki_breadcrumbs_vault",
            "github_breadcrumb_flow": "deprecated",
        }
        r = mod.evaluate_manifest(man)
        self.assertFalse(r["up_to_date"])
        self.assertTrue(r["ios_needs_work"])
        self.assertIn("rebuild_ios_team_sign", r["macbook_actions"])

    def test_check_local_stage_runs(self):
        mod = _load_vault()
        r = mod.check_local_stage()
        self.assertIn("monopin", r)
        self.assertIn("up_to_date", r)
        self.assertEqual(r["github_breadcrumb_flow"], "deprecated")
        self.assertEqual(r["source_of_truth"], "helsinki_breadcrumbs_vault")


class TestBreadcrumbsServeGate(unittest.TestCase):
    def test_only_vault_files_allowed(self):
        serve = _load_serve()
        self.assertTrue(serve.breadcrumbs_path_allowed(["current", "manifest.json"]))
        self.assertTrue(serve.breadcrumbs_path_allowed(["0.5.1", "APPLE_HANDOFF.md"]))
        self.assertFalse(
            serve.breadcrumbs_path_allowed(
                ["current", "restore-privacy-client-0.5.1-macos.zip"]
            )
        )
        self.assertFalse(serve.breadcrumbs_path_allowed(["current", "evil.exe"]))
        self.assertFalse(serve.breadcrumbs_path_allowed(["../etc", "passwd"]))


class TestGithubDeprecatedDocs(unittest.TestCase):
    def test_operator_docs_point_at_vault(self):
        vault = (ROOT / "scripts" / "breadcrumbs_vault.py").read_text(encoding="utf-8")
        self.assertIn("helsinki_breadcrumbs_vault", vault)
        self.assertIn("deprecated", vault)
        self.assertIn("check --fetch", vault)
        # Handoff for current pin should mention vault after publish stage banner
        from downloads import RELEASE_VERSION

        handoff = ROOT / "client_app" / f"APPLE_HANDOFF_{RELEASE_VERSION}.md"
        if handoff.is_file():
            # Source file may not yet have banner; staged copy does
            mod = _load_vault()
            with tempfile.TemporaryDirectory() as td:
                mod.stage_vault(out_root=Path(td))
                staged = (Path(td) / "current" / "APPLE_HANDOFF.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("Breadcrumbs vault (Helsinki)", staged)
                self.assertIn("Do **not** treat a private GitHub pull", staged)


if __name__ == "__main__":
    unittest.main()
