# Windows + Linux/Arch handoff — monopin 1.1.4

**Audience:** Windows build machine operator (and Arch/Linux rebuild agent).

**Catalog monopin:** `1.1.4` (`client/VERSION` must match).

**Note:** Catalog monopin **1.1.4** is the next ship after **1.1.3** (dedicated residual VPN product truth: VPN-only chrome, Quit lower-left, tray **rpT0**).

## Product truth (1.1.4)

| Topic | Product |
|-------|---------|
| Shell | **Residual VPN only** — no Evolve / % wallet / rpAI / Backup chrome |
| First-use | Licence (scroll-to-bottom, justified) → KEYGEN **or** continue 72h trial → main VPN |
| Return visit | Trial remaining **or** valid KEYGEN required |
| Username/password | **Never** offered on product path |
| Quit | Main screen **lower-left**; disconnect residual tunnel **then** full process exit |
| System tray text | Always **`rpT0`** (Windows tray tip + menu; durable across monopin ships) |
| Self-update push | Removed / fail-closed (manual free-DL only) |

## Target PE basenames

```text
releases/1.1.4/restore-privacy-client-1.1.4-windows-x64-setup.exe
releases/1.1.4/restore-privacy-client-1.1.4-linux-x64.tar.gz
```

Also stage into:

```text
status_page/assets/1.1.4/
```

and Helsinki `paid_assets/1.1.4/` for free-DL fulfilment.

## Windows rebuild (this machine)

1. Pull `main` at the 1.1.4 release commit.
2. Confirm pin:

   ```bat
   type client\VERSION
   rem must print 1.1.4
   ```

3. Preferred residual client path is **Flutter** `client_app` when Windows Flutter packaging is configured. If this agent still builds the Python residual shell PE:

   ```bat
   python scripts\build_windows_installer.py
   rem or project-local PE script used for prior monopin
   ```

4. Authenticode-sign the setup EXE with the company code-signing certificate.
5. Copy to `releases\1.1.4\restore-privacy-client-1.1.4-windows-x64-setup.exe`.
6. Do **not** claim native seal complete until SHA-256 of the signed PE is recorded in breadcrumbs.

### Windows tray + Quit checks

- Tray hover / tip base string is **`rpT0`** (`client/windows/tray_win.py` → `TRAY_DISPLAY_NAME`).
- Quit is lower-left on main chrome; sequence is full residual teardown then exit (`_quit_app` / `run_quit_residual_teardown`).

## Linux / Arch rebuild

1. Pull `main` at 1.1.4.
2. Build residual client package (Flutter linux release when available, else desktop Python packaging):

   ```bash
   cd client_app && flutter build linux --release --build-name=1.1.4
   # package into restore-privacy-client-1.1.4-linux-x64.tar.gz
   ```

3. Arch packaging may wrap the same tarball (no multi-product Suite deps required).
4. Quit control is lower-left; process exit after disconnect.

## macOS / iOS / Android (Mac agent)

On Darwin, operators normally run:

```bash
python3 scripts/build_suite_1.1.4.py
# optional: --host-paid after local stage is honest
```

- **macOS:** Developer ID Application + notary when credentials present.
- **iOS:** Team/Distribution sign + residual pub inject before catalog zip.
- **Android:** `flutter build apk --release --build-name=1.1.4`.

## Honesty

If this host only **carry-forwards** a prior PE renamed to 1.1.4, record that in breadcrumbs. Replace with native rebuild before claiming platform seal.

## Residual fleet (unchanged)

IS + DE residual peers; US retired. KEYGEN / 72h device trial entitlement unchanged.
