# Release notes — Restore Privacy **0.5.8**

**Catalog monopin:** 0.5.8

## Highlights

- **Get update** opens a **platform-matched monopin installer download** (not Stripe `/pay` Checkout). Active keygen/session mints a time-limited `/download?token=` grant.
- **Keygen + licence rollover** across app upgrades for active subscriptions (durable user-data stores; version bump alone does not force re-unlock).
- **Resource lean residual (P0–P2):** Android pad/cover/outer-obfs default OFF (Settings/Connect drive flags); Windows/Linux dataplane idle backoff; Apple cover timer at product interval + session crypto reuse; Settings honesty that Connected still uses power when idle.
- **Arch / CachyOS Linux:** `install.sh` supports **pacman**; `install_linux_arch.sh` / `install_linux_cachyos.sh`; optional PKGBUILD stage under `releases/0.5.8/arch/`.
- Residual peers unchanged: **IS / DE / US** (default entry **DE**). Multi-hop exit DE.

## Packages

| Platform | File |
|----------|------|
| Windows | `restore-privacy-client-0.5.8-windows-x64-setup.exe` *(Windows machine PE seal)* |
| Linux | `restore-privacy-client-0.5.8-linux-x64.tar.gz` |
| Android | `restore-privacy-client-0.5.8-android.apk` |
| macOS | `restore-privacy-client-0.5.8-macos.zip` |
| iOS | `restore-privacy-client-0.5.8-ios.zip` |

## Status host

Requires deploy of `/upgrade-download` and `/api/subscriber-upgrade-download` for in-app mint.
