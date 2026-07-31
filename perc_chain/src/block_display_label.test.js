import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { genericBlockLabel } from './block_display_label.js';

describe('genericBlockLabel', () => {
  it('maps percent chance scenario rewards', () => {
    const label = genericBlockLabel({
      scenarioLabel: 'Percent chance: What is the chance of unrest near-term?',
      transactions: [{ kind: 'scenarioReward', scenarioLabel: 'Percent chance: What is the chance of unrest near-term?' }],
    });
    assert.equal(label, '% chance input');
  });

  it('maps social cohesion scenario rewards', () => {
    const label = genericBlockLabel({
      scenarioLabel: 'Social cohesion score: Glasgow ward cohesion',
      transactions: [{ kind: 'scenarioReward' }],
    });
    assert.equal(label, 'SCS input');
  });

  it('maps manual transfers', () => {
    const label = genericBlockLabel({
      triggerUsername: 'alice',
      transactions: [
        { kind: 'transfer', memo: 'Thanks for the help with the pilot' },
        { kind: 'feeBurn', memo: 'Burned network fee' },
      ],
    });
    assert.equal(label, 'Manual tx');
  });

  it('maps staking rewards', () => {
    const label = genericBlockLabel({
      transactions: [{ kind: 'stakingReward', memo: 'Cumulative staking (0.01 per block)' }],
    });
    assert.equal(label, 'Staked reward');
  });

  it('maps fee burn only', () => {
    const label = genericBlockLabel({
      transactions: [{ kind: 'feeBurn', memo: 'Burned network fee' }],
    });
    assert.equal(label, 'Burned PERC');
  });

  it('maps treasury regeneration', () => {
    const label = genericBlockLabel({
      scenarioLabel: 'Treasury regeneration',
      transactions: [{ kind: 'treasuryEmission', memo: 'Treasury regeneration — balance below 0.66 PERC' }],
    });
    assert.equal(label, 'Treasury regeneration');
  });

  it('maps microblock seal', () => {
    const label = genericBlockLabel({
      microblockSeal: true,
      scenarioLabel: 'Chronoflux microblock seal',
      transactions: [{ kind: 'chronofluxMicroblock' }],
    });
    assert.equal(label, 'Microblock seal');
  });
});