import crypto from 'crypto';

const CHAIN_ID = 'evolve-chronoflux-principia-chain-1';
const PRINCIPIA_ID = 'chronoflux-principia-roy-d-herbert';
const MAIN_CHAIN_ID = 'perc-main-evolve-1';
const SIDE_CHAIN_ID = 'perc-chronoflux-side-1';

export function generateSalt() {
  return crypto.randomBytes(16).toString('base64url');
}

export function deriveConfidentialAddress(username, salt) {
  const digest = crypto
    .createHash('sha256')
    .update(`beam-confidential:${username}:${salt}`)
    .digest('hex');
  return `percpriv1${digest.substring(0, 40)}`;
}

export function zeroAmount() {
  return { microUnits: 0 };
}

/**
 * Fresh block-0 ledger with a new evolve_treasury wallet (password not set).
 */
export function createGenesisLedger({
  genesisRevision = 2,
  treasuryUsername = 'evolve_treasury',
  treasurySalt = generateSalt(),
} = {}) {
  const treasury = {
    username: treasuryUsername,
    passwordHash: '',
    salt: treasurySalt,
    address: deriveConfidentialAddress(treasuryUsername, treasurySalt),
    passwordSet: false,
    balance: zeroAmount(),
    cumulativeStakingEarned: zeroAmount(),
    transactions: [],
  };

  return {
    version: 9,
    networkGenesisRevision: genesisRevision,
    evolutionaryChainId: CHAIN_ID,
    chronofluxPrincipiaId: PRINCIPIA_ID,
    mainChainId: MAIN_CHAIN_ID,
    sideChainId: SIDE_CHAIN_ID,
    connectedAppVersion: '3.0.0',
    evolvedAppVersions: [],
    evolutionSteps: [],
    evolutionEpoch: 1,
    accounts: { [treasuryUsername]: treasury },
    blocks: [],
    lastScenarioAt: null,
    treasuryGenesisDone: false,
    cumulativeTreasuryMinted: zeroAmount(),
    cumulativeBurnedPerc: zeroAmount(),
    treasuryCycle: 1,
    blockchainLaunched: false,
    sessionUsername: null,
    nextTxId: 1,
    microblockCount: 0,
    totalMicroblocks: 0,
    walletPeers: {},
    networkNodes: {},
    wardProposals: [],
    wardBallots: [],
    nextWardProposalId: 1,
    pendingInboundTransfers: [],
  };
}