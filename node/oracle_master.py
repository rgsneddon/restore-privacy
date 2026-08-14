"""Helsinki master/oracle — collate co-joined satellite node heartbeats.

Observes residual fleet signals (capacity + co-joined readiness), live residual
peer catalog (**IS + DE only** post-1.0.8), Suite architecture learn parameters
(VPN, wallet/Backup, Evolve analysis|voting, credit, rpAI), and optional
non-PII trial/entitlement **ops counters**. Produces an aggregate snapshot for
admin rpS.

GOD learns oracle parameters as honest counters (not a claim of full ML training).
Never stores KEYGEN strings, payment cards, seed phrases, or reinstall-trial
attack-surface prose in durable oracle/GOD state.
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Sequence

# Stable Suite surface ids (match SuiteNavDest product map).
# "backup" is the user-facing Security/Backup recovery tab.
SUITE_SURFACE_IDS: tuple[str, ...] = (
    "vpn",
    "wallet",
    "backup",
    "analysis",
    "voting",
    "credit",
    "rpai",
)

SUITE_SURFACE_LABELS: dict[str, str] = {
    "vpn": "Residual VPN",
    "wallet": "Wallet (%)",
    "backup": "Backup recovery",
    "analysis": "Evolve analysis",
    "voting": "Evolve voting",
    "credit": "Credit",
    "rpai": "rpAI · GOD",
}

# Alias map so heartbeats can use enum-like or legacy names.
_SURFACE_ALIASES: dict[str, str] = {
    "security": "backup",
    "suite_security": "backup",
    "nav_security": "backup",
    "evolve": "analysis",
    "perccent": "wallet",
    "percent": "wallet",
    "wallet_shell": "wallet",
    "ned": "rpai",
    "suite_guide": "rpai",
}

# Live residual catalog peers (product monopin post-US retirement).
# Matches client.multihop / architecture_inventory PUBLIC residual set.
LIVE_RESIDUAL_PEER_CODES: tuple[str, ...] = ("DE",)
RETIRED_RESIDUAL_PEER_CODES: frozenset[str] = frozenset({"US", "RO"})

# Peer-code aliases → live or retired canonical codes.
_PEER_CODE_ALIASES: dict[str, str] = {
    "is": "IS",
    "iceland": "IS",
    "de": "DE",
    "germany": "DE",
    "deutschland": "DE",
    "us": "US",
    "usa": "US",
    "united_states": "US",
    "ro": "RO",
    "romania": "RO",
    "exit": "DE",  # multihop exit is DE pin material
}

# Non-PII fleet ops counters only (integer aggregates). Never KEYGEN/card/seed.
OPS_ENTITLEMENT_COUNTER_KEYS: frozenset[str] = frozenset(
    {
        "trial_claims",
        "trial_active",
        "trial_denied",
        "device_trial_claims",
        "device_trial_denied",
        "entitled_sessions",
        "keygen_entitled",  # count of entitled devices — not KEYGEN strings
        "connect_entitled",
        "licence_active",  # count
    }
)

# Forbidden user-data keys — never retained in collate snapshot or durable GOD stats.
# CERBERUS / Helsinki oracle is fleet orchestration only (no PII persistence).
FORBIDDEN_USER_DATA_KEYS: frozenset[str] = frozenset(
    {
        "connection_log",
        "connection_log_lines",
        "connection_log_text",
        "log_lines",
        "support_log",
        "mnemonic",
        "seed_phrase",
        "seed_words",
        "seed",
        "passphrase",
        "backup_passphrase",
        "backup_bytes",
        "backup_file",
        "percbackup",
        "encrypted_backup",
        "licence_text",
        "license_text",
        "licence_acceptance",
        "license_acceptance",
        "acceptance_prose",
        "user_password",
        "password",
        "private_key",
        "priv_key",
        "wallet_seed",
        "raw_seed",
        # KEYGEN / payment / device identity secrets (ops counters only elsewhere)
        "keygen",
        "keygen_string",
        "keygen_token",
        "keygen_code",
        "keygen_key",
        "licence_key",
        "license_key",
        "stripe_session",
        "stripe_session_id",
        "stripe_customer",
        "stripe_customer_id",
        "card_number",
        "card_cvc",
        "card_cvv",
        "payment_card",
        "payment_method",
        "install_id",
        "device_pub",
        "device_private",
        # Reinstall-for-trial attack-surface prose (never durable)
        "reinstall_attack",
        "reinstall_for_trial",
        "trial_attack_surface",
        "reinstall_trial_caveat",
    }
)

# Substring markers (case-insensitive) for key names that imply user secrets.
_FORBIDDEN_KEY_FRAGMENTS: tuple[str, ...] = (
    "mnemonic",
    "seed_phrase",
    "passphrase",
    "connection_log",
    "backup_bytes",
    "percbackup",
    "licence_text",
    "license_text",
    "private_key",
    "keygen_string",
    "keygen_token",
    "keygen_code",
    "card_number",
    "card_cvc",
    "stripe_session",
    "stripe_customer",
    "reinstall_for_trial",
    "reinstall_attack",
    "trial_attack",
)


def _key_is_forbidden(key: Any) -> bool:
    k = str(key).strip().lower()
    if not k:
        return False
    if k in FORBIDDEN_USER_DATA_KEYS:
        return True
    return any(frag in k for frag in _FORBIDDEN_KEY_FRAGMENTS)


def strip_user_data(obj: Any, *, _depth: int = 0) -> Any:
    """Deep-strip forbidden user-secret keys from dict/list trees.

    Does not encrypt-and-store: OBJECTIVE forbids durable save of user data
    even as ciphertext. Stripped fields are dropped entirely.
    """
    if _depth > 64:
        return None
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if _key_is_forbidden(k):
                continue
            cleaned = strip_user_data(v, _depth=_depth + 1)
            # Drop empty dicts that only held secrets
            if cleaned is None and v is not None and not isinstance(v, (int, float, bool)):
                continue
            out[str(k)] = cleaned
        return out
    if isinstance(obj, list):
        return [strip_user_data(x, _depth=_depth + 1) for x in obj]
    if isinstance(obj, tuple):
        return [strip_user_data(x, _depth=_depth + 1) for x in obj]
    return obj


def sanitize_satellite_payload(sat: Mapping[str, Any] | None) -> dict[str, Any]:
    """Allowlist-shaped satellite for oracle: host, cojoined, capacity, suite, peers, ops."""
    if not isinstance(sat, Mapping):
        return {}
    cleaned = strip_user_data(dict(sat))
    if not isinstance(cleaned, dict):
        return {}
    # Operational keys only at top level (no secrets / KEYGEN / cards).
    allow = {
        "host",
        "cojoined",
        "capacity",
        "suite",
        "suite_architecture",
        "suite_surfaces",
        "updated_unix",
        "role",
        "peer_code",
        "residual_country",
        "country",
        "residual_peers",
        "peers",
        "catalog_peers",
        "fleet_peers",
        "ops",
        "entitlement_ops",
        "trial_ops",
        # Flat ops counters (ints only absorbed later)
        *OPS_ENTITLEMENT_COUNTER_KEYS,
    }
    return {k: v for k, v in cleaned.items() if k in allow}


def assert_no_user_data(obj: Any, *, path: str = "$") -> list[str]:
    """Return list of paths where forbidden keys still appear (empty = clean)."""
    hits: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if _key_is_forbidden(k):
                hits.append(p)
            hits.extend(assert_no_user_data(v, path=p))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hits.extend(assert_no_user_data(v, path=f"{path}[{i}]"))
    return hits


def empty_suite_architecture() -> dict[str, Any]:
    """Zeroed Suite architecture learn map (all major Suite destinations)."""
    surfaces = {
        sid: {
            "observed": 0,
            "learned": False,
            "label": SUITE_SURFACE_LABELS.get(sid, sid),
        }
        for sid in SUITE_SURFACE_IDS
    }
    return {
        "surfaces": surfaces,
        "surfaces_observed": 0,
        "surfaces_total": len(SUITE_SURFACE_IDS),
        "all_suite_surfaces_observed": False,
        "suite_learn_points": 0,
    }


def empty_residual_peers() -> dict[str, Any]:
    """Zeroed live residual peer catalog (IS + DE only)."""
    peers = {
        code: {"observed": 0, "learned": False, "live": True}
        for code in LIVE_RESIDUAL_PEER_CODES
    }
    return {
        "peers": peers,
        "live_codes": list(LIVE_RESIDUAL_PEER_CODES),
        "retired_observed": [],
        "peers_observed": 0,
        "peers_total": len(LIVE_RESIDUAL_PEER_CODES),
        "all_live_peers_observed": False,
    }


def empty_ops_entitlement() -> dict[str, int]:
    """Zeroed non-PII trial/entitlement fleet ops counters."""
    return {k: 0 for k in sorted(OPS_ENTITLEMENT_COUNTER_KEYS)}


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
            "suite_surfaces_observed": 0,
            "suite_surfaces_total": len(SUITE_SURFACE_IDS),
            "suite_learn_points": 0,
            "residual_peers_observed": 0,
            "residual_peers_total": len(LIVE_RESIDUAL_PEER_CODES),
        },
        "suite_architecture": empty_suite_architecture(),
        "residual_peers": empty_residual_peers(),
        "ops_entitlement": empty_ops_entitlement(),
        "housework": [],
        "findings": [],
        "updated_unix": 0,
    }


def normalize_suite_surface_id(raw: Any) -> str | None:
    """Map a free-form surface token to a stable SUITE_SURFACE_IDS id."""
    if raw is None:
        return None
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None
    if key in SUITE_SURFACE_IDS:
        return key
    return _SURFACE_ALIASES.get(key)


def normalize_residual_peer_code(raw: Any) -> str | None:
    """Map free-form peer token to canonical code (IS/DE live, US/RO retired).

    Returns uppercase catalog code, or None if not a known residual peer token.
    Retired codes are returned so callers can record them as retired_observed
    without counting them toward live catalog completeness.
    """
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        for k in ("code", "country", "peer", "peer_code", "residual_country"):
            if k in raw:
                return normalize_residual_peer_code(raw.get(k))
        return None
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None
    upper = key.upper()
    if upper in LIVE_RESIDUAL_PEER_CODES or upper in RETIRED_RESIDUAL_PEER_CODES:
        return upper
    return _PEER_CODE_ALIASES.get(key)


def _truthy_count(val: Any) -> int:
    """Observation count for a surface value.

    Nested architecture entries look like ``{observed: N, learned: bool, ...}`` —
    only the numeric ``observed`` field counts. A bare Mapping is never treated
    as truthy (empty_suite_architecture re-feed must stay zero).
    """
    if val is True:
        return 1
    if val is False or val is None:
        return 0
    if isinstance(val, Mapping):
        # Collated / architecture entry — never invent observations from the dict itself.
        try:
            return max(0, int(val.get("observed") or 0))
        except (TypeError, ValueError, AttributeError):
            return 0
    if isinstance(val, (int, float)):
        try:
            return max(0, int(val))
        except (TypeError, ValueError):
            return 0
    if isinstance(val, str):
        low = val.strip().lower()
        if low in ("", "0", "false", "no", "off"):
            return 0
        if low in ("1", "true", "yes", "on", "observed", "learned"):
            return 1
        try:
            return max(0, int(low))
        except ValueError:
            return 1  # non-empty string counts as observed once
    # list/tuple of surface tokens handled elsewhere; other types = not observed
    return 0


def extract_suite_surface_hits(
    sat: Mapping[str, Any],
) -> dict[str, int]:
    """Pure: pull Suite surface observation counts from one satellite payload.

    Accepts any of:
      - suite_surfaces: ["vpn", "wallet", "backup", ...]
      - suite: {surfaces: {vpn: true, wallet: 1, ...}} or {vpn: true, ...}
      - suite_architecture: same shape as suite
      - cojoined.suite / cojoined.suite_architecture
    """
    hits: dict[str, int] = {sid: 0 for sid in SUITE_SURFACE_IDS}

    def absorb_list(items: Any) -> None:
        if not isinstance(items, (list, tuple)):
            return
        for item in items:
            sid = normalize_suite_surface_id(item)
            if sid:
                hits[sid] = hits.get(sid, 0) + 1

    def absorb_map(m: Any) -> None:
        if not isinstance(m, Mapping):
            return
        # Nested surfaces map preferred
        if isinstance(m.get("surfaces"), Mapping):
            for k, v in m["surfaces"].items():
                sid = normalize_suite_surface_id(k)
                if sid:
                    hits[sid] = hits.get(sid, 0) + _truthy_count(v)
            return
        # Flat map of surface → bool/count
        for k, v in m.items():
            if k in ("surfaces_observed", "surfaces_total", "all_suite_surfaces_observed",
                     "suite_learn_points", "label", "labels"):
                continue
            sid = normalize_suite_surface_id(k)
            if sid:
                hits[sid] = hits.get(sid, 0) + _truthy_count(v)

    # Top-level list
    absorb_list(sat.get("suite_surfaces"))

    for key in ("suite", "suite_architecture"):
        blob = sat.get(key)
        if isinstance(blob, Mapping):
            absorb_map(blob)
            absorb_list(blob.get("suite_surfaces") or blob.get("surfaces_list"))
        elif isinstance(blob, (list, tuple)):
            absorb_list(blob)

    cj = sat.get("cojoined") if isinstance(sat.get("cojoined"), Mapping) else {}
    if cj:
        absorb_list(cj.get("suite_surfaces"))
        for key in ("suite", "suite_architecture"):
            blob = cj.get(key)
            if isinstance(blob, Mapping):
                absorb_map(blob)
            elif isinstance(blob, (list, tuple)):
                absorb_list(blob)

    return hits


def extract_residual_peer_hits(
    sat: Mapping[str, Any],
) -> tuple[dict[str, int], list[str]]:
    """Pure: pull live residual peer observation counts from one satellite.

    Accepts any of:
      - residual_peers / peers / catalog_peers / fleet_peers: ["IS","DE"] or maps
      - peer_code / residual_country / country / role (single code)
      - cojoined.residual_peers / cojoined.peers

    Returns (live_hits IS/DE counts, retired_codes_seen e.g. US/RO).
    Does **not** invent live catalog completeness from retired peers.
    """
    live_hits: dict[str, int] = {c: 0 for c in LIVE_RESIDUAL_PEER_CODES}
    retired: list[str] = []

    def absorb_one(raw: Any) -> None:
        code = normalize_residual_peer_code(raw)
        if not code:
            return
        if code in RETIRED_RESIDUAL_PEER_CODES:
            if code not in retired:
                retired.append(code)
            return
        if code in live_hits:
            live_hits[code] = live_hits.get(code, 0) + 1

    def absorb_list(items: Any) -> None:
        if not isinstance(items, (list, tuple)):
            return
        for item in items:
            absorb_one(item)

    def absorb_map(m: Any) -> None:
        if not isinstance(m, Mapping):
            return
        # Nested peers map preferred
        for nest in ("peers", "residual_peers", "catalog_peers"):
            nested = m.get(nest)
            if isinstance(nested, Mapping):
                for k, v in nested.items():
                    code = normalize_residual_peer_code(k)
                    if not code:
                        continue
                    n = _truthy_count(v)
                    if n <= 0:
                        continue
                    if code in RETIRED_RESIDUAL_PEER_CODES:
                        if code not in retired:
                            retired.append(code)
                    elif code in live_hits:
                        live_hits[code] = live_hits.get(code, 0) + n
                return
            if isinstance(nested, (list, tuple)):
                absorb_list(nested)
                return
        # Flat map of code → bool/count
        for k, v in m.items():
            if k in (
                "peers_observed",
                "peers_total",
                "all_live_peers_observed",
                "live_codes",
                "retired_observed",
                "label",
            ):
                continue
            code = normalize_residual_peer_code(k)
            if not code:
                continue
            n = _truthy_count(v)
            if n <= 0:
                continue
            if code in RETIRED_RESIDUAL_PEER_CODES:
                if code not in retired:
                    retired.append(code)
            elif code in live_hits:
                live_hits[code] = live_hits.get(code, 0) + n

    for key in ("residual_peers", "peers", "catalog_peers", "fleet_peers"):
        blob = sat.get(key)
        if isinstance(blob, Mapping):
            absorb_map(blob)
        elif isinstance(blob, (list, tuple)):
            absorb_list(blob)

    for key in ("peer_code", "residual_country", "country", "role"):
        if key in sat:
            absorb_one(sat.get(key))

    cj = sat.get("cojoined") if isinstance(sat.get("cojoined"), Mapping) else {}
    if cj:
        for key in ("residual_peers", "peers", "catalog_peers", "fleet_peers"):
            blob = cj.get(key)
            if isinstance(blob, Mapping):
                absorb_map(blob)
            elif isinstance(blob, (list, tuple)):
                absorb_list(blob)
        for key in ("peer_code", "residual_country", "country", "role"):
            if key in cj:
                absorb_one(cj.get(key))

    return live_hits, retired


def extract_ops_entitlement_counters(
    sat: Mapping[str, Any],
) -> dict[str, int]:
    """Pure: non-PII trial/entitlement ops counters only (integer aggregates).

    Looks at top-level allowlisted counter keys and nested ops / entitlement_ops
    / trial_ops maps. Never returns KEYGEN strings or card material.
    """
    out: dict[str, int] = {k: 0 for k in OPS_ENTITLEMENT_COUNTER_KEYS}

    def absorb_map(m: Any) -> None:
        if not isinstance(m, Mapping):
            return
        for k, v in m.items():
            key = str(k).strip().lower()
            if key not in OPS_ENTITLEMENT_COUNTER_KEYS:
                continue
            if _key_is_forbidden(key):
                continue
            try:
                n = int(v)
            except (TypeError, ValueError):
                # Booleans only as 0/1; strings that are not ints ignored
                if v is True:
                    n = 1
                elif v is False or v is None:
                    n = 0
                else:
                    continue
            if n < 0:
                n = 0
            out[key] = out.get(key, 0) + n

    absorb_map(sat)
    for nest in ("ops", "entitlement_ops", "trial_ops"):
        absorb_map(sat.get(nest))
    cj = sat.get("cojoined") if isinstance(sat.get("cojoined"), Mapping) else {}
    if cj:
        absorb_map(cj)
        for nest in ("ops", "entitlement_ops", "trial_ops"):
            absorb_map(cj.get(nest))
    return out


def merge_suite_architecture(
    base: dict[str, Any] | None,
    hits: Mapping[str, int],
) -> dict[str, Any]:
    """Merge surface hits into an architecture map (additive counters)."""
    arch = empty_suite_architecture()
    if isinstance(base, dict) and isinstance(base.get("surfaces"), dict):
        for sid, entry in base["surfaces"].items():
            nsid = normalize_suite_surface_id(sid) or sid
            if nsid not in arch["surfaces"]:
                continue
            if isinstance(entry, Mapping):
                try:
                    arch["surfaces"][nsid]["observed"] = max(
                        0, int(entry.get("observed") or 0)
                    )
                except (TypeError, ValueError):
                    pass
                arch["surfaces"][nsid]["learned"] = bool(entry.get("learned"))
    for sid, n in hits.items():
        nsid = normalize_suite_surface_id(sid)
        if not nsid or nsid not in arch["surfaces"]:
            continue
        try:
            add = max(0, int(n))
        except (TypeError, ValueError):
            add = 0
        arch["surfaces"][nsid]["observed"] = int(
            arch["surfaces"][nsid]["observed"]
        ) + add
    observed = sum(
        1 for sid in SUITE_SURFACE_IDS if int(arch["surfaces"][sid]["observed"]) > 0
    )
    points = sum(int(arch["surfaces"][sid]["observed"]) for sid in SUITE_SURFACE_IDS)
    arch["surfaces_observed"] = observed
    arch["surfaces_total"] = len(SUITE_SURFACE_IDS)
    arch["all_suite_surfaces_observed"] = observed == len(SUITE_SURFACE_IDS)
    arch["suite_learn_points"] = points
    return arch


def merge_residual_peers(
    live_hits: Mapping[str, int],
    retired_seen: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build residual peer catalog map from live hits + retired observations."""
    peers_map = empty_residual_peers()
    for code in LIVE_RESIDUAL_PEER_CODES:
        try:
            n = max(0, int(live_hits.get(code) or 0))
        except (TypeError, ValueError):
            n = 0
        peers_map["peers"][code]["observed"] = n
        peers_map["peers"][code]["learned"] = n > 0
    observed = sum(
        1
        for code in LIVE_RESIDUAL_PEER_CODES
        if int(peers_map["peers"][code]["observed"]) > 0
    )
    peers_map["peers_observed"] = observed
    peers_map["peers_total"] = len(LIVE_RESIDUAL_PEER_CODES)
    peers_map["all_live_peers_observed"] = observed == len(LIVE_RESIDUAL_PEER_CODES)
    retired_list: list[str] = []
    for r in retired_seen or []:
        code = normalize_residual_peer_code(r)
        if code and code in RETIRED_RESIDUAL_PEER_CODES and code not in retired_list:
            retired_list.append(code)
    peers_map["retired_observed"] = retired_list
    return peers_map


