/**
 * Durable ledger resume: after save, a new LedgerStore on the same data dir
 * reloads tip/height (not empty genesis-only state).
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { createGenesisLedger } from './genesis.js';
import {
  LedgerStore,
  blockHeight,
  tipHash,
} from './ledger_store.js';

test('LedgerStore resumes tip/height from seed_ledger.json after restart', () => {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-ledger-resume-'));
  try {
    const first = new LedgerStore(dataDir);
    // Non-empty chain state with real blocks (same shape as production seed_ledger).
    const ledger = createGenesisLedger({ genesisRevision: 2 });
    ledger.blockchainLaunched = true;
    ledger.blocks = [
      {
        index: 0,
        timestamp: '2026-07-31T19:58:00.000Z',
        treasuryEmitted: { microUnits: 100_000_000 },
        transactions: [],
      },
      {
        index: 1,
        timestamp: '2026-07-31T20:00:00.000Z',
        treasuryEmitted: { microUnits: 0 },
        transactions: [
          {
            id: 'tx-resume-1',
            kind: 'transfer',
            amount: { microUnits: 5 },
            timestamp: '2026-07-31T20:00:00.000Z',
            blockIndex: 1,
            confirmations: 1,
          },
        ],
      },
    ];
    if (typeof first.forceReplaceLedger === 'function') {
      first.forceReplaceLedger(ledger);
    } else {
      first.ledger = ledger;
    }
    first.revision = 7;
    first.genesisRevision = 2;
    first.lastBootstrapAt = '2026-07-31T19:58:06.583Z';
    first.save();

    const heightBefore = blockHeight(first.ledger);
    const tipBefore = tipHash(first.ledger);
    assert.ok(heightBefore >= 1, `expected non-empty height, got ${heightBefore}`);
    assert.ok(tipBefore && tipBefore.length >= 16);
    assert.ok(fs.existsSync(path.join(dataDir, 'seed_ledger.json')));

    // New process / new store instance against the same durable dir.
    const second = new LedgerStore(dataDir);
    assert.equal(second.hasLedger(), true);
    assert.equal(blockHeight(second.ledger), heightBefore);
    assert.equal(tipHash(second.ledger), tipBefore);
    assert.equal(second.revision, 7);
    assert.equal(second.genesisRevision, 2);
    assert.equal(second.lastBootstrapAt, '2026-07-31T19:58:06.583Z');
  } finally {
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
});

test('empty data dir starts without ledger (honest baseline)', () => {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-ledger-empty-'));
  try {
    const store = new LedgerStore(dataDir);
    assert.equal(store.hasLedger(), false);
    assert.equal(blockHeight(store.ledger), 0);
  } finally {
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
});
