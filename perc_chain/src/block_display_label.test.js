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

  it('maps admin action seals', () => {
    assert.equal(
      genericBlockLabel({
        adminAction: true,
        adminActionKind: 'mint_keygen',
        scenarioLabel: 'Admin: Mint Keygen',
        transactions: [{ kind: 'adminAction', scenarioLabel: 'Admin: Mint Keygen' }],
      }),
      'Admin: Mint Keygen',
    );
    assert.equal(
      genericBlockLabel({
        transactions: [{ kind: 'adminAction' }],
        scenarioLabel: 'Admin: Push Suite Packages',
      }),
      'Admin: Push Suite Packages',
    );
  });

  it('labels admin seal with confirmed transfer txs as Admin (not Manual tx)', () => {
    // Admin seals include pending/relayed transfers in the same block — must stay Admin.
    assert.equal(
      genericBlockLabel({
        adminAction: true,
        adminActionKind: 'push_suite_packages',
        scenarioLabel: 'Admin: Push Suite Packages',
        transactions: [
          { kind: 'adminAction', scenarioLabel: 'Admin: Push Suite Packages' },
          { kind: 'transfer', id: 'xfer-1', confirmedBy: 'adminAction' },
          { kind: 'transfer', id: 'xfer-2' },
        ],
      }),
      'Admin: Push Suite Packages',
    );
    assert.notEqual(
      genericBlockLabel({
        adminAction: true,
        adminActionKind: 'mint_keygen',
        transactions: [
          { kind: 'transfer', id: 'a' },
          { kind: 'adminAction' },
        ],
      }),
      'Manual tx',
    );
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