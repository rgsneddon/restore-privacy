import test from 'node:test';
import assert from 'node:assert/strict';
import {
  isPeerOnline,
  isRecipientOnlineOnSeed,
  touchPeerHeartbeatOnSeed,
} from './peer_online.js';

test('isPeerOnline requires heartbeat within seven minutes', () => {
  const now = Date.now();
  assert.equal(isPeerOnline({ updatedAt: now - 60_000 }, now), true);
  assert.equal(isPeerOnline({ updatedAt: now - 8 * 60 * 1000 }, now), false);
});

test('isRecipientOnlineOnSeed matches username or wallet address', () => {
  const now = Date.now();
  const peers = new Map([
    [
      'alice',
      {
        sessionUsername: 'alice',
        walletAddress: 'percpriv1alice',
        updatedAt: now - 30_000,
      },
    ],
  ]);
  const addresses = new Map([['percpriv1alice', 'alice']]);

  assert.equal(
    isRecipientOnlineOnSeed({
      peers,
      addresses,
      username: 'alice',
      now,
    }),
    true,
  );
  assert.equal(
    isRecipientOnlineOnSeed({
      peers,
      addresses,
      address: 'percpriv1alice',
      now,
    }),
    true,
  );
  assert.equal(
    isRecipientOnlineOnSeed({
      peers,
      addresses,
      username: 'bob',
      now,
    }),
    false,
  );
});

test('touchPeerHeartbeatOnSeed marks wallet online from address publish', () => {
  const now = Date.now();
  const peers = new Map();
  const addresses = new Map();

  touchPeerHeartbeatOnSeed({
    peers,
    addresses,
    username: 'bob',
    address: 'percpriv1bob',
    endpoint: 'https://evolve-perc-internet.onrender.com',
    now,
  });

  assert.equal(
    isRecipientOnlineOnSeed({
      peers,
      addresses,
      address: 'percpriv1bob',
      now,
    }),
    true,
  );
});

test('stale peer heartbeats are treated as offline for sends', () => {
  const now = Date.now();
  const peers = new Map([
    [
      'alice',
      {
        sessionUsername: 'alice',
        walletAddress: 'percpriv1alice',
        updatedAt: now - 10 * 60 * 1000,
      },
    ],
  ]);
  assert.equal(
    isRecipientOnlineOnSeed({
      peers,
      addresses: new Map(),
      address: 'percpriv1alice',
      now,
    }),
    false,
  );
});