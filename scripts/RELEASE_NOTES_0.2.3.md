# Restore Privacy 0.2.3 — release notes

**Status:** Public package release (post-0.2.2 privacy/ops delta: transparency Settings, licence gate, monitoring, threat model, FDE, ephemeral nodes, native wire parity).

## Highlights

- Production node remains **`82.221.101.241:44044`**.
- **Settings transparency:** local-only **connection log** (exportable), **leak test** control, clearer **DPI / traffic-analysis mitigation** disclaimers (Windows + Flutter).
- **Licence acceptance gate** before Connect (and autoconnect); anonymous device registration with **no admin/operator verification** (OS elevation for residual still separate).
- **Native residual wire parity:** Android + Apple NativePrep dual-wire **pad/cover, outer obfs, PFS** with Python (product obfs key **33 bytes**).
- **Monitoring without logging:** process-wide aggregate bandwidth only; public status stays **title-only**.
- **Threat model** docs in `AUDIT.md` §4.6, `PRIVACY_POLICY.md`, and `README.md` (VPS compromise, ISP traffic analysis, device seizure; endpoint correlation / behavioral analysis limits).
- **Node FDE:** LUKS/dm-crypt operator helpers + shutdown auto-wipe (compose with no-log).
- **Ephemeral / short-lived nodes:** periodic snapshot/rebuild plan (`scripts/ephemeral_node.py`, timer install); dry-run default.
- Catalog, README, privacy policy, and **AUDIT.md** updated for **0.2.3**.

## Package provenance (honest)

| Asset | Provenance |
|-------|------------|
| Windows `.exe` | Rebuilt when PyInstaller available; else staged from **0.2.2** renamed to 0.2.3 |
| Linux `.tar.gz` | Rebuilt via `package_linux.py` when possible; else staged |
| Android `.apk` | Flutter rebuild when toolchain present; else staged from **0.2.2** |
| macOS / iOS `.zip` | **Prep packages** staged from prior Apple artifacts; **Mac rebuild/sign required** for residual NE |

## Upgrade

Install **0.2.3** from this GitHub Release or the status page. Accept the end-user licence on first Connect. Prefer upgrading from 0.2.2 for Settings transparency and licence gate.

## Operators

- Self-host: `sudo bash scripts/selfhost_node.sh`
- Ephemeral dry-run: `python scripts/ephemeral_node.py --dry-run`
- FDE check: `bash node/install_disk_encryption.sh check`
- Build: `python scripts/build_release_0.2.3.py`
- Audit: [AUDIT.md](../AUDIT.md)
