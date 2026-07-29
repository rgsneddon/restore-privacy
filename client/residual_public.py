"""Public residual peer labels vs private dial hosts.

Connect/HELLO still use real catalog monopin IPv4 constants. User-facing UI,
support logs, and public status surfaces must show country/code only — never
plain residual peer IPs. Admin fleet views may still show hosts.

Honesty: binaries may still contain dial constants (recoverable by reverse
engineering). This module is presentation hygiene against casual scrapers and
user-visible leaks, not a claim that IPs are unrecoverable.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

# Residual monopin IPv4s shipped in catalog (keep in sync with multihop/endpoint).
# Listed here as well so redaction works even if multihop import fails on status host.
_FALLBACK_MONOPIN_HOSTS: tuple[str, ...] = (
    "82.221.101.241",  # IS
    "178.105.187.178",  # DE
    "5.161.242.85",  # US
    # Retired monopin hosts — still redact if they appear in old logs/strings
    "185.146.232.107",  # former RO
    "167.233.224.5",  # former DE
)

# IPv4 dotted-quad (for generic residual host redaction when known monopin).
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
)


def residual_monopin_hosts() -> frozenset[str]:
    """All residual catalog monopin IPv4s (dial constants)."""
    hosts: set[str] = set(_FALLBACK_MONOPIN_HOSTS)
    try:
        from client.multihop import product_country_catalog

        for n in product_country_catalog():
            h = str(getattr(n, "host", "") or "").strip()
            if h:
                hosts.add(h)
    except Exception:  # noqa: BLE001
        pass
    try:
        from client.endpoint import PRODUCT_NODE_HOST

        if PRODUCT_NODE_HOST:
            hosts.add(str(PRODUCT_NODE_HOST).strip())
    except Exception:  # noqa: BLE001
        pass
    return frozenset(h for h in hosts if h)


def is_residual_monopin_host(host: str | None) -> bool:
    """True when *host* is a catalog residual monopin (exact IPv4 match)."""
    h = (host or "").strip()
    if not h:
        return False
    # Strip optional :port
    if ":" in h and h.count(":") == 1:
        # host:port (not IPv6)
        left, right = h.rsplit(":", 1)
        if right.isdigit():
            h = left
    return h in residual_monopin_hosts()


def public_label_for_code(code: str | None, *, name: str | None = None) -> str:
    """User-facing peer label: ``Iceland (IS)`` — never an IP."""
    c = (code or "").strip().upper()
    if not c:
        return "VPN node"
    if name and str(name).strip():
        return f"{str(name).strip()} ({c})"
    try:
        from client.multihop import country_node_for_code

        n = country_node_for_code(c)
        nm = str(getattr(n, "name", "") or "").strip()
        if nm:
            return f"{nm} ({c})"
    except Exception:  # noqa: BLE001
        pass
    return c


def public_label_for_host(host: str | None) -> str:
    """Map monopin host → public country label; unknown host → ``VPN node``."""
    h = (host or "").strip()
    if not h:
        return "VPN node"
    if ":" in h and h.count(":") == 1:
        left, right = h.rsplit(":", 1)
        if right.isdigit():
            h = left
    try:
        from client.multihop import product_country_catalog

        for n in product_country_catalog():
            if str(getattr(n, "host", "") or "").strip() == h:
                return public_label_for_code(
                    getattr(n, "code", None), name=getattr(n, "name", None)
                )
    except Exception:  # noqa: BLE001
        pass
    if is_residual_monopin_host(h):
        return "VPN node"
    # Non-catalog host: do not echo raw IP in public strings
    if _IPV4_RE.fullmatch(h):
        return "VPN node"
    return "VPN node"


def redact_residual_hosts_in_text(text: str | None) -> str:
    """Replace known residual monopin IPv4s (and host:port) with public labels."""
    s = str(text or "")
    if not s:
        return ""
    # Longest hosts first; replace host:port then bare host
    hosts = sorted(residual_monopin_hosts(), key=len, reverse=True)
    for host in hosts:
        label = public_label_for_host(host)
        # host:port forms
        s = re.sub(
            re.escape(host) + r":\d+",
            label,
            s,
        )
        s = s.replace(host, label)
    return s


def public_country_option_dict(
    *,
    code: str,
    name: str,
    flag: str = "",
    host: str = "",
    admin: bool = False,
) -> dict[str, str]:
    """Serialize a catalog row for UI/JSON.

    Non-admin: never includes residual monopin *host*. Admin may include host.
    """
    out: dict[str, str] = {
        "code": (code or "").strip().upper(),
        "name": (name or "").strip() or (code or "").strip().upper(),
        "flag": (flag or "").strip(),
        "label": public_label_for_code(code, name=name),
    }
    if admin and (host or "").strip():
        out["host"] = str(host).strip()
    return out


def public_catalog_peers(*, admin: bool = False) -> list[dict[str, Any]]:
    """Catalog peers for public JSON (no hosts) or admin (with hosts)."""
    try:
        from client.multihop import product_country_catalog

        cat = product_country_catalog()
    except Exception:  # noqa: BLE001
        cat = ()
    out: list[dict[str, Any]] = []
    for n in cat:
        code = str(getattr(n, "code", "") or "").strip().upper()
        name = str(getattr(n, "name", "") or "").strip()
        host = str(getattr(n, "host", "") or "").strip()
        port = int(getattr(n, "port", 44044) or 44044)
        if not code:
            continue
        row: dict[str, Any] = {
            "code": code,
            "name": name or code,
            "port": port,
            "label": public_label_for_code(code, name=name),
        }
        if admin and host:
            row["host"] = host
        out.append(row)
    return out


def redact_mapping_values(
    data: Mapping[str, Any] | None,
    *,
    keys_always_redact: Sequence[str] = (
        "host",
        "node_host",
        "residual_host",
        "entry_host",
        "exit_host",
        "server_host",
        "url",
    ),
) -> dict[str, Any]:
    """Deep-ish redact of known host keys and monopin IPs in string values."""
    if not data:
        return {}
    out: dict[str, Any] = {}
    key_set = {k.lower() for k in keys_always_redact}
    for k, v in data.items():
        key = str(k)
        kl = key.lower()
        if isinstance(v, Mapping):
            out[key] = redact_mapping_values(v, keys_always_redact=keys_always_redact)
        elif isinstance(v, str):
            if kl in key_set or is_residual_monopin_host(v):
                # Prefer country label when host is a monopin
                if is_residual_monopin_host(v) or kl in key_set:
                    out[key] = public_label_for_host(v) if is_residual_monopin_host(v) else redact_residual_hosts_in_text(v)
                else:
                    out[key] = redact_residual_hosts_in_text(v)
            else:
                out[key] = redact_residual_hosts_in_text(v)
        elif isinstance(v, (list, tuple)):
            out[key] = [
                redact_residual_hosts_in_text(str(x))
                if isinstance(x, str)
                else x
                for x in v
            ]
        else:
            out[key] = v
    return out


def public_security_audit_payload(
    data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Strip monopin IPs from a security_audit_latest-style dict for public serve."""
    if not data:
        return {}
    # Shallow copy then targeted redaction
    blob = dict(data)
    if "node_host" in blob:
        blob["node_host"] = public_label_for_host(str(blob.get("node_host") or ""))
    for section in ("tcp_status", "udp", "http_status"):
        sec = blob.get(section)
        if isinstance(sec, dict):
            sec2 = dict(sec)
            if "host" in sec2:
                sec2["host"] = public_label_for_host(str(sec2.get("host") or ""))
            if "url" in sec2:
                sec2["url"] = redact_residual_hosts_in_text(str(sec2.get("url") or ""))
            blob[section] = sec2
    # Nested string walk for free-form reasons/messages
    return redact_mapping_values(blob)
