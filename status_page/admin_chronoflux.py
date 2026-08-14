"""Admin → Evolve ChronoFlux progression (confirmed blocks on the explorer path).

After a **successful** status-host admin mutator, call :func:`progress_admin_action`
so the ChronoFlux ledger gains a confirmed block that:

  * identifies the admin action (kind / label / path), and
  * confirms any pending relayed transfers waiting at seal time
    (same seal pattern as SCS / % chance scenario progression).

Read-only GETs and failed actions must **not** call this hook.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ADMIN_ACTION_KIND = "adminAction"
CHAIN_ID = "evolve-chronoflux-principia-chain-1"

_ROOT = Path(__file__).resolve().parent
_DEFAULT_LEDGER = _ROOT / "data" / "chronoflux_admin_ledger.json"


def admin_chronoflux_ledger_path() -> Path:
    raw = os.environ.get("RPT_CHRONOFLUX_ADMIN_LEDGER", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _DEFAULT_LEDGER


def admin_action_display_label(action_kind: str, label: str = "") -> str:
    lab = (label or "").strip()
    if lab:
        return lab if len(lab) <= 80 else lab[:77] + "…"
    kind = (action_kind or "action").strip() or "action"
    pretty = kind.replace("_", " ").replace("-", " ").title()
    return f"Admin: {pretty}"


def empty_ledger() -> dict[str, Any]:
    return {
        "version": 9,
        "evolutionaryChainId": CHAIN_ID,
        "blocks": [],
        "pendingInboundTransfers": [],
        "nextTxId": 1,
        "lastScenarioAt": None,
    }


def load_ledger(path: Path | None = None) -> dict[str, Any]:
    p = path or admin_chronoflux_ledger_path()
    if not p.is_file():
        return empty_ledger()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_ledger()
    if not isinstance(data, dict):
        return empty_ledger()
    data.setdefault("blocks", [])
    data.setdefault("pendingInboundTransfers", [])
    data.setdefault("evolutionaryChainId", CHAIN_ID)
    return data


def save_ledger(ledger: dict[str, Any], path: Path | None = None) -> None:
    p = path or admin_chronoflux_ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def queue_pending_relayed_transfer(
    tx: dict[str, Any],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Queue a pending relayed transfer to be confirmed on the next admin seal."""
    ledger = load_ledger(path)
    pending = list(ledger.get("pendingInboundTransfers") or [])
    entry = dict(tx)
    entry.setdefault("kind", "transfer")
    entry.setdefault("id", f"pending-{secrets.token_hex(6)}")
    pending.append(entry)
    ledger["pendingInboundTransfers"] = pending
    save_ledger(ledger, path)
    return entry


