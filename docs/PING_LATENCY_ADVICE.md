# Ping / RTT reduction — operator advice only

**This note does not change product defaults.** It lists methods already present
in the monorepo that can lower measured or perceived latency. Apply only after
explicit operator decision; trade-offs favour privacy vs snappiness.

Live RTT is dominated by **geography and path** (device → catalog peer). Table
order on the AUDIT UK ping matrix does not change latency.

## User / Settings levers (already shipped)

| Lever | Where | Effect on ping / feel | Honesty |
|-------|--------|------------------------|---------|
| **Traffic shaping OFF** | Settings → privacy-scale; `PrivacyScalePrefs.traffic_shape`; env `RPT_TRAFFIC_SHAPE` unset/off | Less pad / jitter / cover → snappier feel | Default is **off** (`client/product_policy.py`). ON enables pad_bucket 128, jitter ≤40 ms, cover ~2 s (`PRODUCT_ENABLED_TRAFFIC_SHAPE` / `node/traffic_shape.py`). |
| **Outer obfuscation OFF** | Settings; env `RPT_OBFS` | Slightly less header/CPU overhead | Default **off**. ~0 ms pure RTT delta in AUDIT estimates; still real CPU/path cost when ON (QUIC-mimic wrap). |
| **Multi-hop OFF** | Settings multi-hop; env `RPT_MULTIHOP_ENABLED` | Single-hop to **entry** only — usually lower lag | Default **off**. ON = residual-via-exit (e.g. Romania) → higher latency for path privacy (`EXPLAINER_MULTIHOP`). |
| **Entry country closer to user** | Product country catalog / entry selection | Shorter Internet path → lower probe RTT | Catalog peers IS / RO / DE; pick entry by geography when residual policy allows. |
| **Measure from the user device** | Settings “Ping statistics” / `client/node_ping.py` | Live device→entry (and exit if multi-hop) | AUDIT live probes are from **audit host**, not the customer’s phone. |

## Probe / measurement notes (do not “game” for lower numbers)

| Topic | Module / fact | Advice |
|-------|----------------|--------|
| Probe path | `client/node_ping.py` | UDP **44044** first, then TCP **8080** status port fallback. TCP status RTT ≠ residual UDP data path RTT. |
| Timeouts | `DEFAULT_PROBE_TIMEOUT_S` (~1.5 s) | Raising timeout only waits longer on failure; it does not lower successful RTT. |
| AUDIT UK table | `client/uk_ping_estimates.py` | Live ms + optional **shape feel** band (+~5 ms estimate). Lean rows (shape off) show pure live base when probes succeed. |

## Infrastructure / path (operator, not client defaults)

| Topic | Advice |
|-------|--------|
| Peer location | Prefer residual **entry** in a region near the user when product policy allows (IS vs RO vs DE). |
| Host firewall / Cloud FW | Unreachable or hairpin paths inflate or fail probes; fix reachability before tuning app layers. |
| Multi-hop residual | Extra hop always adds latency; keep multi-hop **opt-in** for users who accept that cost. |
| Capacity migration | Near-capacity residual dial to a freer peer (`RPT_CAPACITY_TOKEN`) can avoid a loaded host — may help tail latency, not baseline geography. |

## What not to do without a product decision

- Do **not** silently turn shape/obfs/multihop off in code “to improve ping” (defaults are already lean-off).
- Do **not** shorten HELLO/connect timeouts solely to report lower ms (causes false failures).
- Do **not** treat AUDIT live RTT from a non-UK host as London SLA.

## Related code

- Settings explainers: `client/product_policy.py` (`EXPLAINER_*`)
- Shape policy: `node/traffic_shape.py`
- Outer obfs: `node/obfuscation.py`
- Multi-hop residual: `client/multihop.py`
- Live probe helpers: `client/node_ping.py`
- AUDIT matrix: `client/uk_ping_estimates.py`
