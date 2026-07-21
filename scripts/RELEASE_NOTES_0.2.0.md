# Restore Privacy 0.2.0 — release notes

**Status:** Public package release for production node **82.221.101.241**.

## Headline

Clients target the **FlokiNET** RPT node at **`82.221.101.241:44044`**.
Includes privacy work since 0.1.8:

- UK public-IP geo admission **removed** (no third-party geo on Connect)
- Full-tunnel DNS defaults to node **10.88.0.1** (tunnel-only Unbound on node)
- IPv6 leak mitigation + honest status when IPv6 is not protected
- Device keys + residual-honest Connect unchanged

## Upgrade

Install **0.2.0** packages from the GitHub Release or VPN APP Shop. Older
0.1.8 installers may still point at the previous node IP until upgraded.

## Operators

- Node deploy: `scripts/deploy_rpt_node.py` with `RPT_SSH_HOST=82.221.101.241`
- DNS: `node/install_dns.sh`; host quiet logging: `node/install_host_privacy.sh`
