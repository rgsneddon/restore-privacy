**0.3.4** — Node LUKS2 + zram ram-only volume; catalog pin alignment.

# Restore Privacy **0.3.4** — release notes

**Status:** Public package release (catalog + packaging).  
**Tag:** `0.3.4`  
**URL:** https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.4

Catalog advances to **0.3.4**.

## Highlights

- **Node-only encryption:** optional **zram + LUKS2** ram-backed encrypted volume for node host data (`node/install_zram_luks.sh`, pure planners in `node/disk_encryption.py`). **Clients never install LUKS/zram.**
- Classic **LUKS2 disk** data-at-rest path remains (`node/install_disk_encryption.sh`).
- Host privacy / self-host compose check both disk LUKS and zram+LUKS2 (non-destructive check modes).
- Product residual Connect unchanged (HELLO + full tunnel); licence + payment gates unchanged.
- Version pin **0.3.4** on all client platforms (Windows/Linux/Flutter).

## Downloads

| Asset | Notes |
|-------|--------|
| `restore-privacy-client-0.3.4-windows-x64-setup.exe` | Windows installer |
| `restore-privacy-client-0.3.4-android.apk` | Flutter APK |
| `restore-privacy-client-0.3.4-linux-x64.tar.gz` | Linux package |
| `restore-privacy-client-0.3.4-macos.zip` | Developer ID signed + notarized (when built) |
| `restore-privacy-client-0.3.4-ios.zip` | Team-signed sideload (when built) |

## Operator (node)

```bash
# Non-destructive
bash node/install_zram_luks.sh check
bash node/install_zram_luks.sh dry-run
# Destructive RAM volume (node only)
RPT_ZRAM_LUKS_CONFIRM=yes bash node/install_zram_luks.sh format
```

Honesty: zram+LUKS2 is an encrypted **RAM-backed node volume**, not full live-root secrecy, not client FDE, not erasure of provider snapshots/netflow.

## Upgrade

Install **0.3.4** from the VPN APP Shop download catalog (catalog **v0.3.4**, paid buttons fulfil the same assets). Accept the end-user licence on first Connect.
