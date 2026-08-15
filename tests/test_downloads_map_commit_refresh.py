"""Commit-path downloads-map inventory refresh drives the shipped updater + renderer."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _canned_releases(repo: str) -> list[dict]:
    href = (
        f"https://github.com/rgsneddon/{repo}/releases/download/"
        f"v9.9.9/{repo}-v9.9.9-windows.zip"
    )
    older = (
        f"https://github.com/rgsneddon/{repo}/releases/download/"
        f"v1.0.0/{repo}-v1.0.0-windows.zip"
    )
    return [
        {
            "tag": "v9.9.9",
            "assets": [
                {
                    "platform": "windows",
                    "filename": f"{repo}-v9.9.9-windows.zip",
                    "href": href,
                }
            ],
        },
        {
            "tag": "v1.0.0",
            "assets": [
                {
                    "platform": "windows",
                    "filename": f"{repo}-v1.0.0-windows.zip",
                    "href": older,
                }
            ],
        },
    ]


class TestCommitPathDownloadsMapRefresh(unittest.TestCase):
    def test_hook_and_script_call_shipped_updater(self) -> None:
        hook_mod = _load(
            "install_commit_package_task",
            ROOT / "scripts" / "install_commit_package_task.py",
        )
        refresh_mod = _load(
            "refresh_downloads_map_inventory",
            ROOT / "scripts" / "refresh_downloads_map_inventory.py",
        )
        shipped = _load(
            "_refresh_github_release_inventory",
            ROOT / "status_page" / "_refresh_github_release_inventory.py",
        )
        self.assertTrue(hasattr(shipped, refresh_mod.COMMIT_PATH_FUNCTION))
        self.assertEqual(
            refresh_mod.COMMIT_PATH_FUNCTION, "refresh_github_release_inventory"
        )
        loaded = refresh_mod.load_shipped_updater()
        self.assertTrue(callable(getattr(loaded, refresh_mod.COMMIT_PATH_FUNCTION)))
        self.assertIn(
            "refresh_downloads_map_inventory.py",
            hook_mod.HOOK_BODY,
        )
        self.assertIn("--stage", hook_mod.HOOK_BODY)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git" / "hooks").mkdir(parents=True)
            path = hook_mod.install_pre_commit(repo_root=root, force=True)
            self.assertTrue(hook_mod.hook_invokes_downloads_map_refresh(path))
            self.assertTrue(hook_mod.hook_invokes_assure(path))

    def test_updater_inventory_hrefs_appear_in_rendered_map(self) -> None:
        refresh_mod = _load(
            "refresh_downloads_map_inventory",
            ROOT / "scripts" / "refresh_downloads_map_inventory.py",
        )
        from downloads import (
            list_downloads_map_rows,
            load_github_release_inventory,
            render_downloads_map_page_html,
        )

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "github_release_inventory.json"
            result = refresh_mod.run_commit_path_refresh(
                dest=dest,
                fetch_fn=_canned_releases,
            )
            self.assertTrue(result["ok"], result)
            self.assertTrue(dest.is_file())
            payload = json.loads(dest.read_text(encoding="utf-8"))
            self.assertIsInstance(payload.get("repos"), list)
            self.assertGreaterEqual(len(payload["repos"]), 1)
            multi = [r for r in payload["repos"] if len(r.get("releases") or []) > 1]
            self.assertTrue(multi, payload["repos"])
            repos = load_github_release_inventory(dest)
            self.assertEqual(len(repos), len(payload["repos"]))
            hrefs = []
            for repo in repos:
                for rel in repo.get("releases") or []:
                    for asset in rel.get("assets") or []:
                        hrefs.append(asset["href"])
            self.assertTrue(hrefs)
            rows = list_downloads_map_rows(inventory_path=dest)
            row_hrefs = {r["href"] for r in rows}
            page = render_downloads_map_page_html(inventory_path=dest).decode("utf-8")
            self.assertIn("data-downloads-map-page", page)
            for href in hrefs:
                self.assertIn(href, row_hrefs)
                self.assertIn(href, page)

    def test_offline_commit_path_keeps_existing_snapshot(self) -> None:
        refresh_mod = _load(
            "refresh_downloads_map_inventory",
            ROOT / "scripts" / "refresh_downloads_map_inventory.py",
        )
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "github_release_inventory.json"
            first = refresh_mod.run_commit_path_refresh(
                dest=dest, fetch_fn=_canned_releases
            )
            self.assertTrue(first["wrote"])
            before = dest.read_text(encoding="utf-8")
            second = refresh_mod.run_commit_path_refresh(
                dest=dest, allow_network=False
            )
            self.assertTrue(second["ok"])
            self.assertTrue(second["skipped_network"])
            self.assertFalse(second["wrote"])
            self.assertEqual(dest.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
