"""god.restoreprivacy.online:1474 — dedicated rpAI HTTP control plane.

Only GOD / Grokbot / NED / FRED / PEDRO functions: page, ask, /goal, learn,
and the agent output feed. No shop, no tickets, no miner, no tunnel.
"""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from god_rpai import (
    GOD_HTTP_PORT,
    GOD_LEARN_PATH,
    GOD_RPAI_API,
    GOD_RPAI_PORT,
    learn_from_input,
    render_god_rpai_page_html,
    rpai_dashboard_payload,
)

_STATIC = Path(__file__).resolve().parent / "static"
_STATIC_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
    ".zip": "application/zip",
}
_BRAND_PATHS = {
    "/god_banner.jpg": "god_banner.jpg",
    "/banner.jpg": "god_banner.jpg",
    "/favicon.ico": "god_favicon.ico",
    "/favicon.png": "god_favicon.png",
    "/apple-touch-icon.png": "god_apple_touch.png",
    "/god_icon.png": "god_icon.png",
    "/logo_transparent.png": "god_icon.png",
    "/logo.png": "god_icon.png",
    "/static/banner.jpg": "god_banner.jpg",
    "/static/god_icon.png": "god_icon.png",
    "/static/data_path_motif.svg": "data_path_motif.svg",
}


def _send_file(handler: BaseHTTPRequestHandler, dest: Path) -> bool:
    if not dest.is_file():
        return False
    data = dest.read_bytes()
    ctype = _STATIC_TYPES.get(dest.suffix.lower(), "application/octet-stream")
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "public, max-age=3600")
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(data)
    return True


CORS_HEADERS = (
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, Cookie"),
    ("Access-Control-Expose-Headers", "Set-Cookie"),
)


def _cors(handler: BaseHTTPRequestHandler) -> None:
    for key, value in CORS_HEADERS:
        handler.send_header(key, value)


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps({k: v for k, v in payload.items() if k != "state"}).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _cors(handler)
    extra = payload.get("cookie")
    if extra:
        handler.send_header("Set-Cookie", str(extra))
    handler.end_headers()
    handler.wfile.write(body)


