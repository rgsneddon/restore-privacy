/// Suite-level Perccent rendezvous / chain network defaults.
///
/// The paid Render service **evolve-perc-internet.onrender.com** is paused to
/// save money. Clients must use the Helsinki-hosted perc_chain internet node
/// (or an operator env override), never re-enable Render as the required live
/// rendezvous by default.
library;

/// Helsinki store / suite chain host (paid-asset CDN + perc_chain default).
const String kHelsinkiHost = '135.181.152.10';

/// TLS hostname on Helsinki (Let's Encrypt sslip.io).
const String kHelsinkiSslIpHost = '135.181.152.10.sslip.io';

/// Backend perc_chain listen port (loopback behind nginx).
const int kPercChainPort = 9478;

/// Default public rendezvous base URL for suite wallet / evolve tabs.
///
/// Served via nginx `/perc/` on Helsinki (cloud firewall blocks raw :9478).
/// Override with `--dart-define=PERC_RENDEZVOUS_URL=...` (see
/// [resolveSuiteRendezvousUrl]).
const String kHelsinkiPercRendezvousUrl =
    'https://$kHelsinkiSslIpHost/perc';

/// Retired paid Render endpoint — do not use as the required live rendezvous.
const String kPausedRenderPercInternet =
    'https://evolve-perc-internet.onrender.com';

/// Operator note recorded in-repo for deploy docs and config comments.
const String kPercInternetPausedNote =
    'evolve-perc-internet (Render) is paused to save money; '
    'Helsinki perc_chain is the default suite rendezvous.';

/// Compile-time override: `--dart-define=PERC_RENDEZVOUS_URL=https://host:port`.
const String kPercRendezvousUrlFromEnvironment = String.fromEnvironment(
  'PERC_RENDEZVOUS_URL',
  defaultValue: '',
);

/// Resolve the suite client rendezvous URL (env define → Helsinki default).
///
/// Never falls back to the paused Render host.
String resolveSuiteRendezvousUrl({String? override}) {
  final o = (override ?? '').trim();
  if (o.isNotEmpty) return o.replaceAll(RegExp(r'/$'), '');
  final fromDefine = kPercRendezvousUrlFromEnvironment.trim();
  if (fromDefine.isNotEmpty) {
    return fromDefine.replaceAll(RegExp(r'/$'), '');
  }
  return kHelsinkiPercRendezvousUrl;
}

/// True when [url] is the paused Render paid endpoint (should not be required).
bool isPausedRenderPercInternet(String? url) {
  final u = (url ?? '').trim().toLowerCase().replaceAll(RegExp(r'/$'), '');
  if (u.isEmpty) return false;
  return u.contains('evolve-perc-internet.onrender.com');
}

/// JSON map for suite-bundled `perc_network.json` (Helsinki default).
Map<String, Object?> suitePercNetworkJson({String? rendezvousUrl}) {
  return {
    'rendezvousUrl': resolveSuiteRendezvousUrl(override: rendezvousUrl),
    'seedUsername': 'evolve_seed_node',
    'networkGenesisRevision': 2,
    'publicIpLookupUrls': [
      'https://api.ipify.org',
      'https://ifconfig.me/ip',
    ],
    'publicEndpointOverride': '',
    // Operator note: evolve-perc-internet is paused to save money.
    '_comment_paused_render': kPercInternetPausedNote,
  };
}
