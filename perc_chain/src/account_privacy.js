import crypto from 'crypto';

import { maskEndpoint } from './endpoint_privacy.js';

/** Public alias length — five usable characters per wallet. */
export const PUBLIC_ALIAS_LENGTH = 5;

/** Usable characters (no ambiguous 0/O/1/l/I). */
export const PUBLIC_ALIAS_CHARS =
  'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';

const USERNAME_FIELD_KEYS = new Set([
  'username',
  'sessionUsername',
  'fromUsername',
  'toUsername',
  'triggerUsername',
  'from',
  'to',
  'launchedBy',
]);

const SECRET_FIELD_KEYS = new Set([
  'password',
  'passwordHash',
  'salt',
  'passwordSet',
  'encryptedSeedMnemonic',
  'seedRecoveryEnvelope',
  'seedFingerprint',
  'passwordSwitchCommit',
]);

export function privacySalt() {
  return (process.env.PERC_PRIVACY_SALT ?? 'evolve-perc-account-privacy-v1').trim();
}

/**
 * Deterministic five-character public alias for a username.
 * @param {string|null|undefined} username
 * @returns {string|null}
 */
export function obfuscateUsername(username) {
  if (username == null) return null;
  const raw = String(username).trim();
  if (!raw) return null;

  const digest = crypto.createHmac('sha256', privacySalt()).update(raw).digest();
  let alias = '';
  for (let i = 0; i < PUBLIC_ALIAS_LENGTH; i++) {
    alias += PUBLIC_ALIAS_CHARS[digest[i] % PUBLIC_ALIAS_CHARS.length];
  }
  return alias;
}

