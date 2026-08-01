/**
 * Dual-seed sync helpers (Helsinki ↔ Render: resistance / shear biases).
 *
 * Both seeds often share the same SEED_USERNAME (`evolve_seed_node`). Ledger
 * adopt must still pull from the remote seed's public endpoint / upstream URL,
 * not skip the peer merely because the username matches.
 */

import { blockHeight, shouldImportLedger } from './ledger_store.js';

/**
 * Prefer configured upstream rendezvous for network ledger pull when set.
 * Falls back to public endpoint (solo/local) only when upstream is empty.
 *
 * @param {string} upstreamUrl
 * @param {string} publicEndpointUrl
 * @returns {string}
 */
export function resolveNetworkSyncBase(upstreamUrl, publicEndpointUrl) {
  const up = String(upstreamUrl || '')
    .trim()
    .replace(/\/$/, '');
  if (up) return up;
  const local = String(publicEndpointUrl || '')
    .trim()
    .replace(/\/$/, '');
  return local;
}

/**
 * Normalize endpoint for comparison (strip trailing slash; treat privacy masks).
 * @param {string} endpoint
 */
export function normalizeEndpoint(endpoint) {
  const e = String(endpoint || '')
    .trim()
    .replace(/\/$/, '');
  if (!e || e === 'Private node' || e.toLowerCase() === 'private') return '';
  return e;
}

/**
 * True when a peer row is the remote dual seed (or any taller remote) we should
 * attempt ledger fetch from — not the local process's own registration.
 *
 * @param {{ sessionUsername?: string, endpoint?: string, blockHeight?: number, publicAlias?: string }} peer
 * @param {{ seedUsername: string, localEndpoint: string }} ctx
 */
export function isRemoteLedgerCandidate(peer, ctx) {
  if (!peer || typeof peer !== 'object') return false;
  const username = String(peer.sessionUsername || '').trim();
  const height = Number(peer.blockHeight ?? 0) || 0;
  if (height < 1) return false;
  const peerEp = normalizeEndpoint(peer.endpoint);
  const localEp = normalizeEndpoint(ctx.localEndpoint);
  // Hidden / empty identity with no fetchable endpoint is useless
  if (!username && !peerEp) return false;
  // Same username + same endpoint → local self
  if (username && username === ctx.seedUsername) {
    if (!peerEp || peerEp === localEp) return false;
    // Same seed username, different public URL → dual remote seed
    return true;
  }
  // Other wallets / seeds with a height
  return true;
}

/**
 * Choose the taller of local vs remote ledgers for adopt (pure).
 * Returns remote when it should replace local; otherwise null.
 *
 * @param {object|null} localLedger
 * @param {object|null} remoteLedger
 * @returns {object|null}
 */
export function selectTallerLedger(localLedger, remoteLedger) {
  if (!remoteLedger || typeof remoteLedger !== 'object') return null;
  if (shouldImportLedger(localLedger, remoteLedger)) return remoteLedger;
  return null;
}

/**
 * Rank candidate ledgers by height then prefer non-null tip.
 * @param {Array<object|null|undefined>} ledgers
 * @returns {object|null}
 */
export function pickBestLedger(ledgers) {
  let best = null;
  for (const led of ledgers) {
    if (!led || typeof led !== 'object') continue;
    if (!best || blockHeight(led) > blockHeight(best)) {
      best = led;
    }
  }
  return best;
}
