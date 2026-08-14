/**
 * GOD / rpAI observe-learn + explorer lines (Perccent confirmation log).
 *
 * GOD is the current helper identity. NED is the hierarchical leader under
 * GOD. FRED and PEDRO report to NED. Each agent may learn for the
 * betterment of humanity. Surfaces match node/rpai_learn.py
 * and PRIVACY_POLICY.md. Public confirmations store a non-personal part
 * label + confirm id — never raw user prose, KEYGENs, cards, or tunnel
 * payloads.
 */

export const GOD_IDENTITY = 'GOD · rpAI';
export const NED_ITERATION = 'NED';
export const FRED_ITERATION = 'FRED';
export const PEDRO_ITERATION = 'PEDRO';
/** @deprecated Use PEDRO_ITERATION — display name is PEDRO. */
export const PED_ITERATION = PEDRO_ITERATION;
/** Helsinki scenario cadence for FRED (and GOD when it opts to run the same bot). */
export const SCENARIO_INTERVAL_SEC = 7200;
/** PEDRO X/Grok analysis fires at minute 34. With :14 and :54 seals → ~3 blocks/hour. */
export const PEDRO_MINUTE = 34;
export const PED_MINUTE = PEDRO_MINUTE;
export const SEAL_MINUTES = Object.freeze([14, 34, 54]);
export const TARGET_BLOCKS_PER_HOUR = 3;

export const NED_OBSERVE_SURFACES = Object.freeze({
  beam_pool: 'Beam pool',
  perc_pool: 'Perccent PERC pool',
  vpn_architecture: 'Residual Restore VPN architecture',
  evolve_structure: 'Evolve project structure',
  evolve_calculation: 'Evolve app calculation',
});

/** Shipped Perc pool cores — pool shape only, never miner identities. */
export const PERC_POOL_CORE_PARTS = Object.freeze([
  { label: 'Perccent PERC pool BeamHash III' },
  { label: 'mineperc.restoreprivacy.online:1466 normal difficulty' },
  { label: 'mineperc.restoreprivacy.online:3334 high difficulty' },
  { label: 'perc-mine linked to perc-stratum-pool and BASiC' },
]);

const FORBIDDEN_KEYS = new Set([
  'keygen',
  'key_gen',
  'rpt_key',
  'seed',
  'seed_phrase',
  'mnemonic',
  'card',
  'card_number',
  'tunnel_payload',
  'payload',
  'packet',
  'ciphertext',
  'raw_bytes',
]);

const FORBIDDEN_RE =
  /RPT-KEY-|keygen|seed phrase|mnemonic|tunnel payload|packet bytes|ciphertext|card number/i;

function norm(s) {
  return String(s ?? '').replace(/\s+/g, ' ').trim();
}

export function partKey(surface, label) {
  return `${surface}:${norm(label).toLowerCase()}`;
}

export function isForbiddenObservation(snapshot) {
  if (snapshot == null) return false;
  if (Array.isArray(snapshot)) return snapshot.some(isForbiddenObservation);
  if (typeof snapshot === 'object') {
    for (const [k, v] of Object.entries(snapshot)) {
      const lk = String(k || '').trim().toLowerCase();
      if (FORBIDDEN_KEYS.has(lk) || FORBIDDEN_RE.test(lk)) return true;
      if (isForbiddenObservation(v)) return true;
    }
    return false;
  }
  return FORBIDDEN_RE.test(String(snapshot));
}

export function emptyNedState() {
  return { height: 0, parts: [], index: {} };
}

export function emptyFredState() {
  return {
    calculations: [],
    lastAt: 0,
    nextAt: 0,
    scenarios: 0,
    lastSource: '',
    lastQuestion: '',
  };
}

export function emptyPedState() {
  return {
    calculations: [],
    lastAt: 0,
    nextAt: 0,
    scenarios: 0,
    lastSource: '',
    lastQuestion: '',
    lastWallet: '',
    grokPerpetual: false,
    xObserve: 0,
  };
}

