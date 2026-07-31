import test from 'node:test';
import assert from 'node:assert/strict';

import {
  PUBLIC_ALIAS_LENGTH,
  obfuscateUsername,
  sanitizeLedgerForPublic,
  sanitizePeerForPublic,
  sanitizePublicPayload,
} from './account_privacy.js';

test('obfuscateUsername returns stable five-character aliases', () => {
  const a = obfuscateUsername('alice');
  const b = obfuscateUsername('alice');
  const c = obfuscateUsername('bob');
  assert.equal(a, b);
  assert.notEqual(a, c);
  assert.equal(a.length, PUBLIC_ALIAS_LENGTH);
  assert.match(a, /^[A-Za-z0-9]{5}$/);
});

test('sanitizeLedgerForPublic strips credentials and obfuscates usernames', () => {
  const sanitized = sanitizeLedgerForPublic({
    sessionUsername: 'alice',
    accounts: {
      alice: {
        username: 'alice',
        passwordHash: 'secret-hash',
        salt: 'secret-salt',
        passwordSet: true,
        address: 'percpriv1abc',
        balance: { microUnits: 100 },
        transactions: [
          { id: 'tx-1', fromUsername: 'alice', toUsername: 'bob', amount: { microUnits: 1 } },
        ],
      },
      bob: {
        username: 'bob',
        passwordHash: 'hash2',
        salt: 'salt2',
        address: 'percpriv1def',
        balance: { microUnits: 0 },
        transactions: [],
      },
    },
    blocks: [
      {
        index: 0,
        triggerUsername: 'alice',
        transactions: [{ fromUsername: 'alice', toUsername: 'bob' }],
      },
    ],
  });

  const accountKeys = Object.keys(sanitized.accounts);
  assert.equal(accountKeys.length, 2);
  assert.ok(!accountKeys.includes('alice'));
  assert.ok(!accountKeys.includes('bob'));

  const first = sanitized.accounts[accountKeys[0]];
  assert.equal(first.passwordHash, undefined);
  assert.equal(first.salt, undefined);
  assert.equal(first.passwordSet, undefined);
  assert.equal(first.username.length, PUBLIC_ALIAS_LENGTH);
  assert.equal(sanitized.sessionUsername.length, PUBLIC_ALIAS_LENGTH);
  assert.equal(sanitized.blocks[0].triggerUsername.length, PUBLIC_ALIAS_LENGTH);
  assert.equal(sanitized.blocks[0].transactions[0].fromUsername.length, PUBLIC_ALIAS_LENGTH);
});

test('sanitizePeerForPublic hides sessionUsername and password fields', () => {
  const peer = sanitizePeerForPublic({
    sessionUsername: 'alice',
    password: 'never',
    endpoint: 'http://192.168.0.4:9477',
    blockHeight: 3,
  });
  assert.equal(peer.sessionUsername, undefined);
  assert.equal(peer.password, undefined);
  assert.equal(peer.publicAlias.length, PUBLIC_ALIAS_LENGTH);
  assert.equal(peer.endpoint, 'Private node');
});

test('sanitizeLedgerForPublic obfuscates ward voting usernames', () => {
  const sanitized = sanitizeLedgerForPublic({
    wardProposals: [{ id: 'p1', proposerUsername: 'alice' }],
    wardBallots: [{ proposalId: 'p1', voterUsername: 'bob' }],
  });
  assert.notEqual(sanitized.wardProposals[0].proposerUsername, 'alice');
  assert.equal(sanitized.wardProposals[0].proposerUsername.length, 5);
  assert.notEqual(sanitized.wardBallots[0].voterUsername, 'bob');
  assert.equal(sanitized.wardBallots[0].voterUsername.length, 5);
});

test('sanitizePublicPayload obfuscates network snapshot usernames', () => {
  const payload = sanitizePublicPayload({
    seedUsername: 'evolve_seed_node',
    peerList: [{ username: 'alice', sessionUsername: 'alice', endpoint: 'https://a.example' }],
    walletBlockChart: {
      users: [{ username: 'alice', displayBlock: 3 }],
    },
  });
  assert.equal(payload.seedUsername, undefined);
  assert.equal(payload.publicAlias.length, PUBLIC_ALIAS_LENGTH);
  assert.equal(payload.peerList[0].username, undefined);
  assert.equal(payload.peerList[0].publicAlias.length, PUBLIC_ALIAS_LENGTH);
  assert.equal(payload.walletBlockChart.users[0].username, undefined);
  assert.equal(payload.walletBlockChart.users[0].publicAlias.length, PUBLIC_ALIAS_LENGTH);
});