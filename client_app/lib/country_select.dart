/// Entry-country selector helpers (flags, United States/US default, Connect gate).
///
/// Catalog mirrors [client/multihop.py] PRODUCT_COUNTRY_CATALOG (IS/RO/US).
library;

/// Product default residual entry (empty prefs / fresh install).
const String kDefaultEntryCountry = 'US';
const String kCountryIceland = 'IS';
const String kCountryRomania = 'RO';
const String kCountryUnitedStates = 'US';
/// Retired residual peer code — [normalizeEntryCountry] maps DE → default US.
const String kCountryGermany = 'DE';

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
    code: kCountryRomania,
    name: 'Romania',
    flag: '🇷🇴',
    host: '185.146.232.107',
  ),
  CountryOption(
    code: kCountryUnitedStates,
    name: 'United States',
    flag: '🇺🇸',
    host: '5.161.242.85',
  ),
];

String defaultEntryCountry() => kDefaultEntryCountry;

/// Strict parse — unknown/empty/stale DE → null (does not default).
String? parseCatalogCountryCode(String? raw) {
  final upper = (raw ?? '').trim().toUpperCase();
  if (upper.isEmpty) return null;
  // Stale DE prefs are not a catalog member
  if (upper == 'DE' ||
      upper == 'GERMANY' ||
      upper == 'DEU' ||
      upper == 'DEUTSCHLAND') {
    return null;
  }
  const aliases = {
    'ICELAND': kCountryIceland,
    'IS': kCountryIceland,
    'ROMANIA': kCountryRomania,
    'RO': kCountryRomania,
    'ROU': kCountryRomania,
    'UNITED STATES': kCountryUnitedStates,
    'UNITED STATES OF AMERICA': kCountryUnitedStates,
    'USA': kCountryUnitedStates,
    'US': kCountryUnitedStates,
    'AMERICA': kCountryUnitedStates,
  };
  final want = aliases[upper] ?? upper;
  for (final o in kProductCountryCatalog) {
    if (o.code == want) return o.code;
  }
  return null;
}

/// Normalize: empty/unknown/stale DE → United States/US (durable prefs default).
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
        reason: 'default_united_states',
      );
    }
    return (ok: false, code: '', reason: 'missing_entry_country');
  }
  final code = parseCatalogCountryCode(trimmed);
  if (code == null) {
    // Stale DE / unknown: when allowDefault, map to product default US
    if (allowDefault) {
      final upper = trimmed.toUpperCase();
      if (upper == 'DE' ||
          upper == 'GERMANY' ||
          upper == 'DEU' ||
          upper == 'DEUTSCHLAND') {
        return (
          ok: true,
          code: kDefaultEntryCountry,
          reason: 'default_united_states',
        );
      }
    }
    return (ok: false, code: '', reason: 'invalid_entry_country');
  }
  return (ok: true, code: code, reason: 'ok');
}

bool entryCountryAllowsConnect(
  String? raw, {
  bool allowDefault = true,
}) {
  return resolveEntryCountrySelection(raw, allowDefault: allowDefault).ok;
}

CountryOption? countryOptionForCode(String? code) {
  final c = normalizeEntryCountry(code);
  for (final o in kProductCountryCatalog) {
    if (o.code == c) return o;
  }
  return kProductCountryCatalog.first;
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
  // Any bare IPv4 (or unknown host) — never echo monopin IP in UI.
  if (RegExp(r'^\d+\.\d+\.\d+\.\d+$').hasMatch(h)) {
    return 'VPN node';
  }
  return 'VPN node';
}

String residualHostForEntryCountry(String? code, {bool multiHop = false}) {
  // Multi-hop residual dials a non-entry peer; single-hop uses entry monopin.
  final entry = countryOptionForCode(code);
  if (!multiHop) return entry?.host ?? kProductCountryCatalog.first.host;
  for (final o in kProductCountryCatalog) {
    if (o.code != (entry?.code ?? kDefaultEntryCountry) && o.host.isNotEmpty) {
      return o.host;
    }
  }
  return entry?.host ?? kProductCountryCatalog.first.host;
}

/// ElGamal public pin basename for residual HELLO from dial *host* monopin.
///
/// IS → `node_elgamal.pub`; RO → `exit_node_elgamal.pub`; US → `us_node_elgamal.pub`.
String residualNodePubNameForHost(String host) {
  final h = host.trim();
  for (final o in kProductCountryCatalog) {
    if (o.host.isNotEmpty && (h == o.host || h.endsWith(o.host))) {
      switch (o.code) {
        case kCountryRomania:
          return 'exit_node_elgamal.pub';
        case kCountryUnitedStates:
          return 'us_node_elgamal.pub';
        default:
          return 'node_elgamal.pub';
      }
    }
  }
  // Legacy host constants without catalog match
  if (h == '185.146.232.107') return 'exit_node_elgamal.pub';
  if (h == '5.161.242.85') return 'us_node_elgamal.pub';
  return 'node_elgamal.pub';
}
