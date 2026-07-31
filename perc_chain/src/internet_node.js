import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  buildNetworkSnapshot,
  getBlockDetail,
  isHiddenPeer,
  listBlocks,
} from './explorer_api.js';
import { LedgerStore, blockHeight, tipHash } from './ledger_store.js';
import { regenerateTreasuryIfLow } from './treasury_regeneration.js';
import {
  obfuscateUsername,
  sanitizeLedgerForPublic,
  sanitizePeerForPublic,
  sanitizePeersForPublic,
} from './account_privacy.js';
import { maskEndpoint, sanitizeForPublicExplorer } from './endpoint_privacy.js';
import {
  findAddressInLedgerCollection,
  indexLedgerAddresses,
} from './address_index.js';
import {
  isRecipientOnlineOnSeed,
  touchPeerHeartbeatOnSeed,
} from './peer_online.js';
import { applyRelayLedgerPut } from './rendezvous_ledger_put.js';
import {
  createInboundHintsStore,
  fetchInboundRelayHints,
} from './rendezvous_inbound_hints.js';
import { mergeUpstreamPeers } from './upstream_rendezvous.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, '..', 'public');

const PORT = Number(process.env.PORT ?? process.env.PERC_RENDEZVOUS_PORT ?? 9478);
const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
const SEED_USERNAME = process.env.PERC_SEED_USERNAME ?? 'evolve_seed_node';
const TREASURY_USERNAME = process.env.PERC_TREASURY_USERNAME ?? 'evolve_treasury';
const DATA_DIR = process.env.PERC_DATA_DIR ?? path.join(process.cwd(), 'data');
const SYNC_INTERVAL_MS = Number(process.env.PERC_SYNC_INTERVAL_MS ?? 120_000);
const TREASURY_REGEN_INTERVAL_MS = Number(process.env.PERC_TREASURY_REGEN_INTERVAL_MS ?? 30_000);
const CHAIN_GENESIS_REVISION = Number(process.env.PERC_CHAIN_GENESIS_REVISION ?? 2);

/** @type {Map<string, object>} */
const peers = new Map();
/** @type {Map<string, object>} */
const ledgers = new Map();
/** @type {Map<string, string>} wallet address → sessionUsername */
const addresses = new Map();
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

const store = new LedgerStore(DATA_DIR);

function publicEndpoint() {
  const explicit = (process.env.PERC_PUBLIC_ENDPOINT ?? process.env.RENDER_EXTERNAL_URL ?? '').trim();
  if (explicit) return explicit.replace(/\/$/, '');
  return `http://127.0.0.1:${PORT}`;
}

function readDefaultUpstreamRendezvousUrl() {
  const configPath = path.join(__dirname, '..', '..', 'assets', 'config', 'perc_network.json');
  try {
    const raw = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    const url = (raw.rendezvousUrl ?? '').trim();
    if (url) return url.replace(/\/$/, '');
  } catch {
    // optional — env override still works
  }
  return 'https://evolve-perc-internet.onrender.com';
}

function upstreamRendezvousUrl() {
  const explicit = (process.env.PERC_UPSTREAM_RENDEZVOUS_URL ?? '').trim();
  if (explicit) return explicit.replace(/\/$/, '');
  return readDefaultUpstreamRendezvousUrl();
}

function networkSyncBase() {
  const local = publicEndpoint();
  const isLocal =
    !local ||
    local.includes('127.0.0.1') ||
    local.includes('localhost') ||
    local.startsWith('http://[::1]');
  return isLocal ? upstreamRendezvousUrl() : local;
}

function json(res, code, body) {
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  });
  res.end(JSON.stringify(body));
}

function html(res, code, body) {
  res.writeHead(code, {
    'Content-Type': 'text/html; charset=utf-8',
    'Cache-Control': 'no-cache',
  });
  res.end(body);
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

function servePublic(relPath, res) {
  const safe = path.normalize(relPath).replace(/^(\.\.[/\\])+/, '');
  const filePath = path.join(PUBLIC_DIR, safe);
  if (!filePath.startsWith(PUBLIC_DIR)) {
    return false;
  }
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    return false;
  }
  const ext = path.extname(filePath).toLowerCase();
  const types = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
  };
  res.writeHead(200, {
    'Content-Type': types[ext] ?? 'application/octet-stream',
    'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=3600',
  });
  res.end(fs.readFileSync(filePath));
  return true;
}

