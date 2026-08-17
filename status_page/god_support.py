"""GOD support box — field-input Q&A above the public ticket form.

GOD is the current rpAI helper. If a question is not already known, GOD
must research and learn a real answer *before* replying. Users never teach
GOD; placeholders like "I do not have that part yet" are not answers and
are never stored as learned topics.

FRED still runs the Helsinki two-hour scenario cadence; GOD may run the
same bot. Learning stores non-personal question topics only — never emails,
KEYGENs, cards, or tunnel payloads.
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
from typing import Any, Callable

GOD_ASK_PATH = "/support/god-ask"
GOD_BOX_ID = "god-support-box"
SCENARIO_INTERVAL_SEC = 7200
FRED_NAME = "FRED"
GOD_NAME = "GOD"
MAX_QUESTION = 800
MAX_LEARN_ROWS = 200
MAX_ANSWER = 2000

FORBIDDEN_RE = re.compile(
    r"RPT-KEY-|keygen|seed phrase|mnemonic|card number|password|tunnel payload",
    re.I,
)

# Grow-fallback prose from the first GOD box — never treat as a learned answer.
GROW_MARKERS: tuple[str, ...] = (
    "i do not have that part yet",
    "thrilled to learn it",
    "i can author the next one",
    "for account help, use the ticket form",
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
        "Community contact is Discord (https://discord.gg/H9TdGyCUCa). "
        "Email tickets live on restoreprivacy.online/support, not the GOD "
        "page. Do not paste passwords, cards, or KEYGENs.",
    ),
    (
        "privacy",
        "Residual Connect does not keep browsing history on our nodes. "
        "Visit logs for Audit live on your own device.",
    ),
    (
        "evolve",
        "evolve.restoreprivacy.online is the Evolve Chronoflux app landing "
        "(downloads + info). /explorer is the Perccent explorer. GOD is the "
        "identity; NED leads under GOD; FRED and PEDRO report to NED.",
    ),
    (
        "suite architecture",
        "The Restore Privacy Suite nav map is seven surfaces: Residual VPN, "
        "Wallet (%), Backup recovery, Evolve analysis, Evolve voting, Credit, "
        "and rpAI · Ned. GOD learns each surface from residual heartbeats.",
    ),
    (
        "suite surfaces",
        "Suite surfaces are vpn, wallet, backup, analysis, voting, credit, "
        "and rpai. Backup is the Security/Backup recovery tab.",
    ),
    (
        "beamhash",
        "Perccent PERC pool uses BeamHash III. Normal difficulty is "
        "mineperc.restoreprivacy.online:1466; high difficulty is :3334.",
    ),
    (
        "perc pool",
        "The Perccent pool is mineperc.restoreprivacy.online — port 1466 "
        "normal difficulty, port 3334 high difficulty, BeamHash III.",
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
            FRED_NAME: {
                "last_at": 0,
                "next_at": 0,
                "count": 0,
                "last_source": "",
                "last_q": "",
            },
            GOD_NAME: {
                "last_at": 0,
                "next_at": 0,
                "count": 0,
                "last_source": "",
                "last_q": "",
            },
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


def is_real_answer(text: str) -> bool:
    """True when *text* is a usable answer, not a grow/placeholder line."""
    raw = (text or "").strip()
    if len(raw) < 24:
        return False
    low = raw.lower()
    return not any(marker in low for marker in GROW_MARKERS)


def record_learn(question: str, answer: str, source: str) -> dict[str, Any]:
    q = strip_secrets(question)
    if not q:
        return {"ok": False, "refused": "forbidden_or_empty"}
    if not is_real_answer(answer):
        return {"ok": False, "refused": "not_a_real_answer"}
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
            ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
    existing.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(existing[-MAX_LEARN_ROWS:]) + "\n", encoding="utf-8")
    return {"ok": True, "learned": True, "topic": row["topic"]}


def learned_count() -> int:
    p = learn_path()
    if not p.is_file():
        return 0
    return sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip())


_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "what",
        "how",
        "are",
        "was",
        "can",
        "you",
        "your",
        "does",
        "did",
        "about",
        "please",
        "tell",
        "into",
        "have",
        "has",
        "not",
        "why",
        "who",
        "when",
        "where",
    }
)


def _question_tokens(question: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9]{3,}", (question or "").lower())
        if t not in _STOPWORDS
    }


def local_answer(question: str) -> str | None:
    """Known product fact or a previously *real* learned answer.

    Grow/placeholder rows are ignored — users never teach GOD, and a stored
    'I do not have that part yet' is not knowledge.
    """
    q = (question or "").strip().lower()
    if not q:
        return None
    for needle, ans in GOD_KNOWN:
        if needle in q:
            return ans
    tokens = _question_tokens(q)
    best_ans = ""
    best_hits = 0
    for needle, ans in GOD_KNOWN:
        hits = len(tokens & _question_tokens(needle))
        if hits > best_hits and hits >= 2:
            best_hits = hits
            best_ans = ans
    if best_ans:
        return best_ans
    p = learn_path()
    if p.is_file():
        for ln in reversed(p.read_text(encoding="utf-8").splitlines()):
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if str(rec.get("source") or "") == "grow":
                continue
            prev = str(rec.get("q") or "").lower()
            ans = str(rec.get("a") or "").strip()
            if not prev or not is_real_answer(ans):
                continue
            if prev in q or q in prev:
                return ans
    return None


_DOC_CACHE: list[str] | None = None
_DOC_NAMES: tuple[str, ...] = (
    "README.md",
    "PRIVACY_POLICY.md",
    "CERBERUS.md",
    "EVOLVE.md",
    "RPOS.md",
    "RX.md",
    "NODE_OPERATOR.md",
)


def _public_doc_dir() -> Path:
    return Path(__file__).resolve().parent / "public"


def _split_passages(text: str) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if buf:
                chunk = " ".join(buf).strip()
                if len(chunk) >= 40:
                    chunks.append(chunk[:500])
                buf = []
            continue
        if stripped.startswith("#"):
            if buf:
                chunk = " ".join(buf).strip()
                if len(chunk) >= 40:
                    chunks.append(chunk[:500])
                buf = []
            continue
        buf.append(stripped)
    if buf:
        chunk = " ".join(buf).strip()
        if len(chunk) >= 40:
            chunks.append(chunk[:500])
    return chunks


def _doc_passages() -> list[str]:
    global _DOC_CACHE
    if _DOC_CACHE is not None:
        return _DOC_CACHE
    out: list[str] = []
    root = _public_doc_dir()
    for name in _DOC_NAMES:
        path = root / name
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.extend(_split_passages(raw)[:40])
    try:
        from node.oracle_master import SUITE_SURFACE_IDS, SUITE_SURFACE_LABELS

        labels = ", ".join(
            f"{sid} ({SUITE_SURFACE_LABELS.get(sid, sid)})" for sid in SUITE_SURFACE_IDS
        )
        out.append(
            "Suite architecture surfaces: "
            + labels
            + ". Backup is the Security/Backup recovery tab. "
            "GOD learns these from residual /api/private/cojoined heartbeats."
        )
    except Exception:  # noqa: BLE001
        out.append(
            "Suite architecture surfaces: vpn, wallet, backup, analysis, "
            "voting, credit, rpai. Backup is the Security/Backup recovery tab."
        )
    _DOC_CACHE = out
    return out


def retrieve_product_passages(question: str, *, limit: int = 6) -> list[str]:
    """Score local product facts + public docs by token overlap."""
    tokens = _question_tokens(question)
    if not tokens:
        return []
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for needle, ans in GOD_KNOWN:
        hits = len(tokens & _question_tokens(needle + " " + ans))
        if hits <= 0:
            continue
        if ans in seen:
            continue
        seen.add(ans)
        scored.append((hits, ans))
    for passage in _doc_passages():
        hits = len(tokens & _question_tokens(passage))
        if hits <= 0:
            continue
        if passage in seen:
            continue
        seen.add(passage)
        scored.append((hits, passage))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    return [p for _s, p in scored[: max(1, int(limit))]]


def _xai_answer(question: str, *, context: str = "") -> str | None:
    key = (os.environ.get("XAI_API_KEY") or "").strip()
    if not key:
        return None
    ctx = (context or "").strip()
    prompt = (
        "You are GOD, the Restore Privacy Helper (rpAI). "
        "Find a factual answer before you reply. Never invent product facts. "
        "Never ask for KEYGENs, cards, or passwords. "
        "If the retrieved notes answer the question, use them. "
        "If they do not, reason from public Restore Privacy product knowledge "
        "only — residual VPN, Suite, Perccent, Evolve, rpAI.\n\n"
    )
    if ctx:
        prompt += f"Retrieved notes:\n{ctx[:3500]}\n\n"
    prompt += f"Question: {question[:MAX_QUESTION]}"
    body = json.dumps({"model": "grok-4.5", "input": prompt}).encode("utf-8")
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
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    text = str(data.get("output_text") or "").strip()
    if text:
        return text[:MAX_ANSWER]
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
            return joined[:MAX_ANSWER]
    return None


def _fetch_public_page(url: str, *, timeout_s: float = 8.0) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "text/plain, text/html;q=0.8", "User-Agent": "GOD-rpAI"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2500]


_PUBLIC_RESEARCH_URLS: tuple[str, ...] = (
    "https://restoreprivacy.online/privacy",
    "https://restoreprivacy.online/evolve",
    "https://restoreprivacy.online/",
)


def research_answer(
    question: str,
    *,
    xai_fn: Callable[..., str | None] | None = None,
    fetch_public: bool = True,
) -> tuple[str | None, str]:
    """Work hard on *this* question: retrieve, ask xAI, compose from notes.

    Returns (answer, source). Never returns grow-placeholder prose.
    Users do not supply answers — GOD finds them.
    """
    q = (question or "").strip()
    if not q:
        return None, ""
    passages = retrieve_product_passages(q)
    known = local_answer(q)
    if known and is_real_answer(known) and known not in passages:
        passages = [known] + passages

    # Second pass: public product pages only when local notes found nothing.
    if fetch_public and not passages:
        tokens = _question_tokens(q)
        for url in _PUBLIC_RESEARCH_URLS:
            page = _fetch_public_page(url)
            if not page:
                continue
            if not tokens or len(tokens & _question_tokens(page)) < 2:
                continue
            passages.append(page[:500])
            if len(passages) >= 4:
                break

    ctx = "\n---\n".join(passages[:6])
    caller = xai_fn if xai_fn is not None else _xai_answer
    remote = None
    try:
        remote = caller(q, context=ctx)
    except TypeError:
        try:
            remote = caller(q)  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            remote = None
    except Exception:  # noqa: BLE001
        remote = None
    if remote and is_real_answer(str(remote)):
        return str(remote).strip()[:MAX_ANSWER], "web"

    if known and is_real_answer(known):
        return known, "rpAI"
    if passages:
        composed = passages[0].strip()
        if is_real_answer(composed):
            return composed[:MAX_ANSWER], "docs"
    return None, ""


def answer_god_question(
    question: str,
    *,
    xai_fn: Callable[..., str | None] | None = None,
    fetch_public: bool = True,
) -> dict[str, Any]:
    """Research first, learn the real answer, then reply.

    Never replies with a grow placeholder. Never records a non-answer as
    learned. If research finds nothing, fail closed (still searching).
    """
    q = strip_secrets(question)
    if not q:
        return {
            "ok": False,
            "error": "Ask a question without secrets (no KEYGEN, card, or password).",
        }
    ans, source = research_answer(q, xai_fn=xai_fn, fetch_public=fetch_public)
    if not ans or not is_real_answer(ans):
        sc = load_scenarios()
        return {
            "ok": False,
            "who": GOD_NAME,
            "error": (
                "GOD is still researching that from product docs and public "
                "pages — no invented answer. Ask again shortly, or find us "
                "on Discord."
            ),
            "source": "researching",
            "learned": learned_count(),
            "thrilled": True,
            "fred": sc.get(FRED_NAME),
            "god_scenario": sc.get(GOD_NAME),
            "interval_sec": SCENARIO_INTERVAL_SEC,
        }
    recorded = record_learn(q, ans, source)
    if recorded.get("ok"):
        tick_scenario(
            GOD_NAME, source=source if source == "web" else "self", question=q
        )
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
    Ask GOD anything — product, rpAI mind, or the wider world. GOD finds
    an answer before it speaks. Visitors do not teach GOD. FRED still
    runs Helsinki scenarios every two hours. PEDRO reads x.com through Grok
    at minute 34. GOD is the rpAI leader; Grokbot (Grok Build) stays with
    GOD, NED, FRED, and PEDRO.
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
