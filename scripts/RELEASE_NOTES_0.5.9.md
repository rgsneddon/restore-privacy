# Release notes — Restore Privacy **0.5.9**

**Catalog monopin:** 0.5.9

## Highlights

- **Residual catalog:** live peers **Iceland (IS)** and **Germany (DE)** only.
  **United States (US)** residual peer is **retired** (stale prefs map to DE, same as RO).
- **Seamless upgrade:** paid keygen/licence rolls over across monopin bumps (version alone does not force re-unlock).
- **macOS Packet Tunnel:** reuse existing product VPN protocol configuration on prepare/Connect so System VPN preferences keep working after package upgrade (0.5.7→0.5.8 class fix).
- Default residual entry remains **Germany (DE)**; multi-hop exit DE; fleet wipe order **IS → DE**.

## Packages

| Platform | File |
|----------|------|
| Windows | `restore-privacy-client-0.5.9-windows-x64-setup.exe` *(Windows machine PE seal)* |
| Linux | `restore-privacy-client-0.5.9-linux-x64.tar.gz` |
| Android | `restore-privacy-client-0.5.9-android.apk` |
| macOS | `restore-privacy-client-0.5.9-macos.zip` |
| iOS | `restore-privacy-client-0.5.9-ios.zip` |

## Status host

Requires deploy of catalog monopin **0.5.9** assets after host.
