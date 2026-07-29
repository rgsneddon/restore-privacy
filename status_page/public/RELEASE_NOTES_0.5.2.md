# Release notes — Restore Privacy **0.5.2**

**Catalog monopin:** 0.5.2  
**Paid installers:** Windows, Linux, Android (this ship). macOS/iOS after Mac native seal (Helsinki breadcrumbs).

## Highlights

- **Admin licence database clear-all** for pre-BETA cleanup (`CLEAR_ALL_LICENCES` confirm; durable payment store).
- **Settings architecture alignment:** dual-stack IPv4/IPv6 protect (default ON); privacy-scale traffic shape / outer obfuscation / multi-hop **lean-off** by default; disconnect residual before Settings apply while connected.
- **Android residual** honors protect-IPv6 + Settings-driven shape/obfs at tunnel start.
- **Audit page last-run** advances on every `scripts/run_security_audit.py --write` via `status_page/static/security_audit_latest.json` (served at `/static/security_audit_latest.json`); ticker shows last-run time.
- **Privacy policy + Settings guide** updated for lean residual defaults and dual-stack honesty.

## Packages

| Platform | File |
|----------|------|
| Windows | `restore-privacy-client-0.5.2-windows-x64-setup.exe` |
| Linux | `restore-privacy-client-0.5.2-linux-x64.tar.gz` |
| Android | `restore-privacy-client-0.5.2-android.apk` |
| macOS | `restore-privacy-client-0.5.2-macos.zip` (Mac seal) |
| iOS | `restore-privacy-client-0.5.2-ios.zip` (Mac Team-sign) |

## Operators

```bash
python scripts/build_release_0.5.2.py --no-apple   # Win host
python scripts/host_paid_assets_vps.py --stage --upload --version 0.5.2 --force
python scripts/breadcrumbs_vault.py publish
python scripts/run_security_audit.py --write
```
