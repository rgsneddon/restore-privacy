"""Admin fleet node usage: bandwidth used vs capability (authenticated only).

Public status stays title-only. This module builds operator rows for IS/RO/US
from the product country catalog and optional private capacity probes.

Limits are **per-peer**:
  - **Bandwidth** — IS/RO product **unlimited-class** (extendable at cost); US fixed
    200 Mbps product budget. Not auto-detected NIC line-rate.
  - **Session soft max** — utilization / residual routing hint (RO 256, IS 512 so
    Iceland > Romania; US 512). Not a hard public admission lock.
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

# Injectable: (url, headers, timeout_s) -> body text
TransportFn = Callable[[str, dict[str, str], float], str]


def _product_maps():
    """Lazy import product budgets from node.private_capacity (single source)."""
    try:
        from node.private_capacity import (
            DEFAULT_MAX_SESSIONS,
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
            PRODUCT_BANDWIDTH_CAP_BPS = {
                "US": 200 * _MBPS,
                "5.161.242.85": 200 * _MBPS,
            }
            PRODUCT_SESSION_SOFT_MAX = {
                "RO": 256,
                "IS": 512,
                "US": 512,
                "185.146.232.107": 256,
                "82.221.101.241": 512,
                "5.161.242.85": 512,
            }

            def product_bandwidth_unlimited(*, code: str = "", host: str = ""):
                c = (code or "").strip().upper()
                h = (host or "").strip()
                return c in {"IS", "RO"} or h in {
                    "82.221.101.241",
                    "185.146.232.107",
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
            {"code": "RO", "name": "Romania", "host": "185.146.232.107", "port": 44044},
            {"code": "US", "name": "United States", "host": "5.161.242.85", "port": 44044},
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
    Product: IS/RO unlimited-class (None); US 200 Mbps.
    Status host flat ``RPT_NODE_BANDWIDTH_CAP_BPS`` alone does **not** pin every
    peer — that would re-impose a single budget on unlimited-class IS/RO.
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
    """Resolve session soft max for a peer (IS > RO; US = 512).

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
    # Product unlimited-class (IS/RO): do not re-pin a legacy node-reported Mbps budget
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
        # Prefer product soft max so US is 2× IS/RO even when a node still has
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


def fleet_usage_json_payload(
    rows: Sequence[NodeUsageRow] | None = None,
    *,
    live: bool = True,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
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
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "refreshed_at": now,
        "refresh_ms": fleet_refresh_interval_ms(env),
        "rows": [r.to_dict() for r in row_list],
    }


def render_admin_node_usage_section_html(
    rows: Sequence[NodeUsageRow] | None = None,
    *,
    live: bool = True,
    env: Mapping[str, str] | None = None,
    transport: TransportFn | None = None,
    top_link_html: str = "",
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

    return f"""
<section id="admin-node-usage" class="card" aria-labelledby="admin-node-usage-heading"
         data-admin-node-usage="1"
         data-fleet-refresh-ms="{refresh_ms}"
         data-fleet-usage-api="{FLEET_USAGE_API_PATH}">
  <h2 id="admin-node-usage-heading">Fleet node usage (bandwidth)</h2>
  <p class="muted" id="admin-node-usage-probe-note">
  Residual peers (IS / RO / US). Avg used rate from private probes; table refreshes
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
