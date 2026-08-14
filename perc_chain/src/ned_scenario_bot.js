/**
 * NED hourly Chronoflux bot — observe X, run unique SCS + % chance scenarios.
 * Chain activity (hourly SCS + % chance seals) powers rewards.
 * When a miner is running, every user (including miner wallets) gets the
 * same faucet xx/100 PERC as the initiator. Miners are users.
 */
import crypto from 'crypto';
import { UNITS_PER_PERC } from './chain_constants.js';

export const NED_USERNAME = 'ned';
export const FRED_USERNAME = 'fred';
export const TREASURY_USERNAME = 'evolve_treasury';
export const SEED_USERNAME = 'evolve_seed_node';

const X_OBSERVE_URLS = [
  'https://r.jina.ai/http://x.com/explore',
  'https://r.jina.ai/https://x.com/explore',
];

const TOPIC_CORPUS = [
  'civic trust after a public service outage',
  'neighbourhood cohesion during a heatwave',
  'local election turnout in a coastal ward',
  'hospital wait-time pressure this week',
  'school attendance after a transport strike',
  'food-price shock on a market street',
  'flood-alert coordination in a river town',
  'night-bus safety after a high-profile incident',
  'library opening hours in a shrinking budget',
  'harbour workers and overtime rules',
  'youth sports club funding gap',
  'power-cut recovery in a tower block',
  'water-quality scare on a commuter line',
  'festival crowd control in a small city',
  'housing list backlogs after a factory closure',
];

export function faucetMicroForOutcome(score) {
  const pct = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
  return Math.round((pct / 100) * UNITS_PER_PERC);
}

export function minerBookIsRunning(book) {
  const workers = book?.workers || book || [];
  if (Number(book?.minersOnline) > 0) return true;
  if (!Array.isArray(workers)) return false;
  return workers.some((w) => w && (w.connected === true || Number(w.lastHashAt) > 0));
}

export function registeredUsernames(ledger) {
  return Object.keys(ledger?.accounts || {}).filter(
    (k) => k && k !== TREASURY_USERNAME && k !== SEED_USERNAME,
  );
}

export function activeMinerWallets(book) {
  const workers = Array.isArray(book?.workers)
    ? book.workers
    : Array.isArray(book)
      ? book
      : [];
  const out = [];
  for (const w of workers) {
    if (!w) continue;
    const wallet = String(w.wallet || '').trim();
    const user = String(w.username || w.login || '').trim();
    const id = wallet || (user.includes('.') ? user.slice(0, user.indexOf('.')) : user);
    if (id) out.push(id);
  }
  return [...new Set(out)];
}

/** 0.00000005 PERC per 1 PERC already held — same as PercStaking.rewardPerPercHeld. */
export const STAKING_MICRO_PER_PERC = 5;

export function stakingMicroForHeld(heldMicro) {
  const held = Number(heldMicro) || 0;
  if (held <= 0) return 0;
  return Math.floor((held * STAKING_MICRO_PER_PERC) / UNITS_PER_PERC);
}

export function scenarioRecipients(
  ledger,
  { minerWallets = [], initiator = NED_USERNAME, minerRunning = false } = {},
) {
  const init = String(initiator || NED_USERNAME);
  const out = new Set([init]);
  if (minerRunning) {
    for (const name of registeredUsernames(ledger)) out.add(name);
    for (const raw of minerWallets || []) {
      const w = String(raw || '').trim();
      if (w) out.add(w);
    }
  }
  return [...out].filter((k) => k && k !== TREASURY_USERNAME && k !== SEED_USERNAME);
}

