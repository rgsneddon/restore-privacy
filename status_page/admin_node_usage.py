"""Admin fleet node usage: bandwidth used vs capability (authenticated only).

Public status stays title-only. This module builds operator rows for **IS/DE**
(live residual catalog only) from the product country catalog and optional
private capacity probes. United States (US) and Romania (RO) are **retired**
and must not appear as live fleet peers.

Limits are **per-peer** (from ``node.private_capacity``):
  - **Bandwidth** — IS/DE product **unlimited-class** (extendable at cost; DE has
    30 TB class entitlement). Not auto-detected NIC line-rate.
  - **Session soft max** — utilization / residual routing hint (IS **512**;
    DE dedicated 8 vCPU / 32 GB → **1024**). Not a hard public admission lock.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

ENV_CAPACITY_TOKEN = "RPT_CAPACITY_TOKEN"
ENV_BANDWIDTH_CAP_MAP = "RPT_BANDWIDTH_CAP_BPS_MAP"  # JSON host→bps or code→bps
ENV_SESSION_SOFT_MAX_MAP = "RPT_SESSION_SOFT_MAX_MAP"  # JSON host/code → sessions
ENV_BANDWIDTH_CAP_DEFAULT = "RPT_NODE_BANDWIDTH_CAP_BPS"
ENV_PROBE_TIMEOUT = "RPT_CAPACITY_PROBE_TIMEOUT"
ENV_FLEET_REFRESH_MS = "RPT_ADMIN_FLEET_REFRESH_MS"
DEFAULT_PROBE_TIMEOUT = 2.0
DEFAULT_UI_PORT = 8080
DEFAULT_FLEET_REFRESH_MS = 5000  # real-time admin table poll
PRIVATE_CAPACITY_PATH = "/api/private/capacity"
FLEET_USAGE_API_PATH = "/admin/api/fleet-usage"
# Paid installer package host (Helsinki storage box) — load + disk only
PACKAGE_HOST_METRICS_PATH = "/api/private/host-metrics"
ENV_ASSET_TOKEN = "RPT_ASSET_FETCH_TOKEN"
ENV_VPS_ASSET_BASE = "RPT_VPS_ASSET_BASE"
ENV_PACKAGE_HOST_LABEL = "RPT_PACKAGE_HOST_LABEL"
DEFAULT_PACKAGE_HOST_BASE = "https://135.181.152.10.sslip.io"
DEFAULT_PACKAGE_HOST_LABEL = "Package store (HEL1)"

# Injectable: (url, headers, timeout_s) -> body text
TransportFn = Callable[[str, dict[str, str], float], str]


def _product_maps():
    """Lazy import product budgets from node.private_capacity (single source)."""
    try:
        from node.private_capacity import (
            DEFAULT_MAX_SESSIONS,
            DEFAULT_MAX_SESSIONS_DE,
            DEFAULT_MAX_SESSIONS_IS,
            DEFAULT_MAX_SESSIONS_US,
            PRODUCT_BANDWIDTH_CAP_BPS,
            PRODUCT_SESSION_SOFT_MAX,
            product_bandwidth_cap_bps,
            product_bandwidth_unlimited,
            product_session_soft_max,
        )
    except Exception:  # noqa: BLE001
        try:
            from private_capacity import (  # type: ignore
                DEFAULT_MAX_SESSIONS,
                DEFAULT_MAX_SESSIONS_DE,
                DEFAULT_MAX_SESSIONS_IS,
                DEFAULT_MAX_SESSIONS_US,
                PRODUCT_BANDWIDTH_CAP_BPS,
                PRODUCT_SESSION_SOFT_MAX,
                product_bandwidth_cap_bps,
                product_bandwidth_unlimited,
                product_session_soft_max,
            )
        except Exception:  # noqa: BLE001
            _MBPS = 1_000_000
            DEFAULT_MAX_SESSIONS = 256
            DEFAULT_MAX_SESSIONS_IS = 512
            DEFAULT_MAX_SESSIONS_US = 512
            DEFAULT_MAX_SESSIONS_DE = 1024
            PRODUCT_BANDWIDTH_CAP_BPS = {
                "US": 200 * _MBPS,
                "5.161.242.85": 200 * _MBPS,
            }
            PRODUCT_SESSION_SOFT_MAX = {
                "IS": 512,
                "US": 512,
                "DE": 1024,
                "82.221.101.241": 512,
                "5.161.242.85": 512,
                "178.105.187.178": 1024,
            }

            def product_bandwidth_unlimited(*, code: str = "", host: str = ""):
                c = (code or "").strip().upper()
                h = (host or "").strip()
                return c in {"IS", "DE"} or h in {
                    "82.221.101.241",
                    "178.105.187.178",
                }

            def product_bandwidth_cap_bps(*, code: str = "", host: str = ""):
                if product_bandwidth_unlimited(code=code, host=host):
                    return None
                for k in (code, host, code.upper()):
                    if k and k in PRODUCT_BANDWIDTH_CAP_BPS:
                        return PRODUCT_BANDWIDTH_CAP_BPS[k]
                return None

            def product_session_soft_max(*, code: str = "", host: str = ""):
                for k in (code, host, code.upper()):
                    if k and k in PRODUCT_SESSION_SOFT_MAX:
                        return PRODUCT_SESSION_SOFT_MAX[k]
                return None

    return {
        "DEFAULT_MAX_SESSIONS": DEFAULT_MAX_SESSIONS,
        "DEFAULT_MAX_SESSIONS_IS": DEFAULT_MAX_SESSIONS_IS,
        "DEFAULT_MAX_SESSIONS_US": DEFAULT_MAX_SESSIONS_US,
        "DEFAULT_MAX_SESSIONS_DE": DEFAULT_MAX_SESSIONS_DE,
        "PRODUCT_BANDWIDTH_CAP_BPS": PRODUCT_BANDWIDTH_CAP_BPS,
        "PRODUCT_SESSION_SOFT_MAX": PRODUCT_SESSION_SOFT_MAX,
        "product_bandwidth_cap_bps": product_bandwidth_cap_bps,
        "product_bandwidth_unlimited": product_bandwidth_unlimited,
        "product_session_soft_max": product_session_soft_max,
    }


@dataclass(frozen=True)
class NodeUsageRow:
    """One residual peer row for the admin fleet panel."""

    code: str
    name: str
    host: str
    port: int
    # Bandwidth focus
    bandwidth_used_bps: float | None  # average bits/s since process start when known
    bandwidth_cap_bps: int | None
    bandwidth_util: float | None  # used/cap in [0,1] when both known
    bytes_relayed: int | None
    uptime_sec: int | None
    # Session soft capacity (secondary)
    sessions_live: int | None
    sessions_cap: int | None
    session_util: float | None
    status: str  # ok | unknown | error
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "bandwidth_used_bps": self.bandwidth_used_bps,
            "bandwidth_cap_bps": self.bandwidth_cap_bps,
            "bandwidth_util": self.bandwidth_util,
            "bytes_relayed": self.bytes_relayed,
            "uptime_sec": self.uptime_sec,
            "sessions_live": self.sessions_live,
            "sessions_cap": self.sessions_cap,
            "session_util": self.session_util,
            "status": self.status,
            "detail": self.detail,
            # Preformatted cells for live UI refresh
            "bandwidth_used_display": format_bps(self.bandwidth_used_bps),
            "bandwidth_cap_display": format_bandwidth_cap(
                self.bandwidth_cap_bps, code=self.code, host=self.host
            ),
            "bandwidth_util_display": format_pct(self.bandwidth_util),
            "bytes_relayed_display": format_bytes(self.bytes_relayed),
            "sessions_display": format_sessions(
                self.sessions_live, self.sessions_cap, self.session_util
            ),
        }


def product_catalog_peers() -> list[dict[str, Any]]:
    """Residual catalog peers (code, name, host, port) in product order."""
    try:
        from client.multihop import product_country_catalog

        cat = product_country_catalog()
    except Exception:  # noqa: BLE001
        # Minimal fallback if client tree unavailable on status host
        return [
            {"code": "IS", "name": "Iceland", "host": "82.221.101.241", "port": 44044},
            {"code": "DE", "name": "Germany", "host": "178.105.187.178", "port": 44044},
        ]
    out: list[dict[str, Any]] = []
    for n in cat:
        out.append(
            {
                "code": str(getattr(n, "code", "") or "").strip().upper(),
                "name": str(getattr(n, "name", "") or "").strip(),
                "host": str(getattr(n, "host", "") or "").strip(),
                "port": int(getattr(n, "port", 44044) or 44044),
            }
        )
    return [p for p in out if p["code"] and p["host"]]


def parse_int_map(raw: str | None) -> dict[str, int]:
    """Parse JSON map of host or country code → positive int."""
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(blob, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in blob.items():
        key = str(k or "").strip()
        if not key:
            continue
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[key] = n
            out[key.upper()] = n
    return out


def parse_bandwidth_cap_map(raw: str | None) -> dict[str, int]:
    """Parse JSON map of host or country code → bps capability."""
    return parse_int_map(raw)


def resolve_bandwidth_cap_bps(
    *,
    code: str,
    host: str,
    env: Mapping[str, str] | None = None,
    caps: Mapping[str, int] | None = None,
) -> int | None:
    """Resolve operator bandwidth budget for a peer.

    Priority: env map (host/code) → product peer allowance.
    Product: IS/DE unlimited-class (None); US 200 Mbps.
    Status host flat ``RPT_NODE_BANDWIDTH_CAP_BPS`` alone does **not** pin every
    peer — that would re-impose a single budget on unlimited-class IS/DE.
    """
    e = env if env is not None else os.environ
    m = dict(caps) if caps is not None else parse_bandwidth_cap_map(
        e.get(ENV_BANDWIDTH_CAP_MAP, "")
    )
    for key in (host, code, code.upper(), host.strip()):
        if key in m:
            v = int(m[key])
            # 0 in map → unlimited-class for that peer
            return v if v > 0 else None
    maps = _product_maps()
    # Product unlimited-class wins over a legacy global default env
    if maps["product_bandwidth_unlimited"](code=code, host=host):
        return None
    prod = maps["product_bandwidth_cap_bps"](code=code, host=host)
    if prod is not None:
        return prod
    raw = str(e.get(ENV_BANDWIDTH_CAP_DEFAULT, "") or "").strip()
    if raw and raw.lower() not in ("0", "unlimited", "none", "-"):
        try:
            n = int(raw)
            if n > 0:
                return n
        except ValueError:
            pass
    return None


def resolve_session_soft_max(
    *,
    code: str,
    host: str,
    env: Mapping[str, str] | None = None,
    caps: Mapping[str, int] | None = None,
) -> int:
    """Resolve session soft max for a peer (DE 1024; IS 512; live catalog).

    Priority: ``RPT_SESSION_SOFT_MAX_MAP`` → product map → base 256.
    """
    e = env if env is not None else os.environ
    m = dict(caps) if caps is not None else parse_int_map(
        e.get(ENV_SESSION_SOFT_MAX_MAP, "")
    )
    for key in (host, code, code.upper(), host.strip()):
        if key in m and m[key] > 0:
            return max(1, int(m[key]))
    maps = _product_maps()
    prod = maps["product_session_soft_max"](code=code, host=host)
    if prod is not None:
        return max(1, int(prod))
    return max(1, int(maps["DEFAULT_MAX_SESSIONS"]))


def average_bps_from_bytes(
    total_bytes: int | None,
    uptime_sec: int | None,
) -> float | None:
    """Average bits/s over process uptime (not instantaneous NIC rate)."""
    if total_bytes is None or uptime_sec is None:
        return None
    b = max(0, int(total_bytes))
    u = max(0, int(uptime_sec))
    if u <= 0:
        return 0.0 if b == 0 else None
    return (b * 8.0) / float(u)


def bandwidth_utilization(
    used_bps: float | None,
    cap_bps: int | None,
) -> float | None:
    if used_bps is None or cap_bps is None or cap_bps <= 0:
        return None
    u = float(used_bps) / float(cap_bps)
    if u < 0.0:
        return 0.0
    if u > 1.0:
        return 1.0
    return u


def format_bps(bps: float | None) -> str:
    if bps is None:
        return "—"
    x = float(bps)
    if x < 1000:
        return f"{x:.0f} bps"
    if x < 1_000_000:
        return f"{x / 1000:.1f} kbps"
    if x < 1_000_000_000:
        return f"{x / 1_000_000:.2f} Mbps"
    return f"{x / 1_000_000_000:.2f} Gbps"


def format_bandwidth_cap(
    bps: int | float | None,
    *,
    code: str = "",
    host: str = "",
) -> str:
    """Display bandwidth capacity; product unlimited-class → ``unlimited``."""
    maps = _product_maps()
    if bps is None or (isinstance(bps, (int, float)) and bps <= 0):
        if maps["product_bandwidth_unlimited"](code=code, host=host) or bps is None:
            # Unlimited-class peers, or no budget set
            if maps["product_bandwidth_unlimited"](code=code, host=host):
                return "unlimited"
            return "—"
    return format_bps(float(bps) if bps is not None else None)


def format_bytes(n: int | None) -> str:
    if n is None:
        return "—"
    v = float(max(0, int(n)))
    for unit, div in (("B", 1), ("KiB", 1024), ("MiB", 1024**2), ("GiB", 1024**3)):
        if v < 1024 or unit == "GiB":
            if unit == "B":
                return f"{int(v)} {unit}"
            return f"{v:.1f} {unit}"
        v /= 1024.0
    return f"{int(n)} B"


def format_pct(util: float | None) -> str:
    if util is None:
        return "—"
    return f"{100.0 * float(util):.1f}%"


def format_sessions(
    live: int | None,
    cap: int | None,
    util: float | None = None,
) -> str:
    if live is not None and cap is not None:
        s = f"{live}/{cap}"
        if util is not None:
            s += f" ({format_pct(util)})"
        return s
    if cap is not None:
        return f"—/{cap}"
    return "—"


def fleet_refresh_interval_ms(env: Mapping[str, str] | None = None) -> int:
    """Admin table poll interval (ms). Min 2000 so probes are not a stampede."""
    e = env if env is not None else os.environ
    raw = str(e.get(ENV_FLEET_REFRESH_MS, "") or "").strip()
    if raw:
        try:
            n = int(raw)
            return max(2000, min(n, 120_000))
        except ValueError:
            pass
    return DEFAULT_FLEET_REFRESH_MS


def row_from_probe_payload(
    peer: Mapping[str, Any],
    payload: Mapping[str, Any] | None,
    *,
    bandwidth_cap_bps: int | None = None,
    sessions_cap: int | None = None,
    status: str = "ok",
    detail: str = "",
) -> NodeUsageRow:
    """Pure: build a NodeUsageRow from catalog peer + private capacity JSON."""
    code = str(peer.get("code") or "").strip().upper()
    name = str(peer.get("name") or code).strip()
    host = str(peer.get("host") or "").strip()
    port = int(peer.get("port") or 44044)
    # Product / map soft max is the admin budget column (peers differ)
    product_sess = sessions_cap
    if product_sess is None:
        product_sess = resolve_session_soft_max(code=code, host=host)

    if payload is None:
        return NodeUsageRow(
            code=code,
            name=name,
            host=host,
            port=port,
            bandwidth_used_bps=None,
            bandwidth_cap_bps=bandwidth_cap_bps,
            bandwidth_util=None,
            bytes_relayed=None,
            uptime_sec=None,
            sessions_live=None,
            sessions_cap=product_sess,
            session_util=None,
            status=status if status != "ok" else "unknown",
            detail=detail or "no probe data",
        )

    bi = payload.get("total_bytes_in")
    bo = payload.get("total_bytes_out")
    br = payload.get("total_bytes_relayed")
    try:
        bytes_relayed = (
            int(br)
            if br is not None
            else (
                (int(bi or 0) + int(bo or 0))
                if bi is not None or bo is not None
                else None
            )
        )
    except (TypeError, ValueError):
        bytes_relayed = None
    try:
        uptime = (
            int(payload["process_uptime_sec"])
            if payload.get("process_uptime_sec") is not None
            else None
        )
    except (TypeError, ValueError):
        uptime = None
    used_bps = average_bps_from_bytes(bytes_relayed, uptime)
    maps = _product_maps()
    unlimited = maps["product_bandwidth_unlimited"](code=code, host=host)
    cap = bandwidth_cap_bps
    # Product unlimited-class (IS/DE): do not re-pin a legacy node-reported Mbps budget
    if unlimited:
        cap = None
    elif cap is None and payload.get("bandwidth_cap_bps") is not None:
        try:
            cap = int(payload["bandwidth_cap_bps"])
        except (TypeError, ValueError):
            cap = None
    bw_util = bandwidth_utilization(used_bps, cap)

    sess_live = None
    sess_cap = product_sess
    sess_util = None
    extra_detail = detail
    try:
        if payload.get("live") is not None:
            sess_live = max(0, int(payload["live"]))
        node_cap = None
        if payload.get("capacity") is not None:
            node_cap = max(1, int(payload["capacity"]))
        # Prefer product soft max (IS 512, DE 1024) even when a node still has
        # a flat env of 256; note node-reported capacity when it differs.
        if node_cap is not None and product_sess is not None and node_cap != product_sess:
            note = f"node reports capacity={node_cap}"
            extra_detail = f"{extra_detail}; {note}" if extra_detail else note
        if sess_live is not None and sess_cap is not None:
            sess_util = min(1.0, sess_live / float(sess_cap))
        elif payload.get("utilization") is not None and sess_live is None:
            sess_util = float(payload["utilization"])
    except (TypeError, ValueError):
        pass

    st = status
    if st == "ok" and used_bps is None and sess_live is None:
        st = "unknown"
        extra_detail = extra_detail or "probe missing bandwidth and session fields"

    return NodeUsageRow(
        code=code,
        name=name,
        host=host,
        port=port,
        bandwidth_used_bps=used_bps,
        bandwidth_cap_bps=cap,
        bandwidth_util=bw_util,
        bytes_relayed=bytes_relayed,
        uptime_sec=uptime,
        sessions_live=sess_live,
        sessions_cap=sess_cap,
        session_util=sess_util,
        status=st,
        detail=extra_detail,
    )


def build_fleet_usage_rows(
    *,
    probes_by_host: Mapping[str, Mapping[str, Any] | None] | None = None,
    peers: Sequence[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
    errors_by_host: Mapping[str, str] | None = None,
) -> list[NodeUsageRow]:
    """Pure: one row per catalog peer using optional probe map."""
    catalog = list(peers) if peers is not None else product_catalog_peers()
    probes = dict(probes_by_host or {})
    errs = dict(errors_by_host or {})
    e = env if env is not None else os.environ
    bw_caps = parse_bandwidth_cap_map(e.get(ENV_BANDWIDTH_CAP_MAP, ""))
    sess_caps = parse_int_map(e.get(ENV_SESSION_SOFT_MAX_MAP, ""))
    rows: list[NodeUsageRow] = []
    for p in catalog:
        host = str(p.get("host") or "").strip()
        code = str(p.get("code") or "").strip().upper()
        bw_cap = resolve_bandwidth_cap_bps(
            code=code, host=host, env=e, caps=bw_caps
        )
        sess_cap = resolve_session_soft_max(
            code=code, host=host, env=e, caps=sess_caps
        )
        payload = probes.get(host)
        if payload is None and code in probes:
            payload = probes.get(code)
        err = errs.get(host) or errs.get(code) or ""
        if payload is None and err:
            rows.append(
                row_from_probe_payload(
                    p,
                    None,
                    bandwidth_cap_bps=bw_cap,
                    sessions_cap=sess_cap,
                    status="error",
                    detail=err,
                )
            )
        elif payload is None:
            rows.append(
                row_from_probe_payload(
                    p,
                    None,
                    bandwidth_cap_bps=bw_cap,
                    sessions_cap=sess_cap,
                    status="unknown",
                    detail="not probed",
                )
            )
        else:
            rows.append(
                row_from_probe_payload(
                    p,
                    payload,
                    bandwidth_cap_bps=bw_cap,
                    sessions_cap=sess_cap,
                    status="ok",
                )
            )
    return rows


def _default_transport(url: str, headers: dict[str, str], timeout_s: float) -> str:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def private_capacity_url(host: str, *, ui_port: int = DEFAULT_UI_PORT) -> str:
    h = (host or "").strip()
    return f"http://{h}:{int(ui_port)}{PRIVATE_CAPACITY_PATH}"


def probe_peer_private_capacity(
    host: str,
    *,
    token: str,
    timeout_s: float = DEFAULT_PROBE_TIMEOUT,
    transport: TransportFn | None = None,
    ui_port: int = DEFAULT_UI_PORT,
) -> tuple[dict[str, Any] | None, str]:
    """HTTP probe private capacity; returns (payload, error_message)."""
    h = (host or "").strip()
    tok = (token or "").strip()
    if not h:
        return None, "missing host"
    if not tok:
        return None, "RPT_CAPACITY_TOKEN not set"
    url = private_capacity_url(h, ui_port=ui_port)
    headers = {
        "Authorization": f"Bearer {tok}",
        "X-RPT-Capacity-Token": tok,
        "Accept": "application/json",
    }
    fn = transport or _default_transport
    try:
        body = fn(url, headers, float(timeout_s))
        data = json.loads(body)
        if not isinstance(data, dict):
            return None, "invalid capacity JSON"
        return data, ""
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"unreachable ({exc.reason})"
    except TimeoutError:
        return None, "timeout"
    except json.JSONDecodeError:
        return None, "invalid JSON"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)[:120]


def collect_live_fleet_usage_rows(
    *,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
    peers: Sequence[Mapping[str, Any]] | None = None,
) -> list[NodeUsageRow]:
    """Probe each catalog peer (fail-soft) and build admin rows."""
    e = env if env is not None else os.environ
    token = str(e.get(ENV_CAPACITY_TOKEN, "") or "").strip()
    try:
        timeout = float(e.get(ENV_PROBE_TIMEOUT, "") or DEFAULT_PROBE_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_PROBE_TIMEOUT
    catalog = list(peers) if peers is not None else product_catalog_peers()
    probes: dict[str, Mapping[str, Any] | None] = {}
    errors: dict[str, str] = {}
    if not token:
        for p in catalog:
            errors[str(p.get("host") or "")] = "RPT_CAPACITY_TOKEN not set on status host"
        return build_fleet_usage_rows(
            probes_by_host=probes, peers=catalog, env=e, errors_by_host=errors
        )
    for p in catalog:
        host = str(p.get("host") or "").strip()
        payload, err = probe_peer_private_capacity(
            host, token=token, timeout_s=timeout, transport=transport
        )
        if payload is not None:
            probes[host] = payload
        else:
            errors[host] = err or "probe failed"
            probes[host] = None
    return build_fleet_usage_rows(
        probes_by_host=probes, peers=catalog, env=e, errors_by_host=errors
    )


@dataclass(frozen=True)
class PackageHostRow:
    """Installer package host (storage box): load + drive only — no paths."""

    id: str
    label: str
    host: str
    load_1: float | None
    load_5: float | None
    load_15: float | None
    disk_total_bytes: int | None
    disk_used_bytes: int | None
    disk_avail_bytes: int | None
    disk_util: float | None
    uptime_sec: int | None
    status: str  # ok | unknown | error
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Public row shape for admin JSON/HTML — never includes file paths."""
        return {
            "id": self.id,
            "label": self.label,
            "host": self.host,
            "load_1": self.load_1,
            "load_5": self.load_5,
            "load_15": self.load_15,
            "disk_total_bytes": self.disk_total_bytes,
            "disk_used_bytes": self.disk_used_bytes,
            "disk_avail_bytes": self.disk_avail_bytes,
            "disk_util": self.disk_util,
            "uptime_sec": self.uptime_sec,
            "status": self.status,
            "detail": self.detail,
            "load_display": format_load_triple(self.load_1, self.load_5, self.load_15),
            "disk_used_display": format_bytes(self.disk_used_bytes),
            "disk_total_display": format_bytes(self.disk_total_bytes),
            "disk_avail_display": format_bytes(self.disk_avail_bytes),
            "disk_util_display": format_pct(self.disk_util),
            "uptime_display": format_uptime(self.uptime_sec),
        }


