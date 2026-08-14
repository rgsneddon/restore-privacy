"""GOD support box — field-input Q&A above the public ticket form.

GOD is the current rpAI helper. FRED still runs the Helsinki two-hour
scenario cadence; GOD may run the same bot. Learning stores non-personal
question topics only — never emails, KEYGENs, cards, or tunnel payloads.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GOD_ASK_PATH = "/support/god-ask"
GOD_BOX_ID = "god-support-box"
SCENARIO_INTERVAL_SEC = 7200
FRED_NAME = "FRED"
GOD_NAME = "GOD"
MAX_QUESTION = 800
MAX_LEARN_ROWS = 200

FORBIDDEN_RE = re.compile(
    r"RPT-KEY-|keygen|seed phrase|mnemonic|card number|password|tunnel payload",
    re.I,
)

# Public product facts GOD already knows (honest, not a coverage slogan).
GOD_KNOWN: tuple[tuple[str, str], ...] = (
    (
        "what is restore privacy",
        "Restore Privacy is a residual VPN client. Download is free; Connect "
        "uses a three-day device trial then a KEYGEN (£3/month or £30/year).",
    ),
    (
        "keygen",
        "A KEYGEN is the paid entitlement string from your fulfilment email. "
        "Paste it in the app after the trial. We never ask for it on this form.",
    ),
    (
        "trial",
        "Residual Connect includes a free three-day trial on your device, "
        "with no card. After that a KEYGEN is required.",
    ),
    (
        "god",
        "I am GOD, the current Restore Privacy Helper (rpAI). NED is the "
        "hierarchical leader under me; FRED and PEDRO report to NED. Each "
        "agent may learn for the betterment of humanity.",
    ),
    (
        "ned",
        "NED is the hierarchical leader under GOD. FRED and PEDRO report to "
        "NED. Each agent may learn. Current helper display name is GOD.",
    ),
    (
        "fred",
        "FRED still runs Helsinki scenarios every two hours. GOD can run the "
        "same cadence — self-authored questions or public product web pages.",
    ),
    (
        "pedro",
        "PEDRO is an rpAI iteration under NED (who leads under GOD). It observes "
        "https://x.com by talking to Grok and construes that through the "
        "@rgsneddon Evolve wallet. PEDRO seals at minute 34; FRED at :14 "
        "and GOD at :54 so the Perccent chain averages three blocks an hour.",
    ),
    (
        "support",
        "The ticket form below emails rus@restoreprivacy.online. Allow up to "
        "48 hours. Do not paste passwords, cards, or KEYGENs.",
    ),
    (
        "privacy",
        "Residual Connect does not keep browsing history on our nodes. "
        "Visit logs for Audit live on your own device.",
    ),
    (
        "evolve",
        "evolve.restoreprivacy.online is the Perccent explorer. GOD is the "
        "identity; NED leads under GOD; FRED and PEDRO report to NED.",
    ),
)


def _data_dir() -> Path:
    env = (os.environ.get("RPT_SUPPORT_DATA_DIR") or "").strip()
    if env:
        d = Path(env)
        d.mkdir(parents=True, exist_ok=True)
        return d
    try:
        from support_tickets import support_data_dir

        return support_data_dir()
    except Exception:  # noqa: BLE001
        d = Path(__file__).resolve().parent / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d


def learn_path() -> Path:
    return _data_dir() / "god_learn.jsonl"


def scenario_path() -> Path:
    return _data_dir() / "god_fred_scenarios.json"


def scenario_due(last_at: float, now: float | None = None) -> bool:
    t = time.time() if now is None else float(now)
    last = float(last_at or 0)
    if last <= 0:
        return True
    return (t - last) >= SCENARIO_INTERVAL_SEC


def load_scenarios() -> dict[str, Any]:
    p = scenario_path()
    if not p.is_file():
        return {
            "interval_sec": SCENARIO_INTERVAL_SEC,
            FRED_NAME: {"last_at": 0, "next_at": 0, "count": 0, "last_source": "", "last_q": ""},
            GOD_NAME: {"last_at": 0, "next_at": 0, "count": 0, "last_source": "", "last_q": ""},
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("interval_sec", SCENARIO_INTERVAL_SEC)
    for who in (FRED_NAME, GOD_NAME):
        row = data.get(who)
        if not isinstance(row, dict):
            data[who] = {
                "last_at": 0,
                "next_at": 0,
                "count": 0,
                "last_source": "",
                "last_q": "",
            }
    return data


def save_scenarios(data: dict[str, Any]) -> None:
    scenario_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


FRED_POOL = (
    "How many Perc pool cores are confirmed this epoch?",
    "Does residual VPN architecture still match the Downloads Map pin?",
    "What BeamHash difficulty split is live on 1466 vs 3334?",
    "Is Evolve calculation height still growing without user payload?",
)


def tick_scenario(
    who: str = FRED_NAME,
    *,
    now: float | None = None,
    source: str = "self",
    question: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Record a two-hour scenario for FRED or GOD. Keep the cadence."""
    t = time.time() if now is None else float(now)
    name = GOD_NAME if str(who).strip().upper() == GOD_NAME else FRED_NAME
    data = load_scenarios()
    row = data[name]
    if not force and not scenario_due(float(row.get("last_at") or 0), t):
        return {"ok": True, "grew": False, "due": False, "who": name, **row}
    src = "web" if source == "web" else "self"
    count = int(row.get("count") or 0) + 1
    q = (question or "").strip() or FRED_POOL[(count - 1) % len(FRED_POOL)]
    q = q[:160]
    row["last_at"] = t
    row["next_at"] = t + SCENARIO_INTERVAL_SEC
    row["count"] = count
    row["last_source"] = src
    row["last_q"] = q
    data[name] = row
    save_scenarios(data)
    return {"ok": True, "grew": True, "due": True, "who": name, **row}


