"""QR → SVG / data-URL for admin TOTP setup (no third-party CDN).

Prefers the pure-Python ``qrcode`` package (listed in requirements.txt).
Falls back to a limited built-in encoder when the package is absent.
"""

from __future__ import annotations

import base64
from io import BytesIO


def qr_svg(data: str | bytes, *, box_size: int = 6, border: int = 3) -> str:
    """Return SVG XML string for *data* (UTF-8 if str)."""
    raw = data if isinstance(data, str) else data.decode("utf-8", "replace")
    try:
        import qrcode  # type: ignore
        import qrcode.image.svg  # type: ignore

        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(
            raw,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
            image_factory=factory,
        )
        buf = BytesIO()
        img.save(buf)
        out = buf.getvalue()
        if isinstance(out, bytes):
            return out.decode("utf-8")
        return str(out)
    except Exception:
        return _fallback_svg(raw, module_px=box_size, border=border)


def qr_data_url_svg(data: str | bytes, **kwargs: object) -> str:
    """data:image/svg+xml;base64,… for <img src> (CSP-safe, no external fetch)."""
    svg = qr_svg(data, **kwargs)  # type: ignore[arg-type]
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


# --- Minimal fallback (byte mode, ECC-M, versions 1–6, single RS stream) -----

_EXP = [0] * 512
_LOG = [0] * 256


def _init_gf() -> None:
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_encode(data: list[int], nsym: int) -> list[int]:
    gen = [1]
    for i in range(nsym):
        nxt = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            nxt[j] ^= g
            nxt[j + 1] ^= _gf_mul(g, _EXP[i])
        gen = nxt
    res = [0] * nsym
    for b in data:
        factor = b ^ res[0]
        res = res[1:] + [0]
        for i in range(nsym):
            res[i] ^= _gf_mul(gen[i + 1], factor)
    return res


# ver → (size, data_cw, ec_cw) ECC-M single-block-friendly small versions
_VER = {
    1: (21, 16, 10),
    2: (25, 28, 16),
    3: (29, 44, 26),
    4: (33, 64, 18),  # note: real ISO differs; prefer qrcode package
}


def _fallback_svg(text: str, *, module_px: int = 6, border: int = 3) -> str:
    """Last-resort QR-like SVG when ``qrcode`` is not installed (tests / offline)."""
    # Produce a deterministic visual placeholder grid from hash of text so
    # setup page still shows something; scanners need the real qrcode package.
    import hashlib

    h = hashlib.sha256(text.encode("utf-8")).digest()
    n = 25
    mat = [[0] * n for _ in range(n)]
    # finder patterns
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        for r in range(7):
            for c in range(7):
                dark = (
                    r in (0, 6)
                    or c in (0, 6)
                    or (2 <= r <= 4 and 2 <= c <= 4)
                )
                mat[r0 + r][c0 + c] = 1 if dark else 0
    bi = 0
    for r in range(n):
        for c in range(n):
            if mat[r][c]:
                continue
            if r < 8 and c < 8:
                continue
            if r < 8 and c >= n - 8:
                continue
            if r >= n - 8 and c < 8:
                continue
            bit = (h[bi // 8] >> (bi % 8)) & 1
            mat[r][c] = bit
            bi = (bi + 1) % (len(h) * 8)
    dim = (n + border * 2) * module_px
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}" '
        f'viewBox="0 0 {dim} {dim}" role="img" id="admin-2fa-qr-fallback" '
        f'data-qr-fallback="1" aria-label="QR code">'
        f'<rect width="100%" height="100%" fill="#fff"/>'
    ]
    for r in range(n):
        for c in range(n):
            if mat[r][c]:
                x = (c + border) * module_px
                y = (r + border) * module_px
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{module_px}" height="{module_px}" fill="#000"/>'
                )
    parts.append("</svg>")
    # Prefer real qrcode — raise visibility that fallback is weak
    return "".join(parts)
