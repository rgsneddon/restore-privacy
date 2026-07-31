import test from 'node:test';
import assert from 'node:assert/strict';
import {
  findAddressInLedger,
  findAddressInLedgerCollection,
  indexLedgerAddresses,
} from './address_index.js';

test('indexLedgerAddresses maps every account address', () => {
  const addresses = new Map();
  indexLedgerAddresses(
    {
      accounts: {
        alice: { address: 'percpriv1abc' },
        bob: { address: 'percpriv1def' },
      },
    },
    addresses,
  );
  assert.equal(addresses.get('percpriv1abc'), 'alice');
  assert.equal(addresses.get('percpriv1def'), 'bob');
});

test('findAddressInLedgerCollection searches multiple ledgers', () => {
  const hit = findAddressInLedgerCollection('percpriv1zzz', [
    { accounts: { alice: { address: 'percpriv1aaa' } } },
    { accounts: { bob: { address: 'percpriv1zzz' } } },
  ]);
  assert.deepEqual(hit, { username: 'bob', address: 'percpriv1zzz' });
});

test('findAddressInLedger returns null when missing', () => {
  assert.equal(findAddressInLedger({ accounts: {} }, 'percpriv1nope'), null);
});