function publicLabel(surface, snapshot) {
  const surfName = NED_OBSERVE_SURFACES[surface] || surface;
  if (snapshot && typeof snapshot === 'object' && !Array.isArray(snapshot)) {
    const raw = snapshot.label || snapshot.part || snapshot.name;
    if (raw) return norm(raw).slice(0, 120);
  }
  if (typeof snapshot === 'string' && snapshot.trim()) return norm(snapshot).slice(0, 120);
  return surfName;
}

export function applyObservation(state, { surface, snapshot = null, kind = 'observe' } = {}) {
  const st = state && typeof state === 'object' ? state : emptyNedState();
  if (!Array.isArray(st.parts)) st.parts = [];
  if (!st.index || typeof st.index !== 'object') st.index = {};
  if (!Number.isFinite(st.height)) st.height = 0;
  const surf = String(surface || '').trim();
  if (!Object.prototype.hasOwnProperty.call(NED_OBSERVE_SURFACES, surf)) {
    return { ok: false, refused: 'unknown_surface', state: st, grew: false };
  }
  if (isForbiddenObservation(snapshot)) {
    return { ok: false, refused: 'forbidden', state: st, grew: false };
  }
  const label = publicLabel(surf, snapshot);
  const key = partKey(surf, label);
  if (st.index[key]) {
    const existing = st.parts.find((p) => p.key === key) || null;
    return {
      ok: true,
      duplicate: true,
      part: existing,
      confirmId: existing?.confirmId,
      height: st.height,
      state: st,
      grew: false,
    };
  }
  const height = st.height + 1;
  const confirmId = `ned-${String(height).padStart(6, '0')}`;
  const part = {
    key,
    surface: surf,
    line: label,
    kind,
    confirmId,
    height,
  };
  st.height = height;
  st.parts.push(part);
  st.index[key] = confirmId;
  return {
    ok: true,
    duplicate: false,
    part,
    confirmId,
    height,
    state: st,
    grew: true,
  };
}

export function seedPercPoolCores(state) {
  const st = state && typeof state === 'object' ? state : emptyNedState();
  const results = [];
  for (const snapshot of PERC_POOL_CORE_PARTS) {
    results.push(applyObservation(st, { surface: 'perc_pool', snapshot, kind: 'core' }));
  }
  return { state: st, results, grew: results.some((r) => r.grew) };
}

export function applyNedCalculation(state, { label = 'Evolve app calculation', digest = '' } = {}) {
  const snap = { label: norm(label) || 'Evolve app calculation' };
  if (digest) snap.digest = norm(digest).slice(0, 64);
  return applyObservation(state, {
    surface: 'evolve_calculation',
    snapshot: snap,
    kind: 'calculation',
  });
}

export function scenarioDue(lastAt, now = Date.now(), intervalSec = SCENARIO_INTERVAL_SEC) {
  const last = Number(lastAt || 0);
  const t = Number(now);
  if (!Number.isFinite(t)) return false;
  if (!last) return true;
  return t - last >= intervalSec * 1000;
}

const FRED_SELF_QUESTIONS = Object.freeze([
  'How many Perc pool cores are confirmed this epoch?',
  'Does residual VPN architecture still match the Downloads Map pin?',
  'What BeamHash difficulty split is live on 1466 vs 3334?',
  'Is Evolve calculation height still growing without user payload?',
]);

