# Apple handoff — Restore Privacy 0.5.1

Catalog monopin: **0.5.1**

> **Helsinki breadcrumbs vault** is the MacBook source of truth for “what needs
> updating” (macOS / iOS). Do **not** use a private GitHub pull of this handoff
> as the primary task queue.
>
> ```bash
> # On the Mac (token = same class as paid-assets):
> export RPT_ASSET_FETCH_TOKEN='…'
> python3 scripts/breadcrumbs_vault.py check --fetch
> # or: curl -fsS -H "X-RPT-Asset-Token: $RPT_ASSET_FETCH_TOKEN" \
> #   https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json
> ```
>
> Windows operator publish: `python scripts/breadcrumbs_vault.py publish`

## Catalog honesty (current paid assets on Helsinki store)

| Package | Status on VPS **now** |
|---------|------------------------|
| `restore-privacy-client-0.5.1-macos.zip` | **Native** Flutter release rebuild monopin **0.5.1**; **Developer ID signed + notarized + stapled** when secrets present. Host `CFBundleShortVersionString` **must be 0.5.1** (gate: refuse publish if CFBundle lags). Residual Team re-sign still required for **local** Packet Tunnel residual testing (`sign_macos_residual_team.py`). |
| `restore-privacy-client-0.5.1-ios.zip` | **Native** Flutter iOS rebuild monopin **0.5.1** when built on Mac (sideload zip; Team-sign as device tooling allows). |

Hosted at VPS `/opt/restore-privacy/paid_assets/0.5.1/` for paid fulfilment. Default residual entry: **United States**.

**Always:** catalog macOS zip host `CFBundleShortVersionString` == monopin (`client/VERSION` / `RELEASE_VERSION`). Silent carry-forward rename of an older zip is **rejected** by `scripts/build_release_0.5.1.py` and `host_paid_assets_vps.py`.

## Product behaviour (must ship in macOS + iOS builds)

1. **Accept end-user licence** (local only).
2. **Connect allowed = active subscription + keygen activated.**
3. **EXPIRED renew surface** when subscription is revoked/failed/period-ended.
4. **Device bind after active keygen** when node requires payment entitlement.
5. **Download alone does not unlock residual.**
6. Connect only while status **OK**; catalog pay monthly or yearly.
7. **Privacy-scale Settings** — lean residual defaults.
8. **Main-shell country picker** above Connect: **IS / RO / US**; default **US**.
9. Banner: **Virtual Private Network**.
10. **Version monopin 0.5.1** — `CFBundleShortVersionString` / `productVersion` **0.5.1**.
11. Keygen unlock is **version-agnostic** (same `RPT-KEY-…` re-applies after upgrade while active).
12. **Discrete Quit** (bottom-right of main connection screen): stops Packet Tunnel, then **exits** the app completely (not hide-to-tray). Minimize still keeps tunnel up.

## Mac rebuild (operator)

```bash
cd client_app
flutter build macos --release
# Confirm CFBundle before stage:
# plutil -p build/macos/Build/Products/Release/restore_privacy_client.app/Contents/Info.plist | grep ShortVersion
flutter build ios --no-codesign   # or device Team-sign path
cd ..
python3 scripts/build_release_0.5.1.py --apple-only
# residual Team-sign for local NE residual testing:
python3 scripts/sign_macos_residual_team.py \
  --app client_app/build/macos/Build/Products/Release/restore_privacy_client.app
RPT_SSH_USER=raskul RPT_SSH_SUDO=1 python3 scripts/host_paid_assets_vps.py \
  --stage --upload --version 0.5.1 --force
```

## Pin checks

```bash
grep productVersion client_app/lib/rpt_config.dart   # expect 0.5.1
cat client/VERSION                                   # expect 0.5.1
grep RELEASE_VERSION status_page/downloads.py        # expect 0.5.1
python3 -c "from pathlib import Path; import sys; sys.path.insert(0,'status_page'); from apple_package_audit import require_macos_zip_matches_monopin; print(require_macos_zip_matches_monopin(Path('releases/0.5.1/restore-privacy-client-0.5.1-macos.zip'),'0.5.1'))"
```

## Windows remaining work

See [`client/windows/WINDOWS_HANDOFF_0.5.1.md`](../client/windows/WINDOWS_HANDOFF_0.5.1.md).
