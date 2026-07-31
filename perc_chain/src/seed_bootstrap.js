import fs from 'fs';
import path from 'path';
import { compactLedgerForSeed } from './ledger_compact.js';

function cloneLedger(ledger) {
  if (typeof structuredClone === 'function') return structuredClone(ledger);
  return JSON.parse(JSON.stringify(ledger));
}

/**
 * @returns {number} 0 = no cap
 */
export function annualBootstrapDays() {
  const raw = Number(process.env.PERC_ANNUAL_BOOTSTRAP_DAYS ?? 0);
  if (!Number.isFinite(raw) || raw <= 0) return 0;
  return Math.min(Math.floor(raw), 3650);
}

/**
 * Build a checkpoint ledger for a new seed epoch — preserves accounts and treasury
 * totals, clears block history and non-essential logs.
 *
 * @param {object} ledger
 * @param {{ now?: Date, seedUsername?: string }} [options]
 */
export function bootstrapSeedEpoch(ledger, options = {}) {
  if (!ledger || typeof ledger !== 'object') {
    throw new Error('bootstrapSeedEpoch requires a ledger object');
  }

  const now = options.now ?? new Date();
  const iso = now.toISOString();
  const seedUsername = options.seedUsername ?? process.env.PERC_SEED_USERNAME ?? 'evolve_seed_node';
  const previousRevision = ledger.networkGenesisRevision ?? 1;
  const newRevision = previousRevision + 1;

  const out = cloneLedger(ledger);
  out.networkGenesisRevision = newRevision;
  out.blocks = [
    {
      index: 0,
      timestamp: iso,
      transactions: [],
      treasuryEmitted: { microUnits: 0 },
      scenarioLabel: `Seed epoch bootstrap (revision ${previousRevision} → ${newRevision})`,
      triggerUsername: seedUsername,
    },
  ];
  out.microblockLog = [];
  out.evolutionSteps = [];
  out.evolvedAppVersions = Array.isArray(out.evolvedAppVersions)
    ? [...out.evolvedAppVersions]
    : [];
  out.wardProposals = [];
  out.wardBallots = [];
  out.sessionUsername = null;
  out.seedEpochBootstrappedAt = iso;
  out.seedEpochPreviousRevision = previousRevision;

  for (const account of Object.values(out.accounts ?? {})) {
    if (!account || typeof account !== 'object') continue;
    account.transactions = [];
  }

  const compact = compactLedgerForSeed(out);
  return {
    ledger: compact,
    previousRevision,
    newRevision,
    bootstrappedAt: iso,
  };
}

/**
 * Write the current ledger snapshot to an archive file under dataDir.
 *
 * @param {string} dataDir
 * @param {object} snapshot
 * @returns {string} archive file path
 */
export function archiveSeedLedger(dataDir, snapshot) {
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const archivePath = path.join(dataDir, `seed_ledger_archive_${stamp}.json`);
  fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(archivePath, JSON.stringify(snapshot, null, 2));
  return archivePath;
}

/**
 * @param {string|undefined|null} lastBootstrapAt ISO timestamp
 * @param {{ now?: Date }} [options]
 */
export function isAnnualBootstrapDue(lastBootstrapAt, options = {}) {
  const days = annualBootstrapDays();
  if (days <= 0) return false;
  if (!lastBootstrapAt) return false;
  const now = options.now ?? new Date();
  const last = new Date(lastBootstrapAt);
  if (Number.isNaN(last.getTime())) return true;
  const elapsedDays = (now.getTime() - last.getTime()) / 86_400_000;
  return elapsedDays >= days;
}