/**
 * Lightweight wake hints: sender relay PUT notifies a recipient to burst-poll.
 * @typedef {Map<string, Map<string, number>>} InboundHintsStore
 */

/** @returns {InboundHintsStore} */
export function createInboundHintsStore() {
  return new Map();
}

/**
 * @param {InboundHintsStore} hints
 * @param {string | undefined | null} recipientUsername
 * @param {string | undefined | null} senderUsername
 */
export function recordInboundRelayHint(hints, recipientUsername, senderUsername) {
  const recipient = recipientUsername?.trim();
  const sender = senderUsername?.trim();
  if (!recipient || !sender) return;
  let senders = hints.get(recipient);
  if (!senders) {
    senders = new Map();
    hints.set(recipient, senders);
  }
  senders.set(sender, Date.now());
}

/**
 * @param {InboundHintsStore} hints
 * @param {string | undefined | null} recipientUsername
 * @returns {{ sender: string, updatedAt: number }[]}
 */
export function fetchInboundRelayHints(hints, recipientUsername) {
  const recipient = recipientUsername?.trim();
  if (!recipient) return [];
  const senders = hints.get(recipient);
  if (!senders) return [];
  return [...senders.entries()].map(([sender, updatedAt]) => ({
    sender,
    updatedAt,
  }));
}