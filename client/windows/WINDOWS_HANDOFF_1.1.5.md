# Windows + Linux/Arch handoff — monopin 1.1.5

**Audience:** Windows build machine operator (and Arch/Linux rebuild agent).

**Catalog monopin:** `1.1.5` (`client/VERSION` must match).

## Product truth (1.1.5)

| Topic | Product |
|-------|---------|
| Shell | **Residual VPN only** — no Evolve / % wallet / rpAI / Backup chrome |
| First-use | Licence (scroll-to-bottom, justified) → KEYGEN **or** continue 72h trial → main VPN |
| Return visit | Trial remaining **or** valid KEYGEN required |
| Username/password | **Never** offered on product path |
| Quit | Main screen **lower-left**; disconnect residual tunnel **then** full process exit |
| System tray text | Always **`Privacy, Restored`** (comma + capital R; durable across monopin ships) |
| Self-update push | Removed / fail-closed (manual free-DL only) |

## Target package basenames

```text
releases/1.1.5/restore-privacy-client-1.1.5-windows-x64-setup.exe
releases/1.1.5/restore-privacy-client-1.1.5-android.apk
releases/1.1.5/restore-privacy-client-1.1.5-macos.zip
releases/1.1.5/restore-privacy-client-1.1.5-ios.zip
releases/1.1.5/restore-privacy-client-1.1.5-linux-x64.tar.gz
```

Stage also into `status_page/assets/1.1.5/` and Helsinki `paid_assets/1.1.5/`.

## Windows rebuild

1. Pull `main` at the 1.1.5 release commit.
2. Confirm pin: `type client\VERSION` → `1.1.5`
3. Build PE (Flutter Windows packaging if configured, else project PE script).
4. Authenticode-sign setup EXE.
5. Output: `releases\1.1.5\restore-privacy-client-1.1.5-windows-x64-setup.exe`
6. Tray constant: `client/windows/tray_win.py` → `TRAY_DISPLAY_NAME = "Privacy, Restored"`
7. Quit: lower-left; `run_quit_residual_teardown` then process exit.

## Linux / Arch rebuild

```bash
cd client_app && flutter build linux --release --build-name=1.1.5
# package into restore-privacy-client-1.1.5-linux-x64.tar.gz
```

Quit is lower-left; disconnect then exit.

## macOS / iOS / Android (Mac agent)

```bash
python3 scripts/build_suite_1.1.5.py
# optional: --host-paid after local stage is honest
```

- macOS: Developer ID Application + notary when credentials present.
- iOS: Team/Distribution sign + residual pub inject before catalog zip.
- Android: `flutter build apk --release --build-name=1.1.5`.

## Honesty

If this host only carry-forwards a prior PE renamed to 1.1.5, record that in breadcrumbs. Replace with native rebuild before claiming platform seal.

## Residual fleet (unchanged)

IS + DE residual peers; US retired. KEYGEN / 72h device trial entitlement unchanged.
