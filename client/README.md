# Restore Privacy client

## Windows (this machine)

```bash
# From repo root, with secrets present:
python -m client.windows
```

Requires:

1. Secrets in `./secrets/` (gitignored) — copy from Vultr `/opt/restore-privacy/secrets/`:
   - `client_ed25519.priv`
   - `node_elgamal.pub`
2. **Administrator** for full system VPN (creates a **Wintun** virtual NIC, installs default routes, starts sealed RPT DATA plane).
3. `client/windows/native/wintun.dll` (shipped open-source TUN driver — not the WireGuard protocol).

Without admin, the session still handshakes but OS capture cannot be installed.

Retro UI: dark blue banner, black background, white text, scrolling privacy string; **auto-connect on launch**.

## Android

```bash
cd client_app
flutter run   # device/emulator with VPN permission
# or
flutter build apk
```

## iOS / macOS

See `client_app/ios/BUILD_ON_MAC.md` and `client_app/macos/BUILD_ON_MAC.md`.