export function parseXHeadlines(text) {
  const raw = String(text || '');
  const lines = raw
    .split('\n')
    .map((l) => l.replace(/^#+\s*/, '').trim())
    .filter((l) => l.length >= 24 && l.length <= 160 && /[a-zA-Z]/.test(l));
  const seen = new Set();
  const out = [];
  for (const line of lines) {
    const key = line.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(line);
    if (out.length >= 12) break;
  }
  return out;
}

export function uniqueScenarioPair(now = new Date(), headlines = [], salt = NED_USERNAME) {
  const hourKey = `${now.toISOString().slice(0, 13)}:${salt}`;
  const h = crypto.createHash('sha256').update(hourKey).digest();
  const pool = headlines.length ? headlines : TOPIC_CORPUS;
  const i = h[0] % pool.length;
  const j = (h[1] + 1) % pool.length;
  const pctScore = 1 + (h[2] % 99);
  let scsScore = 1 + (h[3] % 99);
  if (scsScore === pctScore) scsScore = (scsScore % 99) + 1;
  const a = pool[i];
  const b = pool[j === i ? (j + 1) % pool.length : j];
  return {
    hourKey,
    percent: {
      kind: 'percent_chance',
      label: `Percent chance: ${a}?`,
      score: pctScore,
    },
    cohesion: {
      kind: 'social_cohesion',
      label: `Social cohesion score: ${b}`,
      score: scsScore,
    },
  };
}

function ensureAccount(ledger, username) {
  ledger.accounts = ledger.accounts || {};
  if (!ledger.accounts[username]) {
    ledger.accounts[username] = {
      username,
      address: '',
      balance: { microUnits: 0 },
      cumulativeStakingEarned: { microUnits: 0 },
      transactions: [],
    };
  }
  return ledger.accounts[username];
}

function addMicro(bal, delta) {
  return { microUnits: (bal?.microUnits || 0) + delta };
}

export function applyNedScenario(
  ledger,
  run,
  { minerWallets = [], minerRunning = false, now = new Date(), initiator = NED_USERNAME } = {},
) {
  const score = run.score;
  const unit = faucetMicroForOutcome(score);
  const agent = String(initiator || NED_USERNAME);
  const recipients = scenarioRecipients(ledger, {
    minerWallets,
    initiator: agent,
    minerRunning,
  });
  ensureAccount(ledger, TREASURY_USERNAME);
  for (const u of recipients) ensureAccount(ledger, u);
  const held = {};
  for (const name of registeredUsernames(ledger)) {
    held[name] = ledger.accounts[name]?.balance?.microUnits || 0;
  }
  const faucetSet = new Set(recipients);
  const stakePays = [];
  for (const name of registeredUsernames(ledger)) {
    if (faucetSet.has(name)) continue;
    const stake = stakingMicroForHeld(held[name] || 0);
    if (stake > 0) stakePays.push({ name, stake });
  }
  const stakeTotal = stakePays.reduce((s, p) => s + p.stake, 0);
  const total = unit * recipients.length + stakeTotal;
  const treasury = ledger.accounts[TREASURY_USERNAME];
  if ((treasury.balance?.microUnits || 0) < total) {
    return { ok: false, reason: 'treasuryEmpty', unit, recipients, stakePays };
  }
  const ts = now.toISOString();
  const index = (ledger.blocks || []).length;
  const txs = [];
  treasury.balance = addMicro(treasury.balance, -total);
  for (const name of recipients) {
    const acc = ledger.accounts[name];
    acc.balance = addMicro(acc.balance, unit);
    const tx = {
      id: `ned-${run.kind}-${index}-${name}-${crypto.randomBytes(3).toString('hex')}`,
      kind: 'scenarioReward',
      amount: { microUnits: unit },
      timestamp: ts,
      fromUsername: TREASURY_USERNAME,
      toUsername: name,
      scenarioLabel: run.label,
      percentChance: score,
      blockIndex: index,
    };
    acc.transactions = acc.transactions || [];
    acc.transactions.unshift(tx);
    treasury.transactions = treasury.transactions || [];
    treasury.transactions.unshift(tx);
    txs.push(tx);
  }
  for (const { name, stake } of stakePays) {
    const acc = ledger.accounts[name];
    acc.balance = addMicro(acc.balance, stake);
    acc.cumulativeStakingEarned = addMicro(acc.cumulativeStakingEarned, stake);
    const tx = {
      id: `ned-stake-${run.kind}-${index}-${name}-${crypto.randomBytes(3).toString('hex')}`,
      kind: 'stakingReward',
      amount: { microUnits: stake },
      timestamp: ts,
      fromUsername: TREASURY_USERNAME,
      toUsername: name,
      memo: 'Staking on already-held PERC (chain activity)',
      scenarioLabel: run.label,
      blockIndex: index,
    };
    acc.transactions = acc.transactions || [];
    acc.transactions.unshift(tx);
    treasury.transactions.unshift(tx);
    txs.push(tx);
  }
  ledger.blocks = ledger.blocks || [];
  ledger.blocks.push({
    index,
    timestamp: ts,
    scenarioLabel: run.label,
    triggerUsername: agent,
    nedHourly: true,
    nedKind: run.kind,
    agent,
    transactions: txs,
  });
  ledger.lastScenarioAt = ts;
  return {
    ok: true,
    unit,
    recipients,
    stakePays,
    score,
    label: run.label,
    kind: run.kind,
    height: index,
    initiator: agent,
  };
}

export function applyNedHourlyPair(
  ledger,
  {
    minerWallets = [],
    minerRunning = false,
    now = new Date(),
    headlines = [],
    initiator = NED_USERNAME,
  } = {},
) {
  const wallets = minerWallets || [];
  const agent = String(initiator || NED_USERNAME);
  const pair = uniqueScenarioPair(now, headlines, agent);
  const percent = applyNedScenario(ledger, pair.percent, {
    minerWallets: wallets,
    minerRunning,
    now,
    initiator: agent,
  });
  const cohesion = applyNedScenario(ledger, pair.cohesion, {
    minerWallets: wallets,
    minerRunning,
    now,
    initiator: agent,
  });
  return {
    hourKey: pair.hourKey,
    percent,
    cohesion,
    minerRunning,
    minerWallets: wallets,
    initiator: agent,
  };
}

export async function observeXHeadlines(fetchImpl = globalThis.fetch, urls = X_OBSERVE_URLS) {
  if (typeof fetchImpl !== 'function') return [];
  for (const url of urls) {
    try {
      const res = await fetchImpl(url, { headers: { 'User-Agent': 'NED-chronoflux/1.0' } });
      if (!res || !res.ok) continue;
      const text = await res.text();
      const heads = parseXHeadlines(text);
      if (heads.length) return heads;
    } catch {
      // try next
    }
  }
  return [];
}
