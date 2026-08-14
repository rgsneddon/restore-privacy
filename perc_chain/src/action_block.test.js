import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { createActionChain } from './action_block.js';
import { confirmBlock, wardsForVotingEpoch } from './block_confirm.js';
import { buildExplorerDiagrams } from './explorer_diagrams.js';
import { createRpaiLearner, RPAI_SOURCE_WALLET, RPAI_SOURCE_VPN } from './rpai_ned.js';
import {
  TREASURY_MINT_KEEP_DENOMINATOR,
  TREASURY_MINT_KEEP_NUMERATOR,
  TREASURY_MINT_MICRO_PER_COOLDOWN,
  TREASURY_MINT_PRIOR_MICRO_PER_COOLDOWN,
} from './chain_constants.js';

describe('action blocks + confirm + diagrams + mint', () => {
  it('records tab click and keystroke as confirmable blocks', () => {
    const chain = createActionChain();
    const tab = chain.recordTabClick('wallet');
    const key = chain.recordKeystroke('a');
    const c1 = chain.confirm(tab.id);
    const c2 = chain.confirm(key.id);
    assert.equal(c1.status, 'confirmed');
    assert.equal(c2.status, 'confirmed');
    assert.equal(c1.block.kind, 'tab_click');
    assert.equal(c2.block.kind, 'keystroke');
  });

  it('confirm never throws: confirmed / not_found / rejected', () => {
    const chain = createActionChain();
    const b = chain.recordTabClick('security');
    assert.equal(confirmBlock(b.id, { actionBlocks: chain.blocks }).status, 'confirmed');
    assert.equal(confirmBlock('missing', { actionBlocks: chain.blocks }).status, 'not_found');
    assert.equal(confirmBlock('', { actionBlocks: chain.blocks }).status, 'rejected');
    assert.equal(confirmBlock(null, {}).status, 'rejected');
  });

  it('voting epoch maps into wards', () => {
    const wards = wardsForVotingEpoch('epoch-2026-08-w1');
    assert.ok(wards.length >= 1);
    assert.equal(wards[0].epochId, 'epoch-2026-08-w1');
    assert.ok(wards[0].wardId.includes('ward-epoch-2026-08-w1-1'));
  });

  it('treasury mint is one third of prior', () => {
    assert.equal(TREASURY_MINT_KEEP_NUMERATOR, 1);
    assert.equal(TREASURY_MINT_KEEP_DENOMINATOR, 3);
    assert.equal(
      TREASURY_MINT_MICRO_PER_COOLDOWN,
      Math.floor(TREASURY_MINT_PRIOR_MICRO_PER_COOLDOWN / 3),
    );
    assert.equal(
      TREASURY_MINT_MICRO_PER_COOLDOWN * TREASURY_MINT_KEEP_DENOMINATOR,
      99999999,
    );
  });

  it('diagrams produce non-empty series plus NED stats', () => {
    const chain = createActionChain();
    chain.recordTabClick('wallet');
    chain.recordKeystroke('x');
    const learner = createRpaiLearner();
    learner.learn({ source: RPAI_SOURCE_WALLET, kind: 'keystroke', payload: 'x' });
    learner.learn({ source: RPAI_SOURCE_VPN, kind: 'connect', payload: 'helsinki' });
    const diagrams = buildExplorerDiagrams({
      actionBlocks: chain.blocks,
      rpaiStats: learner.stats(),
      epochId: 'epoch-2026-08-w1',
    });
    assert.ok(diagrams.graphs.blocks.length > 0);
    assert.ok(diagrams.graphs.wards.length > 0);
    assert.ok(diagrams.graphs.mint.length > 0);
    assert.ok(diagrams.graphs.rpai.length > 0);
    assert.equal(diagrams.ned.identity, 'NED');
    assert.equal(diagrams.ned.learned, 2);
  });

  it('rpAI learns wallet+vpn and rejects others', () => {
    const ned = createRpaiLearner();
    assert.equal(ned.learn({ source: RPAI_SOURCE_WALLET, kind: 'tab_click', payload: 'w' }).accepted, true);
    assert.equal(ned.learn({ source: RPAI_SOURCE_VPN, kind: 'connect', payload: 'h' }).accepted, true);
    const denied = ned.learn({ source: 'random-website', kind: 'scrape', payload: 'n' });
    assert.equal(denied.accepted, false);
    assert.equal(denied.reason, 'source_not_permitted');
    const s = ned.stats();
    assert.equal(s.walletEvents, 1);
    assert.equal(s.vpnEvents, 1);
    assert.equal(s.learned, 2);
    assert.equal(s.rejected, 1);
  });
});