def _drain_pending(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    pending = [
        dict(t)
        for t in (ledger.get("pendingInboundTransfers") or [])
        if isinstance(t, dict)
    ]
    for t in pending:
        t.setdefault("kind", "transfer")
        t["confirmedBy"] = ADMIN_ACTION_KIND
    ledger["pendingInboundTransfers"] = []
    return pending


def mint_admin_action_block(
    ledger: dict[str, Any],
    *,
    action_kind: str,
    label: str = "",
    memo: str = "",
    path: str = "",
    actor: str = "admin",
    relay_ledgers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure-ish progression: mutate *ledger* in place; return seal result.

    *relay_ledgers* entries may include ``blocks`` with transfer txs; those
    transfer ids are recorded as confirmed with this seal (promotion memo).
    Full peer-height merge lives on the JS seed path; status host records ids.
    """
    if not isinstance(ledger.get("blocks"), list):
        ledger["blocks"] = []

    kind = (action_kind or "admin_action").strip() or "admin_action"
    disp = admin_action_display_label(kind, label)
    confirmed_ids: list[str] = []
    for relay in relay_ledgers or []:
        if not isinstance(relay, dict):
            continue
        for block in relay.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            for tx in block.get("transactions") or []:
                if not isinstance(tx, dict):
                    continue
                if tx.get("kind") == "transfer" and tx.get("id"):
                    confirmed_ids.append(str(tx["id"]))

    pending_txs = _drain_pending(ledger)
    # Also fold any transfer txs we just saw from relays into this seal block
    # when not already present as pending.
    for rid in confirmed_ids:
        if any(t.get("id") == rid for t in pending_txs):
            continue
        pending_txs.append(
            {
                "id": rid,
                "kind": "transfer",
                "confirmedBy": ADMIN_ACTION_KIND,
                "memo": "relay confirmed by admin seal",
            }
        )

    index = len(ledger["blocks"])
    tx_id = f"admin-{kind}-{int(time.time())}-{secrets.token_hex(4)}"
    admin_tx = {
        "id": tx_id,
        "kind": ADMIN_ACTION_KIND,
        "actionKind": kind,
        "scenarioLabel": disp,
        "memo": (memo or disp).strip(),
        "path": (path or "").strip(),
        "actor": (actor or "admin").strip() or "admin",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "blockIndex": index,
    }
    block = {
        "index": index,
        "scenarioLabel": disp,
        "transactions": [admin_tx, *pending_txs],
        "timestamp": admin_tx["timestamp"],
        "triggerUsername": admin_tx["actor"],
        "adminAction": True,
        "adminActionKind": kind,
        "chronofluxFingerprint": hashlib.sha256(
            f"{CHAIN_ID}:admin:{kind}:{index}:{tx_id}".encode()
        ).hexdigest()[:32],
    }
    ledger["blocks"].append(block)
    ledger["lastScenarioAt"] = block["timestamp"]
    if isinstance(ledger.get("nextTxId"), int):
        ledger["nextTxId"] = int(ledger["nextTxId"]) + 1

    return {
        "ok": True,
        "block": block,
        "height": index,
        "confirmedRelayTxIds": confirmed_ids,
        "pendingIncluded": len(pending_txs),
        "label": disp,
        "chainId": CHAIN_ID,
    }


def progress_admin_action(
    *,
    action_kind: str,
    label: str = "",
    memo: str = "",
    path: str = "",
    actor: str = "admin",
    relay_ledgers: list[dict[str, Any]] | None = None,
    ledger_path: Path | None = None,
    remote: bool = True,
) -> dict[str, Any]:
    """Post-success ChronoFlux progression for a mutator admin action.

    Always advances the local ChronoFlux admin ledger (explorer-compatible
    blocks). Optionally POSTs to ``RPT_CHRONOFLUX_ADMIN_MINT_URL`` when set
    and *remote* is True (live seed); network failure is recorded, not raised.
    """
    lp = ledger_path or admin_chronoflux_ledger_path()
    ledger = load_ledger(lp)
    result = mint_admin_action_block(
        ledger,
        action_kind=action_kind,
        label=label,
        memo=memo,
        path=path,
        actor=actor,
        relay_ledgers=relay_ledgers,
    )
    save_ledger(ledger, lp)
    result["ledgerPath"] = str(lp)
    result["blockCount"] = len(ledger.get("blocks") or [])

    # GOD · rpAI grows on each confirmed ChronoFlux seal (same block just minted).
    try:
        from admin_rps import record_chronoflux_block_growth
    except ImportError:  # pragma: no cover
        try:
            from status_page.admin_rps import (  # type: ignore
                record_chronoflux_block_growth,
            )
        except ImportError:
            record_chronoflux_block_growth = None  # type: ignore
    if record_chronoflux_block_growth is not None:
        try:
            block = result.get("block") if isinstance(result.get("block"), dict) else {}
            result["nedGrowth"] = record_chronoflux_block_growth(
                height=result.get("height", block.get("index")),
                fingerprint=str(
                    block.get("chronofluxFingerprint")
                    or block.get("fingerprint")
                    or ""
                ),
                action_kind=action_kind,
                label=str(result.get("label") or label or ""),
                block=block,
            )
        except Exception as exc:  # noqa: BLE001
            result["nedGrowth"] = {"ok": False, "error": str(exc)[:160]}

    if remote:
        remote_url = os.environ.get("RPT_CHRONOFLUX_ADMIN_MINT_URL", "").strip()
        if remote_url:
            try:
                payload = json.dumps(
                    {
                        "actionKind": action_kind,
                        "label": result.get("label"),
                        "memo": memo,
                        "path": path,
                        "actor": actor,
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    remote_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    result["remoteStatus"] = int(getattr(resp, "status", 200) or 200)
                    result["remoteOk"] = True
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                result["remoteOk"] = False
                result["remoteError"] = str(exc)[:200]
    return result


def list_admin_chronoflux_blocks(
    *,
    limit: int = 50,
    ledger_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Recent confirmed admin ChronoFlux blocks (newest last)."""
    ledger = load_ledger(ledger_path)
    blocks = list(ledger.get("blocks") or [])
    if limit > 0:
        blocks = blocks[-int(limit) :]
    return blocks


def explorer_block_rows(
    *,
    limit: int = 50,
    ledger_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Rows shaped for explorer-style listing (confirmed admin seals)."""
    out: list[dict[str, Any]] = []
    for b in list_admin_chronoflux_blocks(limit=limit, ledger_path=ledger_path):
        if not isinstance(b, dict):
            continue
        txs = b.get("transactions") or []
        kinds = [str(t.get("kind") or "") for t in txs if isinstance(t, dict)]
        out.append(
            {
                "index": b.get("index"),
                "height": b.get("index"),
                "confirmed": True,
                "label": b.get("scenarioLabel") or "Admin action",
                "genericLabel": b.get("scenarioLabel") or "Admin action",
                "adminAction": True,
                "adminActionKind": b.get("adminActionKind"),
                "kinds": kinds,
                "txCount": len(txs),
                "timestamp": b.get("timestamp"),
                "fingerprint": b.get("chronofluxFingerprint"),
            }
        )
    return out


def after_admin_success(
    action_kind: str,
    *,
    label: str = "",
    memo: str = "",
    path: str = "",
    **_extra: Any,
) -> dict[str, Any]:
    """Fire-and-forget-safe wrapper for admin mutator success paths.

    Never raises into the admin HTTP handler — ChronoFlux failure is recorded
    in the return dict so Connect/mint UX still completes.
    """
    try:
        return progress_admin_action(
            action_kind=action_kind,
            label=label or admin_action_display_label(action_kind),
            memo=memo,
            path=path,
            remote=True,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:200],
            "actionKind": action_kind,
        }
