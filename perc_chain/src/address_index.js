/**
 * Index and resolve PERC wallet addresses from ledger account maps.
 */

export function indexLedgerAddresses(ledger, addresses) {
  if (!ledger?.accounts || !(addresses instanceof Map)) return;
  for (const [username, acc] of Object.entries(ledger.accounts)) {
    const addr = acc?.address;
    if (typeof addr === 'string' && addr.trim().length > 0) {
      addresses.set(addr.trim(), username);
    }
  }
}

export function findAddressInLedger(ledger, address) {
  if (!ledger?.accounts || !address) return null;
  const needle = address.trim();
  for (const [username, acc] of Object.entries(ledger.accounts)) {
    if (acc?.address === needle) {
      return { username, address: needle };
    }
  }
  return null;
}

export function findAddressInLedgerCollection(address, sources) {
  const needle = address?.trim();
  if (!needle) return null;
  for (const ledger of sources) {
    const hit = findAddressInLedger(ledger, needle);
    if (hit) return hit;
  }
  return null;
}