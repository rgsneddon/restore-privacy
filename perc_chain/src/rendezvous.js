import http from 'http';
import {
  findAddressInLedgerCollection,
  indexLedgerAddresses,
} from './address_index.js';
import {
  obfuscateUsername,
  sanitizeLedgerForPublic,
  sanitizePeersForPublic,
} from './account_privacy.js';
import {
  isRecipientOnlineOnSeed,
  touchPeerHeartbeatOnSeed,
} from './peer_online.js';
import {
  createInboundHintsStore,
  fetchInboundRelayHints,
  recordInboundRelayHint,
} from './rendezvous_inbound_hints.js';

const PORT = Number(process.env.PORT ?? process.env.PERC_RENDEZVOUS_PORT ?? 9478);
const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';

/** @type {Map<string, object>} */
const peers = new Map();
/** @type {Map<string, object>} */
const ledgers = new Map();
/** @type {Map<string, string>} wallet address → sessionUsername */
const addresses = new Map();
/** @type {Map<string, { envelope: string, updatedAt: number }>} */
const seedRecoveries = new Map();
const inboundHints = createInboundHintsStore();

function findRelayEntryByAddress(address) {
  const needle = (address ?? '').trim();
  if (!needle) return null;

  const mappedUser = addresses.get(needle);
  if (mappedUser && ledgers.has(mappedUser)) {
    return ledgers.get(mappedUser);
  }

  for (const entry of ledgers.values()) {
    const ledger = entry?.ledger;
    if (!ledger?.accounts) continue;
    for (const acc of Object.values(ledger.accounts)) {
      if (acc?.address?.trim() === needle) return entry;
    }
  }
  return null;
}

function json(res, code, body) {
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(JSON.stringify(body));
}

function readBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        resolve({});
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    return json(res, 204, {});
  }

  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (req.method === 'POST' && url.pathname === '/perc/rendezvous/register') {
    const data = await readBody(req);
    if (!data.sessionUsername || !data.endpoint) {
      return json(res, 400, { error: 'sessionUsername and endpoint required' });
    }
    peers.set(data.sessionUsername, {
      ...data,
      evolutionaryChainId: data.evolutionaryChainId ?? CHAIN_ID,
      updatedAt: Date.now(),
    });
    if (data.walletAddress) {
      addresses.set(data.walletAddress, data.sessionUsername);
    }
    const relayed = ledgers.get(data.sessionUsername);
    if (relayed?.ledger) {
      indexLedgerAddresses(relayed.ledger, addresses);
    }
    return json(res, 200, { ok: true });
  }

  if (req.method === 'POST' && url.pathname === '/perc/rendezvous/unregister') {
    const data = await readBody(req);
    if (data.username) {
      peers.delete(data.username);
      // Keep address + ledger entries so offline wallets stay discoverable for sends.
    }
    return json(res, 200, { ok: true });
  }

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/peers') {
    const chainId = url.searchParams.get('chainId') ?? CHAIN_ID;
    const list = [...peers.values()].filter(
      (p) => (p.evolutionaryChainId ?? CHAIN_ID) === chainId,
    );
    return json(res, 200, sanitizePeersForPublic(list));
  }

  if (req.method === 'PUT' && url.pathname === '/perc/rendezvous/ledger') {
    const data = await readBody(req);
    if (!data.username || !data.ledger) {
      return json(res, 400, { error: 'username and ledger required' });
    }
    ledgers.set(data.username, {
      username: data.username,
      ledger: data.ledger,
      updatedAt: Date.now(),
    });
    indexLedgerAddresses(data.ledger, addresses);
    recordInboundRelayHint(inboundHints, data.notifyRecipient, data.username);
    return json(res, 200, { ok: true });
  }

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/inbound-hints') {
    const username = url.searchParams.get('username')?.trim();
    if (!username) {
      return json(res, 400, { error: 'username required' });
    }
    return json(res, 200, {
      hints: fetchInboundRelayHints(inboundHints, username),
    });
  }

  if (req.method === 'POST' && url.pathname === '/perc/rendezvous/address') {
    const data = await readBody(req);
    const address = data.address?.trim();
    if (!address) {
      return json(res, 400, { error: 'address required' });
    }
    const username = data.username?.trim();
    if (username) {
      addresses.set(address, username);
      touchPeerHeartbeatOnSeed({
        peers,
        addresses,
        username,
        address,
        endpoint: `http://127.0.0.1:${PORT}`,
      });
    }
    return json(res, 200, { ok: true });
  }

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/online') {
    const username = url.searchParams.get('username')?.trim();
    const address = url.searchParams.get('address')?.trim();
    const online = isRecipientOnlineOnSeed({
      peers,
      addresses,
      username,
      address,
    });
    return json(res, 200, { online });
  }

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/address') {
    const address = url.searchParams.get('address')?.trim();
    if (!address) {
      return json(res, 404, { error: 'address not found' });
    }
    let username = addresses.get(address);
    if (!username) {
      const found = findAddressInLedgerCollection(address, [
        ...[...ledgers.values()].map((entry) => entry.ledger),
      ]);
      if (found) {
        username = found.username;
        addresses.set(found.address, found.username);
      }
    }
    if (!username) {
      return json(res, 404, { error: 'address not found' });
    }
    return json(res, 200, { address });
  }

  if (req.method === 'PUT' && url.pathname === '/perc/rendezvous/seed-recovery') {
    const data = await readBody(req);
    const fingerprint = data.fingerprint?.trim();
    const envelope = data.envelope?.trim();
    if (!fingerprint || !envelope) {
      return json(res, 400, { error: 'fingerprint and envelope required' });
    }
    seedRecoveries.set(fingerprint, {
      envelope,
      updatedAt: Date.now(),
    });
    return json(res, 200, { ok: true });
  }

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/seed-recovery') {
    const fingerprint = url.searchParams.get('fingerprint')?.trim();
    if (!fingerprint) {
      return json(res, 400, { error: 'fingerprint required' });
    }
    const entry = seedRecoveries.get(fingerprint);
    if (!entry?.envelope) {
      return json(res, 404, { error: 'seed recovery envelope not found' });
    }
    return json(res, 200, {
      fingerprint,
      envelope: entry.envelope,
      updatedAt: entry.updatedAt ?? null,
    });
  }

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/ledger') {
    const username = url.searchParams.get('username')?.trim();
    const address = url.searchParams.get('address')?.trim();
    let entry = null;
    if (username && ledgers.has(username)) {
      entry = ledgers.get(username);
    } else if (address) {
      entry = findRelayEntryByAddress(address);
    }
    if (!entry?.ledger) {
      return json(res, 404, { error: 'ledger not found' });
    }
    return json(res, 200, {
      publicAlias: obfuscateUsername(entry.username ?? username ?? ''),
      walletAddress: address ?? null,
      ledger: sanitizeLedgerForPublic(entry.ledger),
      updatedAt: entry.updatedAt ?? null,
    });
  }

  if (req.method === 'GET' && url.pathname === '/health') {
    return json(res, 200, { ok: true, service: 'perc-rendezvous', peers: peers.size });
  }

  return json(res, 404, { error: 'not found' });
});

const bindHost = process.env.PERC_RENDEZVOUS_HOST ?? '0.0.0.0';
server.listen(PORT, bindHost, () => {
  console.log(`Perccent internet rendezvous listening on http://0.0.0.0:${PORT}`);
});