# Release notes — Restore Privacy **0.6.0**

**Catalog monopin:** 0.6.0

## Highlights

- **Node operator app** (`python -m node_operator`): Mac/desktop GUI for lab residual node control, admin session list, **client priority**, and **update-push** to connected clients.
- **Residual update-push wire:** `MsgType.UPDATE_PUSH` + `node/update_push.py` operator push; clients receive via `client/update_receive.py` (version/url/message store for upgrade UX).
- **Client priority:** higher-priority residual clients preferred under admission/IP contention (`node/client_priority.py`).
- **Support tickets:** confirm-gated clear-all; short `RPS-###` ids; no keygen on public form; CSP-safe admin close switches.
- **Paid download links:** default reusable window **12 hours** (was 1 hour).
- **Fleet admin honesty:** live residual peers **IS + DE** only; bandwidth unlimited-class (IS 512 / DE 1024 session soft max).
- **Public nav order:** Home → Settings Guide → Licence → Security Audit → Privacy Policy → Support.
- Residual catalog unchanged: **IS / DE** (default entry **DE**); US/RO retired.

## Packages

| Platform | File |
|----------|------|
| Windows | `restore-privacy-client-0.6.0-windows-x64-setup.exe` *(Windows machine PE seal)* |
| Linux | `restore-privacy-client-0.6.0-linux-x64.tar.gz` |
| Android | `restore-privacy-client-0.6.0-android.apk` |
| macOS | `restore-privacy-client-0.6.0-macos.zip` |
| iOS | `restore-privacy-client-0.6.0-ios.zip` |

## Status host

Requires deploy of catalog monopin **0.6.0** assets after host. Operator update-push may advertise version **0.6.0** with paid store / status-host download URL.
