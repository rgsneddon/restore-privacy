/// Entry-country selector helpers (flags, Iceland default, Connect gate).
///
/// Catalog mirrors [client/multihop.py] PRODUCT_COUNTRY_CATALOG (IS/RO/DE).
library;

const String kDefaultEntryCountry = 'IS';
const String kCountryIceland = 'IS';
const String kCountryRomania = 'RO';
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

  String get label => flag.isEmpty ? '$name ($code)' : '$flag  $name ($code)';
}

/// Shipped catalog — keep aligned with client.multihop PRODUCT_COUNTRY_CATALOG.
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
    code: kCountryGermany,
    name: 'Germany',
    flag: '🇩🇪',
    host: '167.233.224.5',
  ),
];

String defaultEntryCountry() => kDefaultEntryCountry;

/// Strict parse — unknown/empty → null (does not default).
String? parseCatalogCountryCode(String? raw) {
  final upper = (raw ?? '').trim().toUpperCase();
  if (upper.isEmpty) return null;
  const aliases = {
    'ICELAND': kCountryIceland,
    'IS': kCountryIceland,
    'ROMANIA': kCountryRomania,
    'RO': kCountryRomania,
    'ROU': kCountryRomania,
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

/// Normalize: empty/unknown → Iceland (durable prefs default).
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
      return (ok: true, code: kDefaultEntryCountry, reason: 'default_iceland');
    }
    return (ok: false, code: '', reason: 'missing_entry_country');
  }
  final code = parseCatalogCountryCode(trimmed);
  if (code == null) {
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
