import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { LedgerStore, blockHeight, tipHash } from './ledger_store.js';
import { createGenesisLedger } from './genesis.js';

describe('LedgerStore.status aligns with wallet PercChainTip', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'perc-ledger-status-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('reports main-chain block height and tip hash from ledger blocks', () => {
    const store = new LedgerStore(tmpDir);
    const base = createGenesisLedger({ genesisRevision: 2 });
    base.blockchainLaunched = true;
    base.blocks = [
      {
        index: 0,
        timestamp: '2026-07-06T10:00:00.000Z',
        treasuryEmitted: { microUnits: 100_000_000 },
        transactions: [],
      },
      {
        index: 1,
        timestamp: '2026-07-06T11:00:00.000Z',
        treasuryEmitted: { microUnits: 0 },
        transactions: [
          {
            id: 'tx-1',
            kind: 'transfer',
            amount: { microUnits: 5 },
            timestamp: '2026-07-06T11:00:00.000Z',
            blockIndex: 1,
            confirmations: 1,
          },
        ],
      },
    ];
    store.forceReplaceLedger(base);

    const status = store.status('evolve_seed_node', 'https://seed.example');
    assert.equal(status.blockHeight, blockHeight(store.ledger));
    assert.equal(status.tipHash, tipHash(store.ledger));
    assert.equal(status.blockHeight, 2);
  });
});