def format_load_triple(
    a: float | None, b: float | None, c: float | None
) -> str:
    """Load averages 1/5/15 as a single cell."""
    parts: list[str] = []
    for x in (a, b, c):
        if x is None:
            parts.append("—")
        else:
            parts.append(f"{float(x):.2f}")
    if all(p == "—" for p in parts):
        return "—"
    return " / ".join(parts)


def format_uptime(sec: int | None) -> str:
    if sec is None:
        return "—"
    s = max(0, int(sec))
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def package_host_row_from_metrics(
    *,
    host_id: str = "pkg-store",
    label: str = DEFAULT_PACKAGE_HOST_LABEL,
    host: str = "",
    metrics: Mapping[str, Any] | None = None,
    status: str = "ok",
    detail: str = "",
) -> PackageHostRow:
    """Pure: build package-host row from host-metrics JSON (load + disk only)."""
    m = dict(metrics or {}) if metrics else {}
    if not metrics and status == "ok":
        status = "unknown"
        detail = detail or "no probe data"

    def _f(key: str) -> float | None:
        v = m.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _i(key: str) -> int | None:
        v = m.get(key)
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    load_1, load_5, load_15 = _f("load_1"), _f("load_5"), _f("load_15")
    disk_total = _i("disk_total_bytes")
    disk_used = _i("disk_used_bytes")
    disk_avail = _i("disk_avail_bytes")
    disk_util = _f("disk_util")
    if disk_util is None and disk_total and disk_total > 0 and disk_used is not None:
        disk_util = min(1.0, max(0.0, disk_used / float(disk_total)))
    uptime = _i("uptime_sec")

    st = status
    if st == "ok" and load_1 is None and disk_total is None:
        st = "unknown"
        detail = detail or "metrics empty"

    return PackageHostRow(
        id=str(host_id or "pkg-store"),
        label=str(label or DEFAULT_PACKAGE_HOST_LABEL),
        host=str(host or "").strip(),
        load_1=load_1,
        load_5=load_5,
        load_15=load_15,
        disk_total_bytes=disk_total,
        disk_used_bytes=disk_used,
        disk_avail_bytes=disk_avail,
        disk_util=disk_util,
        uptime_sec=uptime,
        status=st,
        detail=detail,
    )


