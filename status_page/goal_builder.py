"""/goal · goalbuilder box on the GOD page."""

from __future__ import annotations

import html
import io
import zipfile
from typing import Any


def goal_builder_css() -> str:
    return """
.goal-builder-box { margin: 0 0 1.2rem; }
.goal-builder-lead { line-height: 1.5; }
#goal-scs, #goal-percent, #goal-brief { display: block; margin: 0.35rem 0 0.65rem; }
#grok-construe { margin-right: 0.45rem; }
"""


def render_goal_builder_box_html() -> str:
    return """
<section class="panel-card goal-builder-box" id="goal-builder-box" data-goal-builder="1">
  <h3>/goal · goalbuilder app</h3>
  <p class="goal-builder-lead hint">
    Type a brief and press Build. Standing orders: <code>/goal</code> starts a
    thing; <code>/quit</code> stops. Users do not teach GOD. Grokbot keeps
    the four agents on the same brief.
  </p>
  <label for="goal-family">Dropdown · product family</label>
  <select id="goal-family" name="family">
    <option value="restore_privacy_vpn">Restore Privacy VPN</option>
    <option value="evolve_suite" selected>Evolve Suite</option>
    <option value="perc_wallet">Perc Wallet</option>
    <option value="rpoffice">rpOffice</option>
    <option value="rpmail">rpMail</option>
    <option value="beam_addons">beam addons</option>
    <option value="gnfp_pool">GNFP pool</option>
  </select>
  <label for="goal-scs">Evolve SCS (social cohesion scoring)</label>
  <input id="goal-scs" name="scs" type="number" min="0" max="100" step="1"/>
  <label for="goal-percent">Percent chance (likelihood in a scenario)</label>
  <input id="goal-percent" name="percent" type="number" min="0" max="100" step="1"/>
  <label for="goal-brief">What to build</label>
  <textarea id="goal-brief" maxlength="800" placeholder="build a quiet notes app"></textarea>
  <p>
    <a id="grok-construe" href="#grok-construe">Grok construe</a>
    <button type="button" id="goal-build-submit">Build</button>
    <button type="button" id="goal-quit">/quit</button>
    <a class="btn" href="/support/goal-builder.zip">Download app</a>
  </p>
  <pre class="goal-builder-answer" id="goal-cli">idle — authorize Grok construe, then press Build.</pre>
</section>
"""


def submit_goal_builder(
    payload: dict[str, Any] | None,
    *,
    cookie: str = "",
    authorization: str = "",
    token: str = "",
) -> dict[str, Any]:
    from grokbot import grokbot_build_goal

    data = payload if isinstance(payload, dict) else {}
    _ = (cookie, authorization, token)
    return grokbot_build_goal(
        str(data.get("brief") or data.get("input") or "/goal build a thing"),
        family=str(data.get("family") or "evolve_suite"),
        persist=True,
    )


def goal_builder_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.txt",
            "/goal goalbuilder — run from god.restoreprivacy.online.\n",
        )
    return buf.getvalue()