function cloneValue(value) {
  if (value == null) return value;
  if (typeof structuredClone === 'function') return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function aliasUsername(value, aliasFor) {
  if (value == null) return value;
  const text = String(value).trim();
  if (!text) return value;
  return aliasFor(text) ?? obfuscateUsername(text);
}

function sanitizeTransactions(txs, aliasFor) {
  if (!Array.isArray(txs)) return txs;
  return txs.map((tx) => {
    if (!tx || typeof tx !== 'object') return tx;
    const out = { ...tx };
    for (const key of USERNAME_FIELD_KEYS) {
      if (out[key] != null) out[key] = aliasUsername(out[key], aliasFor);
    }
    delete out.password;
    delete out.passwordHash;
    delete out.salt;
    return out;
  });
}

/**
 * Strip credentials and replace usernames with five-character aliases.
 * @param {object|null|undefined} ledger
 */
export function sanitizeLedgerForPublic(ledger) {
  if (!ledger || typeof ledger !== 'object') return ledger;

  const out = cloneValue(ledger);
  const aliasFor = (username) => obfuscateUsername(username);

  const accounts = out.accounts ?? {};
  const sanitizedAccounts = {};
  for (const [accountKey, account] of Object.entries(accounts)) {
    if (!account || typeof account !== 'object') continue;
    const alias = aliasUsername(accountKey, aliasFor);
    const clean = { ...account };
    for (const secretKey of SECRET_FIELD_KEYS) delete clean[secretKey];
    if (clean.username != null) clean.username = aliasUsername(clean.username, aliasFor);
    clean.transactions = sanitizeTransactions(clean.transactions, aliasFor);
    sanitizedAccounts[alias] = clean;
  }
  out.accounts = sanitizedAccounts;

  if (out.sessionUsername != null) {
    out.sessionUsername = aliasUsername(out.sessionUsername, aliasFor);
  }

  for (const block of out.blocks ?? []) {
    if (!block || typeof block !== 'object') continue;
    if (block.triggerUsername != null) {
      block.triggerUsername = aliasUsername(block.triggerUsername, aliasFor);
    }
    block.transactions = sanitizeTransactions(block.transactions, aliasFor);
  }

  if (out.networkNodes && typeof out.networkNodes === 'object') {
    const nodes = {};
    for (const [key, node] of Object.entries(out.networkNodes)) {
      const alias = aliasUsername(key, aliasFor);
      const clean = node && typeof node === 'object' ? { ...node } : node;
      if (clean?.username != null) clean.username = aliasUsername(clean.username, aliasFor);
      nodes[alias] = clean;
    }
    out.networkNodes = nodes;
  }

  if (out.walletPeers && typeof out.walletPeers === 'object') {
    const peers = {};
    for (const [key, list] of Object.entries(out.walletPeers)) {
      peers[aliasUsername(key, aliasFor)] = list;
    }
    out.walletPeers = peers;
  }

  if (Array.isArray(out.pendingInboundTransfers)) {
    out.pendingInboundTransfers = out.pendingInboundTransfers.map((entry) => {
      if (!entry || typeof entry !== 'object') return entry;
      const clean = { ...entry };
      for (const key of USERNAME_FIELD_KEYS) {
        if (clean[key] != null) clean[key] = aliasUsername(clean[key], aliasFor);
      }
      return clean;
    });
  }

  for (const proposal of out.wardProposals ?? []) {
    if (!proposal || typeof proposal !== 'object') continue;
    if (proposal.proposerUsername != null) {
      proposal.proposerUsername = aliasUsername(proposal.proposerUsername, aliasFor);
    }
  }

  for (const ballot of out.wardBallots ?? []) {
    if (!ballot || typeof ballot !== 'object') continue;
    if (ballot.voterUsername != null) {
      ballot.voterUsername = aliasUsername(ballot.voterUsername, aliasFor);
    }
  }

  return out;
}

/**
 * @param {object|null|undefined} peer
 */
export function sanitizePeerForPublic(peer) {
  if (!peer || typeof peer !== 'object') return peer;
  const out = { ...peer };
  for (const secretKey of SECRET_FIELD_KEYS) delete out[secretKey];

  if (out.sessionUsername != null) {
    out.publicAlias = obfuscateUsername(out.sessionUsername);
    delete out.sessionUsername;
  }
  if (out.username != null) {
    out.publicAlias = obfuscateUsername(out.username);
    delete out.username;
  }
  if (out.endpoint != null) out.endpoint = maskEndpoint(out.endpoint);
  return out;
}

export function sanitizePeersForPublic(peers) {
  if (!Array.isArray(peers)) return peers;
  return peers.map((peer) => sanitizePeerForPublic(peer));
}

/**
 * Deep-sanitize explorer / network JSON — obfuscate usernames, strip secrets.
 */
export function sanitizePublicPayload(data) {
  if (data == null) return data;
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map((item) => sanitizePublicPayload(item));
  if (typeof data !== 'object') return data;

  const out = {};
  for (const [key, value] of Object.entries(data)) {
    if (SECRET_FIELD_KEYS.has(key)) continue;
    if (key === 'accounts' && value && typeof value === 'object') {
      out[key] = sanitizeLedgerForPublic({ accounts: value }).accounts;
      continue;
    }
    if (key === 'ledger' && value && typeof value === 'object') {
      out[key] = sanitizeLedgerForPublic(value);
      continue;
    }
    if (USERNAME_FIELD_KEYS.has(key) && value != null) {
      out[key === 'sessionUsername' ? 'publicAlias' : key] = obfuscateUsername(value);
      continue;
    }
    if (key === 'endpoint' && typeof value === 'string') {
      out[key] = maskEndpoint(value);
      continue;
    }
    if (key === 'seedUsername' && value != null) {
      out.publicAlias = obfuscateUsername(value);
      continue;
    }
    if (key === 'peerList' && Array.isArray(value)) {
      out[key] = sanitizePeersForPublic(value);
      continue;
    }
    if (key === 'users' && Array.isArray(value)) {
      out[key] = value.map((row) => {
        if (!row || typeof row !== 'object') return row;
        const clean = { ...row };
        if (clean.username != null) {
          clean.publicAlias = obfuscateUsername(clean.username);
          delete clean.username;
        }
        if (clean.endpoint != null) clean.endpoint = maskEndpoint(clean.endpoint);
        return clean;
      });
      continue;
    }
    out[key] = sanitizePublicPayload(value);
  }
  return out;
}