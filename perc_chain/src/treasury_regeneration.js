import { formatPercAmount } from './explorer_api.js';
import { blockHeight } from './ledger_store.js';
import { dynamicEmissionMicroPerMinute } from './dynamic_emission.js';
const REGEN_RATIO_PERCENT = 66;


function treasuryNeedsRegeneration(balanceMicro, targetMicro) {
  return balanceMicro * 100 < targetMicro * REGEN_RATIO_PERCENT;
}

function amount(microUnits) {
  return { microUnits };
}

function addAmount(a, b) {
  return amount((a?.microUnits ?? 0) + (b?.microUnits ?? 0));
}

function subAmount(a, b) {
  return amount((a?.microUnits ?? 0) - (b?.microUnits ?? 0));
}

/**
 * When evolve_treasury balance drops below 66% of the minute target, mint toward the aligned rate.
 * Returns true when a regeneration block was appended.
 */
export function regenerateTreasuryIfLow(store, treasuryUsername = 'evolve_treasury') {
  const ledger = store.ledger;
  if (!ledger?.blockchainLaunched) return false;

  const treasury = ledger.accounts?.[treasuryUsername];
  if (!treasury) return false;

  const balanceMicro = treasury.balance?.microUnits ?? 0;
  const targetMicro = dynamicEmissionMicroPerMinute(ledger);
  if (!treasuryNeedsRegeneration(balanceMicro, targetMicro)) return false;

  const shortfallMicro = targetMicro - balanceMicro;
  if (shortfallMicro <= 0) return false;

  const now = new Date().toISOString();
  const shortfall = amount(shortfallMicro);
  const txId = `tx-${ledger.nextTxId ?? 1}`;

  treasury.balance = addAmount(treasury.balance ?? amount(0), shortfall);
  const tx = {
    id: txId,
    kind: 'treasuryEmission',
    amount: shortfall,
    timestamp: now,
    toUsername: treasuryUsername,
    memo: 'Treasury regeneration — balance below emission target',
    blockIndex: blockHeight(ledger),
    confirmations: 1,
  };
  treasury.transactions = [tx, ...(treasury.transactions ?? [])];

  ledger.cumulativeTreasuryMinted = addAmount(
    ledger.cumulativeTreasuryMinted ?? amount(0),
    shortfall,
  );
  ledger.lastScenarioAt = now;
  ledger.nextTxId = (ledger.nextTxId ?? 1) + 1;
  ledger.blocks = [
    ...(ledger.blocks ?? []),
    {
      index: blockHeight(ledger),
      timestamp: now,
      transactions: [tx],
      treasuryEmitted: shortfall,
      scenarioLabel: 'Treasury regeneration',
      triggerUsername: treasuryUsername,
      treasuryCycle: ledger.treasuryCycle ?? 1,
    },
  ];

  store.forceReplaceLedger(ledger);
  return true;
}

export function treasuryRegenerationStatus(ledger, treasuryUsername = 'evolve_treasury') {
  const treasury = ledger?.accounts?.[treasuryUsername];
  const balanceMicro = treasury?.balance?.microUnits ?? 0;
  const targetMicro = dynamicEmissionMicroPerMinute(ledger);
  return {
    threshold: formatPercAmount({
      microUnits: Math.floor((targetMicro * REGEN_RATIO_PERCENT) / 100),
    }),
    target: formatPercAmount({ microUnits: targetMicro }),
    needsRegeneration: Boolean(
      ledger?.blockchainLaunched &&
        treasuryNeedsRegeneration(balanceMicro, targetMicro),
    ),
    balance: formatPercAmount(treasury?.balance),
  };
}