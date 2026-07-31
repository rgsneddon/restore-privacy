import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { compactLedgerForSeed } from './ledger_compact.js';

/** Representative pilot ledger shape (18 blocks, 4 users, long scenarios). */
function samplePilotLedger(blockCount = 18, holders = 4) {
  const longScenario =
    'Social cohesion score: @ACSPARTAN1: Lanark Larkhall Lesmahagow Coylton Irvine Kilmarnock Fife Rosyth Just some of areas with extremely similar stories in regards to Vietnamese kids in states of real distress chapping doors for help or food or asking passers by to assist them. Silence on this issue from…';

  const blocks = [];
  const treasuryTxs = [];

  for (let i = 0; i < blockCount; i += 1) {
    const txs = [
      {
        id: `tx-em-${i}`,
        kind: 'treasuryEmission',
        amount: { microUnits: 100000000000 * (i + 1) },
        timestamp: `2026-07-05T12:${String(i).padStart(2, '0')}:00.000Z`,
        toUsername: 'evolve_treasury',
        blockIndex: i,
        confirmations: 1,
      },
      {
        id: `tx-sc-${i}`,
        kind: 'scenarioReward',
        amount: { microUnits: 54000000 },
        timestamp: `2026-07-05T12:${String(i).padStart(2, '0')}:00.000Z`,
        fromUsername: 'evolve_treasury',
        toUsername: 'don',
        scenarioLabel: longScenario,
        percentChance: 53.7,
        blockIndex: i,
        confirmations: 1,
        continuumScs: 53.7,
        vortexScs: 53.0,
        shearScs: 53.4,
        resistanceScs: 50.7,
        flowScs: 55.4,
      },
    ];

    for (let h = 0; h < holders; h += 1) {
      const user = ['rus', 'raskul', 'don'][h] ?? `user${h}`;
      txs.push({
        id: `tx-st-${i}-${h}`,
        kind: 'stakingReward',
        amount: { microUnits: 5 },
        timestamp: `2026-07-05T12:${String(i).padStart(2, '0')}:00.000Z`,
        fromUsername: 'evolve_treasury',
        toUsername: user,
        memo: 'Cumulative staking (5 cents per block)',
        blockIndex: i,
        confirmations: 1,
      });
    }

    blocks.push({
      index: i,
      timestamp: `2026-07-05T12:${String(i).padStart(2, '0')}:00.000Z`,
      transactions: txs,
      treasuryEmitted: { microUnits: 100000000000 * (i + 1) },
      scenarioLabel: longScenario,
      triggerUsername: 'don',
      treasuryCycle: 1,
    });

    treasuryTxs.unshift(...txs);
  }

  const accounts = {
    evolve_treasury: {
      username: 'evolve_treasury',
      passwordHash: 'hash',
      salt: 'salt',
      address: 'percpriv169e954fb2cafa80af3ff6eee00fde8a34df25440',
      passwordSet: true,
      balance: { microUnits: 7767910999810 },
      transactions: treasuryTxs,
    },
    don: {
      username: 'don',
      address: 'percpriv1don',
      passwordHash: 'hash',
      salt: 'salt',
      passwordSet: true,
      balance: { microUnits: 1000000 },
      scenarioBlockHeight: 8,
      transactions: treasuryTxs.filter((t) => t.toUsername === 'don' || t.fromUsername === 'don'),
    },
    rus: {
      username: 'rus',
      address: 'percpriv1rus',
      passwordHash: 'hash',
      salt: 'salt',
      passwordSet: true,
      balance: { microUnits: 2000000 },
      scenarioBlockHeight: 5,
      transactions: treasuryTxs.filter((t) => t.toUsername === 'rus' || t.fromUsername === 'rus'),
    },
    raskul: {
      username: 'raskul',
      address: 'percpriv1raskul',
      passwordHash: 'hash',
      salt: 'salt',
      passwordSet: true,
      balance: { microUnits: 3000000 },
      scenarioBlockHeight: 3,
      transactions: treasuryTxs.filter((t) => t.toUsername === 'raskul' || t.fromUsername === 'raskul'),
    },
  };

  return {
    version: 9,
    evolutionaryChainId: 'evolve-chronoflux-principia-chain-1',
    blockchainLaunched: true,
    networkGenesisRevision: 2,
    treasuryCycle: 1,
    cumulativeTreasuryMinted: { microUnits: 77686000000000 },
    accounts,
    blocks,
    pendingInboundTransfers: [],
    microblockLog: [],
  };
}

function prettyBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

describe('disk growth estimates', () => {
  it('reports compaction savings for pilot-scale ledger', () => {
    const full = samplePilotLedger(18, 4);
    const compact = compactLedgerForSeed(full);
    const fullBytes = Buffer.byteLength(JSON.stringify(full), 'utf8');
    const compactBytes = Buffer.byteLength(JSON.stringify(compact), 'utf8');
    const ratio = compactBytes / fullBytes;

    assert.ok(ratio < 0.5, `expected >50% reduction, got ${(ratio * 100).toFixed(1)}%`);

    // Extrapolate to 1 GB threshold at observed ~20 blocks/day pilot rate.
    const bytesPerBlockCompact = compactBytes / 18;
    const blocksPerDay = 20;
    const bytesPerDay = bytesPerBlockCompact * blocksPerDay;
    const threshold = 0.8 * 1024 * 1024 * 1024;
    const daysTo800Mb = threshold / bytesPerDay;

    console.log('--- Seed disk model (18-block pilot) ---');
    console.log(`Full ledger JSON:     ${prettyBytes(fullBytes)}`);
    console.log(`Compact ledger JSON:  ${prettyBytes(compactBytes)}`);
    console.log(`Reduction:            ${((1 - ratio) * 100).toFixed(1)}%`);
    console.log(`Per block (compact):  ${prettyBytes(bytesPerBlockCompact)}`);
    console.log(`At 20 blocks/day:     ${prettyBytes(bytesPerDay)}/day`);
    console.log(`Days to 800 MB:       ${Math.round(daysTo800Mb)} (~${(daysTo800Mb / 365).toFixed(1)} years)`);
  });
});