"""Helsinki master/oracle — collate co-joined satellite node heartbeats.

Observes residual fleet signals (capacity + co-joined readiness) and produces
an aggregate snapshot for admin rpS. Ned learns oracle parameters as honest
counters (not a claim of full ML training).
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Sequence


def empty_oracle_state() -> dict[str, Any]:
    return {
        "role": "helsinki_oracle",
        "satellites_seen": 0,
        "satellites_ready": 0,
        "all_satellites_ready": False,
        "roles_ready": {"vpn": False, "rpai": False, "perccent": False},
        "capabilities": {
            "vpn_sessions_live": 0,
            "vpn_capacity": 0,
            "rpai_epochs": 0,
            "perc_seed_ticks": 0,
            "compute_score": 0,
        },
        "housework": [],
        "findings": [],
        "updated_unix": 0,
    }


def collate_satellite_heartbeats(
    satellites: Sequence[Mapping[str, Any]],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Pure: aggregate ≥0 satellite co-join/capacity payloads into oracle state.

    Each satellite dict may include:
      host, cojoined (snapshot), capacity (private capacity payload)
    """
    t = int(now if now is not None else time.time())
    out = empty_oracle_state()
    out["updated_unix"] = t
    sats = list(satellites or [])
    out["satellites_seen"] = len(sats)
    if not sats:
        out["findings"].append("no satellites reported")
        return out

    role_ready_counts = {"vpn": 0, "rpai": 0, "perccent": 0}
    ready_sats = 0
    sessions = 0
    capacity = 0
    epochs = 0
    ticks = 0
    findings: list[str] = []
    housework: list[str] = []

    for sat in sats:
        host = str(sat.get("host") or "unknown")
        cj = sat.get("cojoined") if isinstance(sat.get("cojoined"), dict) else {}
        cap = sat.get("capacity") if isinstance(sat.get("capacity"), dict) else {}
        readiness = cj.get("readiness") if isinstance(cj.get("readiness"), dict) else {}
        all_ok = bool(cj.get("all_ready"))
        if readiness:
            all_ok = all(bool(readiness.get(r)) for r in ("vpn", "rpai", "perccent"))
        if all_ok:
            ready_sats += 1
        for r in role_ready_counts:
            if readiness.get(r) or (
                isinstance(cj.get("roles"), dict)
                and isinstance(cj["roles"].get(r), dict)
                and cj["roles"][r].get("ready")
            ):
                role_ready_counts[r] += 1
        try:
            sessions += max(0, int(cap.get("live") or 0))
        except (TypeError, ValueError):
            pass
        try:
            capacity += max(0, int(cap.get("capacity") or 0))
        except (TypeError, ValueError):
            pass
        roles = cj.get("roles") if isinstance(cj.get("roles"), dict) else {}
        rpai = roles.get("rpai") if isinstance(roles.get("rpai"), dict) else {}
        perc = roles.get("perccent") if isinstance(roles.get("perccent"), dict) else {}
        try:
            epochs += int((rpai.get("stats") or {}).get("learning_epochs_local") or 0)
        except (TypeError, ValueError):
            pass
        try:
            ticks += int((perc.get("stats") or {}).get("seed_ticks") or 0)
        except (TypeError, ValueError):
            pass
        if not all_ok:
            findings.append(f"{host}: co-join incomplete")
            housework.append(f"nudge_roles_on_{host}")
        else:
            findings.append(f"{host}: co-join ready")

    out["satellites_ready"] = ready_sats
    out["all_satellites_ready"] = ready_sats == len(sats) and len(sats) > 0
    out["roles_ready"] = {
        r: role_ready_counts[r] >= len(sats) and len(sats) > 0 for r in role_ready_counts
    }
    compute = ready_sats * 10 + sessions + epochs + min(ticks, 100)
    out["capabilities"] = {
        "vpn_sessions_live": sessions,
        "vpn_capacity": capacity,
        "rpai_epochs": epochs,
        "perc_seed_ticks": ticks,
        "compute_score": compute,
    }
    out["findings"] = findings[-32:]
    out["housework"] = housework[-32:]
    return out


def ned_learn_oracle(
    stats: dict[str, Any],
    oracle: Mapping[str, Any],
    *,
    points: int = 2,
) -> dict[str, Any]:
    """Pure: Ned growth + housework log from oracle collation.

    Returns a new stats dict with oracle parameters absorbed.
    """
    s = dict(stats or {})
    o = dict(oracle or {})
    s["oracle_role"] = o.get("role") or "helsinki_oracle"
    s["oracle_satellites_seen"] = int(o.get("satellites_seen") or 0)
    s["oracle_satellites_ready"] = int(o.get("satellites_ready") or 0)
    s["oracle_all_ready"] = bool(o.get("all_satellites_ready"))
    s["oracle_capabilities"] = dict(o.get("capabilities") or {})
    s["oracle_findings"] = list(o.get("findings") or [])[-16:]
    s["oracle_housework"] = list(o.get("housework") or [])[-16:]
    s["nodes_online"] = max(
        int(s.get("nodes_online") or 0), int(o.get("satellites_ready") or 0)
    )
    s["nodes_total_seen"] = max(
        int(s.get("nodes_total_seen") or 0), int(o.get("satellites_seen") or 0)
    )
    # Readiness parameters for admin rpS (all true when co-join+oracle healthy)
    roles = o.get("roles_ready") if isinstance(o.get("roles_ready"), dict) else {}
    s["ready_vpn"] = bool(roles.get("vpn") or o.get("all_satellites_ready"))
    s["ready_rpai"] = bool(roles.get("rpai") or o.get("all_satellites_ready"))
    s["ready_perccent"] = bool(roles.get("perccent") or o.get("all_satellites_ready"))
    s["ready_oracle"] = bool(o.get("all_satellites_ready")) or int(
        o.get("satellites_seen") or 0
    ) > 0
    s["ready_cojoined"] = all(
        [s["ready_vpn"], s["ready_rpai"], s["ready_perccent"], s["ready_oracle"]]
    )
    s["learning_epochs"] = int(s.get("learning_epochs") or 0) + 1
    s["growth_score"] = int(s.get("growth_score") or 0) + max(0, int(points))
    s["capability_tier"] = int(s["growth_score"]) // 10
    s["last_oracle_unix"] = int(o.get("updated_unix") or time.time())
    s["ned_housework_done"] = list(s.get("ned_housework_done") or [])
    for task in o.get("housework") or []:
        if task not in s["ned_housework_done"]:
            s["ned_housework_done"].append(f"learned:{task}")
    s["ned_housework_done"] = s["ned_housework_done"][-24:]
    s["compute_score"] = int((o.get("capabilities") or {}).get("compute_score") or 0)
    return s


def oracle_state_to_json(state: dict[str, Any]) -> str:
    return json.dumps(state, indent=2) + "\n"
