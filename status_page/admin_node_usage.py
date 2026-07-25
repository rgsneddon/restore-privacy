"""Admin fleet node usage: bandwidth used vs capability (authenticated only).

Public status stays title-only. This module builds operator rows for IS/RO/DE
from the product country catalog and optional private capacity probes.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.parse import urlparse

ENV_CAPACITY_TOKEN = "RPT_CAPACITY_TOKEN"
ENV_BANDWIDTH_CAP_MAP = "RPT_BANDWIDTH_CAP_BPS_MAP"  # JSON host→bps or code→bps
ENV_BANDWIDTH_CAP_DEFAULT = "RPT_NODE_BANDWIDTH_CAP_BPS"
ENV_PROBE_TIMEOUT = "RPT_CAPACITY_PROBE_TIMEOUT"
DEFAULT_PROBE_TIMEOUT = 2.0
DEFAULT_UI_PORT = 8080
PRIVATE_CAPACITY_PATH = "/api/private/capacity"

# Injectable: (url, headers, timeout_s) -> body text
TransportFn = Callable[[str, dict[str, str], float], str]


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
            {"code": "DE", "name": "Germany", "host": "167.233.224.5", "port": 44044},
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


def parse_bandwidth_cap_map(raw: str | None) -> dict[str, int]:
    """Parse JSON map of host or country code → bps capability."""
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
            bps = int(v)
        except (TypeError, ValueError):
            continue
        if bps > 0:
            out[key] = bps
            out[key.upper()] = bps
    return out


def resolve_bandwidth_cap_bps(
    *,
    code: str,
    host: str,
    env: Mapping[str, str] | None = None,
    caps: Mapping[str, int] | None = None,
) -> int | None:
    e = env if env is not None else os.environ
    m = dict(caps) if caps is not None else parse_bandwidth_cap_map(
        e.get(ENV_BANDWIDTH_CAP_MAP, "")
    )
    for key in (host, code, code.upper(), host.strip()):
        if key in m and m[key] > 0:
            return int(m[key])
    raw = str(e.get(ENV_BANDWIDTH_CAP_DEFAULT, "") or "").strip()
    if raw:
        try:
            n = int(raw)
            return n if n > 0 else None
        except ValueError:
            return None
    return None


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


def row_from_probe_payload(
    peer: Mapping[str, Any],
    payload: Mapping[str, Any] | None,
    *,
    bandwidth_cap_bps: int | None = None,
    status: str = "ok",
    detail: str = "",
) -> NodeUsageRow:
    """Pure: build a NodeUsageRow from catalog peer + private capacity JSON."""
    code = str(peer.get("code") or "").strip().upper()
    name = str(peer.get("name") or code).strip()
    host = str(peer.get("host") or "").strip()
    port = int(peer.get("port") or 44044)
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
            sessions_cap=None,
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
    cap = bandwidth_cap_bps
    if cap is None and payload.get("bandwidth_cap_bps") is not None:
        try:
            cap = int(payload["bandwidth_cap_bps"])
        except (TypeError, ValueError):
            cap = None
    bw_util = bandwidth_utilization(used_bps, cap)

    sess_live = sess_cap = sess_util = None
    try:
        if payload.get("live") is not None:
            sess_live = max(0, int(payload["live"]))
        if payload.get("capacity") is not None:
            sess_cap = max(1, int(payload["capacity"]))
        if payload.get("utilization") is not None:
            sess_util = float(payload["utilization"])
        elif sess_live is not None and sess_cap is not None:
            sess_util = min(1.0, sess_live / float(sess_cap))
    except (TypeError, ValueError):
        pass

    st = status
    if st == "ok" and used_bps is None and sess_live is None:
        st = "unknown"
        detail = detail or "probe missing bandwidth and session fields"

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
        detail=detail,
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
    caps = parse_bandwidth_cap_map(e.get(ENV_BANDWIDTH_CAP_MAP, ""))
    rows: list[NodeUsageRow] = []
    for p in catalog:
        host = str(p.get("host") or "").strip()
        code = str(p.get("code") or "").strip().upper()
        cap = resolve_bandwidth_cap_bps(code=code, host=host, env=e, caps=caps)
        payload = probes.get(host)
        if payload is None and code in probes:
            payload = probes.get(code)
        err = errs.get(host) or errs.get(code) or ""
        if payload is None and err:
            rows.append(
                row_from_probe_payload(
                    p, None, bandwidth_cap_bps=cap, status="error", detail=err
                )
            )
        elif payload is None:
            rows.append(
                row_from_probe_payload(
                    p,
                    None,
                    bandwidth_cap_bps=cap,
                    status="unknown",
                    detail="not probed",
                )
            )
        else:
            rows.append(
                row_from_probe_payload(p, payload, bandwidth_cap_bps=cap, status="ok")
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

    body_rows: list[str] = []
    for r in row_list:
        badge = {
            "ok": "ok",
            "unknown": "bad",
            "error": "bad",
        }.get(r.status, "bad")
        used_s = format_bps(r.bandwidth_used_bps)
        cap_s = format_bps(
            float(r.bandwidth_cap_bps) if r.bandwidth_cap_bps is not None else None
        )
        util_s = format_pct(r.bandwidth_util)
        bytes_s = format_bytes(r.bytes_relayed)
        if r.sessions_live is not None and r.sessions_cap is not None:
            sess_s = f"{r.sessions_live}/{r.sessions_cap}"
            if r.session_util is not None:
                sess_s += f" ({format_pct(r.session_util)})"
        else:
            sess_s = "—"
        detail = _escape(r.detail) if r.detail else ""
        body_rows.append(
            "<tr>"
            f"<td><strong>{_escape(r.code)}</strong><br/>"
            f"<span class=\"muted\">{_escape(r.name)}</span></td>"
            f"<td><code>{_escape(r.host)}</code></td>"
            f"<td id=\"admin-node-bw-used-{_escape(r.code)}\">{_escape(used_s)}</td>"
            f"<td id=\"admin-node-bw-cap-{_escape(r.code)}\">{_escape(cap_s)}</td>"
            f"<td id=\"admin-node-bw-util-{_escape(r.code)}\">{_escape(util_s)}</td>"
            f"<td>{_escape(bytes_s)}</td>"
            f"<td>{_escape(sess_s)}</td>"
            f'<td><span class="badge {badge}" '
            f'id="admin-node-status-{_escape(r.code)}">{_escape(r.status)}</span>'
            f"{('<br/><span class=\"muted\">' + detail + '</span>') if detail else ''}"
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
         data-admin-node-usage="1">
  <h2 id="admin-node-usage-heading">Fleet node usage (bandwidth)</h2>
  <p class="muted" id="admin-node-usage-blurb">
  Residual catalog peers (IS / RO / DE). <strong>Bandwidth used</strong> is average
  process-wide relay rate since node start (bits/s from private counters).
  <strong>Capacity</strong> is operator-configured budget
  (<code>RPT_NODE_BANDWIDTH_CAP_BPS</code> or per-host
  <code>RPT_BANDWIDTH_CAP_BPS_MAP</code>) — not auto-detected NIC line-rate unless
  you set it. Probes use token-gated
  <code>/api/private/capacity</code> (<code>RPT_CAPACITY_TOKEN</code> on status host
  and nodes). Fail-soft: unavailable peers show <code>unknown</code> / error — never
  invented load. Not shown on the public shop.
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
{top}</section>
"""


def _escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
