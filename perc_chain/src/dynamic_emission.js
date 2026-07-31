import {
  FAUCET_COOLDOWN_SECONDS,
  MAX_FAUCET_PAYOUT_MICRO,
  UNITS_PER_PERC,
} from './chain_constants.js';

const TREASURY_USERNAME = 'evolve_treasury';
const MIN_COMBINED_PERCENT = 50;
const MAX_COMBINED_PERCENT = 1000;

function formatPercMicro(micro) {
  const whole = Math.floor(micro / UNITS_PER_PERC);
  const fraction = micro % UNITS_PER_PERC;
  if (!fraction) return String(whole);
  const frac = String(fraction).padStart(8, '0').replace(/0+$/, '');
  return frac ? `${whole}.${frac}` : String(whole);
}

function averageBlockSeconds(blocks) {
  if (!blocks || blocks.length < 2) return FAUCET_COOLDOWN_SECONDS;
  const first = new Date(blocks[0].timestamp).getTime();
  const last = new Date(blocks[blocks.length - 1].timestamp).getTime();
  const spanSec = Math.max(1, Math.floor((last - first) / 1000));
  return Math.max(1, Math.floor(spanSec / (blocks.length - 1)));
}

function emissionContextFromLedger(ledger) {
  const accounts = ledger?.accounts ?? {};
  const wallets = Object.keys(accounts).filter((k) => k !== TREASURY_USERNAME).length;
  const nodes = Object.values(ledger?.networkNodes ?? {});
  const online = nodes.filter((n) => n.online && n.username !== TREASURY_USERNAME).length;
  const walletCount = Math.max(wallets > 0 ? wallets : 1, online > 0 ? online : 1);
  return {
    walletCount,
    onlineWalletCount: online,
    averageBlockSeconds: averageBlockSeconds(ledger?.blocks ?? []),
  };
}

function loadFactorPercent(walletCount) {
  const wallets = Math.max(1, walletCount);
  const raw = Math.round(Math.sqrt(wallets) * 100);
  return Math.min(MAX_COMBINED_PERCENT, Math.max(100, raw));
}

function blockTimeFactorPercent(averageBlockSeconds) {
  const avgSec = Math.max(1, Math.min(86400, averageBlockSeconds));
  const raw = Math.floor((FAUCET_COOLDOWN_SECONDS * 100) / avgSec);
  return Math.min(500, Math.max(MIN_COMBINED_PERCENT, raw));
}

function combinedFactorPercent(context) {
  const load = loadFactorPercent(context.walletCount);
  const block = blockTimeFactorPercent(context.averageBlockSeconds);
  const combined = Math.floor((load * block) / 100);
  return Math.min(MAX_COMBINED_PERCENT, Math.max(MIN_COMBINED_PERCENT, combined));
}

export function dynamicEmissionMicroPerMinute(ledger) {
  const context = emissionContextFromLedger(ledger);
  const combined = combinedFactorPercent(context);
  const perCooldown = Math.floor((MAX_FAUCET_PAYOUT_MICRO * combined) / 100);
  return Math.floor((perCooldown * 60) / FAUCET_COOLDOWN_SECONDS);
}

export function buildDynamicEmissionStats(ledger) {
  const context = emissionContextFromLedger(ledger);
  const load = loadFactorPercent(context.walletCount);
  const block = blockTimeFactorPercent(context.averageBlockSeconds);
  const combined = combinedFactorPercent(context);
  const microPerMinute = dynamicEmissionMicroPerMinute(ledger);
  const regenThresholdMicro = Math.floor((microPerMinute * 66) / 100);
  const balanceMicro = ledger?.accounts?.[TREASURY_USERNAME]?.balance?.microUnits ?? 0;

  return {
    emissionPerMinute: formatPercMicro(microPerMinute),
    emissionMicroPerMinute: microPerMinute,
    loadFactorPercent: load,
    blockTimeFactorPercent: block,
    combinedFactorPercent: combined,
    walletLoadCount: context.walletCount,
    averageBlockSeconds: context.averageBlockSeconds,
    regenerationThreshold: formatPercMicro(regenThresholdMicro),
    needsRegeneration: balanceMicro * 100 < microPerMinute * 66,
    dynamic: true,
  };
}