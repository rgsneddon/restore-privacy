# rpOS — Restore Privacy Operating System

Commercial privacy-focused OS product (**£3000** deposit path via Restore Privacy Service).

**Monopin 0.2.1** ships **RxShell** — the PowerShell-type multi-language CLI of rpOS.

## Positioning

rpOS is a **privacy-first operating system** SDK surface for commercial deployment.
**Free bundled apps** (Desktop launchers after install):

| Brand | Role | Package |
|-------|------|---------|
| **Pens** | Documents | `pens-*-installer.zip` |
| **Tables** | Spreadsheets | `tables-*-installer.zip` |
| **Slides** | Presentations | `slides-*-installer.zip` |

Also: Database creator · Email (**rpMail**) · Private Browser (**Rx**) · VPN · **Evolve** · **MISHI** moderator GUI · **RxShell** CLI.

## RxShell

PowerShell-type interactive CLI (not full Microsoft PowerShell). Accepts snippets in
**shell**, **Python**, **JavaScript**, and **PowerShell**-style when host runtimes exist.

```bash
python3 -m rpos.rxshell
python3 -m rpos.rxshell -c ':python print(2+2)'
python3 -m rpos.rxshell -c ':shell echo hi'
python3 -m rpos.rxshell --list-languages
# From a package stage root:
./RxShell
```

Missing interpreters fail closed (clear error, no fake success).

## Installable platforms (desktop only)

| OS | Arch | How to get |
|----|------|------------|
| **Windows** | x86_64 | `releases/rpos/0.2.1/rpos-0.2.1-windows-x64.zip` |
| **macOS** | universal | `releases/rpos/0.2.1/rpos-0.2.1-macos.zip` |
| **Linux** | x86_64 | `releases/rpos/0.2.1/rpos-0.2.1-linux-x86_64.tar.gz` |
| **Linux** | aarch64 | `releases/rpos/0.2.1/rpos-0.2.1-linux-aarch64.tar.gz` |

```bash
# From restore-privacy monorepo
python3 scripts/package_rpos.py
python3 scripts/package_pts_apps.py   # Pens / Tables / Slides free installers
```

**Not installable:** iOS, Android.

## Install story (honest)

### Single-click RESTORE

Primary control: **`RESTORE_rpOS`** (Unix) or **`RESTORE_rpOS.cmd`** (Windows).

1. **Advisories** — BE CAREFUL · IRREVERSIBLE · DATA LOSS  
2. **Gate** — type exact `RESTORE` or abort  
3. **Wipe intent** — absolute format intent; default **dry-run**  
4. **Install** — foundation + free **Pens · Tables · Slides** → **user Desktop** launchers  
5. **GOD OOBE** — timezone → language → email → **rpMail**  
6. **GOD locked guide** — **Pens → Tables → Slides** before full OS unlock  

Full utilisation stays **locked** until GOD finishes showing all three Desktop apps.

```bash
python3 -m rpos.installer smoke   # safe dry-run of full path
python3 -m rpos.installer apps-tour --prefix ~/.rpos/install --auto
```

## Repositories

- Private GitHub: `rgsneddon/rpOS`
- Suite monorepo: `restore-privacy`
- Office apps: `rgsneddon/rpOffice` (**Pens · Tables · Slides**)

## Licence

MIT — see [LICENSE](LICENSE).
