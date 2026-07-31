/// Entry-country selector helpers (flags, Germany/DE default, Connect gate).
///
/// Catalog mirrors [client/multihop.py] PRODUCT_COUNTRY_CATALOG (IS/DE only).
library;

/// Product default residual entry (empty prefs / fresh install).
const String kDefaultEntryCountry = 'DE';
const String kCountryIceland = 'IS';
const String kCountryGermany = 'DE';
const String kCountryUnitedStates = 'US'; // retired — normalize maps US → DE
/// Retired residual peer codes — [normalizeEntryCountry] maps RO/US → default DE.
const String kCountryRomania = 'RO';

/// Product residual entry peers (code, name, flag emoji, monopin host).
class CountryOption {
  final String code;
  final String name;
  final String flag;
  final String host;

  const CountryOption({
    required this.code,
    required this.name,
    required this.flag,
    this.host = '',
  });

  /// User-facing label never includes residual monopin IP (dial host is private).
  String get label => flag.isEmpty ? '$name ($code)' : '$flag  $name ($code)';
}

/// Shipped catalog — keep aligned with client.multihop PRODUCT_COUNTRY_CATALOG.
///
/// [host] is the private dial address used by residual Connect/HELLO only.
/// UI must use [label] / [code] / [name] — never paint [host] in user surfaces.
const List<CountryOption> kProductCountryCatalog = [
  CountryOption(
    code: kCountryIceland,
    name: 'Iceland',
    flag: '🇮🇸',
    host: '82.221.101.241',
  ),
  CountryOption(
    code: kCountryGermany,
    name: 'Germany',
    flag: '🇩🇪',
    host: '178.105.187.178',
  ),
];

String defaultEntryCountry() => kDefaultEntryCountry;

/// Strict parse — unknown/empty/stale RO → null (does not default).
String? parseCatalogCountryCode(String? raw) {
  final upper = (raw ?? '').trim().toUpperCase();
  if (upper.isEmpty) return null;
  // Stale RO/US prefs are not catalog members (normalize maps to DE)
  if (upper == 'RO' ||
      upper == 'ROMANIA' ||
      upper == 'ROU' ||
      upper == 'US' ||
      upper == 'USA' ||
      upper == 'UNITED STATES' ||
      upper == 'UNITED STATES OF AMERICA' ||
      upper == 'AMERICA') {
    return null;
  }
  const aliases = {
    'ICELAND': kCountryIceland,
    'IS': kCountryIceland,
    'GERMANY': kCountryGermany,
    'DE': kCountryGermany,
    'DEU': kCountryGermany,
    'DEUTSCHLAND': kCountryGermany,
  };
  final want = aliases[upper] ?? upper;
  for (final o in kProductCountryCatalog) {
    if (o.code == want) return o.code;
  }
  return null;
}

/// Normalize: empty/unknown/stale RO/US → Germany/DE (durable prefs default).
String normalizeEntryCountry(String? raw) {
  final c = parseCatalogCountryCode(raw);
  return c ?? kDefaultEntryCountry;
}

/// Resolve for Connect: (ok, code, reason).
({bool ok, String code, String reason}) resolveEntryCountrySelection(
  String? raw, {
  bool allowDefault = true,
}) {
  final trimmed = (raw ?? '').trim();
  if (trimmed.isEmpty) {
    if (allowDefault) {
      return (
        ok: true,
        code: kDefaultEntryCountry,
        reason: 'default_germany',
      );
    }
    return (ok: false, code: '', reason: 'missing_entry_country');
  }
  final code = parseCatalogCountryCode(trimmed);
  if (code == null) {
    // Stale RO / unknown: when allowDefault, map to product default DE
    if (allowDefault) {
      final upper = trimmed.toUpperCase();
      if (upper == 'RO' || upper == 'ROMANIA' || upper == 'ROU') {
        return (
          ok: true,
          code: kDefaultEntryCountry,
          reason: 'stale_ro_to_default_germany',
        );
      }
      if (upper == 'US' ||
          upper == 'USA' ||
          upper == 'UNITED STATES' ||
          upper == 'UNITED STATES OF AMERICA' ||
          upper == 'AMERICA') {
        return (
          ok: true,
          code: kDefaultEntryCountry,
          reason: 'stale_us_to_default_germany',
        );
      }
      // Other unknown → product default
      return (
        ok: true,
        code: kDefaultEntryCountry,
        reason: 'unknown_to_default_germany',
      );
    }
    return (ok: false, code: '', reason: 'unknown_entry_country');
  }
  return (ok: true, code: code, reason: 'catalog');
}

