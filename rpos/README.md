# rpOS — Restore Privacy Operating System

Commercial privacy-focused OS product (**£3000** deposit path via Restore Privacy Service).

## Positioning

rpOS is a **privacy-first operating system** SDK surface for commercial deployment.
Bundled app surfaces (built per customer requirements):

- Database creator
- Word Processor
- Spreadsheet
- Email client (SMTP / IMAP / POP3 import; company emails by **moderator only**)
- Private Browser (**Rx**) with free basic **IPv4-only** VPN extension posture
- VPN
- **Evolve** game with rewards tokens

Moderator / governance surface: **MISHI** (GUI whitewash for every function as SDK).

## Installable platforms (desktop only)

| OS | Arch | How to get |
|----|------|------------|
| **Windows** | x86_64 | `releases/rpos/0.1.0/rpos-0.1.0-windows-x64.zip` |
| **macOS** | universal | `releases/rpos/0.1.0/rpos-0.1.0-macos.zip` |
| **Linux** | x86_64 | `releases/rpos/0.1.0/rpos-0.1.0-linux-x86_64.tar.gz` |
| **Linux** | aarch64 | `releases/rpos/0.1.0/rpos-0.1.0-linux-aarch64.tar.gz` |

```bash
# From restore-privacy monorepo
python3 scripts/package_rpos.py
```

**Not installable:** iOS, Android.

## Install story (honest)

### Single-click RESTORE (IMPERATIVE product path)

Primary control after extraction: **`RESTORE_rpOS`** (Unix) or **`RESTORE_rpOS.cmd`**
(Windows). Flow:

1. **Advisories** — BE CAREFUL · IRREVERSIBLE · DATA LOSS  
2. **Gate** — type exact `RESTORE` or abort (no wipe, no install)  
3. **Wipe intent** — absolute format/remove-all intent; default adapter is **dry-run**  
4. **Install** — rpOS foundation from scratch  
5. **Ned** — guides timezone → language → email bound to **rpMail**

```bash
python3 -m rpos.installer smoke   # safe dry-run of full path
```

Silent wipe without advisories is **not** shipped.

## Repositories

- Private GitHub: `rgsneddon/rpOS` (this product line)
- Suite monorepo companion: `restore-privacy` (catalog, admin deploy how-to)

## Docs

| File | Role |
|------|------|
| [LICENSE](LICENSE) | MIT |
| [PRIVACY_POLICY.md](PRIVACY_POLICY.md) | Privacy policy |
| [security/AUDIT.md](security/AUDIT.md) | Security audit (also Rx browser homepage content) |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Deploy how-to (mirror of admin-only status host page) |
| [sdk/](sdk/) | MISHI + app SDK whitewash scaffolds |

## Licence

MIT — see [LICENSE](LICENSE).

## Companion private app repos

| Product | Repo |
|---------|------|
| rpMail | https://github.com/rgsneddon/rpMail |
| rpOffice | https://github.com/rgsneddon/rpOffice |
| MISHI GUI | https://github.com/rgsneddon/mishi |