async function registerSeed() {
  const endpoint = publicEndpoint();
  if (!endpoint) return;
  const explicitPublic = Boolean((process.env.PERC_PUBLIC_ENDPOINT ?? '').trim());
  const isLoopback =
    endpoint.includes('127.0.0.1') ||
    endpoint.includes('localhost') ||
    endpoint.startsWith('http://[::1]');
  // Self-hosted multi-seed dev: allow loopback when PERC_PUBLIC_ENDPOINT is set explicitly.
  if (isLoopback && !explicitPublic) return;
  const status = store.status(SEED_USERNAME, endpoint);
  peers.set(SEED_USERNAME, {
    sessionUsername: SEED_USERNAME,
    endpoint,
    evolutionaryChainId: status.evolutionaryChainId,
    blockHeight: status.blockHeight,
    tipHash: status.tipHash,
    revision: status.revision,
    updatedAt: Date.now(),
  });
  if (store.hasLedger()) {
    ledgers.set(SEED_USERNAME, {
      username: SEED_USERNAME,
      ledger: store.ledger,
      updatedAt: Date.now(),
    });
    indexLedgerAddresses(store.ledger, addresses);
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) return null;
  return response.json();
}

async function syncUpstreamPeers() {
  const upstream = upstreamRendezvousUrl();
  if (!upstream) return 0;
  try {
    const peerList = await fetchJson(
      `${upstream}/perc/rendezvous/peers?chainId=${encodeURIComponent(CHAIN_ID)}`,
    );
    return mergeUpstreamPeers(peers, peerList, CHAIN_ID);
  } catch (err) {
    console.warn('Upstream peer merge failed:', err?.message ?? err);
    return 0;
  }
}