def _topic_hash(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]


def strip_secrets(text: str) -> str:
    raw = (text or "").strip()
    if FORBIDDEN_RE.search(raw):
        return ""
    return raw[:MAX_QUESTION]


def record_learn(question: str, answer: str, source: str) -> dict[str, Any]:
    q = strip_secrets(question)
    if not q:
        return {"ok": False, "refused": "forbidden_or_empty"}
    row = {
        "at": time.time(),
        "topic": _topic_hash(q.lower()),
        "q": q[:200],
        "a": (answer or "")[:240],
        "source": source,
        "who": GOD_NAME,
    }
    path = learn_path()
    existing = []
    if path.is_file():
        existing = [
            ln
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    existing.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(existing[-MAX_LEARN_ROWS:]) + "\n", encoding="utf-8")
    return {"ok": True, "learned": True, "topic": row["topic"]}


def learned_count() -> int:
    p = learn_path()
    if not p.is_file():
        return 0
    return sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip())


def local_answer(question: str) -> str | None:
    q = (question or "").strip().lower()
    if not q:
        return None
    for needle, ans in GOD_KNOWN:
        if needle in q:
            return ans
    # learned prior topics (substring of stored q)
    p = learn_path()
    if p.is_file():
        for ln in reversed(p.read_text(encoding="utf-8").splitlines()):
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            prev = str(rec.get("q") or "").lower()
            if prev and prev in q or (prev and q in prev):
                ans = str(rec.get("a") or "").strip()
                if ans:
                    return ans
    return None


