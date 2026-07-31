import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { LedgerStore } from './ledger_store.js';
import { createGenesisLedger } from './genesis.js';
import { buildTreasuryWalletView } from './treasury_api.js';
import { buildNetworkSnapshot } from './explorer_api.js';
import { sumAccountBalancesMicro } from './treasury_merge.js';

const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
const TREASURY = 'evolve_treasury';

function launchLedger(base) {
  return {
    ...base,
    blockchainLaunched: true,
    treasuryGenesisDone: true,
    blocks: [
      ...(base.blocks ?? []),
      {
        index: base.blocks?.length ?? 0,
        timestamp: '2026-07-06T10:00:00.000Z',
        scenarioLabel: 'Blockchain launch',
        transactions: [],
      },
    ],
  };
}

function canonicalWithPayoutApplied(ledger, { percent, user, treasuryBefore, userBefore }) {
  const rewardMicro = percent * 1_000_000;
  const index = ledger.blocks.length;
  ledger.accounts[TREASURY].balance = { microUnits: treasuryBefore - rewardMicro };
  ledger.accounts[user] = {
    username: user,
    passwordHash: 'hash',
    salt: 'salt',
    address: `percpriv1${user}`,
    passwordSet: true,
    balance: { microUnits: userBefore + rewardMicro },
    cumulativeStakingEarned: { microUnits: 0 },
    transactions: [],
  };
  ledger.lastScenarioAt = '2026-07-06T12:00:00.000Z';
  ledger.blocks.push({
    index,
    timestamp: '2026-07-06T12:00:00.000Z',
    triggerUsername: user,
    scenarioLabel: 'Scenario analysis reward',
    transactions: [
      {
        id: `tx-scenario-${user}-${index}`,
        kind: 'scenarioReward',
        amount: { microUnits: rewardMicro },
        fromUsername: TREASURY,
        toUsername: user,
        percentChance: percent,
        timestamp: '2026-07-06T12:00:00.000Z',
      },
    ],
  });
  return rewardMicro;
}

