/// Evolve inherits Suite account from first-run step 1 (no redundant full wall).
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/suite_account.dart';
import 'package:restore_privacy_client/settings_store.dart';

void main() {
  test('suiteEvolveInheritsSuiteLogin when registered + wallet session live', () {
    expect(
      suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: true,
        walletHasAppAccess: true,
      ),
      isTrue,
    );
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: true,
        walletHasAppAccess: true,
      ),
      isFalse,
    );
  });

  test('suiteEvolveShowsLoginWall when no Suite account yet', () {
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: false,
        walletHasAppAccess: false,
      ),
      isTrue,
    );
    expect(
      suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: false,
        walletHasAppAccess: false,
      ),
      isFalse,
    );
  });

  test('Suite registered without live session still needs password (not create)', () {
    expect(
      suiteEvolveShowsLoginWall(
        suiteAccountRegistered: true,
        walletHasAppAccess: false,
      ),
      isTrue,
    );
    expect(
      suiteEvolveInheritsSuiteLogin(
        suiteAccountRegistered: true,
        walletHasAppAccess: false,
      ),
      isFalse,
    );
  });

  test('SuiteAccountBus notify + store markRegistered share identity', () async {
    final prefs = MemorySettingsBackend();
    final store = SuiteAccountStore(prefs);
    SuiteAccountBus.instance.lastUsername = null;
    await store.markRegistered('first_run_user');
    SuiteAccountBus.instance.notifyRegistered('first_run_user');
    expect(await store.isRegistered(), isTrue);
    expect(await store.username(), 'first_run_user');
    expect(SuiteAccountBus.instance.lastUsername, 'first_run_user');
  });
}
