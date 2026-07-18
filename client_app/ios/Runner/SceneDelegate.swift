import Flutter
import UIKit

class SceneDelegate: FlutterSceneDelegate {
  /// Scene-based lifecycle: when the UI scene backgrounds (home / app switcher),
  /// stop Packet Tunnel so residual public IP returns. Same path as AppDelegate.
  override func sceneDidEnterBackground(_ scene: UIScene) {
    RptVpnChannel.stopAllTunnels()
    super.sceneDidEnterBackground(scene)
  }
}
