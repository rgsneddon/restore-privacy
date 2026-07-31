/** @type {number} */
export const PEER_ONLINE_MS = Number(process.env.PERC_PEER_ONLINE_MS ?? 7 * 60 * 1000);

export function isPeerOnline(peer, now = Date.now()) {
  const updated = peer?.updatedAt ?? 0;
  return updated > 0 && now - updated <= PEER_ONLINE_MS;
}

/** True when the seed has a fresh heartbeat for this wallet address or username. */
export function isRecipientOnlineOnSeed({
  peers,
  addresses,
  username,
  address,
  now = Date.now(),
}) {
  const needleUser = username?.trim();
  const needleAddr = address?.trim();
  if (!needleUser && !needleAddr) return false;

  for (const peer of peers.values()) {
    if (!isPeerOnline(peer, now)) continue;
    if (needleUser && peer.sessionUsername === needleUser) return true;
    if (needleAddr && peer.walletAddress === needleAddr) return true;
  }

  if (needleAddr) {
    const mapped = addresses.get(needleAddr);
    if (mapped) {
      const peer = peers.get(mapped);
      if (peer && isPeerOnline(peer, now)) return true;
    }
  }

  return false;
}

/** Refresh seed peer heartbeat when a wallet publishes its address while signed in. */
export function touchPeerHeartbeatOnSeed({
  peers,
  addresses,
  username,
  address,
  endpoint,
  evolutionaryChainId = 'evolve-chronoflux-principia-chain-1',
  now = Date.now(),
}) {
  const user = username?.trim();
  if (!user) return false;

  const addr = address?.trim();
  const existing = peers.get(user) ?? {};

  peers.set(user, {
    ...existing,
    sessionUsername: user,
    evolutionaryChainId: existing.evolutionaryChainId ?? evolutionaryChainId,
    endpoint: endpoint ?? existing.endpoint,
    walletAddress: addr ?? existing.walletAddress,
    updatedAt: now,
  });

  if (addr) {
    addresses.set(addr, user);
  }

  return true;
}