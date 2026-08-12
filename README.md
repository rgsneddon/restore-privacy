# Restore Privacy

**Version v1.2.1** — monorepo for the free residual VPN client and operator tooling.

Public storefront: [restoreprivacy.online](https://restoreprivacy.online).  
Open Pages export: [rgsneddon.github.io/restore-privacy-suite](https://rgsneddon.github.io/restore-privacy-suite/).

## Product (shipped)

Install free. Connect is unlocked by a **3-day device trial** or a paid **KEYGEN** (£3.00/month or yearly on `/pay`). There is no account username/password on the product path.

Once connected, residual captures device traffic on a full-tunnel path where the OS allows it. Minimize keeps the tunnel up; **Quit** (main screen lower-left) disconnects then fully exits. Tray chrome: **Privacy, Restored**.

### Settings (defaults lean)

Traffic shaping, outer obfuscation, multi-hop extras, and kill switch are **off by default** (opt-in). Residual Connect does not arm them on first launch.

| Control | Default | Role |
|---------|---------|------|
| Run at device startup | Off | Open the app at sign-in (does not alone start VPN) |
| Autoconnect on launch | Off | Start Connect when the UI opens after unlock |
| **Auto connect if idle** | Off | Re-open residual after an unexpected drop (Android service backoff; Disconnect/Quit do not re-arm) |
| Residual IPv4 | Always on | Full-tunnel IPv4 capture (not user-off) |
| Residual IPv6 | On | Optional ISP IPv6 leak posture while residual is up |
| Traffic shaping / outer obfs / multi-hop | Off | Privacy-scale extras |
| Kill switch | Off | Opt-in fail-closed UI with explicit confirm |
| Leak test / local log | On demand | Device-local honesty diagnostics |
| Updates | Manual | Free re-download when a newer monopin is published |

## Catalog packages

| Platform | File |
|----------|------|
| Windows | `restore-privacy-client-1.2.1-windows-x64-setup.exe` (native PE from Windows host) |
| Android | `restore-privacy-client-1.2.1-android.apk` |
| macOS | `restore-privacy-client-1.2.1-macos.zip` — Notarized Developer ID + residual Packet Tunnel **host NE** |
| iOS | `restore-privacy-client-1.2.1-ios.zip` — IPA `Payload/Runner.app` + embedded provisions (Team-signed sideload; rename to `.ipa`) |
| Linux | `restore-privacy-client-1.2.1-linux-x64.tar.gz` |

## Operator build

- Pin: `client/VERSION` → `1.2.1`
- Flutter client: `client_app/`
- Stage script: `scripts/build_suite_1.2.1.py` (this Mac host skips Windows CF)
- Full ship skill: type `kyrusfables` / `/kyrusfables`
- Public static export: `python3 scripts/build_public_pages.py` → `public_site/`

## Licence & support

Proprietary full copyright — see `LICENSE` and the in-app EULA scroll.  
Operator source is **private**; installers ship from the public storefront only.  
Contact: rus@restoreprivacy.online

| Doc | |
|-----|--|
| Privacy | [PRIVACY_POLICY.md](PRIVACY_POLICY.md) |
| Licence | [LICENSE](LICENSE) |
| Credits | [CREDITS.md](CREDITS.md) |
