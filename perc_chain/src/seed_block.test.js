import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  chainBlockHeightFromLedger,
  treasuryEmissionMilestoneFromLedger,
  treasuryMintedMicroUnits,
} from './seed_block.js';

describe('seed_block height vs treasury milestone', () => {
  it('chain height is zero on fresh genesis ledger', () => {
    const ledger = { blocks: [], cumulativeTreasuryMinted: { microUnits: 0 } };
    assert.equal(chainBlockHeightFromLedger(ledger), 0);
  });

  it('chain height tracks blocks.length as blocks append', () => {
    const ledger = {
      blocks: [{ index: 0 }, { index: 1 }],
      cumulativeTreasuryMinted: { microUnits: 0 },
    };
    assert.equal(chainBlockHeightFromLedger(ledger), 2);
  });

  it('treasury milestone stays at 1 below first 100M emission', () => {
    const ledger = { blocks: [], cumulativeTreasuryMinted: { microUnits: 0 } };
    assert.equal(treasuryEmissionMilestoneFromLedger(ledger), 1);
    assert.equal(treasuryMintedMicroUnits(ledger), 0);
  });

  it('treasury milestone advances at 100M PERC thresholds', () => {
    const threshold = 100_000_000 * 100_000_000;
    const ledger = {
      blocks: [{ index: 0 }],
      cumulativeTreasuryMinted: { microUnits: threshold },
    };
    assert.equal(treasuryEmissionMilestoneFromLedger(ledger), 2);
    assert.equal(chainBlockHeightFromLedger(ledger), 1);
  });
});