def collate_satellite_heartbeats(
    satellites: Sequence[Mapping[str, Any]],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Pure: aggregate ≥0 satellite co-join/capacity/suite/peer/ops payloads.

    Each satellite dict may include:
      host, cojoined (snapshot), capacity (private capacity payload),
      suite / suite_architecture / suite_surfaces (Suite product surfaces observed),
      residual_peers / peers / catalog_peers (live residual catalog IS+DE),
      ops / entitlement_ops / trial_ops (non-PII integer fleet counters only)

    User secrets (connection logs, mnemonics, passphrases, backup bytes, licence
    prose, KEYGEN strings, payment cards, reinstall-trial attack prose) are
    stripped at the boundary and never appear in the snapshot.
    """
    t = int(now if now is not None else time.time())
    out = empty_oracle_state()
    out["updated_unix"] = t
    # Sanitize every satellite before any absorb (no user-data retention).
    sats = [sanitize_satellite_payload(s) for s in (satellites or [])]
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
    suite_hits_total: dict[str, int] = {sid: 0 for sid in SUITE_SURFACE_IDS}
    peer_hits_total: dict[str, int] = {c: 0 for c in LIVE_RESIDUAL_PEER_CODES}
    retired_total: list[str] = []
    ops_total: dict[str, int] = empty_ops_entitlement()

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

        hits = extract_suite_surface_hits(sat)
        for sid, n in hits.items():
            suite_hits_total[sid] = suite_hits_total.get(sid, 0) + n
        observed_here = sum(1 for n in hits.values() if n > 0)
        if observed_here:
            findings.append(
                f"{host}: suite surfaces observed={observed_here}/{len(SUITE_SURFACE_IDS)}"
            )
        missing = [sid for sid in SUITE_SURFACE_IDS if hits.get(sid, 0) <= 0]
        if missing and observed_here > 0:
            # Partial suite map → honest housework, not full readiness invent
            housework.append(f"learn_suite_surfaces_on_{host}:{','.join(missing[:4])}")
        elif observed_here == 0:
            housework.append(f"report_suite_architecture_on_{host}")

        peer_hits, retired_here = extract_residual_peer_hits(sat)
        for code, n in peer_hits.items():
            peer_hits_total[code] = peer_hits_total.get(code, 0) + n
        for r in retired_here:
            if r not in retired_total:
                retired_total.append(r)
        peer_obs_here = sum(1 for n in peer_hits.values() if n > 0)
        if peer_obs_here:
            findings.append(
                f"{host}: residual peers observed="
                f"{peer_obs_here}/{len(LIVE_RESIDUAL_PEER_CODES)}"
                + (f" retired={','.join(retired_here)}" if retired_here else "")
            )
        missing_peers = [
            c for c in LIVE_RESIDUAL_PEER_CODES if peer_hits.get(c, 0) <= 0
        ]
        if missing_peers and peer_obs_here > 0:
            housework.append(
                f"learn_residual_peers_on_{host}:{','.join(missing_peers)}"
            )
        elif peer_obs_here == 0:
            housework.append(f"report_residual_peers_on_{host}")
        if retired_here:
            # Retired peers must never complete the live catalog
            housework.append(
                f"drop_retired_residual_peers_on_{host}:{','.join(retired_here)}"
            )

        ops_here = extract_ops_entitlement_counters(sat)
        for k, n in ops_here.items():
            ops_total[k] = ops_total.get(k, 0) + int(n or 0)

        if not all_ok:
            findings.append(f"{host}: co-join incomplete")
            housework.append(f"nudge_roles_on_{host}")
        else:
            findings.append(f"{host}: co-join ready")

    arch = merge_suite_architecture(None, suite_hits_total)
    peers = merge_residual_peers(peer_hits_total, retired_total)
    out["suite_architecture"] = arch
    out["residual_peers"] = peers
    out["ops_entitlement"] = ops_total
    out["satellites_ready"] = ready_sats
    out["all_satellites_ready"] = ready_sats == len(sats) and len(sats) > 0
    out["roles_ready"] = {
        r: role_ready_counts[r] >= len(sats) and len(sats) > 0 for r in role_ready_counts
    }
    suite_pts = int(arch.get("suite_learn_points") or 0)
    peer_obs = int(peers.get("peers_observed") or 0)
    compute = (
        ready_sats * 10
        + sessions
        + epochs
        + min(ticks, 100)
        + min(suite_pts, 50)
        + peer_obs * 2
    )
    out["capabilities"] = {
        "vpn_sessions_live": sessions,
        "vpn_capacity": capacity,
        "rpai_epochs": epochs,
        "perc_seed_ticks": ticks,
        "compute_score": compute,
        "suite_surfaces_observed": int(arch.get("surfaces_observed") or 0),
        "suite_surfaces_total": int(arch.get("surfaces_total") or len(SUITE_SURFACE_IDS)),
        "suite_learn_points": suite_pts,
        "residual_peers_observed": peer_obs,
        "residual_peers_total": int(
            peers.get("peers_total") or len(LIVE_RESIDUAL_PEER_CODES)
        ),
        "all_live_peers_observed": bool(peers.get("all_live_peers_observed")),
        # Parallel architecture map (also top-level suite_architecture)
        "suite_architecture": arch,
        "residual_peers": peers,
        "ops_entitlement": dict(ops_total),
    }
    # Per-surface capability counters for admin / GOD absorb
    for sid in SUITE_SURFACE_IDS:
        out["capabilities"][f"suite_{sid}_observed"] = int(
            arch["surfaces"][sid]["observed"]
        )
    for code in LIVE_RESIDUAL_PEER_CODES:
        out["capabilities"][f"residual_peer_{code}_observed"] = int(
            peers["peers"][code]["observed"]
        )
    out["findings"] = findings[-32:]
    out["housework"] = housework[-32:]
    # Final strip — collated snapshot must never retain forbidden keys.
    return strip_user_data(out)


def ned_learn_oracle(
    stats: dict[str, Any],
    oracle: Mapping[str, Any],
    *,
    points: int = 2,
) -> dict[str, Any]:
    """Pure: GOD growth + housework log from oracle collation.

    Absorbs co-join readiness, Suite architecture, live residual peer catalog
    (IS+DE), and non-PII trial/entitlement ops counters so GOD can continue
    learning product surfaces and fleet shape over time.
    Returns a new stats dict with oracle parameters absorbed.
    Never copies forbidden user-secret keys into the learned stats dict.
    """
    s = strip_user_data(dict(stats or {}))
    if not isinstance(s, dict):
        s = {}
    o = strip_user_data(dict(oracle or {}))
    if not isinstance(o, dict):
        o = {}
    s["oracle_role"] = o.get("role") or "helsinki_oracle"
    s["oracle_satellites_seen"] = int(o.get("satellites_seen") or 0)
    s["oracle_satellites_ready"] = int(o.get("satellites_ready") or 0)
    s["oracle_all_ready"] = bool(o.get("all_satellites_ready"))
    caps = dict(o.get("capabilities") or {})
    s["oracle_capabilities"] = caps
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

    # --- Suite architecture absorb ---
    arch_in = o.get("suite_architecture")
    if not isinstance(arch_in, Mapping):
        arch_in = caps.get("suite_architecture") if isinstance(caps, Mapping) else None
    if not isinstance(arch_in, Mapping):
        arch_in = empty_suite_architecture()
    prev_learned = list(s.get("suite_surfaces_learned") or [])
    prev_set = {str(x) for x in prev_learned}
    new_learned: list[str] = []
    surfaces_out: dict[str, Any] = {}
    surfaces_in = (
        arch_in.get("surfaces") if isinstance(arch_in.get("surfaces"), Mapping) else {}
    )
    for sid in SUITE_SURFACE_IDS:
        entry = surfaces_in.get(sid) if isinstance(surfaces_in.get(sid), Mapping) else {}
        try:
            obs = max(0, int(entry.get("observed") or 0))
        except (TypeError, ValueError):
            obs = 0
        # Also accept flat capability counters
        if obs <= 0:
            try:
                obs = max(0, int(caps.get(f"suite_{sid}_observed") or 0))
            except (TypeError, ValueError):
                obs = 0
        # Only observed counts (or durable prev_set) mark learned — ignore forged
        # learned:true with observed:0 (no free growth_points).
        learned = obs > 0 or sid in prev_set
        if obs > 0 and sid not in prev_set:
            new_learned.append(sid)
        surfaces_out[sid] = {
            "observed": obs,
            "learned": learned,
            "label": SUITE_SURFACE_LABELS.get(sid, sid),
        }
    observed_n = sum(1 for sid in SUITE_SURFACE_IDS if surfaces_out[sid]["observed"] > 0)
    learned_list = sorted(
        {
            *(prev_set),
            *(sid for sid in SUITE_SURFACE_IDS if surfaces_out[sid]["observed"] > 0),
        }
    )
    suite_pts = sum(int(surfaces_out[sid]["observed"]) for sid in SUITE_SURFACE_IDS)
    arch_out = {
        "surfaces": surfaces_out,
        "surfaces_observed": observed_n,
        "surfaces_total": len(SUITE_SURFACE_IDS),
        "all_suite_surfaces_observed": observed_n == len(SUITE_SURFACE_IDS),
        "suite_learn_points": suite_pts,
    }
    s["suite_architecture"] = arch_out
    s["suite_surfaces_learned"] = learned_list[-24:]
    s["suite_surfaces_observed"] = observed_n
    s["suite_surfaces_total"] = len(SUITE_SURFACE_IDS)
    s["ready_suite_architecture"] = bool(arch_out["all_suite_surfaces_observed"])
    # Full co-joined stack does NOT invent suite completeness
    if not arch_out["all_suite_surfaces_observed"]:
        s["ready_suite_architecture"] = False

    # --- Live residual peer catalog absorb (IS + DE only) ---
    peers_in = o.get("residual_peers")
    if not isinstance(peers_in, Mapping):
        peers_in = caps.get("residual_peers") if isinstance(caps, Mapping) else None
    if not isinstance(peers_in, Mapping):
        peers_in = empty_residual_peers()
    prev_peers = list(s.get("residual_peers_learned") or [])
    prev_peer_set = {str(x).upper() for x in prev_peers}
    new_peers: list[str] = []
    peers_out: dict[str, Any] = {}
    peers_map_in = (
        peers_in.get("peers") if isinstance(peers_in.get("peers"), Mapping) else {}
    )
    for code in LIVE_RESIDUAL_PEER_CODES:
        entry = (
            peers_map_in.get(code) if isinstance(peers_map_in.get(code), Mapping) else {}
        )
        try:
            obs = max(0, int(entry.get("observed") or 0))
        except (TypeError, ValueError):
            obs = 0
        if obs <= 0:
            try:
                obs = max(0, int(caps.get(f"residual_peer_{code}_observed") or 0))
            except (TypeError, ValueError):
                obs = 0
        learned_p = obs > 0 or code in prev_peer_set
        if obs > 0 and code not in prev_peer_set:
            new_peers.append(code)
        peers_out[code] = {
            "observed": obs,
            "learned": learned_p,
            "live": True,
        }
    peer_obs_n = sum(
        1 for code in LIVE_RESIDUAL_PEER_CODES if peers_out[code]["observed"] > 0
    )
    peer_learned_list = sorted(
        {
            *(prev_peer_set),
            *(
                code
                for code in LIVE_RESIDUAL_PEER_CODES
                if peers_out[code]["observed"] > 0
            ),
        }
    )
    retired_obs = []
    for r in peers_in.get("retired_observed") or []:
        rc = normalize_residual_peer_code(r)
        if rc and rc in RETIRED_RESIDUAL_PEER_CODES and rc not in retired_obs:
            retired_obs.append(rc)
    # Never promote retired peers into learned live set
    peer_learned_list = [c for c in peer_learned_list if c in LIVE_RESIDUAL_PEER_CODES]
    residual_out = {
        "peers": peers_out,
        "live_codes": list(LIVE_RESIDUAL_PEER_CODES),
        "retired_observed": retired_obs,
        "peers_observed": peer_obs_n,
        "peers_total": len(LIVE_RESIDUAL_PEER_CODES),
        "all_live_peers_observed": peer_obs_n == len(LIVE_RESIDUAL_PEER_CODES),
    }
    s["residual_peers"] = residual_out
    s["residual_peers_learned"] = peer_learned_list[-16:]
    s["residual_peers_observed"] = peer_obs_n
    s["residual_peers_total"] = len(LIVE_RESIDUAL_PEER_CODES)
    s["ready_residual_catalog"] = bool(residual_out["all_live_peers_observed"])
    if not residual_out["all_live_peers_observed"]:
        s["ready_residual_catalog"] = False

    # --- Downloads Map (latest installer per platform; no user data) ---
    dm_in = o.get("downloads_map")
    if not isinstance(dm_in, Mapping):
        dm_in = caps.get("downloads_map") if isinstance(caps, Mapping) else None
    if isinstance(dm_in, Mapping):
        prev_dm = s.get("downloads_map") if isinstance(s.get("downloads_map"), dict) else {}
        plats_in = dm_in.get("platforms") if isinstance(dm_in.get("platforms"), Mapping) else {}
        plats_out: dict[str, Any] = {}
        if isinstance(plats_in, Mapping):
            for plat, entry in plats_in.items():
                key = str(plat or "").strip().lower()
                if not key or not isinstance(entry, Mapping):
                    continue
                plats_out[key] = {
                    "version": str(entry.get("version") or "").strip(),
                    "filename": str(entry.get("filename") or "").strip(),
                }
        learned = {
            "updated": str(dm_in.get("updated") or ""),
            "platforms": plats_out,
        }
        prev_plats = prev_dm.get("platforms") if isinstance(prev_dm.get("platforms"), dict) else {}
        if learned["platforms"] != prev_plats:
            s["learning_epochs"] = int(s.get("learning_epochs") or 0) + 1
        s["downloads_map"] = learned
        s["downloads_map_learned"] = True

    # --- Ops entitlement counters (non-PII ints only) ---
    ops_in = o.get("ops_entitlement")
    if not isinstance(ops_in, Mapping):
        ops_in = caps.get("ops_entitlement") if isinstance(caps, Mapping) else None
    if not isinstance(ops_in, Mapping):
        ops_in = {}
    ops_out = empty_ops_entitlement()
    for k in OPS_ENTITLEMENT_COUNTER_KEYS:
        try:
            ops_out[k] = max(0, int(ops_in.get(k) or 0))
        except (TypeError, ValueError):
            ops_out[k] = 0
    s["ops_entitlement"] = ops_out

    bonus = len(new_learned) + len(new_peers)  # +1 per new Suite surface or live peer
    base_pts = max(0, int(points))
    total_pts = base_pts + bonus

    s["learning_epochs"] = int(s.get("learning_epochs") or 0) + 1
    s["growth_score"] = int(s.get("growth_score") or 0) + total_pts
    s["capability_tier"] = int(s["growth_score"]) // 10
    s["last_oracle_unix"] = int(o.get("updated_unix") or time.time())
    s["ned_housework_done"] = list(s.get("ned_housework_done") or [])
    for task in o.get("housework") or []:
        tag = f"learned:{task}"
        if tag not in s["ned_housework_done"] and task not in s["ned_housework_done"]:
            s["ned_housework_done"].append(tag)
    for sid in new_learned:
        tag = f"learned_suite:{sid}"
        if tag not in s["ned_housework_done"]:
            s["ned_housework_done"].append(tag)
    for code in new_peers:
        tag = f"learned_residual_peer:{code}"
        if tag not in s["ned_housework_done"]:
            s["ned_housework_done"].append(tag)
    s["ned_housework_done"] = s["ned_housework_done"][-48:]
    s["compute_score"] = int((o.get("capabilities") or {}).get("compute_score") or 0)
    s["growth_points_applied"] = total_pts
    s["suite_new_surfaces_learned"] = new_learned
    s["residual_new_peers_learned"] = new_peers
    # Never return or persist user secrets even if caller tainted *stats*.
    return strip_user_data(s)


def sanitize_stats_for_persist(stats: Mapping[str, Any] | None) -> dict[str, Any]:
    """Strip forbidden user-data keys before any durable GOD/oracle write."""
    cleaned = strip_user_data(dict(stats or {}))
    return cleaned if isinstance(cleaned, dict) else {}


def oracle_state_to_json(state: dict[str, Any]) -> str:
    return json.dumps(strip_user_data(state), indent=2) + "\n"
