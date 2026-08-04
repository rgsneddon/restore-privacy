---
name: kyrusfables
description: >
  Full Restore Privacy ship pipeline in this monorepo: build all, sign/notarize,
  NE tunnel assurances, commit+push GitHub, deploy Helsinki, update docs. Trigger
  on kyrusfables or /kyrusfables.
when-to-use: kyrusfables; /kyrusfables; full ship restore-privacy
user-invocable: true
argument-hint: "[--dry-run] [--skip-build] [--skip-deploy]"
metadata:
  short-description: "kyrusfables = full ship this repo"
---

# kyrusfables (project)

Load and follow the same pipeline as the user skill, with **this repo as `$REPO`**:

`/Users/russellsneddon/restore-privacy`

Primary instructions (keep in sync conceptually):

1. Preflight `client/VERSION` + `scripts/build_suite_<PIN>.py`
2. Flutter NE honesty tests under `client_app/test/`
3. `python3 scripts/build_suite_<PIN>.py` (optional `--host-paid`)
4. Seal re-check: monopin DevID no host NE; residual-team host NE + launch
5. Docs if pin/filenames changed
6. `git commit` + `pull --rebase` + `push origin HEAD`
7. `python3 scripts/host_paid_assets_vps.py --stage --upload --force` if not already deployed
8. Final ship card

Also see `scripts/kyrusfables.sh` for a non-interactive CLI skeleton (agent still owns honesty gates and git messages).

Full operator detail: `~/.grok/skills/kyrusfables/SKILL.md` and `references/pipeline.md`.