def _resolve_package_host_token(env: Mapping[str, str] | None = None) -> str:
    """Asset token from *env*, process env, or admin processor store (same as payments)."""
    if env is not None:
        for key in (ENV_ASSET_TOKEN, "RPT_VPS_ASSET_TOKEN"):
            val = str(env.get(key, "") or "").strip()
            if val:
                return val
    for key in (ENV_ASSET_TOKEN, "RPT_VPS_ASSET_TOKEN"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    try:
        from payments import vps_asset_fetch_token
    except ImportError:  # pragma: no cover
        try:
            from status_page.payments import vps_asset_fetch_token  # type: ignore
        except ImportError:
            return ""
    try:
        return (vps_asset_fetch_token() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _resolve_package_host_asset_base(env: Mapping[str, str] | None = None) -> str:
    """``RPT_VPS_ASSET_BASE`` from *env*, process env, or processor store."""
    e = env if env is not None else {}
    raw = str(e.get(ENV_VPS_ASSET_BASE, "") or "").strip().rstrip("/")
    if raw:
        return raw
    try:
        from payments import vps_asset_base_url
    except ImportError:  # pragma: no cover
        try:
            from status_page.payments import vps_asset_base_url  # type: ignore
        except ImportError:
            vps_asset_base_url = None  # type: ignore
    if vps_asset_base_url is not None:
        try:
            raw = (vps_asset_base_url() or "").strip().rstrip("/")
            if raw:
                return raw
        except Exception:  # noqa: BLE001
            pass
    raw = (os.environ.get(ENV_VPS_ASSET_BASE) or "").strip().rstrip("/")
    return raw


def package_host_base_url(env: Mapping[str, str] | None = None) -> str:
    """Origin for the package store (no ``/paid-assets`` path suffix).

    Metrics live at ``{origin}/api/private/host-metrics`` on the store host
    (not under ``/paid-assets/…``). Accepts bases with or without that prefix.
    """
    raw = _resolve_package_host_asset_base(env)
    if raw:
        base = raw.rstrip("/")
        # Strip one or more trailing /paid-assets segments
        while base.endswith("/paid-assets"):
            base = base[: -len("/paid-assets")].rstrip("/")
        if base:
            return base
    return DEFAULT_PACKAGE_HOST_BASE


def package_host_metrics_url(env: Mapping[str, str] | None = None) -> str:
    return f"{package_host_base_url(env)}{PACKAGE_HOST_METRICS_PATH}"


def probe_package_host_metrics(
    *,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
    timeout_s: float | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Token-gated GET host-metrics on package store; (payload, error).

    Token and base URL resolve the same way as paid delivery: process env,
    then admin processor store (``vps_asset_fetch_token`` / ``vps_asset_base_url``).
    """
    e = env if env is not None else os.environ
    tok = _resolve_package_host_token(env)
    if not tok:
        return (
            None,
            "Package store token not configured "
            "(set RPT_ASSET_FETCH_TOKEN in admin Processors or host env)",
        )
    try:
        t = (
            float(timeout_s)
            if timeout_s is not None
            else float(
                (e.get(ENV_PROBE_TIMEOUT) if hasattr(e, "get") else None)
                or os.environ.get(ENV_PROBE_TIMEOUT, "")
                or DEFAULT_PROBE_TIMEOUT
            )
        )
    except ValueError:
        t = DEFAULT_PROBE_TIMEOUT
    url = package_host_metrics_url(env)
    headers = {
        "X-RPT-Asset-Token": tok,
        "Accept": "application/json",
        "User-Agent": "RestorePrivacy-admin-package-host/1",
    }
    fn = transport or _default_transport
    try:
        body = fn(url, headers, t)
        data = json.loads(body)
        if not isinstance(data, dict):
            return None, "invalid host-metrics JSON"
        return data, ""
    except urllib.error.HTTPError as exc:
        if int(getattr(exc, "code", 0) or 0) == 401:
            return None, "package store rejected asset token (HTTP 401)"
        if int(getattr(exc, "code", 0) or 0) == 404:
            return None, "host-metrics path not found on package store (HTTP 404)"
        return None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"unreachable ({exc.reason})"
    except TimeoutError:
        return None, "timeout"
    except json.JSONDecodeError:
        return None, "invalid JSON"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)[:120]


def collect_package_host_rows(
    *,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
    metrics: Mapping[str, Any] | None = None,
    error: str = "",
) -> list[PackageHostRow]:
    """One row for the configured package store host (or honest unavailable)."""
    e = env if env is not None else os.environ
    base = package_host_base_url(e)
    # Display host only (hostname), never full URL paths
    host_disp = base.replace("https://", "").replace("http://", "").split("/")[0]
    label = str(e.get(ENV_PACKAGE_HOST_LABEL, "") or "").strip() or DEFAULT_PACKAGE_HOST_LABEL
    if metrics is not None:
        return [
            package_host_row_from_metrics(
                host_id="pkg-store",
                label=label,
                host=host_disp,
                metrics=metrics,
                status="ok" if metrics.get("ok", True) else "unknown",
            )
        ]
    if error:
        return [
            package_host_row_from_metrics(
                host_id="pkg-store",
                label=label,
                host=host_disp,
                metrics=None,
                status="error",
                detail=error,
            )
        ]
    payload, err = probe_package_host_metrics(env=e, transport=transport)
    if payload is not None:
        return [
            package_host_row_from_metrics(
                host_id="pkg-store",
                label=label,
                host=host_disp,
                metrics=payload,
                status="ok" if payload.get("ok", True) else "unknown",
            )
        ]
    return [
        package_host_row_from_metrics(
            host_id="pkg-store",
            label=label,
            host=host_disp,
            metrics=None,
            status="error" if err else "unknown",
            detail=err or "not probed",
        )
    ]


def fleet_usage_json_payload(
    rows: Sequence[NodeUsageRow] | None = None,
    *,
    live: bool = True,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
    package_host_rows: Sequence[PackageHostRow] | None = None,
) -> dict[str, Any]:
    """JSON for authenticated ``GET /admin/api/fleet-usage`` (live refresh)."""
    if rows is None and live:
        try:
            row_list = collect_live_fleet_usage_rows(env=env, transport=transport)
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:120]
            row_list = build_fleet_usage_rows(
                peers=product_catalog_peers(),
                env=env,
                errors_by_host={p["host"]: err for p in product_catalog_peers()},
            )
    elif rows is None:
        row_list = build_fleet_usage_rows(peers=product_catalog_peers(), env=env)
    else:
        row_list = list(rows)

    if package_host_rows is not None:
        pkg_rows = list(package_host_rows)
    elif live:
        try:
            pkg_rows = collect_package_host_rows(env=env, transport=transport)
        except Exception as exc:  # noqa: BLE001
            pkg_rows = collect_package_host_rows(
                env=env, error=str(exc)[:120]
            )
    else:
        pkg_rows = collect_package_host_rows(env=env, error="not probed")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "refreshed_at": now,
        "refresh_ms": fleet_refresh_interval_ms(env),
        "rows": [r.to_dict() for r in row_list],
        "package_hosts": [r.to_dict() for r in pkg_rows],
    }


def render_package_host_usage_section_html(
    rows: Sequence[PackageHostRow] | None = None,
    *,
    live: bool = True,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
) -> str:
    """Second fleet table: package-store host load + drive (no paths/filenames)."""
    if rows is None and live:
        try:
            row_list = collect_package_host_rows(env=env, transport=transport)
        except Exception as exc:  # noqa: BLE001
            row_list = collect_package_host_rows(env=env, error=str(exc)[:120])
    elif rows is None:
        row_list = collect_package_host_rows(env=env, error="not probed")
    else:
        row_list = list(rows)

    body_rows: list[str] = []
    for r in row_list:
        badge = {"ok": "ok", "unknown": "bad", "error": "bad"}.get(r.status, "bad")
        rid = _escape(r.id)
        detail = _escape(r.detail) if r.detail else ""
        d = r.to_dict()
        body_rows.append(
            "<tr>"
            f"<td><strong id=\"admin-pkg-label-{rid}\">{_escape(r.label)}</strong></td>"
            f"<td><code id=\"admin-pkg-host-{rid}\">{_escape(r.host)}</code></td>"
            f"<td id=\"admin-pkg-load-{rid}\">{_escape(d['load_display'])}</td>"
            f"<td id=\"admin-pkg-disk-used-{rid}\">{_escape(d['disk_used_display'])}</td>"
            f"<td id=\"admin-pkg-disk-total-{rid}\">{_escape(d['disk_total_display'])}</td>"
            f"<td id=\"admin-pkg-disk-avail-{rid}\">{_escape(d['disk_avail_display'])}</td>"
            f"<td id=\"admin-pkg-disk-util-{rid}\">{_escape(d['disk_util_display'])}</td>"
            f"<td id=\"admin-pkg-uptime-{rid}\">{_escape(d['uptime_display'])}</td>"
            f'<td><span class="badge {badge}" id="admin-pkg-status-{rid}">'
            f"{_escape(r.status)}</span>"
            f"<br/><span class=\"muted\" id=\"admin-pkg-detail-{rid}\">{detail}</span>"
            f"</td>"
            "</tr>"
        )
    table = (
        "\n".join(body_rows)
        if body_rows
        else '<tr><td colspan="9">No package host configured</td></tr>'
    )
    return f"""
<section id="admin-package-host-usage" class="card"
         aria-labelledby="admin-package-host-usage-heading"
         data-admin-package-host-usage="1">
  <h2 id="admin-package-host-usage-heading">Installer package host (storage)</h2>
  <p class="muted" id="admin-package-host-usage-blurb">
  Server(s) that hold paid installer packages (storage box).
  <strong>Load</strong> and <strong>drive</strong> utilisation only —
  no file paths, package directories, or filenames.
  Refreshes with the residual fleet table.
  </p>
  <table id="admin-package-host-usage-table">
    <thead><tr>
      <th>Role</th><th>Host</th>
      <th>Load (1 / 5 / 15)</th>
      <th>Disk used</th><th>Disk total</th><th>Disk free</th><th>Disk util</th>
      <th>Uptime</th><th>Status</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
</section>
"""


def render_admin_node_usage_section_html(
    rows: Sequence[NodeUsageRow] | None = None,
    *,
    live: bool = True,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
    top_link_html: str = "",
    package_host_rows: Sequence[PackageHostRow] | None = None,
) -> str:
    """HTML section: fleet bandwidth used vs capability (admin only)."""
    if rows is None and live:
        try:
            row_list = collect_live_fleet_usage_rows(env=env, transport=transport)
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:120]
            row_list = build_fleet_usage_rows(
                peers=product_catalog_peers(),
                env=env,
                errors_by_host={
                    p["host"]: err for p in product_catalog_peers()
                },
            )
    elif rows is None:
        row_list = build_fleet_usage_rows(peers=product_catalog_peers(), env=env)
    else:
        row_list = list(rows)

    refresh_ms = fleet_refresh_interval_ms(env)

    body_rows: list[str] = []
    for r in row_list:
        badge = {
            "ok": "ok",
            "unknown": "bad",
            "error": "bad",
        }.get(r.status, "bad")
        used_s = format_bps(r.bandwidth_used_bps)
        cap_s = format_bandwidth_cap(
            r.bandwidth_cap_bps, code=r.code, host=r.host
        )
        util_s = format_pct(r.bandwidth_util)
        bytes_s = format_bytes(r.bytes_relayed)
        sess_s = format_sessions(r.sessions_live, r.sessions_cap, r.session_util)
        detail = _escape(r.detail) if r.detail else ""
        code_e = _escape(r.code)
        # Node column: short label only (code + name) — no long why blurb
        body_rows.append(
            "<tr>"
            f"<td><strong>{code_e}</strong><br/>"
            f"<span class=\"muted\">{_escape(r.name)}</span>"
            f"</td>"
            f"<td><code>{_escape(r.host)}</code></td>"
            f"<td id=\"admin-node-bw-used-{code_e}\">{_escape(used_s)}</td>"
            f"<td id=\"admin-node-bw-cap-{code_e}\">{_escape(cap_s)}</td>"
            f"<td id=\"admin-node-bw-util-{code_e}\">{_escape(util_s)}</td>"
            f"<td id=\"admin-node-bytes-{code_e}\">{_escape(bytes_s)}</td>"
            f"<td id=\"admin-node-sess-{code_e}\">{_escape(sess_s)}</td>"
            f'<td><span class="badge {badge}" '
            f'id="admin-node-status-{code_e}">{_escape(r.status)}</span>'
            f"{('<br/><span class=\"muted\" id=\"admin-node-detail-' + code_e + '\">' + detail + '</span>') if detail else ('<br/><span class=\"muted\" id=\"admin-node-detail-' + code_e + '\"></span>')}"
            f"</td>"
            "</tr>"
        )
    table = (
        "\n".join(body_rows)
        if body_rows
        else '<tr><td colspan="8">No catalog peers</td></tr>'
    )
    top = top_link_html or (
        '<p class="admin-top-link">'
        '<a href="#admin-heading" class="admin-top-link-a">^top</a></p>\n'
    )
    pkg_html = render_package_host_usage_section_html(
        package_host_rows,
        live=live,
        env=env,
        transport=transport,
    )

    return f"""
<section id="admin-node-usage" class="card" aria-labelledby="admin-node-usage-heading"
         data-admin-node-usage="1"
         data-fleet-refresh-ms="{refresh_ms}"
         data-fleet-usage-api="{FLEET_USAGE_API_PATH}">
  <h2 id="admin-node-usage-heading">Fleet node usage (bandwidth)</h2>
  <p class="muted" id="admin-node-usage-probe-note">
  Live residual peers <strong>IS</strong> (Iceland) and <strong>DE</strong> (Germany) only —
  US and RO are retired. Bandwidth capability is product
  <strong>unlimited-class</strong> for both (extendable at cost); session soft max
  IS&nbsp;512 / DE&nbsp;1024. Avg used rate from private probes; table refreshes
  about every {refresh_ms // 1000}s
  (<span id="admin-node-usage-refreshed">—</span>). Not on the public shop.
  </p>
  <table id="admin-node-usage-table">
    <thead><tr>
      <th>Node</th><th>Host</th>
      <th>Used (avg)</th><th>Capacity</th><th>Util %</th>
      <th>Bytes relayed</th><th>Sessions</th><th>Status</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
{pkg_html}
{top}<script id="admin-fleet-usage-script" src="/static/admin_fleet_usage.js"></script>
</section>
"""


def _escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
