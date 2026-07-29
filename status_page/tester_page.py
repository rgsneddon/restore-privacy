"""Unlinked app-tester page: licence accept → one-package one-month mint.

Direct URL only (``/app-testers``). Not linked from homepage, downloads, footer,
or public chrome. After the tester checks that they have read the full licence
and disclaimer, they may mint **one** catalog platform via the existing
one-month tester mint path (download token + KEYGEN). A durable claim keyed by
HTTP-only cookie refuses a second package.
"""

from __future__ import annotations

import html
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

# Public paths (direct URL only — do not add to public nav/footer)
TESTER_PAGE_PATH = "/app-testers"
TESTER_MINT_PATH = "/app-testers/mint"
TESTER_ALREADY_PATH = "/app-testers/already-used"
TESTER_COOKIE = "rpt_app_tester_claim"
CLAIM_COOKIE_MAX_AGE = 86400 * 400  # ~13 months (covers one-month test + return)

# User-facing refusal (objective typo "trsters" → "testers")
ALREADY_USED_MESSAGE = (
    "You have already generated a testers link and keygen, "
    "please use that to test the Restore Privacy VPN."
)

ACCEPT_FIELD = "read_licence_fully"
PLATFORM_FIELD = "platform"

CATALOG_PLATFORMS: tuple[tuple[str, str], ...] = (
    ("windows", "Windows"),
    ("android", "Android"),
    ("macos", "macOS"),
    ("linux", "Linux"),
    ("ios", "iOS"),
)


def tester_page_paths() -> frozenset[str]:
    """All HTTP paths served by the app-tester flow."""
    return frozenset(
        {
            TESTER_PAGE_PATH,
            TESTER_PAGE_PATH + "/",
            TESTER_MINT_PATH,
            TESTER_MINT_PATH + "/",
            TESTER_ALREADY_PATH,
            TESTER_ALREADY_PATH + "/",
        }
    )


def normalize_tester_path(path: str) -> str:
    p = (path or "").strip() or "/"
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    return p


def is_tester_page_path(path: str) -> bool:
    return normalize_tester_path(path) in {
        TESTER_PAGE_PATH,
        TESTER_MINT_PATH,
        TESTER_ALREADY_PATH,
    }


def _db_path() -> Path:
    """SQLite file next to payment DB (durable on Render disk when configured)."""
    try:
        from payments import db_path as payment_db_path

        parent = Path(payment_db_path()).parent
    except Exception:  # noqa: BLE001
        raw = os.environ.get("RPT_PAYMENT_DATA_DIR", "").strip()
        parent = Path(raw) if raw else Path.home() / ".restore-privacy" / "payment"
    parent.mkdir(parents=True, exist_ok=True)
    return parent / "app_tester_claims.sqlite3"


