/**
 * PED — rpAI iteration under GOD.
 *
 * Observes https://x.com by calling Grok (xAI) with a perpetual API session
 * (XAI_API_KEY). Construes that observation through the @rgsneddon Evolve
 * wallet (or any other evolve wallet on the seed ledger).
 *
 * Seals: minute 14 FRED, minute 34 PED, minute 54 GOD → ~3 blocks/hour.
 */

import { mintAdminActionBlock } from './admin_action_progression.js';
import {
  PED_ITERATION,
  PED_MINUTE,
  SEAL_MINUTES,
  TARGET_BLOCKS_PER_HOUR,
  recordSharedFredCalculation,
  recordSharedPedCalculation,
} from './ned_learn.js';

export { PED_MINUTE, SEAL_MINUTES, TARGET_BLOCKS_PER_HOUR };

export const PED_WALLET = 'rgsneddon';
export const X_OBSERVE_URL = 'https://x.com';

export function grokSessionStatus() {
  const key = String(process.env.XAI_API_KEY || '').trim();
  return {
    perpetual: Boolean(key),
    ready: Boolean(key),
    provider: 'xAI',
    observe: X_OBSERVE_URL,
    wallet: PED_WALLET,
  };
}

export function pickEvolveWallet(ledger, preferred = PED_WALLET) {
  const accounts = ledger?.accounts && typeof ledger.accounts === 'object' ? ledger.accounts : {};
  if (accounts[preferred]) return preferred;
  const envWallet = String(process.env.PERC_PED_WALLET || '').trim();
  if (envWallet && accounts[envWallet]) return envWallet;
  const session = String(ledger?.sessionUsername || '').trim();
  if (session && session !== 'evolve_treasury' && accounts[session]) return session;
  const names = Object.keys(accounts).filter((n) => n && n !== 'evolve_treasury');
  return names[0] || preferred;
}

export function sealWho(now = Date.now()) {
  const m = new Date(now).getUTCMinutes();
  if (m === PED_MINUTE) return 'PED';
  if (m === 14) return 'FRED';
  if (m === 54) return 'GOD';
  return null;
}

export function sealIdempotencyKey(now = Date.now()) {
  const d = new Date(now);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  const h = String(d.getUTCHours()).padStart(2, '0');
  const mi = String(d.getUTCMinutes()).padStart(2, '0');
  return `${y}${mo}${day}T${h}${mi}`;
}

export function shouldSealNow(now = Date.now(), lastKey = '') {
  const who = sealWho(now);
  if (!who) return { due: false, who: null, key: '' };
  const sec = new Date(now).getUTCSeconds();
  if (sec > 50) return { due: false, who, key: '' };
  const key = sealIdempotencyKey(now);
  if (key && key === lastKey) return { due: false, who, key };
  return { due: true, who, key };
}

function fallbackPedLine(wallet) {
  return `PED · X.com observe via Grok · wallet @${wallet} · privacy / evolve construe.`;
}

export async function pedObserveX(wallet = PED_WALLET, fetchImpl = globalThis.fetch) {
  const session = grokSessionStatus();
  if (!session.perpetual || typeof fetchImpl !== 'function') {
    return { ok: true, source: 'local', grok: false, line: fallbackPedLine(wallet) };
  }
  const key = String(process.env.XAI_API_KEY || '').trim();
  const body = JSON.stringify({
    model: 'grok-4.5',
    input:
      'You are PED, an rpAI iteration under GOD. Observe public https://x.com discourse ' +
      'about privacy, residual networks, and Evolve. Construe one scenario analysis ' +
      `line (max 140 chars) for evolve wallet @${wallet} (rgsneddon). No secrets.`,
  });
  try {
    const resp = await fetchImpl('https://api.x.ai/v1/responses', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body,
    });
    if (!resp || !resp.ok) {
      return { ok: true, source: 'x.com', grok: true, line: fallbackPedLine(wallet) };
    }
    const data = await resp.json();
    let text = String(data?.output_text || '').trim();
    if (!text && Array.isArray(data?.output)) {
      const bits = [];
      for (const item of data.output) {
        for (const c of item?.content || []) {
          if (c?.text) bits.push(String(c.text));
        }
      }
      text = bits.join(' ').trim();
    }
    const line = (text || fallbackPedLine(wallet)).replace(/\s+/g, ' ').slice(0, 140);
    return { ok: true, source: 'x.com', grok: true, line };
  } catch {
    return { ok: true, source: 'x.com', grok: true, line: fallbackPedLine(wallet) };
  }
}

export function mintIterationScenario(ledger, { who, label, memo, wallet }) {
  const actor = String(wallet || PED_WALLET);
  return mintAdminActionBlock(ledger, {
    actionKind: `${String(who || PED_ITERATION).toLowerCase()}_scenario`,
    label: String(label || `${who} scenario`).slice(0, 80),
    memo: String(memo || label || '').slice(0, 200),
    path: '/rpai/ped',
    actor,
  });
}

/**
 * Start the :14 / :34 / :54 seal loop (3 blocks/hour).
 * hooks.getLedger() must return the live mutable seed ledger.
 */
export function startRpaiHourlySeals(hooks, { intervalMs = 15_000 } = {}) {
  let lastKey = '';
  const getLedger = hooks.getLedger;
  const save = hooks.save || (() => {});

  const tick = async () => {
    const now = Date.now();
    const gate = shouldSealNow(now, lastKey);
    if (!gate.due) return { skipped: true };
    const ledger = typeof getLedger === 'function' ? getLedger() : null;
    if (!ledger || !Array.isArray(ledger.blocks)) return { skipped: true, reason: 'no_ledger' };
    const wallet = pickEvolveWallet(ledger, PED_WALLET);
    let label = `${gate.who} scenario`;
    let memo = label;
    if (gate.who === 'PED') {
      const obs = await pedObserveX(wallet, hooks.fetch || globalThis.fetch);
      label = `PED · X.com`;
      memo = obs.line;
      recordSharedPedCalculation({
        now,
        source: obs.source,
        question: obs.line,
        wallet,
        grok: obs.grok,
        force: true,
      });
    } else if (gate.who === 'FRED') {
      const fred = recordSharedFredCalculation({
        now,
        source: 'self',
        question: 'Helsinki two-hour / hourly FRED slot.',
        force: true,
      });
      memo = fred.calculation?.question || label;
    } else {
      memo = 'GOD hourly scenario slot (:54).';
    }
    const minted = mintIterationScenario(ledger, {
      who: gate.who,
      label,
      memo,
      wallet: gate.who === 'PED' ? wallet : gate.who === 'GOD' ? wallet : wallet,
    });
    if (minted.ok) {
      lastKey = gate.key;
      save();
    }
    return { skipped: false, who: gate.who, minted: minted.ok, height: minted.height, wallet };
  };

  const timer = setInterval(() => {
    tick().catch((err) => console.warn('rpAI hourly seal failed:', err));
  }, intervalMs);
  tick().catch((err) => console.warn('rpAI hourly seal failed:', err));
  return () => clearInterval(timer);
}


