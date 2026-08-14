import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { mintAdminActionBlock } from './admin_action_progression.js';
import {
  CONFIRMATION_MS,
  confirmationDelayMs,
  expectedAverageBlockMs,
  expectedBlocksPerHour,
  MINER_UNLOCK_DIFFICULTY_BITS,
  TARGET_BLOCK_INTERVAL_MS,
} from './chain_timing.js';
import { rewardAllOnBlockGen } from './perc_pool_credit.js';
import { blockConfirmation, confirmationSnapshot } from './perc_block_confirm.js';
import { applyPowToLedger, DEFAULT_DIFFICULTY_BITS } from './pow.js';

const BH3 = {
  preWork: '990504d96fba29cfd6d9c2f3f8663e511fca10758f33c1e4dea443bbe6c5aac0',
  nonce: '89c94dfd09620712',
  solution:
    'a4eb00a087831aa944d914c2d500b920b74bb86c9f3a1de38b9a0c5d3c18802ed66c6be4494c0cf7ac4b72e18e6a6ee2e4e842e323f6d8df0367df5b8e36bbd057adf9ec3b1817395ac98b481829fef5c247372eb65acbbed65d64d52e17a0bf9b956bff00000000',
};

describe('alignment without client rebuild', () => {
  it('hard-sets 3 blocks/hour, 20 min average, 72 second confirm', () => {
    assert.equal(expectedBlocksPerHour(), 3);
    assert.equal(expectedAverageBlockMs(), 20 * 60 * 1000);
    assert.equal(confirmationDelayMs(), 72_000);
    assert.equal(CONFIRMATION_MS, 72_000);
    assert.equal(TARGET_BLOCK_INTERVAL_MS, 1_200_000);
    assert.equal(MINER_UNLOCK_DIFFICULTY_BITS, 0);
    assert.equal(DEFAULT_DIFFICULTY_BITS, MINER_UNLOCK_DIFFICULTY_BITS);
  });

  it('every user and miner is credited on block generation', () => {
    const ledger = {
      accounts: {
        alice: { username: 'alice' },
        bob: { username: 'bob' },
        evolve_treasury: { username: 'evolve_treasury' },
      },
      mineCredits: {
        'carol.rig': { asset: 'PERC', username: 'carol', microUnits: 0 },
      },
      blocks: [],
    };
    const minted = mintAdminActionBlock(ledger, {
      actionKind: 'scenario',
      label: 'Alignment seal',
      actor: 'alice',
    });
    assert.equal(minted.ok, true);
    const names = Object.keys(ledger.mineCredits);
    assert.ok(names.includes('alice'));
    assert.ok(names.includes('bob'));
    assert.ok(names.includes('carol'));
    assert.ok(!names.includes('evolve_treasury'));
    assert.ok(ledger.accounts.alice.balance.microUnits > 0);
    assert.ok(ledger.accounts.bob.balance.microUnits > 0);
    assert.ok(ledger.accounts.carol.balance.microUnits > 0);
    const tip = ledger.blocks[0];
    const kinds = (tip.transactions || []).map((t) => t.kind);
    assert.ok(kinds.includes('block_gen_reward'));
    const aliceTx = (ledger.accounts.alice.transactions || []).find(
      (t) => t.kind === 'block_gen_reward',
    );
    assert.ok(aliceTx);
    assert.equal(aliceTx.toUsername, 'alice');
    const again = rewardAllOnBlockGen(ledger, { finder: 'alice', height: 1 });
    assert.ok(again.count >= 3);
  });

  it('valid miner unlocking hash appends a block inside the expected window bits', () => {
    const ledger = {
      blocks: [],
      accounts: { perc_user: { username: 'perc_user' } },
    };
    const accepted = applyPowToLedger(ledger, {
      username: 'perc_user.gpu0',
      nonce: BH3.nonce,
      output: BH3.solution,
      input: BH3.preWork,
    });
    assert.equal(accepted.accepted, true);
    assert.equal(accepted.unlocked, true);
    assert.equal(accepted.targetIntervalMs, TARGET_BLOCK_INTERVAL_MS);
    assert.equal(ledger.blocks.length, 1);
    assert.equal(ledger.blocks[0].minerUnlock, true);
    assert.match(ledger.blocks[0].memo, /Unlocking hash/);
    assert.ok(accepted.rewards.count >= 1);
    assert.ok(ledger.accounts.perc_user.balance.microUnits > 0);
    assert.ok(
      (ledger.accounts.perc_user.transactions || []).some(
        (t) => t.kind === 'block_gen_reward',
      ),
    );
  });

  it('fully confirmed at 72 seconds not 72 minutes', () => {
    const t0 = 1_700_000_000_000;
    const almost = blockConfirmation({ foundAt: t0, miner: 'alice' }, t0 + 71_999);
    assert.equal(almost.confirmed, false);
    const done = blockConfirmation({ foundAt: t0, miner: 'alice' }, t0 + 72_000);
    assert.equal(done.confirmed, true);
    assert.equal(done.spendable, true);
    const snap = confirmationSnapshot(t0);
    assert.equal(snap.spendableAfter, '72 seconds');
    assert.equal(snap.confirmationMs, 72_000);
  });
});
