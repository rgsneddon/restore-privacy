/**
 * Merge upstream rendezvous peer lists into a local peer map.
 * @param {Map<string, object>} localPeers
 * @param {unknown} upstreamList
 * @param {string} chainId
 * @returns {number} count of peers added or updated from upstream
 */
export function mergeUpstreamPeers(localPeers, upstreamList, chainId) {
  if (!Array.isArray(upstreamList)) return 0;
  let merged = 0;
  for (const peer of upstreamList) {
    if (!peer || typeof peer !== 'object') continue;
    const endpoint = peer.endpoint;
    if (!endpoint) continue;
    const sessionUsername = peer.sessionUsername ?? peer.username ?? null;
    const publicAlias = peer.publicAlias ?? null;
    const peerChain = peer.evolutionaryChainId ?? chainId;
    if (peerChain !== chainId) continue;
    const key = String(sessionUsername ?? publicAlias ?? endpoint);
    const existing = localPeers.get(key);
    const incomingRevision = Number(peer.revision ?? 0);
    const existingRevision = Number(existing?.revision ?? 0);
    if (!existing || incomingRevision >= existingRevision) {
      const entry = {
        endpoint,
        evolutionaryChainId: peerChain,
        blockHeight: peer.blockHeight ?? existing?.blockHeight ?? 0,
        tipHash: peer.tipHash ?? existing?.tipHash ?? '',
        revision: incomingRevision || existingRevision,
        updatedAt: Date.now(),
        upstream: true,
      };
      if (sessionUsername) {
        entry.sessionUsername = sessionUsername;
      }
      if (publicAlias) {
        entry.publicAlias = publicAlias;
      } else if (sessionUsername) {
        entry.publicAlias = existing?.publicAlias;
      }
      localPeers.set(key, entry);
      merged += 1;
    }
  }
  return merged;
}