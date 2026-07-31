import test from 'node:test';
import assert from 'node:assert/strict';

test('address map supports publish and lookup flow', () => {
  const addresses = new Map();
  const username = 'alice';
  const address = 'percpriv1abc';

  addresses.set(address, username);
  assert.equal(addresses.get(address), username);
  assert.equal(addresses.get('percpriv1missing'), undefined);
});