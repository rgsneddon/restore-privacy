/** Hide IPv4 addresses and account identities from public explorer/API responses. */

import { sanitizePublicPayload } from './account_privacy.js';

const IPV4_RE =
  /\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b/g;

const PRIVATE_NODE_LABEL = 'Private node';

function hostFromEndpoint(endpoint) {
  if (!endpoint || typeof endpoint !== 'string') return '';
  try {
    return new URL(endpoint).hostname;
  } catch {
    const match = endpoint.match(/^https?:\/\/([^/:]+)/i);
    return match?.[1] ?? '';
  }
}

export function containsIpAddress(value) {
  if (value == null) return false;
  return IPV4_RE.test(String(value));
}

export function maskIpAddresses(value) {
  if (value == null) return value;
  if (typeof value !== 'string') return value;
  return value.replace(IPV4_RE, '[hidden]');
}

/**
 * Replace IP-based wallet endpoints with a neutral label (no host/port leaked).
 */
export function maskEndpoint(endpoint) {
  if (!endpoint || typeof endpoint !== 'string') return endpoint ?? null;
  const host = hostFromEndpoint(endpoint);
  if (host && containsIpAddress(host)) {
    return PRIVATE_NODE_LABEL;
  }
  return maskIpAddresses(endpoint);
}

/**
 * Deep-sanitize JSON payloads before sending to the public explorer.
 */
export function sanitizeForPublicExplorer(data) {
  return sanitizePublicPayload(data);
}