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

/**
 * System accounts that must stay under their real usernames in the public
 * ledger export. Scenario faucet debit/credit needs `evolve_treasury` (not an
 * obfuscated alias) or cold wallets report treasuryEmpty after seed import.
 */
export function systemUsernames() {
  const treasury = (process.env.PERC_TREASURY_USERNAME ?? 'evolve_treasury').trim();
  const seed = (process.env.PERC_SEED_USERNAME ?? 'evolve_seed_node').trim();
  return new Set([treasury, seed].filter(Boolean));
}

export function isSystemUsername(username) {
  if (username == null) return false;
  const raw = String(username).trim();
  if (!raw) return false;
  return systemUsernames().has(raw);
}

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

/**
 * Map a known system-account alias (privacy hash) back to its real username.
 * Durable seed ledgers may already store only obfuscated keys.
 */
export function resolveSystemUsername(username) {
  if (username == null) return null;
  const text = String(username).trim();
  if (!text) return null;
  if (isSystemUsername(text)) return text;
  for (const canonical of systemUsernames()) {
    if (obfuscateUsername(canonical) === text) return canonical;
  }
  return null;
}

function aliasUsername(value, aliasFor) {
  if (value == null) return value;
  const text = String(value).trim();
  if (!text) return value;
  // Keep / restore treasury + seed real names so wallet faucet can debit evolve_treasury.
  const system = resolveSystemUsername(text);
  if (system) return system;
  return aliasFor(text) ?? obfuscateUsername(text);
}

/**
 * In-place: restore canonical treasury/seed account keys on a ledger that was
 * previously exported with obfuscated system usernames (or double-aliased).
 * Also rematerializes treasury from treasuryEmission targets when needed.
 *
 * @param {object|null|undefined} ledger
 * @returns {object|null|undefined}
 */
export function restoreCanonicalSystemAccounts(ledger) {
  if (!ledger || typeof ledger !== 'object') return ledger;
  const accounts = ledger.accounts;
  if (!accounts || typeof accounts !== 'object') return ledger;

  const rewriteRefs = (from, to) => {
    if (ledger.sessionUsername === from) ledger.sessionUsername = to;
    for (const block of ledger.blocks ?? []) {
      if (!block || typeof block !== 'object') continue;
      if (block.triggerUsername === from) block.triggerUsername = to;
      for (const tx of block.transactions ?? []) {
        if (!tx || typeof tx !== 'object') continue;
        for (const key of USERNAME_FIELD_KEYS) {
          if (tx[key] === from) tx[key] = to;
        }
      }
    }
    for (const acc of Object.values(accounts)) {
      if (!acc || typeof acc !== 'object') continue;
      if (acc.username === from) acc.username = to;
      for (const tx of acc.transactions ?? []) {
        if (!tx || typeof tx !== 'object') continue;
        for (const key of USERNAME_FIELD_KEYS) {
          if (tx[key] === from) tx[key] = to;
        }
      }
    }
    if (ledger.networkNodes && typeof ledger.networkNodes === 'object') {
      if (ledger.networkNodes[from] && !ledger.networkNodes[to]) {
        const node = ledger.networkNodes[from];
        delete ledger.networkNodes[from];
        ledger.networkNodes[to] = {
          ...node,
          username: to,
        };
      }
    }
  };

  for (const canonical of systemUsernames()) {
    const alias = obfuscateUsername(canonical);
    if (!alias || alias === canonical) continue;
    if (accounts[alias] && !accounts[canonical]) {
      accounts[canonical] = { ...accounts[alias], username: canonical };
      delete accounts[alias];
      rewriteRefs(alias, canonical);
    } else if (accounts[alias] && accounts[canonical]) {
      // Merge alias into canonical then drop alias.
      const a = accounts[alias];
      const c = accounts[canonical];
      const aBal = Number(a?.balance?.microUnits ?? 0);
      const cBal = Number(c?.balance?.microUnits ?? 0);
      if (aBal > 0) {
        c.balance = { microUnits: cBal + aBal };
      }
      delete accounts[alias];
      rewriteRefs(alias, canonical);
    }
  }

  // Emission-based recovery when salt mismatch left treasury only under a foreign alias.
  const treasury = (process.env.PERC_TREASURY_USERNAME ?? 'evolve_treasury').trim();
  const treasAcc = accounts[treasury];
  const treasBal = Number(treasAcc?.balance?.microUnits ?? 0);
  if (treasBal <= 0) {
    const emissionTotals = new Map();
    for (const block of ledger.blocks ?? []) {
      for (const tx of block.transactions ?? []) {
        if (!tx || tx.kind !== 'treasuryEmission') continue;
        const to = String(tx.toUsername ?? '').trim();
        if (!to || to === treasury) continue;
        const amt = Number(tx.amount?.microUnits ?? 0);
        emissionTotals.set(to, (emissionTotals.get(to) ?? 0) + amt);
      }
    }
    if (emissionTotals.size > 0) {
      let best = null;
      let bestScore = -1;
      for (const [name, emitted] of emissionTotals) {
        const acc = accounts[name];
        if (!acc) continue;
        const score = Number(acc.balance?.microUnits ?? 0);
        // Prefer current balance; use emission total as tie-break.
        const rank = score * 10 + emitted;
        if (rank > bestScore) {
          bestScore = rank;
          best = name;
        }
      }
      if (best && best !== treasury && accounts[best]) {
        const acc = accounts[best];
        if (!accounts[treasury]) {
          accounts[treasury] = { ...acc, username: treasury };
        } else {
          const cBal = Number(accounts[treasury].balance?.microUnits ?? 0);
          const aBal = Number(acc.balance?.microUnits ?? 0);
          accounts[treasury].balance = { microUnits: cBal + aBal };
        }
        delete accounts[best];
        rewriteRefs(best, treasury);
      }
    }
  }

  return ledger;
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
 * System accounts (treasury / seed) stay under their real usernames so scenario
 * rewards can debit the funded treasury after public ledger import.
 * @param {object|null|undefined} ledger
 */
export function sanitizeLedgerForPublic(ledger) {
  if (!ledger || typeof ledger !== 'object') return ledger;

  const out = cloneValue(ledger);
  // Undo prior public-only aliasing of system accounts before re-export.
  restoreCanonicalSystemAccounts(out);
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
    // Helsinki public seed — never advertise paused Render as a live peer endpoint.
    const publicSeed = (process.env.PERC_PUBLIC_ENDPOINT ?? '')
      .trim()
      .replace(/\/$/, '');
    const nodes = {};
    for (const [key, node] of Object.entries(out.networkNodes)) {
      const alias = aliasUsername(key, aliasFor);
      const clean = node && typeof node === 'object' ? { ...node } : node;
      if (clean?.username != null) {
        clean.username = aliasUsername(clean.username, aliasFor);
      }
      if (clean && typeof clean === 'object' && clean.endpoint != null) {
        const ep = String(clean.endpoint);
        if (/onrender\.com/i.test(ep)) {
          // Rewrite paused Render peer ads so cold wallets do not probe a 503 host.
          clean.endpoint = publicSeed || '';
          if (!publicSeed) clean.online = false;
        }
      }
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