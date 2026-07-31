import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { blockTipPayload } from './chain_tip_payload.js';
import {
  compactLedgerForSeed,
  seedBlocksMax,
  truncateScenarioText,
} from './ledger_compact.js';

describe('truncateScenarioText', () => {
  it('leaves short labels unchanged', () => {
    assert.equal(truncateScenarioText('Percent chance: rain?', 120), 'Percent chance: rain?');
  });

  it('truncates long labels with ellipsis', () => {
    const long = `Social cohesion score: ${'x'.repeat(200)}`;
    const out = truncateScenarioText(long, 40);
    assert.equal(out.length, 40);
    assert.ok(out.endsWith('…'));
    assert.ok(out.startsWith('Social cohesion score:'));
  });
});

describe('compactLedgerForSeed', () => {
  it('truncates block scenario text and clears account histories', () => {
    const ledger = {
      blocks: [
        {
          index: 0,
          scenarioLabel: `Percent chance: ${'y'.repeat(300)}`,
          transactions: [
            {
              id: 'tx-1',
              kind: 'scenarioReward',
              scenarioLabel: `Percent chance: ${'y'.repeat(300)}`,
            },
          ],
        },
      ],
      accounts: {
        alice: {
          username: 'alice',
          balance: { microUnits: 1 },
          transactions: [{ id: 'tx-1', kind: 'scenarioReward', scenarioLabel: 'full copy' }],
        },
      },
    };

    const compact = compactLedgerForSeed(ledger);
    assert.ok(compact.blocks[0].scenarioLabel.length <= 120);
    assert.ok(compact.blocks[0].transactions[0].scenarioLabel.length <= 120);
    assert.deepEqual(compact.accounts.alice.transactions, []);
  });

  it('drops microblockLog on seed compaction', () => {
    const ledger = {
      blocks: [],
      accounts: {},
      microblockLog: [
        { index: 1, label: 'Fair usage keystroke' },
        { index: 2, label: 'Another microblock entry' },
      ],
    };
    const compact = compactLedgerForSeed(ledger);
    assert.deepEqual(compact.microblockLog, []);
  });

  it('caps blocks[] when PERC_SEED_BLOCKS_MAX is set', () => {
    const prev = process.env.PERC_SEED_BLOCKS_MAX;
    process.env.PERC_SEED_BLOCKS_MAX = '3';
    try {
      const ledger = {
        blocks: Array.from({ length: 8 }, (_, i) => ({
          index: i,
          scenarioLabel: `block-${i}`,
          transactions: [],
        })),
        accounts: {},
      };
      const compact = compactLedgerForSeed(ledger);
      assert.equal(compact.blocks.length, 3);
      assert.equal(compact.blocks[0].index, 5);
      assert.equal(compact.blocks[2].index, 7);
      assert.equal(seedBlocksMax(), 3);
    } finally {
      if (prev == null) delete process.env.PERC_SEED_BLOCKS_MAX;
      else process.env.PERC_SEED_BLOCKS_MAX = prev;
    }
  });
});

describe('blockTipPayload', () => {
  it('ignores scenario narrative when building tip payload', () => {
    const full = blockTipPayload({
      index: 3,
      timestamp: '2026-07-05T12:00:00.000Z',
      treasuryEmitted: { microUnits: 1 },
      scenarioLabel: 'Percent chance: full scenario question here',
      transactions: [
        {
          id: 'tx-9',
          kind: 'scenarioReward',
          amount: { microUnits: 5 },
          timestamp: '2026-07-05T12:00:00.000Z',
          scenarioLabel: 'Percent chance: full scenario question here',
          memo: 'long memo text',
          percentChance: 42,
        },
      ],
    });
    const truncated = blockTipPayload({
      index: 3,
      timestamp: '2026-07-05T12:00:00.000Z',
      treasuryEmitted: { microUnits: 1 },
      scenarioLabel: 'Percent chance: truncated…',
      transactions: [
        {
          id: 'tx-9',
          kind: 'scenarioReward',
          amount: { microUnits: 5 },
          timestamp: '2026-07-05T12:00:00.000Z',
          scenarioLabel: 'Percent chance: truncated…',
          percentChance: 42,
        },
      ],
    });
    assert.deepEqual(full, truncated);
  });

  it('ignores username fields when building tip payload', () => {
    const canonical = blockTipPayload({
      index: 2,
      timestamp: '2026-07-05T12:00:00.000Z',
      treasuryEmitted: { microUnits: 1 },
      triggerUsername: 'alice',
      transactions: [
        {
          id: 'tx-2',
          kind: 'transfer',
          amount: { microUnits: 5 },
          timestamp: '2026-07-05T12:00:00.000Z',
          fromUsername: 'alice',
          toUsername: 'bob',
        },
      ],
    });
    const aliased = blockTipPayload({
      index: 2,
      timestamp: '2026-07-05T12:00:00.000Z',
      treasuryEmitted: { microUnits: 1 },
      triggerUsername: 'ZZZZZ',
      transactions: [
        {
          id: 'tx-2',
          kind: 'transfer',
          amount: { microUnits: 5 },
          timestamp: '2026-07-05T12:00:00.000Z',
          fromUsername: 'YYYYY',
          toUsername: 'XXXXX',
        },
      ],
    });
    assert.deepEqual(canonical, aliased);
  });

  it('omits null and default fields to match wallet PercChainTip JSON', () => {
    const payload = blockTipPayload({
      index: 31,
      timestamp: '2026-07-06T23:12:07.656777Z',
      treasuryEmitted: { microUnits: 66666666 },
      treasuryCycle: 1,
      isGenesisRenewal: false,
      microblockSeal: false,
      transactions: [
        {
          id: 'tx-96',
          kind: 'treasuryEmission',
          amount: { microUnits: 66666666 },
          timestamp: '2026-07-06T23:12:07.656777Z',
          blockIndex: 31,
          confirmations: 1,
        },
      ],
    });
    assert.deepEqual(payload, {
      index: 31,
      timestamp: '2026-07-06T23:12:07.656777Z',
      treasuryEmitted: { microUnits: 66666666 },
      transactions: [
        {
          id: 'tx-96',
          kind: 'treasuryEmission',
          amount: { microUnits: 66666666 },
          timestamp: '2026-07-06T23:12:07.656777Z',
          blockIndex: 31,
          confirmations: 1,
        },
      ],
    });
    assert.equal(JSON.stringify(payload).includes('null'), false);
  });

  it('coerces missing treasuryEmitted and tx amount to zero microUnits', () => {
    const payload = blockTipPayload({
      index: 0,
      timestamp: '2026-07-06T10:00:00.000Z',
      transactions: [
        {
          id: 'tx-1',
          kind: 'transfer',
          timestamp: '2026-07-06T10:00:00.000Z',
        },
      ],
    });
    assert.deepEqual(payload.treasuryEmitted, { microUnits: 0 });
    assert.deepEqual(payload.transactions[0].amount, { microUnits: 0 });
    assert.equal(JSON.stringify(payload).includes('null'), false);
  });

  it('drops transactions missing required tip fields instead of emitting nulls', () => {
    const payload = blockTipPayload({
      index: 1,
      timestamp: '2026-07-06T11:00:00.000Z',
      treasuryEmitted: { microUnits: 1 },
      transactions: [{ id: 'tx-bad', kind: 'transfer' }],
    });
    assert.deepEqual(payload.transactions, []);
  });
});