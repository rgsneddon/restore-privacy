#!/usr/bin/env python3
"""Upload Stripe-ready brand icon/logo PNGs via Files API.

Reads assets from payments.stripe_brand_asset_paths(). Requires STRIPE_SECRET_KEY.

Attempts to attach files as account branding + colours; platform accounts often
get HTTP 403 on POST /v1/account (connected-accounts only). File upload still
succeeds — finish attach in Dashboard → Branding if so.

Usage:
  export STRIPE_SECRET_KEY=sk_live_...
  python scripts/upload_stripe_branding_assets.py
  python scripts/upload_stripe_branding_assets.py --out /tmp/stripe_brand_upload.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from payments import (  # noqa: E402
    STRIPE_BRAND_PRIMARY_COLOR,
    STRIPE_BRAND_SECONDARY_COLOR,
    stripe_brand_asset_constraints_ok,
    stripe_brand_asset_paths,
    stripe_secret_key,
)


def _multipart_file(path: Path, purpose: str, secret: str) -> dict[str, Any]:
    boundary = "----RptStripeBrandBoundary9k"
    data = path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="purpose"\r\n\r\n'
        f"{purpose}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://files.stripe.com/v1/files",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "restore-privacy-stripe-brand-upload/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {
            "error": True,
            "status": exc.code,
            "body": exc.read().decode("utf-8", errors="replace")[:800],
        }


def _form_post(path: str, form: dict[str, str], secret: str) -> dict[str, Any]:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        f"https://api.stripe.com/v1{path}",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "restore-privacy-stripe-brand-upload/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {
            "error": True,
            "status": exc.code,
            "body": exc.read().decode("utf-8", errors="replace")[:800],
        }


def _get(path: str, secret: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"https://api.stripe.com/v1{path}",
        headers={"Authorization": f"Bearer {secret}"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    secret = stripe_secret_key() or os.environ.get("STRIPE_SECRET_KEY", "").strip()
    paths = stripe_brand_asset_paths()
    summary: dict[str, Any] = {
        "secret_present": bool(secret),
        "constraints": {
            "icon": stripe_brand_asset_constraints_ok(
                paths["icon"], require_square=True, require_transparent=True
            ),
            "logo": stripe_brand_asset_constraints_ok(
                paths["logo"], require_square=False, require_transparent=True
            ),
        },
        "uploads": {},
        "attach": None,
        "readback": None,
        "dashboard_url": "https://dashboard.stripe.com/settings/branding",
        "colours": {
            "primary": STRIPE_BRAND_PRIMARY_COLOR,
            "secondary": STRIPE_BRAND_SECONDARY_COLOR,
        },
    }
    if not secret:
        summary["ok"] = False
        summary["error"] = "STRIPE_SECRET_KEY not set"
        text = json.dumps(summary, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 2

    for key, purpose in (("icon", "business_icon"), ("logo", "business_logo")):
        path = paths[key]
        up = _multipart_file(path, purpose, secret)
        summary["uploads"][key] = {
            "local": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "purpose": purpose,
            "id": up.get("id"),
            "size": up.get("size"),
            "error": up.get("error"),
            "status": up.get("status"),
            "body": up.get("body"),
        }

    icon_id = (summary["uploads"].get("icon") or {}).get("id")
    logo_id = (summary["uploads"].get("logo") or {}).get("id")
    if icon_id and logo_id:
        att = _form_post(
            "/account",
            {
                "settings[branding][icon]": str(icon_id),
                "settings[branding][logo]": str(logo_id),
                "settings[branding][primary_color]": STRIPE_BRAND_PRIMARY_COLOR,
                "settings[branding][secondary_color]": STRIPE_BRAND_SECONDARY_COLOR,
            },
            secret,
        )
        summary["attach"] = {
            "error": att.get("error"),
            "status": att.get("status"),
            "body": att.get("body"),
            "branding": ((att.get("settings") or {}).get("branding") if not att.get("error") else None),
            "hint": (
                "If status=403, open Dashboard → Branding and upload "
                f"{paths['icon'].name} / {paths['logo'].name}; set colours "
                f"{STRIPE_BRAND_PRIMARY_COLOR} / {STRIPE_BRAND_SECONDARY_COLOR}."
            ),
        }

    try:
        acc = _get("/account", secret)
        brand = (acc.get("settings") or {}).get("branding") or {}
        summary["readback"] = {
            "account_id": acc.get("id"),
            "logo": brand.get("logo"),
            "icon": brand.get("icon"),
            "primary_color": brand.get("primary_color"),
            "secondary_color": brand.get("secondary_color"),
        }
    except Exception as exc:  # noqa: BLE001
        summary["readback"] = {"error": str(exc)}

    uploads_ok = bool(icon_id and logo_id)
    attach_ok = bool(summary.get("attach") and not summary["attach"].get("error"))
    summary["ok"] = uploads_ok
    summary["branding_attached"] = attach_ok
    text = json.dumps(summary, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0 if uploads_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
