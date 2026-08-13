import test from 'node:test';
import assert from 'node:assert/strict';

import {
  PUBLIC_ALIAS_LENGTH,
  obfuscateUsername,
  restoreCanonicalSystemAccounts,
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

test('restoreCanonicalSystemAccounts undoes aliased evolve_treasury key', () => {
  const alias = obfuscateUsername('evolve_treasury');
  assert.ok(alias);
  assert.notEqual(alias, 'evolve_treasury');
  const ledger = {
    accounts: {
      [alias]: {
        username: alias,
        balance: { microUnits: 9_000_000_000_000 },
        transactions: [],
      },
      alice: {
        username: 'alice',
        balance: { microUnits: 1 },
        transactions: [],
      },
    },
    blocks: [
      {
        index: 0,
        transactions: [
          {
            kind: 'treasuryEmission',
            toUsername: alias,
            amount: { microUnits: 100 },
          },
          {
            kind: 'scenarioReward',
            fromUsername: alias,
            toUsername: 'alice',
            amount: { microUnits: 50 },
          },
        ],
      },
    ],
  };
  restoreCanonicalSystemAccounts(ledger);
  assert.ok(ledger.accounts.evolve_treasury);
  assert.equal(ledger.accounts.evolve_treasury.balance.microUnits, 9_000_000_000_000);
  assert.equal(ledger.accounts[alias], undefined);
  assert.equal(ledger.blocks[0].transactions[0].toUsername, 'evolve_treasury');
  assert.equal(ledger.blocks[0].transactions[1].fromUsername, 'evolve_treasury');
});

test('sanitizeLedgerForPublic keeps treasury and seed under real usernames', () => {
  const sanitized = sanitizeLedgerForPublic({
    sessionUsername: 'alice',
    accounts: {
      evolve_treasury: {
        username: 'evolve_treasury',
        passwordHash: 'secret',
        salt: 's',
        balance: { microUnits: 9_000_000_000_000 },
        transactions: [],
      },
      evolve_seed_node: {
        username: 'evolve_seed_node',
        balance: { microUnits: 0 },
        transactions: [],
      },
      alice: {
        username: 'alice',
        passwordHash: 'h',
        salt: 's2',
        balance: { microUnits: 1 },
        transactions: [
          {
            id: 'tx-1',
            kind: 'scenarioReward',
            fromUsername: 'evolve_treasury',
            toUsername: 'alice',
            amount: { microUnits: 1 },
          },
        ],
      },
    },
    blocks: [
      {
        index: 0,
        triggerUsername: 'alice',
        transactions: [
          {
            kind: 'treasuryEmission',
            toUsername: 'evolve_treasury',
            amount: { microUnits: 100 },
          },
          {
            kind: 'scenarioReward',
            fromUsername: 'evolve_treasury',
            toUsername: 'alice',
            amount: { microUnits: 50 },
          },
        ],
      },
    ],
  });

  assert.ok(sanitized.accounts.evolve_treasury);
  assert.equal(
    sanitized.accounts.evolve_treasury.balance.microUnits,
    9_000_000_000_000,
  );
  assert.equal(sanitized.accounts.evolve_treasury.passwordHash, undefined);
  assert.ok(sanitized.accounts.evolve_seed_node);
  assert.ok(!sanitized.accounts.alice);
  // Ordinary users still aliased
  const aliases = Object.keys(sanitized.accounts).filter(
    (k) => k !== 'evolve_treasury' && k !== 'evolve_seed_node',
  );
  assert.equal(aliases.length, 1);
  assert.equal(aliases[0].length, PUBLIC_ALIAS_LENGTH);
  // System usernames preserved in txs so faucet debit keys match.
  assert.equal(
    sanitized.blocks[0].transactions[0].toUsername,
    'evolve_treasury',
  );
  assert.equal(
    sanitized.blocks[0].transactions[1].fromUsername,
    'evolve_treasury',
  );
});

test('sanitizeLedgerForPublic rewrites paused Render peer endpoints', () => {
  const prev = process.env.PERC_PUBLIC_ENDPOINT;
  process.env.PERC_PUBLIC_ENDPOINT = 'https://135.181.152.10.sslip.io/perc';
  try {
    const sanitized = sanitizeLedgerForPublic({
      accounts: {},
      blocks: [],
      networkNodes: {
        evolve_seed_node: {
          username: 'evolve_seed_node',
          endpoint: 'https://evolve-perc-internet.onrender.com',
          blockHeight: 97,
          online: true,
        },
        wallet_a: {
          username: 'wallet_a',
          endpoint: 'https://evolve-perc-internet.onrender.com:9477',
          blockHeight: 10,
          online: true,
        },
      },
    });
    const nodes = Object.values(sanitized.networkNodes);
    assert.equal(nodes.length, 2);
    for (const n of nodes) {
      assert.equal(n.endpoint, 'https://135.181.152.10.sslip.io/perc');
      assert.ok(!/onrender\.com/i.test(n.endpoint));
    }
  } finally {
    if (prev === undefined) delete process.env.PERC_PUBLIC_ENDPOINT;
    else process.env.PERC_PUBLIC_ENDPOINT = prev;
  }
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