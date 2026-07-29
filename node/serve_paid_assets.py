#!/usr/bin/env python3
"""Token-gated HTTP server for paid product installers (Helsinki store).

Serves only ``/paid-assets/{version}/{filename}`` when the request carries a
matching ``X-RPT-Asset-Token`` header. Not a free public download surface.

When ``RPT_CATALOG_VERSION`` is set (install-serve sets it to the ship pin),
only that version directory is served — older pin paths return 404.

Environment:
  RPT_ASSET_FETCH_TOKEN   required shared secret (same as status host)
  RPT_VPS_ASSET_REMOTE_ROOT  default /opt/restore-privacy/paid_assets
  RPT_VPS_ASSET_PORT         default 8081
  RPT_VPS_ASSET_BIND         default 0.0.0.0
  RPT_CATALOG_VERSION        when set, only this version segment is served
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

DEFAULT_ROOT = "/opt/restore-privacy/paid_assets"
DEFAULT_BREADCRUMBS_ROOT = "/opt/restore-privacy/breadcrumbs"
DEFAULT_PORT = 8081
PREFIX = "/paid-assets"
BREADCRUMBS_PREFIX = "/breadcrumbs"
# Token-gated host load/disk only (no file paths) for admin fleet package-store table
HOST_METRICS_PATH = "/api/private/host-metrics"
# Safe vault file names only (no installer blobs)
BREADCRUMB_FILES = frozenset(
    {
        "manifest.json",
        "honesty.json",
        "checklist.md",
        "APPLE_HANDOFF.md",
    }
)


def _root() -> Path:
    raw = os.environ.get("RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_ROOT).strip()
    return Path(raw or DEFAULT_ROOT).resolve()


def _breadcrumbs_root() -> Path:
    raw = os.environ.get(
        "RPT_BREADCRUMBS_REMOTE_ROOT", DEFAULT_BREADCRUMBS_ROOT
    ).strip()
    return Path(raw or DEFAULT_BREADCRUMBS_ROOT).resolve()


def _token() -> str:
    return os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip() or os.environ.get(
        "RPT_VPS_ASSET_TOKEN", ""
    ).strip()


def _catalog_version_pin() -> str:
    """Live catalog pin for tidy store (empty = do not pin-filter versions)."""
    return (os.environ.get("RPT_CATALOG_VERSION") or "").strip()


def path_allowed_for_catalog(
    version: str, filename: str, *, catalog_version: str = ""
) -> bool:
    """Pure: refuse stale version dirs and filenames that omit the pin."""
    ver = (version or "").strip()
    name = (filename or "").strip()
    if not ver or not name or name != Path(name).name:
        return False
    pin = (catalog_version or "").strip()
    if pin:
        if ver != pin:
            return False
        if pin not in name:
            return False
    return True


def breadcrumbs_path_allowed(rel_parts: list[str]) -> bool:
    """Pure: allow only current|{version}/known vault filenames."""
    if len(rel_parts) != 2:
        return False
    folder, name = rel_parts
    if not folder or not name or name != Path(name).name:
        return False
    if ".." in folder or ".." in name:
        return False
    if name not in BREADCRUMB_FILES:
        return False
    # folder is monopin or the literal "current"
    if folder == "current":
        return True
    pin = _catalog_version_pin()
    if pin and folder != pin:
        return False
    return True


def collect_host_metrics(
    *,
    loadavg_path: str | Path = "/proc/loadavg",
    uptime_path: str | Path = "/proc/uptime",
    disk_path: str = "/",
) -> dict:
    """Pure-ish host stats for admin: load averages + root volume usage.

    **Never** includes directory paths, package filenames, or asset trees —
    only relative load and drive capacity/used/free aggregates.
    """
    out: dict = {
        "ok": True,
        "role": "package_store",
        "load_1": None,
        "load_5": None,
        "load_15": None,
        "uptime_sec": None,
        "disk_total_bytes": None,
        "disk_used_bytes": None,
        "disk_avail_bytes": None,
        "disk_util": None,
    }
    try:
        raw = Path(loadavg_path).read_text(encoding="utf-8").strip().split()
        if len(raw) >= 3:
            out["load_1"] = float(raw[0])
            out["load_5"] = float(raw[1])
            out["load_15"] = float(raw[2])
    except (OSError, ValueError, TypeError):
        pass
    try:
        u = Path(uptime_path).read_text(encoding="utf-8").strip().split()
        if u:
            out["uptime_sec"] = int(float(u[0]))
    except (OSError, ValueError, TypeError):
        pass
    try:
        usage = shutil.disk_usage(disk_path)
        total = int(usage.total)
        used = int(usage.used)
        free = int(usage.free)
        out["disk_total_bytes"] = total
        out["disk_used_bytes"] = used
        out["disk_avail_bytes"] = free
        if total > 0:
            out["disk_util"] = min(1.0, max(0.0, used / float(total)))
    except (OSError, ValueError, TypeError):
        pass
    if out["load_1"] is None and out["disk_total_bytes"] is None:
        out["ok"] = False
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # No user-info access logs
        return

    def _send_json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _send_file(self, fpath: Path, *, as_attachment: bool) -> None:
        ctype, _ = mimetypes.guess_type(str(fpath))
        if not ctype:
            if fpath.suffix == ".json":
                ctype = "application/json"
            elif fpath.suffix == ".md":
                ctype = "text/markdown; charset=utf-8"
            else:
                ctype = "application/octet-stream"
        data_len = fpath.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(data_len))
        if as_attachment:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{fpath.name}"'
            )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with fpath.open("rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def do_GET(self) -> None:  # noqa: N802
        expected = _token()
        if not expected:
            self.send_error(503, "asset token not configured")
            return
        got = (self.headers.get("X-RPT-Asset-Token") or "").strip()
        if not got or got != expected:
            self.send_error(401, "unauthorized")
            return
        path = unquote(self.path.split("?", 1)[0])

        # --- Host load + drive only (admin fleet package-store table) ---
        if path.rstrip("/") == HOST_METRICS_PATH.rstrip("/"):
            self._send_json(200, collect_host_metrics())
            return

        # --- Apple breadcrumbs vault (task metadata only) ---
        if path.startswith(BREADCRUMBS_PREFIX + "/"):
            rel = path[len(BREADCRUMBS_PREFIX) + 1 :].lstrip("/")
            parts = [p for p in rel.split("/") if p and p not in (".", "..")]
            if not breadcrumbs_path_allowed(parts):
                self.send_error(404, "not found")
                return
            folder, name = parts
            root = _breadcrumbs_root()
            fpath = (root / folder / name).resolve()
            try:
                fpath.relative_to(root)
                fpath.relative_to((root / folder).resolve())
            except ValueError:
                self.send_error(400, "bad path")
                return
            if not fpath.is_file():
                self.send_error(404, "not found")
                return
            self._send_file(fpath, as_attachment=False)
            return

        # --- Paid installers ---
        if not path.startswith(PREFIX + "/"):
            self.send_error(404, "not found")
            return
        rel = path[len(PREFIX) + 1 :].lstrip("/")
        # version/filename only — no traversal
        parts = [p for p in rel.split("/") if p and p not in (".", "..")]
        if len(parts) != 2:
            self.send_error(404, "not found")
            return
        version, filename = parts
        if ".." in version or ".." in filename or "/" in filename or "\\" in filename:
            self.send_error(400, "bad path")
            return
        # Filenames only — no nested paths under version/
        if Path(filename).name != filename:
            self.send_error(400, "bad path")
            return
        if not path_allowed_for_catalog(
            version, filename, catalog_version=_catalog_version_pin()
        ):
            self.send_error(404, "not found")
            return
        root = _root()
        fpath = (root / version / filename).resolve()
        try:
            fpath.relative_to(root)
        except ValueError:
            self.send_error(400, "bad path")
            return
        # Ensure resolved path stays under version dir (no symlink escape)
        try:
            fpath.relative_to((root / version).resolve())
        except ValueError:
            self.send_error(400, "bad path")
            return
        if not fpath.is_file():
            self.send_error(404, "not found")
            return
        self._send_file(fpath, as_attachment=True)


def main() -> int:
    if not _token():
        print("RPT_ASSET_FETCH_TOKEN required", file=sys.stderr)
        return 2
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    _breadcrumbs_root().mkdir(parents=True, exist_ok=True)
    bind = os.environ.get("RPT_VPS_ASSET_BIND", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.environ.get("RPT_VPS_ASSET_PORT", str(DEFAULT_PORT)).strip() or DEFAULT_PORT)
    httpd = ThreadingHTTPServer((bind, port), Handler)
    print(
        f"paid-assets serve root={root} breadcrumbs={_breadcrumbs_root()} "
        f"bind={bind}:{port} prefixes={PREFIX},{BREADCRUMBS_PREFIX},"
        f"{HOST_METRICS_PATH}"
    )
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