describe('treasury_api and explorer treasury truth', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-treasury-api-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('buildTreasuryWalletView balance matches ledger after scenario payout', () => {
    const store = new LedgerStore(tmpDir);
    const ledger = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    const treasuryBefore = 100_000_000_000;
    ledger.accounts[TREASURY].balance = { microUnits: treasuryBefore };
    const rewardMicro = canonicalWithPayoutApplied(ledger, {
      percent: 42,
      user: 'alice',
      treasuryBefore,
      userBefore: 0,
    });
    store.forceReplaceLedger(ledger);

    const view = buildTreasuryWalletView(store);
    const treasury = store.treasuryAccount(TREASURY);

    assert.equal(view.ready, true);
    assert.equal(view.balanceMicroUnits, treasury.balance.microUnits);
    assert.equal(view.treasuryEmission.balance, view.balance);
    assert.equal(view.balanceMicroUnits, treasuryBefore - rewardMicro);
  });

  it('buildTreasuryWalletView balance matches ledger after staking payout', () => {
    const store = new LedgerStore(tmpDir);
    let ledger = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    const treasuryBefore = 50_000_000;
    const rewardMicro = 5;
    ledger.accounts[TREASURY].balance = { microUnits: treasuryBefore };
    ledger.accounts.staker = {
      username: 'staker',
      passwordHash: 'h',
      salt: 's',
      address: 'percpriv1staker',
      passwordSet: true,
      balance: { microUnits: 0 },
      cumulativeStakingEarned: { microUnits: 0 },
      transactions: [],
    };
    ledger.accounts[TREASURY].balance = { microUnits: treasuryBefore - rewardMicro };
    ledger.accounts.staker.balance = { microUnits: rewardMicro };
    ledger.accounts.staker.cumulativeStakingEarned = { microUnits: rewardMicro };
    ledger.blocks.push({
      index: ledger.blocks.length,
      timestamp: '2026-07-06T12:05:00.000Z',
      triggerUsername: 'staker',
      transactions: [
        {
          id: 'tx-staking-staker',
          kind: 'stakingReward',
          amount: { microUnits: rewardMicro },
          fromUsername: TREASURY,
          toUsername: 'staker',
          memo: 'Cumulative staking',
          timestamp: '2026-07-06T12:05:00.000Z',
        },
      ],
    });
    store.forceReplaceLedger(ledger);

    const view = buildTreasuryWalletView(store);
    assert.equal(view.balanceMicroUnits, treasuryBefore - rewardMicro);
    assert.equal(view.treasuryEmission.balance, '0.49999995');
  });

  it('seed import from shorter peer applies payout delta on canonical pre-balances', () => {
    const store = new LedgerStore(tmpDir);
    let tall = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    const preTreasury = 200_000_000_000;
    const preBob = 50_000_000;
    tall.accounts[TREASURY].balance = { microUnits: preTreasury };
    tall.accounts.bob = {
      username: 'bob',
      passwordHash: 'hash',
      salt: 'salt',
      address: 'percpriv1bob',
      passwordSet: true,
      balance: { microUnits: preBob },
      cumulativeStakingEarned: { microUnits: 0 },
      transactions: [],
    };
    tall.lastScenarioAt = '2026-07-06T09:00:00.000Z';
    for (let i = 0; i < 3; i += 1) {
      tall = {
        ...tall,
        blocks: [
          ...tall.blocks,
          {
            index: tall.blocks.length,
            timestamp: `2026-07-06T11:0${i}:00.000Z`,
            scenarioLabel: `Seed filler ${i}`,
            transactions: [{ id: `seed-old-${i}`, kind: 'scenarioReward' }],
          },
        ],
      };
    }
    const preSum = sumAccountBalancesMicro(tall);
    store.forceReplaceLedger(tall);

    const rewardMicro = 10 * 1_000_000;
    const peer = launchLedger(createGenesisLedger({ genesisRevision: 2, chainId: CHAIN_ID }));
    peer.lastScenarioAt = '2026-07-07T12:00:00.000Z';
    peer.accounts.bob = {
      username: 'bob',
      passwordHash: 'hash',
      salt: 'salt',
      address: 'percpriv1bobpeer',
      passwordSet: true,
      balance: { microUnits: rewardMicro },
      cumulativeStakingEarned: { microUnits: 0 },
      transactions: [],
    };
    peer.blocks.push({
      index: peer.blocks.length,
      timestamp: '2026-07-07T12:00:00.000Z',
      triggerUsername: 'bob',
      scenarioLabel: 'Scenario analysis reward',
      transactions: [
        {
          id: 'tx-peer-new-payout',
          kind: 'scenarioReward',
          amount: { microUnits: rewardMicro },
          fromUsername: TREASURY,
          toUsername: 'bob',
          percentChance: 10,
          timestamp: '2026-07-07T12:00:00.000Z',
        },
      ],
    });
    assert.ok(peer.blocks.length < tall.blocks.length);

    const imported = store.importLedger(peer);
    assert.equal(imported, true);

    const treasury = store.treasuryAccount(TREASURY);
    const bob = store.ledger.accounts.bob;
    assert.equal(treasury.balance.microUnits, preTreasury - rewardMicro);
    assert.equal(bob.balance.microUnits, preBob + rewardMicro);
    assert.equal(sumAccountBalancesMicro(store.ledger), preSum);

    const snapshot = buildNetworkSnapshot({
      peers: new Map(),
      ledgers: new Map(),
      store,
      seedUsername: 'evolve_seed_node',
      endpoint: 'http://127.0.0.1:1',
      chainId: CHAIN_ID,
    });
    assert.equal(snapshot.treasuryEmission.balance, buildTreasuryWalletView(store).balance);
  });
});