async function syncFromNetwork() {
  const base = networkSyncBase();
  if (!base) return;

  let peerList = [];
  try {
    peerList = await fetchJson(
      `${base}/perc/rendezvous/peers?chainId=${encodeURIComponent(CHAIN_ID)}`,
    );
  } catch {
    return;
  }
  if (!Array.isArray(peerList)) return;
  mergeUpstreamPeers(peers, peerList, CHAIN_ID);

  let best = null;
  let bestUsername = null;

  for (const peer of peerList) {
    const username = peer.sessionUsername;
    const endpoint = peer.endpoint;
    const height = peer.blockHeight ?? 0;
    if (!username || username === SEED_USERNAME || isHiddenPeer(username)) continue;
    if (height < blockHeight(best)) continue;

    let candidate = null;
    if (endpoint && !endpoint.includes('127.0.0.1') && !endpoint.includes('localhost')) {
      try {
        candidate = await fetchJson(`${endpoint.replace(/\/$/, '')}/perc/ledger`);
      } catch {
        candidate = null;
      }
    }
    if (!candidate || blockHeight(candidate) < height) {
      try {
        const relay = await fetchJson(
          `${base}/perc/rendezvous/ledger?username=${encodeURIComponent(username)}`,
        );
        candidate = relay?.ledger ?? null;
      } catch {
        candidate = null;
      }
    }
    if (candidate && blockHeight(candidate) >= blockHeight(best)) {
      best = candidate;
      bestUsername = username;
    }
  }

  if (best && store.importLedger(best)) {
    console.log(
      `Seed synced to height ${blockHeight(best)} from ${bestUsername ?? 'network'}`,
    );
    await registerSeed();
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    return json(res, 204, {});
  }

  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (req.method === 'GET' && url.pathname === '/api/network') {
    return json(
      res,
      200,
      sanitizeForPublicExplorer(
        buildNetworkSnapshot({
          peers,
          ledgers,
          store,
          seedUsername: SEED_USERNAME,
          endpoint: publicEndpoint(),
          chainId: CHAIN_ID,
        }),
      ),
    );
  }

  const blockMatch = url.pathname.match(/^\/api\/blocks\/(\d+)$/);
  if (req.method === 'GET' && blockMatch) {
    const index = Number(blockMatch[1]);
    if (!store.hasLedger()) {
      return json(res, 503, { error: 'ledger not ready' });
    }
    const detail = getBlockDetail(store.ledger, index);
    if (!detail) return json(res, 404, { error: 'block not found' });
    return json(res, 200, sanitizeForPublicExplorer(detail));
  }

  if (req.method === 'GET' && url.pathname === '/api/blocks') {
    if (!store.hasLedger()) {
      return json(res, 200, { total: 0, offset: 0, limit: 50, blocks: [] });
    }
    const offset = Number(url.searchParams.get('offset') ?? 0);
    const limit = Math.min(Number(url.searchParams.get('limit') ?? 50), 200);
    return json(res, 200, sanitizeForPublicExplorer(listBlocks(store.ledger, { offset, limit })));
  }

  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/explorer')) {
    if (servePublic('index.html', res)) return;
    return json(res, 503, { error: 'explorer UI missing' });
  }

  if (req.method === 'GET' && url.pathname.startsWith('/public/')) {
    if (servePublic(url.pathname.slice('/public/'.length), res)) return;
    return json(res, 404, { error: 'not found' });
  }

  if (req.method === 'POST' && url.pathname === '/perc/rendezvous/register') {
    const data = await readBody(req);
    if (!data.sessionUsername || !data.endpoint) {
      return json(res, 400, { error: 'sessionUsername and endpoint required' });
    }
    if (isHiddenPeer(data.sessionUsername)) {
      return json(res, 200, { ok: true, hidden: true });
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
        endpoint: publicEndpoint(),
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
        store.ledger,
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

  if (req.method === 'GET' && url.pathname === '/perc/rendezvous/peers') {
    const chainId = url.searchParams.get('chainId') ?? CHAIN_ID;
    const list = [...peers.values()]
      .filter((p) => (p.evolutionaryChainId ?? CHAIN_ID) === chainId)
      .filter((p) => !isHiddenPeer(p.sessionUsername));
    return json(res, 200, sanitizePeersForPublic(list));
  }

  if (req.method === 'PUT' && url.pathname === '/perc/rendezvous/ledger') {
    const data = await readBody(req);
    const result = applyRelayLedgerPut({
      store,
      ledgers,
      addresses,
      username: data.username,
      ledger: data.ledger,
      seedUsername: SEED_USERNAME,
      notifyRecipient: data.notifyRecipient,
      inboundHints,
    });
    if (!result.ok) {
      return json(res, 400, { error: result.error });
    }
    return json(res, 200, { ok: true, imported: result.imported });
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

  if (req.method === 'GET' && url.pathname === '/perc/status') {
    const status = store.status(SEED_USERNAME, publicEndpoint());
    return json(res, 200, sanitizePeerForPublic(status));
  }

  if (req.method === 'GET' && url.pathname === '/perc/ledger') {
    if (!store.hasLedger()) {
      store.resetToGenesis(CHAIN_GENESIS_REVISION);
    }
    return json(res, 200, sanitizeLedgerForPublic(store.ledger));
  }

  if (req.method === 'POST' && url.pathname === '/perc/ledger') {
    const remote = await readBody(req);
    if (!remote || typeof remote !== 'object') {
      return json(res, 400, { error: 'ledger body required' });
    }
    store.importLedger(remote);
    indexLedgerAddresses(store.ledger, addresses);
    await registerSeed();
    return json(res, 200, { ok: true });
  }

  if (req.method === 'GET' && url.pathname === '/health') {
    const snapshot = buildNetworkSnapshot({
      peers,
      ledgers,
      store,
      seedUsername: SEED_USERNAME,
      endpoint: publicEndpoint(),
      chainId: CHAIN_ID,
    });
    return json(res, 200, {
      ok: true,
      service: 'perc-internet-node',
      explorer: maskEndpoint(`${publicEndpoint()}/`),
      publicAlias: obfuscateUsername(SEED_USERNAME),
      endpoint: snapshot.endpoint,
      blockHeight: snapshot.blockHeight,
      networkHeight: snapshot.networkHeight,
      tipHash: snapshot.tipHash,
      peers: snapshot.peers.total,
      peersOnline: snapshot.peers.online,
      ledgerReady: snapshot.ledgerReady,
      lastBootstrapAt: store.lastBootstrapAt,
      networkGenesisRevision: store.getGenesisRevision(),
    });
  }

  return json(res, 404, { error: 'not found' });
});

const bindHost = process.env.PERC_BIND_HOST ?? '0.0.0.0';
server.listen(PORT, bindHost, async () => {
  console.log(`Perccent internet node listening on http://${bindHost}:${PORT}`);
  console.log(`Public endpoint: ${publicEndpoint()}`);
  console.log(`Explorer UI: ${publicEndpoint()}/`);
  console.log(`Seed username: ${SEED_USERNAME}`);
  console.log(`Treasury username: ${TREASURY_USERNAME} (hidden from public peers)`);
  console.log(`Chain genesis revision: ${CHAIN_GENESIS_REVISION}`);
  if (store.ensureGenesisRevision(CHAIN_GENESIS_REVISION)) {
    peers.clear();
    ledgers.clear();
    console.log('Chain reset to block 0 with new treasury wallet');
  }
  const annualBootstrap = store.maybeAnnualBootstrap({ seedUsername: SEED_USERNAME });
  if (annualBootstrap?.ok) {
    peers.clear();
    ledgers.clear();
    addresses.clear();
    console.log(
      `Annual seed epoch bootstrap: revision ${annualBootstrap.previousRevision} → ${annualBootstrap.newRevision} (archive ${annualBootstrap.archivePath})`,
    );
  }
  await registerSeed();
  const upstreamMerged = await syncUpstreamPeers();
  if (upstreamMerged > 0) {
    console.log(`Merged ${upstreamMerged} upstream peer(s) from ${upstreamRendezvousUrl()}`);
  }
  await syncFromNetwork();
  if (regenerateTreasuryIfLow(store, TREASURY_USERNAME)) {
    await registerSeed();
  }
  setInterval(async () => {
    await syncUpstreamPeers();
    await syncFromNetwork();
    if (regenerateTreasuryIfLow(store, TREASURY_USERNAME)) {
      await registerSeed();
    }
    await registerSeed();
  }, SYNC_INTERVAL_MS);
  setInterval(() => {
    if (regenerateTreasuryIfLow(store, TREASURY_USERNAME)) {
      registerSeed().catch((err) => console.warn('Treasury regen register failed:', err));
    }
  }, TREASURY_REGEN_INTERVAL_MS);
});