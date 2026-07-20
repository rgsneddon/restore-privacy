# Restore Privacy 0.2.2 — release notes

**Status:** Public package release (traffic-shape default on, docs aligned, Settings legal links).

## Highlights

- Production node remains **`82.221.101.241:44044`**.
- **Product traffic shaping ON by default** (Windows/Linux Python DATA path): packet padding (bucket 128), send jitter (≤40 ms), cover frames (~2 s). Opt out: `RPT_TRAFFIC_SHAPE=0`.
- **Session PFS:** ephemeral X25519 mixed into session AEAD key derivation (Python path).
- **Settings links:** most recent audit (`audit.md`), privacy policy (`PRIVACY_POLICY.md`), end user licence (`LICENSE`) via stable GitHub URLs.
- **Multi-hop:** hop *list* config only — **not residual multi-hop**; status is entry-only / not routed.
- **Self-host:** `scripts/selfhost_node.sh` one-shot install recipe.
- Catalog, README, privacy policy, and **audit.md** updated for **0.2.2**.

## Package provenance (honest)

| Asset | Provenance |
|-------|------------|
| Windows `.exe` | **Rebuilt** for 0.2.2 (PyInstaller; includes Settings legal links + traffic-shape default) |
| Linux `.tar.gz` | **Rebuilt** for 0.2.2 (`package_linux.py` manylinux wheels) |
| Android `.apk` | Flutter release rebuild when toolchain present (Settings legal links + `url_launcher`); else staged from 0.2.1 |
| macOS / iOS `.zip` | **Prep packages** staged from **0.2.1** Apple artifacts; **Mac rebuild/sign required** for residual NE and Settings UI |

## Upgrade

Install **0.2.2** packages from this GitHub Release or the status page. Prefer upgrading from 0.2.1 for traffic-shape defaults and Settings document links.

## Operators

- Self-host: `sudo bash scripts/selfhost_node.sh`
- Build: `python scripts/build_release_0.2.2.py`
- Audit: [audit.md](../audit.md)