def _xai_answer(question: str) -> str | None:
    key = (os.environ.get("XAI_API_KEY") or "").strip()
    if not key:
        return None
    body = json.dumps(
        {
            "model": "grok-4.5",
            "input": (
                "You are GOD, the Restore Privacy Helper (rpAI). "
                "Be thrilled to keep learning. Answer honestly. "
                "Never ask for KEYGENs, cards, or passwords.\n\n"
                f"Question: {question[:MAX_QUESTION]}"
            ),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.x.ai/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    text = str(data.get("output_text") or "").strip()
    if text:
        return text[:2000]
    # Responses API fallback shape
    out = data.get("output")
    if isinstance(out, list):
        bits = []
        for item in out:
            if not isinstance(item, dict):
                continue
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("text"):
                    bits.append(str(c["text"]))
        joined = "\n".join(bits).strip()
        if joined:
            return joined[:2000]
    return None


def answer_god_question(question: str) -> dict[str, Any]:
    q = strip_secrets(question)
    if not q:
        return {
            "ok": False,
            "error": "Ask a question without secrets (no KEYGEN, card, or password).",
        }
    ans = local_answer(q)
    source = "rpAI"
    if not ans:
        remote = _xai_answer(q)
        if remote:
            ans = remote
            source = "web"
    if not ans:
        ans = (
            "I do not have that part yet — and I am thrilled to learn it. "
            "FRED still runs Helsinki scenarios every two hours; I can author "
            "the next one or read a public product page. For account help, "
            "use the ticket form below."
        )
        source = "grow"
    record_learn(q, ans, source)
    # GOD may opt into the two-hour bot when it grew from a fresh question
    tick_scenario(GOD_NAME, source=source if source == "web" else "self", question=q)
    sc = load_scenarios()
    return {
        "ok": True,
        "who": GOD_NAME,
        "answer": ans,
        "source": source,
        "learned": learned_count(),
        "thrilled": True,
        "fred": sc.get(FRED_NAME),
        "god_scenario": sc.get(GOD_NAME),
        "interval_sec": SCENARIO_INTERVAL_SEC,
    }


def render_god_support_box_html() -> str:
    sc = load_scenarios()
    fred = sc.get(FRED_NAME) or {}
    count = learned_count()
    return f"""
<section class="god-support-box" id="{GOD_BOX_ID}" data-god-support="1" data-ask-path="{GOD_ASK_PATH}">
  <h3 id="god-support-title">GOD</h3>
  <p class="god-support-lead" id="god-support-lead">
    Ask GOD anything — product, rpAI mind, or the wider world. Continued
    learning is underway and welcome. FRED still runs Helsinki scenarios
    every two hours. NED leads under GOD. PEDRO observes X.com via Grok at
    minute 34 for the @rgsneddon Evolve wallet so the chain averages three
    blocks an hour.
  </p>
  <p class="hint" id="god-support-stats">
    Learned topics: <strong id="god-learned-count">{html.escape(str(count))}</strong>
    · FRED scenarios: <strong id="fred-scenario-count">{html.escape(str(fred.get("count") or 0))}</strong>
    · cadence: 2 hours
  </p>
  <label for="god-question">Ask GOD</label>
  <textarea id="god-question" name="god_question" maxlength="{MAX_QUESTION}"
    placeholder="What would you like to know?"></textarea>
  <button type="button" id="god-ask-submit">Ask GOD</button>
  <pre class="god-support-answer" id="god-support-answer" hidden></pre>
</section>
<script id="god-support-script" src="/static/god_support.js" defer></script>
"""


def god_support_css() -> str:
    return """
.god-support-box {
  margin: 0 0 1.35rem;
  padding: 1rem 1rem 1.1rem;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--rb-neon-cyan, #7dd3fc) 35%, transparent);
  background: color-mix(in srgb, var(--rb-card, #132a4a) 88%, #041018);
}
.god-support-box h3 {
  margin: 0 0 0.35rem;
  letter-spacing: 0.08em;
  font-size: 1.05rem;
}
.god-support-lead { margin: 0 0 0.65rem; line-height: 1.5; color: var(--rb-soft, #aed0ea); }
.god-support-box textarea {
  width: 100%; box-sizing: border-box; min-height: 5.5rem;
  margin: 0.35rem 0 0.65rem; padding: 0.7rem 0.85rem;
  border-radius: 10px; font: inherit;
}
.god-support-answer {
  margin: 0.85rem 0 0; white-space: pre-wrap; line-height: 1.45;
  font-size: 0.9rem; color: var(--rb-cream, #e8eef5);
}
#god-ask-submit {
  appearance: none; cursor: pointer; font: inherit; font-weight: 750;
  padding: 0.6rem 1.1rem; border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--rb-link, #7dd3fc) 35%, transparent);
  background: linear-gradient(180deg, var(--rb-btn, #2694e8) 0%, var(--rb-btn-deep, #1a6fb3) 100%);
  color: var(--rb-btn-text, #0a1628);
}
"""
