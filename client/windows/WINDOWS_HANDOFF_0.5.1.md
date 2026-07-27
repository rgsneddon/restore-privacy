# Windows handoff — catalog **0.5.1**

## Pins
1. `client/VERSION` → `0.5.1`
2. Catalog `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG` → `0.5.1`
3. Filename: `restore-privacy-client-0.5.1-windows-x64-setup.exe`

## Product UI (this pin)
- Banner: **Virtual Private Network**
- Main shell **country picker** above Connect (**IS / RO / US** + flag images; default **US**)
- Brand taskbar icon (not stock feather)
- Faster warm Connect / Disconnect residual teardown as in 0.5.0 lineage

## Settings defaults (unchanged lean)
Optional residual scale (shape / outer obfs / multi-hop) **off** by default; core residual always required.

## Build (Windows x64)

```bat
python scripts\build_windows_multihop.py
python scripts\build_release_0.5.1.py --windows-only
```

Or full multi-platform stage:

```bat
python scripts\build_release_0.5.1.py
```

Then stage paid assets:

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.1 --force
```

## Honesty
- Catalog 0.5.1 filename alone is not proof of native Windows code freeze — prefer multihop PE rebuild on this host.
- Do not ship `*.priv` keys.
- Apple/Android packages on a Windows-host ship are **honest carry-forward** unless Mac/SDK rebuilds land (see `client_app/APPLE_HANDOFF_0.5.1.md`).
