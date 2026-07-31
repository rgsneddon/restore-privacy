import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  archiveSeedLedger,
  bootstrapSeedEpoch,
  isAnnualBootstrapDue,
} from './seed_bootstrap.js';
import { LedgerStore } from './ledger_store.js';

describe('bootstrapSeedEpoch', () => {
  it('increments revision, preserves accounts, and resets blocks to epoch marker', () => {
    const ledger = {
      version: 9,
      networkGenesisRevision: 2,
      evolutionaryChainId: 'evolve-chronoflux-principia-chain-1',
      blockchainLaunched: true,
      cumulativeTreasuryMinted: { microUnits: 500000000000 },
      treasuryCycle: 3,
      accounts: {
        alice: {
          username: 'alice',
          passwordHash: 'hash',
          salt: 'salt',
          address: 'percpriv1alice',
          passwordSet: true,
          balance: { microUnits: 12345 },
          transactions: [{ id: 'tx-1', kind: 'scenarioReward' }],
        },
      },
      blocks: [
        { index: 0, timestamp: '2026-01-01T00:00:00.000Z', transactions: [] },
        { index: 1, timestamp: '2026-02-01T00:00:00.000Z', transactions: [] },
      ],
      microblockLog: [{ index: 1, label: 'Fair usage keystroke activity here' }],
      evolutionSteps: [{ appVersion: '3.0.0+62' }],
      wardProposals: [{ id: 1, title: 'Proposal' }],
      sessionUsername: 'alice',
    };

    const result = bootstrapSeedEpoch(ledger, {
      now: new Date('2026-07-05T12:00:00.000Z'),
      seedUsername: 'evolve_seed_node',
    });

    assert.equal(result.previousRevision, 2);
    assert.equal(result.newRevision, 3);
    assert.equal(result.ledger.networkGenesisRevision, 3);
    assert.equal(result.ledger.blocks.length, 1);
    assert.ok(result.ledger.blocks[0].scenarioLabel.includes('revision 2 → 3'));
    assert.deepEqual(result.ledger.microblockLog, []);
    assert.deepEqual(result.ledger.evolutionSteps, []);
    assert.deepEqual(result.ledger.wardProposals, []);
    assert.equal(result.ledger.sessionUsername, null);
    assert.equal(result.ledger.accounts.alice.balance.microUnits, 12345);
    assert.deepEqual(result.ledger.accounts.alice.transactions, []);
    assert.equal(result.ledger.cumulativeTreasuryMinted.microUnits, 500000000000);
    assert.equal(result.ledger.treasuryCycle, 3);
  });
});

describe('isAnnualBootstrapDue', () => {
  const prevDays = process.env.PERC_ANNUAL_BOOTSTRAP_DAYS;

  afterEach(() => {
    if (prevDays == null) delete process.env.PERC_ANNUAL_BOOTSTRAP_DAYS;
    else process.env.PERC_ANNUAL_BOOTSTRAP_DAYS = prevDays;
  });

  it('returns false when annual bootstrap is disabled', () => {
    process.env.PERC_ANNUAL_BOOTSTRAP_DAYS = '0';
    assert.equal(isAnnualBootstrapDue('2020-01-01T00:00:00.000Z'), false);
  });

  it('returns false when no prior bootstrap timestamp is recorded', () => {
    process.env.PERC_ANNUAL_BOOTSTRAP_DAYS = '365';
    assert.equal(isAnnualBootstrapDue(null), false);
  });

  it('returns true when interval elapsed', () => {
    process.env.PERC_ANNUAL_BOOTSTRAP_DAYS = '365';
    const now = new Date('2026-07-05T12:00:00.000Z');
    assert.equal(
      isAnnualBootstrapDue('2025-01-01T00:00:00.000Z', { now }),
      true,
    );
    assert.equal(
      isAnnualBootstrapDue('2026-06-01T00:00:00.000Z', { now }),
      false,
    );
  });
});

describe('LedgerStore.bootstrapEpoch', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-seed-bootstrap-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('archives prior ledger and saves compact epoch state', () => {
    const store = new LedgerStore(tmpDir);
    store.ledger = {
      version: 9,
      networkGenesisRevision: 2,
      evolutionaryChainId: 'evolve-chronoflux-principia-chain-1',
      blockchainLaunched: true,
      cumulativeTreasuryMinted: { microUnits: 1 },
      treasuryCycle: 1,
      accounts: {
        evolve_treasury: {
          username: 'evolve_treasury',
          passwordHash: 'hash',
          salt: 'salt',
          address: 'percpriv1treasury',
          passwordSet: true,
          balance: { microUnits: 99 },
          transactions: [],
        },
      },
      blocks: Array.from({ length: 5 }, (_, i) => ({
        index: i,
        timestamp: `2026-07-0${i + 1}T00:00:00.000Z`,
        transactions: [],
      })),
      microblockLog: [{ index: 1, label: 'x'.repeat(200) }],
    };
    store.genesisRevision = 2;
    store.save();

    const result = store.bootstrapEpoch({
      now: new Date('2026-07-05T12:00:00.000Z'),
    });
    assert.equal(result.ok, true);
    assert.equal(result.newRevision, 3);
    assert.ok(fs.existsSync(result.archivePath));
    assert.equal(store.ledger.blocks.length, 1);
    assert.deepEqual(store.ledger.microblockLog, []);
    assert.equal(store.genesisRevision, 3);
    assert.equal(store.lastBootstrapAt, result.bootstrappedAt);

    const reloaded = new LedgerStore(tmpDir);
    assert.equal(reloaded.genesisRevision, 3);
    assert.equal(reloaded.ledger.blocks.length, 1);
    assert.deepEqual(reloaded.ledger.microblockLog, []);
  });
});