class GodRpaiHandler(BaseHTTPRequestHandler):
    """Shipped :1474 handler — rpAI only."""

    server_version = "GOD-rpAI/1474"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8", errors="replace") or "{}")
        except json.JSONDecodeError:
            form = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
            return {k: (v[0] if v else "") for k, v in form.items()}
        return data if isinstance(data, dict) else {}

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        _cors(self)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path in ("/api/grok-construe/start", "/api/grok-construe/start/"):
            try:
                from grok_construe import start_construe
            except ImportError:  # pragma: no cover
                from status_page.grok_construe import start_construe  # type: ignore
            _json(self, 200, start_construe())
            return
        if path in ("/api/grok-construe/status", "/api/grok-construe/status/"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                from grok_construe import construe_status
            except ImportError:  # pragma: no cover
                from status_page.grok_construe import construe_status  # type: ignore
            _json(self, 200, construe_status((qs.get("state") or [""])[0]))
            return
        if path in ("/api/grok-construe/callback", "/api/grok-construe/callback/"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                from grok_construe import complete_construe
            except ImportError:  # pragma: no cover
                from status_page.grok_construe import complete_construe  # type: ignore
            result = complete_construe(
                (qs.get("state") or [""])[0],
                code=(qs.get("code") or [""])[0],
            )
            _json(self, 200, result)
            return
        if path in ("/health", "/health/"):
            _json(self, 200, {"ok": True, "who": "GOD", "port": GOD_RPAI_PORT})
            return
        if path in (GOD_RPAI_API, GOD_RPAI_API + "/", "/api/rpai/"):
            _json(self, 200, rpai_dashboard_payload())
            return
        if path in ("/api/god-build", "/api/god-build/"):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            job_id = (qs.get("id") or [""])[0]
            tick = (qs.get("tick") or [""])[0] in ("1", "true", "yes")
            try:
                from god_build import get_suite_build, tick_suite_build
            except ImportError:  # pragma: no cover
                from status_page.god_build import (  # type: ignore
                    get_suite_build,
                    tick_suite_build,
                )
            if tick:
                result = tick_suite_build(job_id)
            else:
                result = get_suite_build(job_id)
            _json(self, 200 if result.get("ok") else 404, result)
            return
        if path in ("/", "/index.html", "/god", "/god/"):
            page = render_god_rpai_page_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        brand = _BRAND_PATHS.get(path)
        if brand:
            dest = (_STATIC / brand).resolve()
            if dest.parent == _STATIC.resolve() and _send_file(self, dest):
                return
        if path.startswith("/static/"):
            name = Path(path).name
            dest = (_STATIC / name).resolve()
            if dest.parent == _STATIC.resolve() and _send_file(self, dest):
                return
        if path in (
            "/support/goal-builder.zip",
            "/support/goal-package",
            "/downloads/goal-builder.zip",
        ) or path.startswith("/downloads/goal-builder/"):
            os_name = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("os", [""])[0]
            if "/downloads/goal-builder/" in path:
                os_name = Path(path).stem
            try:
                from goal_builder import goal_builder_zip_bytes
            except ImportError:  # pragma: no cover
                from status_page.goal_builder import goal_builder_zip_bytes  # type: ignore
            blob = goal_builder_zip_bytes()
            fname = f"goal-builder-{os_name}.zip" if os_name else "goal-builder.zip"
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(blob)
            return
        self.send_error(404, "rpAI only")

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        payload = self._read_json()
        if path in ("/support/god-ask", "/support/god-ask/", "/ask", "/ask/"):
            try:
                from god_support import answer_god_question
            except ImportError:  # pragma: no cover
                from status_page.god_support import answer_god_question  # type: ignore
            result = answer_god_question(str(payload.get("question") or ""))
            _json(self, 200 if result.get("ok") else 400, result)
            return
        if path in ("/support/goal-build", "/support/goal-build/", "/goal", "/goal/"):
            try:
                from goal_builder import submit_goal_builder
            except ImportError:  # pragma: no cover
                from status_page.goal_builder import submit_goal_builder  # type: ignore
            result = submit_goal_builder(
                payload,
                cookie=self.headers.get("Cookie") or "",
                authorization=self.headers.get("Authorization") or "",
                token=str(payload.get("token") or payload.get("x_construe_token") or ""),
            )
            _json(self, 200 if result.get("ok") else 400, result)
            return
        if path in (GOD_LEARN_PATH, GOD_LEARN_PATH + "/", "/learn", "/learn/"):
            result = learn_from_input(payload)
            _json(self, 200 if result.get("ok") else 400, result)
            return
        if path in ("/api/god-build", "/api/god-build/", "/god-build"):
            try:
                from god_build import start_suite_build
            except ImportError:  # pragma: no cover
                from status_page.god_build import start_suite_build  # type: ignore
            result = start_suite_build(
                device=str(payload.get("device") or ""),
                brief=str(payload.get("brief") or ""),
                user_agent=str(payload.get("user_agent") or ""),
                cookie=self.headers.get("Cookie") or "",
                authorization=self.headers.get("Authorization") or "",
                token=str(payload.get("token") or payload.get("x_construe_token") or ""),
            )
            _json(self, 200 if result.get("ok") else 400, result)
            return
        self.send_error(404, "rpAI only")


def make_god_server(host: str = "127.0.0.1", port: int = GOD_HTTP_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), GodRpaiHandler)


def serve_god_port(host: str = "127.0.0.1", port: int = GOD_HTTP_PORT) -> None:
    httpd = make_god_server(host, port)
    httpd.serve_forever()


if __name__ == "__main__":
    serve_god_port()
