# Deploy rpOS (operator)

See also admin-only page on the status host: `/admin/rpos` (requires admin login).

## Installable platforms (desktop only)

| OS | Arch | Package (monopin 0.2.0 + RxShell) |
|----|------|-----------------------------------|
| Windows | x86_64 | `releases/rpos/0.2.0/rpos-0.2.0-windows-x64.zip` |
| macOS | universal | `releases/rpos/0.2.0/rpos-0.2.0-macos.zip` |
| Linux | x86_64 | `releases/rpos/0.2.0/rpos-0.2.0-linux-x86_64.tar.gz` |
| Linux | aarch64 | `releases/rpos/0.2.0/rpos-0.2.0-linux-aarch64.tar.gz` |

**Not installable:** iOS, Android.

Build all packages from the monorepo:

```bash
python3 scripts/package_rpos.py
python3 scripts/package_rpos.py --inventory
```

Each archive includes:

- `install.*` — foundation stage under `/opt/rpos` or `%ProgramData%\rpos`
- **`RESTORE_rpOS` / `RESTORE_rpOS.cmd`** — **single-click** primary control:
  1. Multi-layer advisories (careful / irreversible / data loss)
  2. Exact confirmation phrase `RESTORE` (anything else aborts)
  3. Absolute wipe **intent** via dry-run adapter by default (no silent format)
  4. Foundation install from scratch
  5. **Ned** OOBE: timezone → language → email into **rpMail**

```bash
# From extracted package root (or monorepo with PYTHONPATH=.)
python3 -m rpos.installer advisories
python3 -m rpos.installer restore --yes-advisories --confirm RESTORE
python3 -m rpos.installer oobe --timezone UTC --language en --email you@example.com
python3 -m rpos.installer smoke
```

## Operator steps

1. Commercial deposit / Service path (£3000 deposit framing).
2. Stage Suite + Rx packages on paid host.
3. Build/ship rpOS desktop packages (`package_rpos.py` → `releases/rpos/0.2.0/`, includes RxShell).
4. Customer install via platform entry; RESTORE path only after wipe warning.
5. Configure custom network via separate company SDK admin installer.
6. Enable Ned (rpAI) narrative helper for install storytelling.
7. Record handoff in admin accounting.
