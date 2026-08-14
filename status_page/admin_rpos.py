"""Admin-only how-to deploy rpOS (Restore Privacy Operating System).

Route ``/admin/rpos`` — not public without admin login. Documents commercial
£3000 positioning, device-wipe RESTORE intent (honest platform limits), and
SDK whitewash surfaces (MISHI moderator + bundled apps).
"""

from __future__ import annotations

ADMIN_RPOS_PATH = "/admin/rpos"
ADMIN_RPOS_PAGE_ID = "admin-rpos-page"
ADMIN_RPOS_HOWTO_ID = "admin-rpos-deploy-howto"

RPOS_COMMERCIAL_PRICE_LABEL = "£3000"
RPOS_PRODUCT_NAME = "rpOS — Restore Privacy Operating System"

# SDK app surfaces whitewashed for per-requirements commercial builds.
RPOS_SDK_APPS: tuple[str, ...] = (
    "Database creator",
    "Word Processor",
    "Spreadsheet",
    "Email client (SMTP/IMAP/POP3 import)",
    "Private Browser (Rx)",
    "VPN (IPv4 basic free extension posture)",
    "Evolve game with rewards tokens",
)

RPOS_MODERATOR_SURFACE = "MISHI"


def current_rpos_monopin() -> str:
    """Shipped rpOS product pin from ``scripts/package_rpos.RPOS_VERSION``."""
    try:
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "package_rpos.py"
        spec = importlib.util.spec_from_file_location("package_rpos_pin", path)
        if spec is None or spec.loader is None:
            raise ImportError("package_rpos")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ver = str(getattr(mod, "RPOS_VERSION", "") or "").strip()
        if ver:
            return ver
    except Exception:  # noqa: BLE001
        pass
    return "0.2.1"


def render_admin_rpos_deploy_howto_html() -> str:
    """Inner deploy how-to body (admin-gated page only)."""
    apps = "".join(f"<li>{a}</li>" for a in RPOS_SDK_APPS)
    rpos_ver = current_rpos_monopin()
    return f"""
<section class="admin-card" id="{ADMIN_RPOS_HOWTO_ID}" data-admin-rpos-howto="1">
  <h2>How to deploy {RPOS_PRODUCT_NAME}</h2>
  <p><strong>Commercial positioning:</strong> full business package / commercial node
  deposit path starts at <strong>{RPOS_COMMERCIAL_PRICE_LABEL}</strong> (Service page).
  Costs may be higher once on-site scope is agreed.</p>

  <h3>1. Pre-flight</h3>
  <ol>
    <li>Confirm customer commercial deposit / KEYGEN path as applicable.</li>
    <li>Stage Suite monopin packages and Rx browser zip on the paid host.</li>
    <li>Review the private <code>rpOS</code> GitHub repository docs (README, MIT,
        privacy policy, security audit).</li>
  </ol>

  <h3>2. Installer story (honest) — desktop packages only</h3>
  <p>rpOS is <strong>installable only on Windows, macOS, and Linux</strong>
  (x86_64 + aarch64). Build with
  <code>python3 scripts/package_rpos.py</code> →
  <code>releases/rpos/{rpos_ver}/</code> (includes <strong>RxShell</strong>):</p>
  <ul id="admin-rpos-packages">
    <li><code>rpos-{rpos_ver}-windows-x64.zip</code> — <code>install.ps1</code> / <code>RESTORE_rpos.ps1</code> / <code>RxShell.cmd</code></li>
    <li><code>rpos-{rpos_ver}-macos.zip</code> — <code>install.sh</code> / <code>RESTORE_rpos.sh</code> / <code>RxShell</code></li>
    <li><code>rpos-{rpos_ver}-linux-x86_64.tar.gz</code></li>
    <li><code>rpos-{rpos_ver}-linux-aarch64.tar.gz</code></li>
  </ul>
  <p>RxShell: <code>python3 -m rpos.rxshell</code> or package launcher <code>./RxShell</code>
  (multi-language shell/Python/JS/PowerShell-style; not full MS PowerShell).</p>
  <p><strong>iOS / Android are not installable slots</strong> for rpOS packages.</p>
  <p>Primary single-click control for <strong>RESTORE rpOS</strong>:
  <code>RESTORE_rpOS</code> /
  <code>RESTORE_rpOS.cmd</code>. Flow: multi-layer advisories (careful /
  irreversible / data loss) → exact phrase <code>RESTORE</code> → absolute wipe
  <em>intent</em> (default dry-run adapter; never silent) → foundation install →
  <strong>GOD</strong> OOBE (timezone → language → email into rpMail). Packages do
  <strong>not</strong> silent-format disks without confirmation.</p>

  <h3>3. SDK whitewash (built per requirements)</h3>
  <p>Moderator surface: <strong>{RPOS_MODERATOR_SURFACE}</strong> (sexy GUI;
  company emails created by moderator only). Every function is an SDK surface
  for custom commercial builds — not a single frozen closed app set.</p>
  <ul id="admin-rpos-sdk-apps">{apps}</ul>

  <h3>4. Network admin installer</h3>
  <p>Separate <strong>company SDK admin installer</strong> configures the
  custom-build residual network for the customer fleet. Staff VPN, audit
  scripts, and optional Evolve rewards token are scoped per contract.</p>

  <h3>5. Browser + extensions</h3>
  <p>rpOS ships <strong>Rx Privacy Browser</strong> with the free basic
  <strong>IPv4-only</strong> VPN extension posture (no other residual settings
  permitted in the free path). Settings allow colour styles and
  <strong>add/remove browser extensions</strong> (all common extension package
  variations allowed in the design). Extension installer path is
  <strong>ground-up</strong> product code — not a wholesale copy of a third-party
  store installer.</p>

  <h3>6. Post-deploy</h3>
  <ol>
    <li>Run the security audit modelled on the monorepo original; surface as
        Rx browser homepage content where configured.</li>
    <li>Enable GOD (rpAI) narrative helper for install storytelling.</li>
    <li>Record commercial handoff in admin accounting / support tickets.</li>
  </ol>
</section>
"""


def render_admin_rpos_page_html() -> bytes:
    """Full admin page for rpOS deploy how-to."""
    try:
        from admin_panel import _admin_page_shell, admin_section_top_link_html
    except ImportError:  # pragma: no cover
        from status_page.admin_panel import (  # type: ignore
            _admin_page_shell,
            admin_section_top_link_html,
        )
    body = f"""
<div id="{ADMIN_RPOS_PAGE_ID}" data-admin-page="rpos" class="admin-main-inner">
  <p class="admin-lead">Admin-only. Not visible on the public shop without login.</p>
  {render_admin_rpos_deploy_howto_html()}
  {admin_section_top_link_html()}
</div>
"""
    return _admin_page_shell(
        title="rpOS deploy — Admin",
        active="rpos",
        main_html=body,
    )
