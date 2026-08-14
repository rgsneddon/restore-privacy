import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  applyCredit,
  creditAcceptedShare,
  PAYOUT_ASSET,
  rewardAllOnBlockGen,
} from './perc_pool_credit.js';
import { checkShare } from './beamhash_iii.js';

describe('creditAcceptedShare', () => {
  it('credits PERC to a Perccent username, never BEAM', () => {
    const rec = creditAcceptedShare({
      username: 'mod_ainsdale.rig1',
      microUnits: 3,
      jobId: 'j1',
    });
    assert.equal(rec.asset, 'PERC');
    assert.equal(rec.asset, PAYOUT_ASSET);
    assert.equal(rec.username, 'mod_ainsdale');
    assert.equal(rec.microUnits, 3);
    assert.equal(rec.kind, 'mined_share');
    assert.notEqual(rec.asset, 'BEAM');
  });

  it('refuses a BEAM payout asset or Beam-style address', () => {
    assert.throws(
      () => creditAcceptedShare({ username: 'alice', asset: 'BEAM' }),
      /payout_asset_must_be_PERC/,
    );
    assert.throws(
      () => creditAcceptedShare({ username: 'beam:sbbs1alice' }),
      /beam_payout_forbidden/,
    );
  });
});

describe('accepted share → PERC credit (shipped path)', () => {
  it('one accepted checkShare result yields a PERC book credit', () => {
    const checked = checkShare({
      preWork: '990504d96fba29cfd6d9c2f3f8663e511fca10758f33c1e4dea443bbe6c5aac0',
      nonce: '89c94dfd09620712',
      solution:
        'a4eb00a087831aa944d914c2d500b920b74bb86c9f3a1de38b9a0c5d3c18802ed66c6be4494c0cf7ac4b72e18e6a6ee2e4e842e323f6d8df0367df5b8e36bbd057adf9ec3b1817395ac98b481829fef5c247372eb65acbbed65d64d52e17a0bf9b956bff00000000',
    });
    assert.equal(checked.ok, true, checked.reason);
    const credit = creditAcceptedShare({
      username: 'perc_miner.gpu0',
      jobId: 'tip-3',
    });
    assert.equal(credit.asset, 'PERC');
    const book = applyCredit({}, credit);
    assert.equal(book.perc_miner.asset, 'PERC');
    assert.equal(book.perc_miner.microUnits, 1);
    assert.notEqual(book.perc_miner.asset, 'BEAM');
  });
});

describe('rewardAllOnBlockGen wallet path', () => {
  it('credits accounts[u].balance and posts block_gen_reward txs wallets sync', () => {
    const ledger = {
      accounts: {
        evolve_treasury: {
          username: 'evolve_treasury',
          balance: { microUnits: 1_000 },
          transactions: [],
        },
        alice: { username: 'alice', balance: { microUnits: 10 }, transactions: [] },
        bob: { username: 'bob', balance: { microUnits: 0 }, transactions: [] },
      },
      blocks: [
        { index: 0, scenarioLabel: 'seal', transactions: [] },
      ],
      mineCredits: {},
    };
    const aliceBefore = ledger.accounts.alice.balance.microUnits;
    const got = rewardAllOnBlockGen(ledger, { finder: 'carol.rig', height: 0 });
    assert.ok(got.count >= 3);
    assert.ok(got.rewarded.includes('alice'));
    assert.ok(got.rewarded.includes('bob'));
    assert.ok(got.rewarded.includes('carol'));
    assert.ok(ledger.accounts.alice.balance.microUnits > aliceBefore);
    assert.ok(ledger.accounts.bob.balance.microUnits > 0);
    assert.ok(ledger.accounts.carol.balance.microUnits > 0);
    const tx = ledger.accounts.alice.transactions.find((t) => t.kind === 'block_gen_reward');
    assert.ok(tx);
    assert.equal(tx.toUsername, 'alice');
    assert.equal(tx.fromUsername, 'evolve_treasury');
    assert.ok(ledger.blocks[0].transactions.some((t) => t.kind === 'block_gen_reward'));
  });
});
