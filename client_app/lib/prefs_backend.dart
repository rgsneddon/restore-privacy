import 'package:shared_preferences/shared_preferences.dart';

import 'settings_store.dart';

/// Production backend: SharedPreferences (survives open/close/open).
class SharedPreferencesBackend implements SettingsBackend {
  SharedPreferencesBackend(this._prefs);

  final SharedPreferences _prefs;

  static Future<SharedPreferencesBackend> create() async {
    final p = await SharedPreferences.getInstance();
    return SharedPreferencesBackend(p);
  }

  @override
  Future<bool?> getBool(String key) async => _prefs.getBool(key);

  @override
  Future<void> setBool(String key, bool value) async {
    await _prefs.setBool(key, value);
  }

  @override
  Future<String?> getString(String key) async => _prefs.getString(key);

  @override
  Future<void> setString(String key, String value) async {
    await _prefs.setString(key, value);
  }
}
