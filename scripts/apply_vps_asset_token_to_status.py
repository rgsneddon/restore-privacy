#!/usr/bin/env python3
"""Apply VPS RPT_ASSET_FETCH_TOKEN to the live status host via admin API.

Use after Render redeploy when processor_env.json was wiped (free tier disk).
Does not print the token. Reads from env or file:

  RPT_ASSET_FETCH_TOKEN or RPT_ASSET_TOKEN_FILE
  RPT_ADMIN_PASSWORD (default: empty → fail)
  RPT_STATUS_BASE (default https://restore-privacy-status.onrender.com)

Example:
  export RPT_ASSET_TOKEN_FILE=/path/to/token
  export RPT_ADMIN_PASSWORD=...
  python scripts/apply_vps_asset_token_to_status.py
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main() -> int:
    base = os.environ.get(
        "RPT_STATUS_BASE", "https://restore-privacy-status.onrender.com"
    ).rstrip("/")
    user = os.environ.get("RPT_ADMIN_USER", "admin").strip() or "admin"
    password = os.environ.get("RPT_ADMIN_PASSWORD", "").strip()
    token = os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip()
    tfile = os.environ.get("RPT_ASSET_TOKEN_FILE", "").strip()
    if not token and tfile and os.path.isfile(tfile):
        token = open(tfile, encoding="utf-8").read().strip()
    vps_base = os.environ.get(
        "RPT_VPS_ASSET_BASE", "http://82.221.101.241:8081/paid-assets"
    ).strip()
    if not password:
        print("BLOCKED: set RPT_ADMIN_PASSWORD", file=sys.stderr)
        return 2
    if not token:
        print("BLOCKED: set RPT_ASSET_FETCH_TOKEN or RPT_ASSET_TOKEN_FILE", file=sys.stderr)
        return 2

    # http.cookiejar handles Set-Cookie on 302 login (urllib default opener).
    jar = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(jar)

    def req(method: str, path: str, data: bytes | None = None, form: bool = False):
        headers = {"User-Agent": "rpt-apply-vps-token"}
        if form and data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        r = urllib.request.Request(
            base + path, data=data, method=method, headers=headers
        )
        try:
            with opener.open(r, timeout=60) as resp:
                body = resp.read()
                return resp.status, body
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    body = urllib.parse.urlencode(
        {"username": user, "password": password}
    ).encode()
    st, raw = req("POST", "/admin/login", body, form=True)
    cookies = list(jar.cookiejar)
    if st not in (200, 302) and not cookies:
        print("login failed", st, file=sys.stderr)
        return 1
    # Successful login redirects to /admin; a re-shown login form is failure.
    login_body = raw.decode("utf-8", "replace") if raw else ""
    if st == 200 and "Admin login" in login_body and not cookies:
        print("login failed (invalid credentials)", file=sys.stderr)
        return 1
    body = urllib.parse.urlencode(
        {
            "plugin_id": "vps_assets",
            "RPT_ASSET_FETCH_TOKEN": token,
            "RPT_VPS_ASSET_BASE": vps_base,
        }
    ).encode()
    st, raw = req("POST", "/admin/processors/apply", body, form=True)
    text = raw.decode("utf-8", "replace")
    ok = st == 200 and "Saved" in text
    print("apply_status", st, "saved", ok)
    if not ok:
        print(text[:300].replace(token, "[REDACTED]"), file=sys.stderr)
        return 1
    # health
    st, raw = req("GET", "/health/fulfilment")
    print("health", raw.decode("utf-8", "replace")[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
