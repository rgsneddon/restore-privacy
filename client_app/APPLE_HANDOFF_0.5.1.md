# Apple handoff — Restore Privacy 0.5.1

Catalog monopin: **0.5.1**

## Catalog honesty (current paid assets)

| Package | Status on VPS **now** (Windows-host ship) |
|---------|-------------------------------------------|
| `restore-privacy-client-0.5.1-macos.zip` | **Honest carry-forward** — catalog **filename** is 0.5.1; **not** a native Developer ID / notarized rebuild of monopin 0.5.1. Internal `CFBundleShortVersionString` may still be **pre-0.5.1** (observed **0.2.3** on CF payload). |
| `restore-privacy-client-0.5.1-ios.zip` | **Honest carry-forward** — catalog **filename** is 0.5.1; **not** a native Team-signed monopin 0.5.1 rebuild. Internal bundle version may still be pre-0.5.1. |

Hosted at VPS `/opt/restore-privacy/paid_assets/0.5.1/` for paid fulfilment. Default residual entry: **United States**.

**After Mac rebuild + secrets (target state):** macOS becomes Developer ID signed + notarized + stapled at monopin **0.5.1** (`CFBundleShortVersionString` **0.5.1**); iOS becomes Team-signed sideload at monopin **0.5.1**. Until then, do **not** document CF zips as those seals.

## Product behaviour (must ship in macOS + iOS **native** builds)

Parity with desktop (catalog **0.5.1** product pin) when Apple packages are **rebuilt** on Mac:

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.**
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended.
4. **Device bind after active keygen** when node requires payment entitlement.
5. **Download alone does not unlock residual.**
6. Connect only while status **OK**; catalog pay monthly or yearly.
7. **Privacy-scale Settings** — lean residual defaults (shape/obfs/multi-hop off).
8. **Main-shell country picker** above Connect: **IS / RO / US**; default **US**.
9. Banner: **Virtual Private Network**.
10. **Version monopin 0.5.1** — `CFBundleShortVersionString` **0.5.1** (native rebuild only; CF zips may still show older CFBundle).
11. Keygen unlock sheet is single-path (no double-present on Accept).

## Mac rebuild (operator)

```bash
cd client_app
flutter build macos --release
flutter build ios --no-codesign
python3 scripts/build_release_0.5.1.py --apple-only
# residual Team-sign for local NE residual testing:
python3 scripts/sign_macos_residual_team.py --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python3 scripts/host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```
