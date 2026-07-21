#!/usr/bin/env python3
"""Token-gated HTTP server for paid product installers on the Iceland VPS.

Serves only ``/paid-assets/{version}/{filename}`` when the request carries a
matching ``X-RPT-Asset-Token`` header. Not a free public download surface.

Environment:
  RPT_ASSET_FETCH_TOKEN   required shared secret (same as status host)
  RPT_VPS_ASSET_REMOTE_ROOT  default /opt/restore-privacy/paid_assets
  RPT_VPS_ASSET_PORT         default 8081
  RPT_VPS_ASSET_BIND         default 0.0.0.0
"""

from __future__ import annotations

import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

DEFAULT_ROOT = "/opt/restore-privacy/paid_assets"
DEFAULT_PORT = 8081
PREFIX = "/paid-assets"


def _root() -> Path:
    raw = os.environ.get("RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_ROOT).strip()
    return Path(raw or DEFAULT_ROOT).resolve()


def _token() -> str:
    return os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip() or os.environ.get(
        "RPT_VPS_ASSET_TOKEN", ""
    ).strip()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # No user-info access logs
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
        ctype, _ = mimetypes.guess_type(str(fpath))
        if not ctype:
            ctype = "application/octet-stream"
        data_len = fpath.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(data_len))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with fpath.open("rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)


def main() -> int:
    if not _token():
        print("RPT_ASSET_FETCH_TOKEN required", file=sys.stderr)
        return 2
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    bind = os.environ.get("RPT_VPS_ASSET_BIND", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.environ.get("RPT_VPS_ASSET_PORT", str(DEFAULT_PORT)).strip() or DEFAULT_PORT)
    httpd = ThreadingHTTPServer((bind, port), Handler)
    print(f"paid-assets serve root={root} bind={bind}:{port} prefix={PREFIX}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