export function tickPedCalculation(
  ped,
  now = Date.now(),
  { source = 'x.com', question = '', wallet = 'rgsneddon', grok = false, force = false } = {},
) {
  const st = ped && typeof ped === 'object' ? ped : emptyPedState();
  if (!Array.isArray(st.calculations)) st.calculations = [];
  const hourMs = 60 * 60 * 1000;
  if (!force && st.lastAt && Number(now) - Number(st.lastAt) < hourMs - 60_000) {
    return { ok: true, grew: false, due: false, state: st };
  }
  const height = st.scenarios + 1;
  const q = norm(question) || 'PEDRO observe https://x.com via Grok for @rgsneddon evolve wallet.';
  const row = {
    id: `ped-${String(height).padStart(6, '0')}`,
    at: Number(now),
    source: source || 'x.com',
    question: q.slice(0, 160),
    iteration: PEDRO_ITERATION,
    wallet: String(wallet || 'rgsneddon'),
  };
  st.scenarios = height;
  st.lastAt = Number(now);
  st.nextAt = Number(now) + hourMs;
  st.lastSource = row.source;
  st.lastQuestion = row.question;
  st.lastWallet = row.wallet;
  st.grokPerpetual = Boolean(grok);
  st.xObserve = Number(st.xObserve || 0) + 1;
  st.calculations.push(row);
  if (st.calculations.length > 48) st.calculations = st.calculations.slice(-48);
  return { ok: true, grew: true, due: true, calculation: row, state: st };
}

export function tickFredCalculation(
  fred,
  now = Date.now(),
  { source = 'self', question = '', force = false } = {},
) {
  const st = fred && typeof fred === 'object' ? fred : emptyFredState();
  if (!Array.isArray(st.calculations)) st.calculations = [];
  if (!force && !scenarioDue(st.lastAt, now)) {
    return { ok: true, grew: false, due: false, state: st };
  }
  const src = source === 'web' ? 'web' : 'self';
  const q =
    norm(question) ||
    FRED_SELF_QUESTIONS[st.scenarios % FRED_SELF_QUESTIONS.length];
  const height = st.scenarios + 1;
  const row = {
    id: `fred-${String(height).padStart(6, '0')}`,
    at: Number(now),
    source: src,
    question: q.slice(0, 160),
    iteration: FRED_ITERATION,
  };
  st.scenarios = height;
  st.lastAt = Number(now);
  st.nextAt = Number(now) + SCENARIO_INTERVAL_SEC * 1000;
  st.lastSource = src;
  st.lastQuestion = row.question;
  st.calculations.push(row);
  if (st.calculations.length > 48) st.calculations = st.calculations.slice(-48);
  return { ok: true, grew: true, due: true, calculation: row, state: st };
}

