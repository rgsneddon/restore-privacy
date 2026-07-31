import { indexLedgerAddresses } from './address_index.js';
import { recordInboundRelayHint } from './rendezvous_inbound_hints.js';

/**
 * Shipped rendezvous PUT /perc/rendezvous/ledger handler body.
 * @param {{
 *   store: import('./ledger_store.js').LedgerStore,
 *   ledgers: Map<string, object>,
 *   addresses: Map<string, string>,
 *   username: string,
 *   ledger: object,
 *   seedUsername: string,
 *   notifyRecipient?: string,
 *   inboundHints?: import('./rendezvous_inbound_hints.js').InboundHintsStore,
 * }} ctx
 */
export function applyRelayLedgerPut({
  store,
  ledgers,
  addresses,
  username,
  ledger,
  seedUsername,
  notifyRecipient,
  inboundHints,
}) {
  if (!username || !ledger) {
    return { ok: false, error: 'username and ledger required' };
  }

  ledgers.set(username, {
    username,
    ledger,
    updatedAt: Date.now(),
  });
  indexLedgerAddresses(ledger, addresses);

  let imported = false;
  if (username !== seedUsername) {
    imported = store.importLedger(ledger);
    if (imported) {
      indexLedgerAddresses(store.ledger, addresses);
    }
  }

  if (inboundHints) {
    recordInboundRelayHint(inboundHints, notifyRecipient, username);
  }

  return { ok: true, imported };
}