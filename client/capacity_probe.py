"""Private residual capacity probes (fail-soft; never invent utilization).

When ``RPT_CAPACITY_TOKEN`` (and optional probe URL map) is configured, clients
may fetch per-peer utilization from a **private** node endpoint and inject the
map into capacity-aware residual selection. Missing config or probe errors leave
that host unknown (no forced migration).

Honesty: not multi-VPS consensus load balancing; timeout-bounded best-effort.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.parse import urlparse

# Optional shared secret for private capacity endpoint.
ENV_CAPACITY_TOKEN = "RPT_CAPACITY_TOKEN"
# JSON object: {"82.221.101.241": "http://82.221.101.241:8080/api/private/capacity", ...}
# or comma list of base URLs; host is derived from URL netloc when map keys missing.
ENV_CAPACITY_PROBE_URLS = "RPT_CAPACITY_PROBE_URLS"
ENV_CAPACITY_PROBE_TIMEOUT = "RPT_CAPACITY_PROBE_TIMEOUT"
DEFAULT_PROBE_TIMEOUT = 1.5
DEFAULT_UI_PORT = 8080
PRIVATE_CAPACITY_PATH = "/api/private/capacity"

# Injectable transport: (url, headers, timeout_s) -> body text
TransportFn = Callable[[str, dict[str, str], float], str]


def parse_private_capacity_payload(
    raw: Any,
    *,
    default_host: str = "",
) -> tuple[str | None, float | None]:
    """Parse private capacity JSON → (host, utilization) or (None, None).

    Accepts utilization directly, or live/capacity counts. Does **not** invent
    values when fields are missing or invalid.
    """
    data: Any = raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None, None
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None, None
    if not isinstance(data, Mapping):
        return None, None

    host = str(data.get("host") or default_host or "").strip() or None

    util: float | None = None
    if "utilization" in data and data.get("utilization") is not None:
        try:
            util = float(data["utilization"])
        except (TypeError, ValueError):
            util = None
    elif data.get("live") is not None and data.get("capacity") is not None:
        try:
            live = max(0, int(data["live"]))
            cap = max(1, int(data["capacity"]))
            util = live / float(cap)
        except (TypeError, ValueError):
            util = None

    if util is None:
        return host, None
    if util < 0.0:
        util = 0.0
    if util > 1.0:
        util = 1.0
    return host, float(util)


def capacity_token_from_env(env: Mapping[str, str] | None = None) -> str:
    e = env if env is not None else os.environ
    return str(e.get(ENV_CAPACITY_TOKEN, "") or "").strip()


def probe_timeout_seconds(env: Mapping[str, str] | None = None) -> float:
    e = env if env is not None else os.environ
    raw = str(e.get(ENV_CAPACITY_PROBE_TIMEOUT, "") or "").strip()
    if not raw:
        return DEFAULT_PROBE_TIMEOUT
    try:
        t = float(raw)
    except ValueError:
        return DEFAULT_PROBE_TIMEOUT
    if t <= 0:
        return DEFAULT_PROBE_TIMEOUT
    return min(t, 10.0)


def parse_probe_url_map(
    raw: str | None,
    *,
    catalog_hosts: Sequence[str] | None = None,
) -> dict[str, str]:
    """Build host → private capacity URL map from env JSON or defaults."""
    text = (raw or "").strip()
    out: dict[str, str] = {}
    if text:
        if text.startswith("{"):
            try:
                blob = json.loads(text)
            except json.JSONDecodeError:
                blob = None
            if isinstance(blob, dict):
                for k, v in blob.items():
                    host = str(k or "").strip()
                    url = str(v or "").strip()
                    if host and url:
                        out[host] = url
        else:
            # Comma-separated full URLs
            for part in text.split(","):
                url = part.strip()
                if not url:
                    continue
                try:
                    p = urlparse(url)
                    host = (p.hostname or "").strip()
                except Exception:  # noqa: BLE001
                    host = ""
                if host:
                    out[host] = url
    if out:
        return out
    # Default: catalog residual hosts → http://host:8080/api/private/capacity
    hosts = list(catalog_hosts or [])
    if not hosts:
        try:
            from client.multihop import PRODUCT_COUNTRY_CATALOG

            hosts = [n.host for n in PRODUCT_COUNTRY_CATALOG if getattr(n, "host", None)]
        except Exception:  # noqa: BLE001
            hosts = []
    for h in hosts:
        hh = (h or "").strip()
        if hh and hh not in out:
            out[hh] = f"http://{hh}:{DEFAULT_UI_PORT}{PRIVATE_CAPACITY_PATH}"
    return out


def default_http_transport(url: str, headers: dict[str, str], timeout_s: float) -> str:
    """urllib GET; raises on HTTP/network errors (caller fail-softs)."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def probe_one_peer(
    url: str,
    *,
    token: str,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT,
    transport: TransportFn | None = None,
    default_host: str = "",
) -> tuple[str | None, float | None]:
    """Probe one private capacity URL. Errors → (None, None) fail-soft."""
    if not (url or "").strip() or not (token or "").strip():
        return None, None
    headers = {
        "Authorization": f"Bearer {token}",
        "X-RPT-Capacity-Token": token,
        "Accept": "application/json",
    }
    fn = transport or default_http_transport
    try:
        body = fn(url.strip(), headers, float(timeout_s))
    except Exception:  # noqa: BLE001 — fail-soft
        return None, None
    return parse_private_capacity_payload(body, default_host=default_host)


def probe_peer_capacity_map(
    *,
    env: Mapping[str, str] | None = None,
    catalog_hosts: Sequence[str] | None = None,
    transport: TransportFn | None = None,
    timeout_s: float | None = None,
    url_map: dict[str, str] | None = None,
) -> dict[str, float]:
    """Best-effort host → utilization for residual selection.

    - No token → empty map (no migration from probes).
    - Probe failure for a host → host omitted (unknown; never invent load).
    """
    e = env if env is not None else os.environ
    token = capacity_token_from_env(e)
    if not token:
        return {}
    urls = url_map if url_map is not None else parse_probe_url_map(
        str(e.get(ENV_CAPACITY_PROBE_URLS, "") or ""),
        catalog_hosts=catalog_hosts,
    )
    if not urls:
        return {}
    t = float(timeout_s) if timeout_s is not None else probe_timeout_seconds(e)
    out: dict[str, float] = {}
    for host, url in urls.items():
        h_default = (host or "").strip()
        got_host, util = probe_one_peer(
            url,
            token=token,
            timeout_s=t,
            transport=transport,
            default_host=h_default,
        )
        if util is None:
            continue
        key = (got_host or h_default or "").strip()
        if not key:
            continue
        out[key] = float(util)
    return out


def public_status_forbids_capacity_fields(payload: Mapping[str, Any] | None) -> bool:
    """Structural honesty helper: public filter must leave only title."""
    from node.aggregate_metrics import filter_public_status

    dirty = dict(payload or {})
    dirty.setdefault("title", "RESTORE PRIVACY")
    dirty.update(
        {
            "utilization": 0.9,
            "live": 12,
            "capacity": 100,
            "active_sessions": 12,
            "clients_connected": 12,
        }
    )
    clean = filter_public_status(dirty)
    return set(clean.keys()) == {"title"} and "utilization" not in clean