export function explorerNedPayload(state, fred, ped) {
  const parts = Array.isArray(state?.parts) ? state.parts : [];
  const recent = parts.slice().reverse();
  const fredSt =
    fred && typeof fred === 'object' ? fred : getSharedFredState();
  const pedSt =
    ped && typeof ped === 'object' ? ped : getSharedPedState();
  const pedCalcs = Array.isArray(pedSt.calculations) ? pedSt.calculations : [];
  const fredCalcs = Array.isArray(fredSt.calculations) ? fredSt.calculations : [];
  const lastNed = parts.length ? parts[parts.length - 1] : null;
  const lastFred = fredCalcs.length ? fredCalcs[fredCalcs.length - 1] : null;
  return {
    identity: GOD_IDENTITY,
    learned: parts.length,
    height: Number(state?.height || 0),
    recentLearned: recent.map((p) => ({
      line: p.line,
      surface: p.surface,
      confirmId: p.confirmId,
      height: p.height,
      kind: p.kind,
    })),
    surfaces: Object.keys(NED_OBSERVE_SURFACES),
    iterations: [
      {
        id: 'GOD',
        name: 'GOD',
        role: 'root helper',
        reportsTo: null,
        mayLearn: true,
        learned: parts.length + fredCalcs.length + pedCalcs.length,
        height: Number(state?.height || 0),
        intervalSec: SCENARIO_INTERVAL_SEC,
        lastAt: lastFred?.at || 0,
        nextAt: Number(fredSt.nextAt || 0),
        status: 'live',
      },
      {
        id: NED_ITERATION,
        name: 'NED',
        role: 'hierarchical leader under GOD',
        reportsTo: 'GOD',
        mayLearn: true,
        learned: parts.length,
        height: Number(state?.height || 0),
        intervalSec: null,
        lastAt: 0,
        lastLine: lastNed?.line || '',
        lastConfirmId: lastNed?.confirmId || '',
        status: 'leading',
      },
      {
        id: FRED_ITERATION,
        name: 'FRED',
        role: 'Helsinki scenario bot',
        reportsTo: 'NED',
        mayLearn: true,
        learned: fredCalcs.length,
        height: Number(fredSt.scenarios || 0),
        intervalSec: SCENARIO_INTERVAL_SEC,
        lastAt: Number(fredSt.lastAt || 0),
        nextAt: Number(fredSt.nextAt || 0),
        lastSource: fredSt.lastSource || '',
        lastQuestion: fredSt.lastQuestion || '',
        status: 'running',
      },
      {
        id: PEDRO_ITERATION,
        name: 'PEDRO',
        role: 'X.com / Grok observer · @rgsneddon wallet',
        reportsTo: 'NED',
        mayLearn: true,
        learned: pedCalcs.length,
        height: Number(pedSt.scenarios || 0),
        intervalSec: 3600,
        lastAt: Number(pedSt.lastAt || 0),
        nextAt: Number(pedSt.nextAt || 0),
        lastSource: pedSt.lastSource || '',
        lastQuestion: pedSt.lastQuestion || '',
        lastWallet: pedSt.lastWallet || 'rgsneddon',
        grokPerpetual: Boolean(pedSt.grokPerpetual),
        status: 'running',
      },
    ],
  };
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Shipped explorer NED fragment — line for line with confirmation ids. */
export function renderNedLearnedHtml(payload) {
  const rows = Array.isArray(payload?.recentLearned) ? payload.recentLearned : [];
  if (!rows.length) {
    return (
      '<ol class="ned-learned-lines" id="ned-learned-lines">' +
      '<li class="ned-learned-empty">No learned parts yet.</li></ol>'
    );
  }
  const items = rows.map((row) => {
    const line = esc(row.line);
    const cid = esc(row.confirmId);
    return (
      `<li class="ned-learned-line" data-confirm="${cid}">` +
      `<span class="ned-part">${line}</span> ` +
      `<span class="ned-confirm" data-confirm-id="${cid}">${cid}</span></li>`
    );
  });
  return `<ol class="ned-learned-lines" id="ned-learned-lines">${items.join('')}</ol>`;
}

let shared = emptyNedState();
let sharedFred = emptyFredState();
let sharedPed = emptyPedState();
let seededPercCores = false;

function ensurePercCores() {
  if (seededPercCores) return;
  seededPercCores = true;
  seedPercPoolCores(shared);
  if (scenarioDue(sharedFred.lastAt)) {
    const result = tickFredCalculation(sharedFred, Date.now(), {
      source: 'self',
      question: 'Helsinki two-hour scenario cadence is live.',
    });
    sharedFred = result.state;
  }
}

export function getSharedNedState() {
  ensurePercCores();
  return shared;
}

export function getSharedFredState() {
  return sharedFred;
}

export function getSharedPedState() {
  return sharedPed;
}

export function resetSharedNedState() {
  shared = emptyNedState();
  sharedFred = emptyFredState();
  sharedPed = emptyPedState();
  seededPercCores = false;
  return shared;
}

export function observeShared(surface, snapshot, kind = 'observe') {
  return applyObservation(shared, { surface, snapshot, kind });
}

export function recordSharedCalculation(opts) {
  return applyNedCalculation(shared, opts);
}

export function recordSharedFredCalculation(opts) {
  const result = tickFredCalculation(sharedFred, opts?.now, opts);
  sharedFred = result.state;
  return result;
}

export function recordSharedPedCalculation(opts) {
  const result = tickPedCalculation(sharedPed, opts?.now, opts);
  sharedPed = result.state;
  return result;
}