CountryOption? countryOptionForCode(String? code) {
  final c = normalizeEntryCountry(code);
  for (final o in kProductCountryCatalog) {
    if (o.code == c) return o;
  }
  return null;
}

/// Product exit hop for multi-hop residual (Germany monopin).
const String kProductExitHost = '178.105.187.178';

/// Residual dial host for entry *code* (+ multi-hop when on).
///
/// Multi-hop ON: dial [kProductExitHost] (DE) when entry is not already DE;
/// if entry is DE, stay on DE (exit == entry).
String residualHostForEntryCountry(
  String? code, {
  bool multiHop = false,
}) {
  final c = normalizeEntryCountry(code);
  if (multiHop) {
    // Residual-via-exit: dial DE exit when entry is not DE.
    if (c != kCountryGermany) {
      return kProductExitHost;
    }
  }
  for (final o in kProductCountryCatalog) {
    if (o.code == c) return o.host;
  }
  return kProductExitHost; // default DE
}

/// Other catalog residual monopin hosts for wipe-drain Connect failover.
///
/// Never includes [excluding] (preferred entry). Order follows product catalog.
List<String> alternateResidualHosts({String excluding = ''}) {
  final skip = excluding.trim();
  return [
    for (final o in kProductCountryCatalog)
      if (o.host.isNotEmpty && o.host != skip) o.host,
  ];
}

/// Public ElGamal pin basename for residual HELLO to *host*.
String residualNodePubNameForHost(String host) {
  final h = host.trim();
  for (final o in kProductCountryCatalog) {
    if (o.host == h) {
      switch (o.code) {
        case kCountryIceland:
          return 'node_elgamal.pub';
        case kCountryGermany:
          return 'de_node_elgamal.pub';
      }
    }
  }
  if (h == kProductExitHost || h == '178.105.187.178') {
    return 'de_node_elgamal.pub';
  }
  // Retired US monopin host — heal to DE pin
  if (h == '5.161.242.85') return 'de_node_elgamal.pub';
  if (h == '82.221.101.241') return 'node_elgamal.pub';
  // Stale RO host still maps to exit pin file (now DE content) for heal path only.
  if (h == '185.146.232.107') return 'exit_node_elgamal.pub';
  return 'node_elgamal.pub';
}

bool entryCountryAllowsConnect(
  String? raw, {
  bool allowDefault = true,
}) {
  return resolveEntryCountrySelection(raw, allowDefault: allowDefault).ok;
}

/// User-facing residual entry label — never a monopin IPv4.
String residualEntryPublicLabel([String? code]) {
  final o = countryOptionForCode(code);
  final name = (o?.name ?? '').trim();
  final c = (o?.code ?? kDefaultEntryCountry).trim();
  if (name.isEmpty) return c;
  return '$name ($c)';
}

/// Map dial host monopin → public country label (for status UI redaction).
String publicLabelForResidualHost(String? host) {
  final h = (host ?? '').trim();
  if (h.isEmpty) return 'VPN node';
  for (final o in kProductCountryCatalog) {
    if (o.host.isNotEmpty && (h == o.host || h.endsWith(o.host))) {
      return residualEntryPublicLabel(o.code);
    }
  }
  if (RegExp(r'^\d+\.\d+\.\d+\.\d+$').hasMatch(h)) {
    return 'VPN node';
  }
  return 'VPN node';
}
