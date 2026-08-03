<!-- Source: https://github.com/rgsneddon/Rx-Privacy-Browser/blob/master/README.md -->

> **On this site:** Rx Privacy Browser documentation mirrored from the [Rx Privacy Browser README](https://github.com/rgsneddon/Rx-Privacy-Browser/blob/master/README.md). That GitHub file remains the source of truth when published. Monorepo copy: `browser_extension/README.md`.

# Rx Privacy Browser


Chromium **Manifest V3** extension — **Rx Privacy Browser** companion for
**browser-scoped** Connect / Disconnect. Ships with **Restore Privacy
1.1.5** native installers; it is not a replacement for residual TUN.

## Honesty

- **Browser only:** routes this browser’s traffic via the configured **local proxy** path (`chrome.proxy`). IPv4-focused free basic path; no OS residual settings surface.
- **Not OS residual:** does **not** create Wintun / Packet Tunnel / system residual TUN. Native VPN clients (Windows · Android · macOS · iOS · Linux, catalog **1.1.5**) remain the residual product path.
- Default proxy target is `socks5://127.0.0.1:1080` (local companion / future bridge). Override via Connect options if your browser stack exposes a different local path.

## Load unpacked (developer)

1. Open Chromium / Chrome / Edge → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this `browser_extension/` directory

Any custom browser that loads Chromium MV3 extensions can use the same package.

## Files

| Path | Role |
|------|------|
| `manifest.json` | MV3 manifest (`proxy`, `storage`) |
| `lib/vpn_core.js` | Pure enable/disable/status (unit-tested) |
| `lib/proxy_adapter.js` | `chrome.proxy.settings` adapter |
| `background.js` | Service worker |
| `popup.html` / `popup.js` / `popup.css` | Connect / Disconnect UI |

## Package zip (release asset)

```bash
cd browser_extension
zip -r ../releases/1.0.1/restore-privacy-browser-extension-1.0.1.zip . \
  -x '*.DS_Store' -x '*__pycache__*' -x 'test/*'
# Rx-branded alias (Service page / store):
cp ../releases/1.0.1/restore-privacy-browser-extension-1.0.1.zip \
   ../releases/1.0.1/restore-privacy-rx-browser-1.0.1.zip
```

## Pay / native residual

https://restoreprivacy.online/
