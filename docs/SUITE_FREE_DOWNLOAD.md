# Suite download (KEYGEN free trial required)

Restore Privacy Suite **v1.0.2** installers are **not** anonymous freebies.
You must start the catalog **KEYGEN** path first — monthly **£3.00** or yearly
**£30.00** with the **3-day free trial** (no money taken until after the trial
ends). Residual Connect also needs that KEYGEN after install.

Download links sit on the public homepage (and on the open `public_site/` Pages
export). Unauthenticated `/suite/download` and `/assets/…` requests **redirect
to `/pay`**. After checkout, use `session_id` / download token / KEYGEN, paste
the KEYGEN from your fulfilment email, then Connect.

After KEYGEN unlock in the app, Suite may offer an **optional** unified
sign-up/sign-in for Perccent wallet (**%**) and Evolve (**EVOLVE**). Choosing
**Not now — use VPN only** defers that account; **Connect is not gated** on
Suite registration. Resume setup or run how-tos from the **rpAI** (Ned) tab —
see [SUITE_ACCOUNT_AND_RPAI.md](SUITE_ACCOUNT_AND_RPAI.md).

Live gated route on the status host: `/suite/download?platform=…`  
(requires `session_id`, `keygen`, or `token` query proof)

**Business-Class / full business package** requires a separate compulsory
**£3000 deposit** via `/pay/commercial-suite` (Service page) — not the KEYGEN
subscription.

**Catalog monopin:** `1.0.2` (`status_page/downloads.py` `RELEASE_VERSION`,
`client/VERSION`).

Open public website (no admin):

- https://rgsneddon.github.io/restore-privacy-suite/
- Source: https://github.com/rgsneddon/restore-privacy-suite

## Platform basenames (Helsinki paid_assets / status assets)

| Platform | Filename |
|----------|----------|
| Windows | `restore-privacy-client-1.0.2-windows-x64-setup.exe` |
| Android | `restore-privacy-client-1.0.2-android.apk` |
| macOS | `restore-privacy-client-1.0.2-macos.zip` |
| iOS | `restore-privacy-client-1.0.2-ios.zip` |
| Linux | `restore-privacy-client-1.0.2-linux-x64.tar.gz` |

Store path: `paid_assets/1.0.2/{filename}` on Helsinki `135.181.152.10`.

## Operators building packages

```bash
# Suite client monopin (Darwin: Flutter android/macos/ios; win/linux carry-forward or native agent)
python3 scripts/build_suite_1.0.2.py

# Companion brand packages
python3 scripts/package_browser_rx.py
python3 scripts/package_rpos.py
python3 scripts/package_pts_apps.py
python3 scripts/package_rpmail_rpoffice.py
python3 scripts/package_node_installers.py
python3 scripts/package_node_operator_linux.py

# Stage + Helsinki upload (SSH key required)
export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_eu
python3 scripts/host_paid_assets_vps.py --stage --upload --version 1.0.2 --force --install-serve

# Breadcrumbs vault (Apple + Windows handoff for builders)
python3 scripts/breadcrumbs_vault.py stage
python3 scripts/breadcrumbs_vault.py publish

# Public Pages export
python3 scripts/build_public_pages.py
# push public_site/ contents to rgsneddon/restore-privacy-suite (public Pages)
```

## Windows builder

Native Windows PE seal is built on a Windows machine. Full steps:

- `client/windows/WINDOWS_HANDOFF_1.0.2.md`
- `releases/1.0.2/WINDOWS_BREADCRUMBS.md`
- Vault: `dist/breadcrumbs/current/WINDOWS_HANDOFF.md`
- Brand-wide large-drive mirror: `scripts/windows_brand_mirror.py`
  (`RPT_WINDOWS_DRIVE` or `--dest`; vault `WINDOWS_BRAND_CHECKLIST.md` +
  `windows_brand_mirror.json` after `breadcrumbs_vault.py stage`)

Target PE:

```text
restore-privacy-client-1.0.2-windows-x64-setup.exe
```

Mirror monorepo + **all brand installers** onto the Windows larger drive before
the PE rebuild:

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE --execute
```

## Honesty

- Brand package delivery requires KEYGEN trial start / active entitlement first.
- Connect requires a valid KEYGEN on the device after install.
- Business-Class work starts only after the **£3000** commercial deposit.
- macOS CFBundle / Windows embedded product version must match monopin **1.0.2**
  for an honest catalog seal (host scripts refuse mismatched macOS zips).
- Carry-forward basenames may be used temporarily; replace with native rebuilds
  before calling the seal final.
