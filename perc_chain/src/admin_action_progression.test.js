import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  ADMIN_ACTION_KIND,
  adminActionDisplayLabel,
  isAdminActionBlock,
  mintAdminActionBlock,
} from './admin_action_progression.js';
import { genericBlockLabel } from './block_display_label.js';
import { createGenesisLedger } from './genesis.js';

describe('admin_action_progression', () => {
  it('mints a confirmed admin-action block with explorer label', () => {
    const ledger = createGenesisLedger();
    const before = ledger.blocks.length;
    const result = mintAdminActionBlock(ledger, {
      actionKind: 'mint_keygen',
      label: 'Admin: Mint Keygen',
      path: '/admin/mint-keygen',
    });
    assert.equal(result.ok, true);
    assert.equal(ledger.blocks.length, before + 1);
    assert.equal(result.block.adminAction, true);
    assert.equal(result.block.transactions[0].kind, ADMIN_ACTION_KIND);
    assert.equal(result.height, before);
    assert.equal(genericBlockLabel(result.block), 'Admin: Mint Keygen');
    assert.equal(isAdminActionBlock(result.block), true);
  });

  it('confirms pending inbound transfers in the same seal', () => {
    const ledger = createGenesisLedger();
    ledger.pendingInboundTransfers = [
      { id: 'xfer-pending-1', kind: 'transfer', amount: { microUnits: 1 } },
      { id: 'xfer-pending-2', kind: 'transfer', amount: { microUnits: 2 } },
    ];
    const result = mintAdminActionBlock(ledger, {
      actionKind: 'push_suite_packages',
      label: 'Admin: Push Suite Packages',
    });
    assert.equal(result.ok, true);
    assert.equal(result.pendingIncluded, 2);
    assert.equal(ledger.pendingInboundTransfers.length, 0);
    const kinds = result.block.transactions.map((t) => t.kind);
    assert.ok(kinds.includes(ADMIN_ACTION_KIND));
    assert.equal(kinds.filter((k) => k === 'transfer').length, 2);
    assert.ok(
      result.block.transactions.some((t) => t.id === 'xfer-pending-1' && t.confirmedBy === ADMIN_ACTION_KIND),
    );
  });

  it('promotes pending relayed transfers from peer relay ledger', () => {
    const ledger = createGenesisLedger();
    // Seed filler so relay height 1 is mergeable
    ledger.blocks.push({
      index: 0,
      transactions: [{ id: 'seed-0', kind: 'scenarioReward' }],
    });
    const relay = {
      networkGenesisRevision: ledger.networkGenesisRevision,
      blocks: [
        {
          index: 1,
          transactions: [
            { id: 'relay-tx-99', kind: 'transfer', blockIndex: 1 },
          ],
        },
      ],
    };
    const result = mintAdminActionBlock(
      ledger,
      { actionKind: 'clear_licences', label: 'Admin: Clear Licences' },
      { relayLedgers: [relay] },
    );
    assert.equal(result.ok, true);
    assert.ok(result.confirmedRelayTxIds.includes('relay-tx-99'));
    // Relay transfer promoted onto canonical chain at source height
    const promoted = ledger.blocks.some((b) =>
      (b.transactions || []).some((t) => t.id === 'relay-tx-99'),
    );
    assert.equal(promoted, true);
  });

  it('display label helper is stable', () => {
    assert.equal(adminActionDisplayLabel('mint_keygen'), 'Admin: Mint Keygen');
    assert.equal(
      adminActionDisplayLabel('x', 'Custom admin seal'),
      'Custom admin seal',
    );
  });
});
