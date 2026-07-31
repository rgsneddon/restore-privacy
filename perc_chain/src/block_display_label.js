/**
 * Short generic labels for the block explorer table.
 * Full scenario / memo text remains in block detail (View).
 */

function norm(value) {
  return (value ?? '').toString().trim().toLowerCase();
}

function collectScenarioText(block) {
  const parts = [block?.scenarioLabel];
  for (const tx of block?.transactions ?? []) {
    parts.push(tx.scenarioLabel, tx.memo);
  }
  return norm(parts.filter(Boolean).join(' '));
}

function isScsInput(text) {
  return (
    text.includes('social cohesion') ||
    /\bscs\b/.test(text) ||
    text.includes('cohesion score')
  );
}

function isPercentChanceInput(text) {
  return text.includes('percent chance') || /\bpercent\b/.test(text);
}

/**
 * @param {object|null|undefined} block
 * @returns {string}
 */
export function genericBlockLabel(block) {
  if (!block) return '—';

  const txs = block.transactions ?? [];
  const kinds = new Set(txs.map((tx) => tx.kind).filter(Boolean));
  const text = collectScenarioText(block);

  if (kinds.has('transfer')) return 'Manual tx';

  if (kinds.has('scenarioReward') || kinds.has('scenarioFaucet')) {
    if (isScsInput(text)) return 'SCS input';
    if (isPercentChanceInput(text)) return '% chance input';
    return 'Scenario reward';
  }
  if (kinds.has('transferRevert')) return 'Transfer revert';

  if (block.microblockSeal || kinds.has('chronofluxMicroblock')) {
    return 'Microblock seal';
  }

  if (kinds.has('genesisRenewal')) return 'Genesis renewal';

  if (kinds.has('stakingReward')) return 'Staked reward';

  if (kinds.has('feeBurn') && !kinds.has('transfer')) return 'Burned PERC';

  if (kinds.has('treasuryEmission')) {
    if (text.includes('regeneration')) return 'Treasury regeneration';
    if (text.includes('launch')) return 'Blockchain launch';
    return 'Treasury emission';
  }

  if (text.includes('chronoflux microblock')) return 'Microblock seal';
  if (text.includes('treasury regeneration')) return 'Treasury regeneration';
  if (text.includes('blockchain launch')) return 'Blockchain launch';
  if (isScsInput(text)) return 'SCS input';
  if (isPercentChanceInput(text)) return '% chance input';

  if (block.triggerUsername) return 'Network activity';
  return '—';
}