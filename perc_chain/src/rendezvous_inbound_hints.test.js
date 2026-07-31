import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  createInboundHintsStore,
  fetchInboundRelayHints,
  recordInboundRelayHint,
} from './rendezvous_inbound_hints.js';
import { applyRelayLedgerPut } from './rendezvous_ledger_put.js';

describe('rendezvous inbound relay hints', () => {
  it('records and fetches sender hints for a recipient', () => {
    const hints = createInboundHintsStore();
    recordInboundRelayHint(hints, 'bob', 'alice');
    const fetched = fetchInboundRelayHints(hints, 'bob');
    assert.equal(fetched.length, 1);
    assert.equal(fetched[0].sender, 'alice');
    assert.ok(fetched[0].updatedAt > 0);
  });

  it('applyRelayLedgerPut records notifyRecipient hint', () => {
    const hints = createInboundHintsStore();
    const ledgers = new Map();
    const addresses = new Map();
    const result = applyRelayLedgerPut({
      store: { importLedger: () => false },
      ledgers,
      addresses,
      username: 'alice',
      ledger: { accounts: {} },
      seedUsername: 'seed',
      notifyRecipient: 'bob',
      inboundHints: hints,
    });
    assert.equal(result.ok, true);
    const fetched = fetchInboundRelayHints(hints, 'bob');
    assert.equal(fetched.length, 1);
    assert.equal(fetched[0].sender, 'alice');
  });
});