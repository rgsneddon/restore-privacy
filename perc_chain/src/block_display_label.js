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

  // Admin ChronoFlux progression (status-host mutators → confirmed seal)
  if (
    block.adminAction === true ||
    kinds.has('adminAction') ||
    text.includes('admin:') ||
    text.startsWith('admin ')
  ) {
    const kind = (block.adminActionKind || '').toString().trim();
    if (kind) {
      const pretty = kind
        .replace(/[_-]+/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
      return `Admin: ${pretty}`;
    }
    if (text.includes('admin:')) {
      const raw = (block?.scenarioLabel || '').toString().trim();
      if (raw) return raw.length > 48 ? `${raw.slice(0, 45)}…` : raw;
    }
    return 'Admin action';
  }

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