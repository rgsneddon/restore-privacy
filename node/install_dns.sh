#!/usr/bin/env bash
# Install tunnel-only recursive DNS (Unbound) for Restore Privacy clients.
# Offline-prep companion to client full-tunnel DNS defaults (10.88.0.1).
#
# Safe to re-run. Does NOT open recursive DNS on the public internet.
# Apply on the VPS after RPT node TUN is up (rpt0 with 10.88.0.1/24).
#
# Usage (on the node host as root):
#   bash /opt/restore-privacy/node/install_dns.sh
#   # or from a checkout:
#   sudo bash node/install_dns.sh
set -euo pipefail

TUN_IFACE="${TUN_IFACE:-rpt0}"
TUNNEL_DNS_ADDR="${TUNNEL_DNS_ADDR:-10.88.0.1}"
CLIENT_NET="${CLIENT_NET:-10.88.0.0/24}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_SRC="${SCRIPT_DIR}/unbound-rpt.conf"

export DEBIAN_FRONTEND=noninteractive

echo "[rpt-dns] packages (unbound + ca-certificates for DoT)"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y unbound ca-certificates
else
  echo "unsupported package manager — install unbound manually and use ${CONF_SRC}" >&2
  exit 1
fi

echo "[rpt-dns] ensure tunnel address ${TUNNEL_DNS_ADDR} exists on ${TUN_IFACE} (best-effort)"
if ip link show "$TUN_IFACE" >/dev/null 2>&1; then
  ip addr show dev "$TUN_IFACE" | grep -q "${TUNNEL_DNS_ADDR}" \
    || ip addr add "${TUNNEL_DNS_ADDR}/24" dev "$TUN_IFACE" 2>/dev/null || true
  ip link set "$TUN_IFACE" up 2>/dev/null || true
else
  echo "[rpt-dns] WARN: ${TUN_IFACE} not up yet — start rpt-node first, then re-run this script"
fi

echo "[rpt-dns] install Unbound config (tunnel-only)"
mkdir -p /etc/unbound/unbound.conf.d
# Rewrite interface/access from env if operator customized
sed \
  -e "s/interface: 10.88.0.1/interface: ${TUNNEL_DNS_ADDR}/" \
  -e "s|access-control: 10.88.0.0/24 allow|access-control: ${CLIENT_NET} allow|" \
  "$CONF_SRC" > /etc/unbound/unbound.conf.d/rpt-tunnel.conf

# Drop any "listen on all" that some distros ship if it would open the world
# (we refuse 0.0.0.0/0 in access-control above).

echo "[rpt-dns] firewall: allow UDP/TCP 53 from tunnel net only (not public)"
# INPUT from tunnel clients to node DNS
iptables -C INPUT -s "$CLIENT_NET" -d "$TUNNEL_DNS_ADDR" -p udp --dport 53 -j ACCEPT 2>/dev/null \
  || iptables -I INPUT 1 -s "$CLIENT_NET" -d "$TUNNEL_DNS_ADDR" -p udp --dport 53 -j ACCEPT
iptables -C INPUT -s "$CLIENT_NET" -d "$TUNNEL_DNS_ADDR" -p tcp --dport 53 -j ACCEPT 2>/dev/null \
  || iptables -I INPUT 1 -s "$CLIENT_NET" -d "$TUNNEL_DNS_ADDR" -p tcp --dport 53 -j ACCEPT
# Do not add a global "ufw allow 53" — that would make an open resolver.

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable unbound.service 2>/dev/null || true
  systemctl restart unbound.service
  sleep 1
  systemctl --no-pager --full status unbound.service || true
fi

echo "[rpt-dns] self-check (must succeed for a *tunnel client* source, not only localhost)"
# Localhost dig can pass while 10.88.0.x clients are REFUSED (product residual bug).
# Bind a temporary client address on the tunnel iface and dig with -b.
if command -v dig >/dev/null 2>&1; then
  PROBE_SRC="${TUNNEL_DNS_PROBE_SRC:-10.88.0.50}"
  if ip link show "$TUN_IFACE" >/dev/null 2>&1; then
    ip addr add "${PROBE_SRC}/24" dev "$TUN_IFACE" 2>/dev/null || true
  fi
  if dig @"$TUNNEL_DNS_ADDR" -b "$PROBE_SRC" example.com A +time=3 +tries=2 +short 2>/dev/null | grep -Eq '^[0-9]+\.'; then
    echo "[rpt-dns] dig ok via ${TUNNEL_DNS_ADDR} from tunnel client ${PROBE_SRC}"
  else
    echo "[rpt-dns] FAIL: dig from tunnel client ${PROBE_SRC} to ${TUNNEL_DNS_ADDR} did not resolve" >&2
    echo "[rpt-dns] residual clients will show Connected with no internet until this works" >&2
    dig @"$TUNNEL_DNS_ADDR" -b "$PROBE_SRC" example.com A +time=3 +tries=1 2>&1 | tail -20 >&2 || true
    exit 1
  fi
else
  echo "[rpt-dns] dig not installed; skip probe"
fi

echo "[rpt-dns] done. Clients use DNS ${TUNNEL_DNS_ADDR} when full tunnel is up."
echo "[rpt-dns] Upstream is DNS-over-TLS (DoT) to privacy resolvers — see unbound-rpt.conf."
echo "[rpt-dns] Do not open port 53 on the public WAN."
echo "[rpt-dns] Do not configure client-side Cloudflare/Google/Quad9 as residual DNS fallbacks."