def init_tester_claim_db() -> Path:
    path = _db_path()
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_tester_claims (
                claim_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                keygen TEXT NOT NULL DEFAULT '',
                download_url TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


def new_claim_id() -> str:
    return secrets.token_urlsafe(24)


def get_claim(claim_id: str | None) -> dict[str, Any] | None:
    """Return stored claim for *claim_id*, or None if never claimed."""
    cid = (claim_id or "").strip()
    if not cid:
        return None
    init_tester_claim_db()
    conn = sqlite3.connect(str(_db_path()))
    try:
        row = conn.execute(
            "SELECT claim_id, platform, session_id, keygen, download_url, "
            "filename, created_at FROM app_tester_claims WHERE claim_id = ?",
            (cid,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "claim_id": str(row[0]),
        "platform": str(row[1] or ""),
        "session_id": str(row[2] or ""),
        "keygen": str(row[3] or ""),
        "download_url": str(row[4] or ""),
        "filename": str(row[5] or ""),
        "created_at": float(row[6] or 0.0),
    }


def has_claimed(claim_id: str | None) -> bool:
    c = get_claim(claim_id)
    return bool(c and (c.get("platform") or "").strip())


def store_claim(
    claim_id: str,
    *,
    platform: str,
    session_id: str = "",
    keygen: str = "",
    download_url: str = "",
    filename: str = "",
    now: float | None = None,
) -> dict[str, Any]:
    """Persist a one-shot claim. Raises ValueError if claim already exists."""
    cid = (claim_id or "").strip()
    if not cid:
        raise ValueError("claim_id required")
    plat = (platform or "").strip().lower()
    if not plat:
        raise ValueError("platform required")
    if has_claimed(cid):
        raise ValueError("already_claimed")
    t = float(now if now is not None else time.time())
    init_tester_claim_db()
    conn = sqlite3.connect(str(_db_path()))
    try:
        conn.execute(
            "INSERT INTO app_tester_claims "
            "(claim_id, platform, session_id, keygen, download_url, filename, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                cid,
                plat,
                str(session_id or ""),
                str(keygen or ""),
                str(download_url or ""),
                str(filename or ""),
                t,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("already_claimed") from exc
    finally:
        conn.close()
    out = get_claim(cid)
    assert out is not None
    return out


def parse_cookie_header(header: str | None, name: str = TESTER_COOKIE) -> str | None:
    raw = header or ""
    want = (name or "").strip()
    if not want:
        return None
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        if k.strip() == want:
            return v.strip() or None
    return None


def format_claim_cookie(
    claim_id: str,
    *,
    max_age: int = CLAIM_COOKIE_MAX_AGE,
    secure: bool = True,
) -> str:
    """Set-Cookie value for the durable tester claim id."""
    cid = (claim_id or "").strip()
    if not cid:
        raise ValueError("empty claim_id")
    bits = [
        f"{TESTER_COOKIE}={cid}",
        "Path=/",
        f"Max-Age={int(max_age)}",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        bits.append("Secure")
    return "; ".join(bits)


def licence_and_disclaimer_text() -> str:
    """Full product licence + tester-specific disclaimer body (plain text)."""
    roots = [
        Path(__file__).resolve().parent / "public" / "LICENSE",
        Path(__file__).resolve().parents[1] / "LICENSE",
        Path(__file__).resolve().parent / "public" / "LICENCE",
    ]
    body = ""
    for p in roots:
        try:
            if p.is_file() and p.stat().st_size > 32:
                body = p.read_text(encoding="utf-8", errors="replace")
                break
        except OSError:
            continue
    if not body.strip():
        body = (
            "RESTORE PRIVACY — PROPRIETARY FULL COPYRIGHT LICENCE\n\n"
            "Copyright (c) 2026 Raskul / Restore Privacy. All rights reserved.\n"
            "This Software is licensed for end-user use only under the product "
            "licence terms distributed with the client packages. You may not "
            "redistribute, reverse engineer, or operate competing services from "
            "this product without written permission.\n"
        )
    disclaimer = """
-------------------------------------------------------------------------------
APP TESTER DISCLAIMER (one-month free tester programme)

By accepting below you confirm that:

1. You are an invited or intentional app tester of Restore Privacy VPN, not a
   substitute for a paid subscription for production use.
2. You receive a **one-month** tester grant and KEYGEN for **one** device package
   platform only. A second package selection for the same tester identity is
   refused.
3. Tester builds may be pre-release or catalog monopin builds; residual VPN
   behaviour, nodes, and host privacy posture are as described in product docs
   (no absolute anonymity or logging-free guarantee beyond published statements).
4. Download links are single-use status-host fulfilment tokens — not permanent
   public installer mirrors. KEYGEN unlocks Connect for the tester period only.
5. After the tester period ends, Connect is refused until a paid subscription
   or new authorised entitlement is obtained.
6. You have read the full licence agreement above and this disclaimer in full
   before generating a testers link and keygen.

"""
    return body.rstrip() + "\n" + disclaimer


def accept_checked(form: dict[str, list[str]] | None) -> bool:
    """True when the form asserts the user read the licence/disclaimer fully."""
    if not form:
        return False
    vals = form.get(ACCEPT_FIELD) or form.get("accept") or []
    for v in vals:
        s = str(v).strip().lower()
        if s in ("1", "on", "yes", "true", "checked"):
            return True
    return False


def selected_platform(form: dict[str, list[str]] | None) -> str:
    if not form:
        return ""
    vals = form.get(PLATFORM_FIELD) or []
    raw = str(vals[0] if vals else "").strip().lower()
    allowed = {p for p, _ in CATALOG_PLATFORMS}
    return raw if raw in allowed else ""


def parse_form_body(raw: bytes | str | None) -> dict[str, list[str]]:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    return parse_qs(text, keep_blank_values=True)


def mint_for_tester(
    platform: str,
    *,
    claim_id: str,
    accepted: bool,
    base_url: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Gate + one-shot mint. Pure decision + real payments mint.

    Returns:
      ``{"ok": True, ...mint fields, "claim_id": ...}``
      ``{"ok": False, "error": "not_accepted"|"already_claimed"|"bad_platform"|"mint_failed",
         "message": str}``
    """
    if not accepted:
        return {
            "ok": False,
            "error": "not_accepted",
            "message": "You must confirm you have read the licence and disclaimer fully.",
        }
    cid = (claim_id or "").strip()
    if not cid:
        return {
            "ok": False,
            "error": "missing_claim",
            "message": "Missing tester claim cookie — reload the page and try again.",
        }
    if has_claimed(cid):
        return {
            "ok": False,
            "error": "already_claimed",
            "message": ALREADY_USED_MESSAGE,
            "redirect": TESTER_ALREADY_PATH,
        }
    plat = (platform or "").strip().lower()
    allowed = {p for p, _ in CATALOG_PLATFORMS}
    if plat not in allowed:
        return {
            "ok": False,
            "error": "bad_platform",
            "message": "Choose one package platform.",
        }
    try:
        from payments import admin_mint_one_month_tester

        minted = admin_mint_one_month_tester(
            plat, now=now, base_url=base_url
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "mint_failed",
            "message": f"Could not generate tester grant: {exc}"[:240],
        }
    try:
        store_claim(
            cid,
            platform=plat,
            session_id=str(minted.get("session_id") or ""),
            keygen=str(minted.get("keygen") or ""),
            download_url=str(minted.get("download_url") or ""),
            filename=str(minted.get("filename") or ""),
            now=now,
        )
    except ValueError as exc:
        if "already_claimed" in str(exc):
            return {
                "ok": False,
                "error": "already_claimed",
                "message": ALREADY_USED_MESSAGE,
                "redirect": TESTER_ALREADY_PATH,
            }
        return {
            "ok": False,
            "error": "mint_failed",
            "message": str(exc)[:240],
        }
    out = dict(minted)
    out["ok"] = True
    out["claim_id"] = cid
    out["public_tester"] = True
    return out


def _css() -> str:
    return """
:root{--bg:#0a1628;--card:#0f2138;--text:#e8eef7;--muted:#94a3b8;--accent:#2694e8;
--ok:#22c55e;--warn:#fbbf24;--border:#1e3a5f}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
background:var(--bg);color:var(--text);line-height:1.5}
.wrap{max-width:46rem;margin:0 auto;padding:1.5rem 1.1rem 3rem}
h1{font-size:1.45rem;margin:0 0 0.5rem}
.lead{color:var(--muted);margin:0 0 1.25rem;font-size:0.95rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;
padding:1.1rem 1.15rem;margin:0 0 1.25rem}
.licence-scroll{max-height:22rem;overflow:auto;padding:0.85rem 1rem;
background:#07101c;border:1px solid var(--border);border-radius:10px;
white-space:pre-wrap;font-size:0.82rem;line-height:1.45;color:#dbeafe}
label.check{display:flex;gap:0.65rem;align-items:flex-start;margin:1rem 0;
font-size:0.95rem;cursor:pointer}
label.check input{margin-top:0.25rem;width:1.15rem;height:1.15rem;flex-shrink:0}
.gen{opacity:0.45;pointer-events:none;transition:opacity .15s}
.gen.enabled{opacity:1;pointer-events:auto}
.plats{display:flex;flex-direction:column;gap:0.55rem;margin:0.75rem 0 1rem}
.plats label{display:flex;gap:0.55rem;align-items:center;cursor:pointer}
button, .btn{appearance:none;border:0;border-radius:10px;padding:0.65rem 1.15rem;
background:var(--accent);color:#fff;font-weight:600;cursor:pointer;font-size:0.95rem}
button:disabled{opacity:0.4;cursor:not-allowed}
.err{color:#fca5a5;background:#3f1d1d;border:1px solid #7f1d1d;padding:0.75rem 1rem;
border-radius:10px;margin:0 0 1rem}
.okbox{background:#052e1a;border:1px solid #166534;border-radius:12px;padding:1.1rem}
.keygen{font-family:ui-monospace,Consolas,monospace;font-size:1.05rem;font-weight:700;
word-break:break-all;color:#fff;margin:0.5rem 0 1rem}
.dl a{color:#7dd3fc;font-weight:600}
.foot{margin-top:1.5rem;font-size:0.8rem;color:var(--muted)}
.refuse{font-size:1.05rem;font-weight:600;line-height:1.55;color:#fef3c7}
"""


def render_already_used_html() -> bytes:
    """HTTP body for the second-claim refusal page (bytes for Handler._send)."""
    msg = html.escape(ALREADY_USED_MESSAGE)
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex,nofollow"/>
<title>App tester — already used</title>
<style>{_css()}</style>
</head>
<body>
<main class="wrap">
  <h1>App tester</h1>
  <div class="card">
    <p class="refuse">{msg}</p>
  </div>
  <p class="foot">Restore Privacy — tester programme (not a public download page).</p>
</main>
</body>
</html>
"""
    return body.encode("utf-8")


def render_success_html(mint: dict[str, Any]) -> bytes:
    """HTTP body after a successful one-package mint (bytes for Handler._send)."""
    kg = html.escape(str(mint.get("keygen") or ""))
    url = html.escape(str(mint.get("download_url") or mint.get("download_path") or ""))
    plat = html.escape(str(mint.get("platform") or ""))
    fname = html.escape(str(mint.get("filename") or ""))
    unlock = html.escape(
        str(
            mint.get("unlock_instruction")
            or "Enter the KEYGEN in the client to unlock Connect."
        )
    )
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex,nofollow"/>
<title>App tester — your link and KEYGEN</title>
<style>{_css()}</style>
</head>
<body>
<main class="wrap">
  <h1>Your one-month tester grant</h1>
  <p class="lead">Platform: <strong>{plat}</strong> · Package: {fname}</p>
  <div class="okbox card">
    <p style="margin:0 0 0.35rem;color:#86efac;font-weight:600">KEYGEN</p>
    <p class="keygen" id="product-keygen">{kg}</p>
    <p class="dl" style="margin:0 0 0.75rem">
      <a href="{url}">Download installer (single-use link)</a>
    </p>
    <p style="margin:0;font-size:0.9rem;color:#bbf7d0">{unlock}</p>
  </div>
  <p class="foot">Save this KEYGEN. A second package cannot be generated for this tester identity.
  If you clear cookies you may appear as a new tester — that is not a multi-device entitlement.</p>
</main>
</body>
</html>
"""
    return body.encode("utf-8")


def render_tester_page_html(
    *,
    error: str = "",
    claim_already: bool = False,
) -> bytes:
    """Main gate page: scrollable licence + accept checkbox + gated generator.

    Returns **bytes** (utf-8) so ``Handler._send`` can write the body directly.
    """
    if claim_already:
        return render_already_used_html()
    lic = html.escape(licence_and_disclaimer_text())
    err = ""
    if error:
        err = f'<div class="err" role="alert">{html.escape(error)}</div>'
    opts = []
    for code, label in CATALOG_PLATFORMS:
        opts.append(
            f'<label><input type="radio" name="{PLATFORM_FIELD}" value="{code}" '
            f'required disabled class="plat-radio"/> {html.escape(label)}</label>'
        )
    platforms = "\n".join(opts)
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex,nofollow"/>
<title>Restore Privacy — app testers</title>
<style>{_css()}</style>
</head>
<body>
<main class="wrap">
  <h1>Restore Privacy — app testers</h1>
  <p class="lead">Read the full licence and tester disclaimer below. After you confirm
  you have read them fully, you may generate a <strong>one-month</strong> tester
  download link and KEYGEN for <strong>one</strong> package only.</p>
  {err}
  <div class="card">
    <h2 style="font-size:1.05rem;margin:0 0 0.65rem">Licence agreement &amp; disclaimer</h2>
    <div class="licence-scroll" id="licence-scroll" tabindex="0">{lic}</div>
    <form method="post" action="{TESTER_MINT_PATH}" id="tester-mint-form">
      <label class="check">
        <input type="checkbox" name="{ACCEPT_FIELD}" id="accept-box" value="1"/>
        <span>I have read the licence agreement and disclaimer <strong>fully</strong>
        (including all scrolled content) and accept them for this one-month tester grant.</span>
      </label>
      <div class="gen" id="generator">
        <p style="margin:0 0 0.4rem;font-weight:600">Select one package</p>
        <div class="plats">
          {platforms}
        </div>
        <button type="submit" id="mint-btn" disabled>Generate download link &amp; KEYGEN</button>
      </div>
    </form>
  </div>
  <p class="foot">This page is not linked from the public site. Direct URL only.
  Not a paid checkout — free one-month tester programme.</p>
</main>
<script>
(function(){{
  var box = document.getElementById('accept-box');
  var gen = document.getElementById('generator');
  var btn = document.getElementById('mint-btn');
  var radios = document.querySelectorAll('.plat-radio');
  function sync(){{
    var on = !!(box && box.checked);
    if (gen) gen.classList.toggle('enabled', on);
    radios.forEach(function(r){{ r.disabled = !on; }});
    if (btn) btn.disabled = !on;
  }}
  if (box) box.addEventListener('change', sync);
  sync();
}})();
</script>
</body>
</html>
"""
    return body.encode("utf-8")


def public_html_must_not_link_tester(html_src: str | bytes | None) -> bool:
    """True when *html_src* has no navigational href to the tester page.

    Route handlers may mention the path string; this checks **link** forms only
    so public HTML/nav does not advertise ``/app-testers``.
    """
    if html_src is None:
        return True
    if isinstance(html_src, bytes):
        try:
            text = html_src.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
    else:
        text = str(html_src)
    low = text.lower()
    needles = (
        'href="/app-testers"',
        "href='/app-testers'",
        'href="/app-testers/',
        "href='/app-testers/",
        'href=/app-testers',
        'href=/app-testers/',
        "action=\"/app-testers",
        "action='/app-testers",
    )
    return not any(n in low for n in needles)
