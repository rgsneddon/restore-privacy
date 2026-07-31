import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { blockTipPayload } from './chain_tip_payload.js';
import { compactLedgerForSeed } from './ledger_compact.js';
import { createGenesisLedger } from './genesis.js';

import {
  archiveSeedLedger,
  bootstrapSeedEpoch,
  isAnnualBootstrapDue,
} from './seed_bootstrap.js';
import { mergeNetworkStateFromPeer } from './merge_network_state.js';

const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';

export function tipHash(ledger) {
  const chainId = ledger?.evolutionaryChainId || CHAIN_ID;
  if (!ledger) {
    return crypto.createHash('sha256').update(`genesis:${chainId}`).digest('hex');
  }
  const blocks = ledger.blocks ?? [];
  if (blocks.length === 0) {
    return crypto.createHash('sha256').update(`genesis:${chainId}`).digest('hex');
  }
  const payload = JSON.stringify(blockTipPayload(blocks[blocks.length - 1]));
  return crypto.createHash('sha256').update(payload).digest('hex');
}

export function blockHeight(ledger) {
  if (!ledger) return 0;
  return ledger.blocks?.length ?? 0;
}

export function ledgerGenesisRevision(ledger) {
  return ledger?.networkGenesisRevision ?? 1;
}

export function shouldImportLedger(local, remote) {
  if (!remote || typeof remote !== 'object') return false;
  const localRev = ledgerGenesisRevision(local);
  const remoteRev = ledgerGenesisRevision(remote);
  if (remoteRev > localRev) return true;
  if (remoteRev < localRev) return false;
  const localH = blockHeight(local);
  const remoteH = blockHeight(remote);
  if (remoteH > localH) return true;
  if (remoteH === localH && remoteH > 0) {
    return tipHash(remote) !== tipHash(local);
  }
  return false;
}

export class LedgerStore {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.filePath = path.join(dataDir, 'seed_ledger.json');
    this.revision = 0;
    this.genesisRevision = 1;
    this.lastBootstrapAt = null;
    this.ledger = null;
    fs.mkdirSync(dataDir, { recursive: true });
    this.load();
  }

  load() {
    if (!fs.existsSync(this.filePath)) return;
    try {
      const raw = fs.readFileSync(this.filePath, 'utf8');
      const parsed = JSON.parse(raw);
      this.ledger = parsed.ledger ?? null;
      this.revision = parsed.revision ?? 0;
      this.genesisRevision = parsed.genesisRevision ?? ledgerGenesisRevision(this.ledger);
      this.lastBootstrapAt = parsed.lastBootstrapAt ?? parsed.savedAt ?? null;
      if (this.ledger) {
        const before = JSON.stringify(this.ledger).length;
        this.ledger = compactLedgerForSeed(this.ledger);
        if (JSON.stringify(this.ledger).length < before) {
          this.save();
        }
      }
    } catch {
      this.ledger = null;
      this.revision = 0;
      this.genesisRevision = 1;
      this.lastBootstrapAt = null;
    }
  }

  save() {
    const payload = {
      revision: this.revision,
      genesisRevision: this.genesisRevision,
      lastBootstrapAt: this.lastBootstrapAt,
      ledger: this.ledger ? compactLedgerForSeed(this.ledger) : null,
      savedAt: new Date().toISOString(),
    };
    fs.writeFileSync(this.filePath, JSON.stringify(payload, null, 2));
  }

  hasLedger() {
    return this.ledger != null;
  }

  getGenesisRevision() {
    return this.genesisRevision;
  }

  status(sessionUsername, endpoint) {
    const ledger = this.ledger;
    return {
      evolutionaryChainId: ledger?.evolutionaryChainId || CHAIN_ID,
      blockHeight: blockHeight(ledger),
      tipHash: tipHash(ledger),
      revision: this.revision,
      networkGenesisRevision: this.genesisRevision,
      lastBootstrapAt: this.lastBootstrapAt,
      sessionUsername,
      endpoint,
    };
  }

  resetToGenesis(genesisRevision = 2) {
    this.ledger = createGenesisLedger({ genesisRevision });
    this.genesisRevision = genesisRevision;
    this.revision += 1;
    this.save();
    return true;
  }

  ensureGenesisRevision(expectedRevision) {
    if (this.genesisRevision === expectedRevision && this.hasLedger()) return false;
    return this.resetToGenesis(expectedRevision);
  }

  importLedger(remote) {
    if (!remote || typeof remote !== 'object') return false;
    if (shouldImportLedger(this.ledger, remote)) {
      this.ledger = compactLedgerForSeed(remote);
      this.genesisRevision = ledgerGenesisRevision(remote);
      this.revision += 1;
      this.save();
      return true;
    }
    if (!this.ledger) return false;
    const ack = mergeNetworkStateFromPeer(this.ledger, remote);
    if (!ack.ok && ack.pendingMerged === 0 && !ack.treasuryMerged) return false;
    this.ledger = compactLedgerForSeed(this.ledger);
    this.revision += 1;
    this.save();
    return true;
  }

  forceReplaceLedger(remote) {
    if (!remote || typeof remote !== 'object') return false;
    this.ledger = compactLedgerForSeed(remote);
    this.genesisRevision = ledgerGenesisRevision(remote);
    this.revision += 1;
    this.save();
    return true;
  }

  /**
   * Archive the live ledger and roll forward to a compact epoch checkpoint.
   * @param {{ now?: Date, seedUsername?: string }} [options]
   */
  bootstrapEpoch(options = {}) {
    if (!this.ledger) {
      return { ok: false, error: 'no ledger' };
    }
    if (!this.ledger.blockchainLaunched) {
      return { ok: false, error: 'blockchain not launched' };
    }

    const archivePath = archiveSeedLedger(this.dataDir, {
      archivedAt: new Date().toISOString(),
      revision: this.revision,
      genesisRevision: this.genesisRevision,
      lastBootstrapAt: this.lastBootstrapAt,
      ledger: this.ledger,
    });

    const result = bootstrapSeedEpoch(this.ledger, options);
    this.ledger = result.ledger;
    this.genesisRevision = result.newRevision;
    this.revision += 1;
    this.lastBootstrapAt = result.bootstrappedAt;
    this.save();

    return {
      ok: true,
      archivePath,
      previousRevision: result.previousRevision,
      newRevision: result.newRevision,
      bootstrappedAt: result.bootstrappedAt,
      blockHeight: blockHeight(this.ledger),
      tipHash: tipHash(this.ledger),
    };
  }

  maybeAnnualBootstrap(options = {}) {
    if (!this.ledger?.blockchainLaunched) return null;
    if (!isAnnualBootstrapDue(this.lastBootstrapAt, options)) return null;
    return this.bootstrapEpoch(options);
  }

  treasuryAccount(treasuryUsername = 'evolve_treasury') {
    return this.ledger?.accounts?.[treasuryUsername] ?? null;
  }
}