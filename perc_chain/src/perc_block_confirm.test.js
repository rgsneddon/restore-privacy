import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  CONFIRMATION_MS,
  averageBlockIntervalMs,
  blockConfirmation,
  confirmationSnapshot,
  listPoolBlocks,
  nextBlockEta,
  recordPoolBlock,
  resetPoolBlocks,
} from './perc_block_confirm.js';

describe('pool block confirmations', () => {
  it('72 minutes until confirmed and spendable; ETA from average interval', () => {
    resetPoolBlocks();
    const t0 = 1_700_000_000_000;
    recordPoolBlock({ miner: 'alice.rig', height: 10, jobId: 'j10', foundAt: t0 });
    recordPoolBlock({ miner: 'bob.rig', height: 11, jobId: 'j11', foundAt: t0 + 600_000 });
    const mid = blockConfirmation({ foundAt: t0, miner: 'alice.rig', height: 10 }, t0 + CONFIRMATION_MS - 1);
    assert.equal(mid.confirmed, false);
    assert.equal(mid.spendable, false);
    assert.equal(mid.status, 'unconfirmed');
    const done = blockConfirmation({ foundAt: t0, miner: 'alice.rig', height: 10 }, t0 + CONFIRMATION_MS);
    assert.equal(done.confirmed, true);
    assert.equal(done.spendable, true);
    assert.equal(done.status, 'confirmed');
    assert.equal(averageBlockIntervalMs(), 600_000);
    const eta = nextBlockEta({ now: t0 + 600_000, rows: [
      { foundAt: t0 },
      { foundAt: t0 + 600_000 },
    ] });
    assert.equal(eta.averageMs, 600_000);
    assert.equal(eta.etaMs, 600_000);
    const snap = confirmationSnapshot(t0 + CONFIRMATION_MS);
    assert.equal(snap.confirmationMinutes, 72);
    assert.equal(snap.confirmationMs, CONFIRMATION_MS);
    assert.equal(snap.confirmed, 1);
    assert.equal(snap.unconfirmed, 1);
    const miners = listPoolBlocks(t0 + CONFIRMATION_MS).map((b) => b.miner);
    assert.ok(miners.includes('alice.rig'));
    assert.ok(miners.includes('bob.rig'));
  });
});
