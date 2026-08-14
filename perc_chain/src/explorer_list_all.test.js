import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { listBlocks, summarizeBlock } from './explorer_api.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC_HTML = join(__dirname, '..', 'public', 'index.html');

function tallLedger(n = 45) {
  const blocks = [];
  for (let i = 0; i < n; i++) {
    blocks.push({
      index: i,
      timestamp: `2026-08-14T12:${String(i).padStart(2, '0')}:00.000Z`,
      scenarioLabel: `Scenario ${i}`,
      memo: `Tied message ${i}`,
      transactions: [
        {
          id: `tx-${i}`,
          kind: 'scenarioReward',
          memo: `Tied message ${i}`,
          scenarioLabel: `Scenario ${i}`,
        },
      ],
    });
  }
  return { blocks };
}

describe('explorer lists every generated block', () => {
  it('listBlocks default returns all indices including > 39 with messages', () => {
    const ledger = tallLedger(45);
    const listed = listBlocks(ledger);
    assert.equal(listed.total, ledger.blocks.length);
    assert.equal(listed.blocks.length, 45);
    const idxs = listed.blocks.map((b) => b.index);
    assert.ok(idxs.includes(44));
    assert.ok(idxs.includes(40));
    assert.ok(Math.max(...idxs) > 39);
    assert.equal(idxs[0], 44);
    const tip = listed.blocks[0];
    assert.ok(tip.messages.includes('Tied message 44'));
    assert.equal(tip.memo, 'Tied message 44');
    assert.equal(tip.scenarioLabel, 'Scenario 44');
    const detail = summarizeBlock(ledger.blocks[41], ledger);
    assert.ok(detail.messages.includes('Tied message 41'));
  });

  it('limit=40 still starts from the tip so height > 39 is visible', () => {
    const listed = listBlocks(tallLedger(45), { limit: 40 });
    const idxs = listed.blocks.map((b) => b.index);
    assert.equal(listed.total, 45);
    assert.ok(idxs.includes(44));
    assert.ok(Math.max(...idxs) > 39);
    assert.ok(!idxs.includes(0));
  });

  it('shipped explorer fetches api/blocks without a 40-block cap', () => {
    const html = readFileSync(PUBLIC_HTML, 'utf8');
    assert.match(html, /explorerApiUrl\s*\(\s*['"]api\/blocks['"]\s*\)/);
    assert.doesNotMatch(html, /api\/blocks\?limit=40/);
  });
});
