"""Device key unify policy — host Packet Tunnel and host HELLO must share identity.

Mirrors shipped pure helper RptSecrets.preferredDevicePrivAmong (macOS NativePrep).
When home/App Support hold a KEYGEN-bound key and App Group has a post-wipe
generated key, home wins and is copied into the group so the sandboxed tunnel
does not HELLO with an unbound identity while host HELLO still assigns a node IP.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "client_app" / "macos" / "NativePrep" / "RptSecrets.swift"
CHANNEL = ROOT / "client_app" / "macos" / "NativePrep" / "RptVpnChannel.swift"
PROVIDER = ROOT / "client_app" / "macos" / "NativePrep" / "PacketTunnelProvider.swift"
ENT = (
    ROOT
    / "client_app"
    / "macos"
    / "PacketTunnel"
    / "PacketTunnelDeveloperID.entitlements"
)


def preferred_device_priv_among(
    home: bytes | None,
    app_support: bytes | None,
    app_group: bytes | None,
) -> bytes | None:
    """Pure mirror of RptSecrets.preferredDevicePrivAmong (32-byte keys only)."""
    for d in (home, app_support, app_group):
        if d is not None and len(d) == 32:
            return d
    return None


class TestDeviceKeyUnifyPolicy(unittest.TestCase):
    def test_shipped_source_has_unify_and_preference_order(self) -> None:
        text = SECRETS.read_text(encoding="utf-8")
        self.assertIn("preferredDevicePrivAmong", text)
        self.assertIn("unifyDeviceAdmissionKeysAcrossWritables", text)
        self.assertIn("preseedSharedWritableSecretsForResidualHost", text)
        # Prefer home then appSupport then appGroup when keys disagree.
        pref_start = text.index("func preferredDevicePrivAmong")
        pref_end = text.index("func unifyDeviceAdmissionKeysAcrossWritables", pref_start)
        pref = text[pref_start:pref_end]
        self.assertIn("home: Data?", pref)
        self.assertIn("appSupport: Data?", pref)
        self.assertIn("appGroup: Data?", pref)
        self.assertLess(pref.index("home:"), pref.index("appSupport:"))
        self.assertLess(pref.index("appSupport:"), pref.index("appGroup:"))
        # Preseed must call unify before only seeding pubs.
        pre_start = text.index("func preseedSharedWritableSecretsForResidualHost")
        pre = text[pre_start:pref_start]
        self.assertIn("unifyDeviceAdmissionKeysAcrossWritables", pre)

    def test_preference_home_wins_over_divergent_app_group(self) -> None:
        home = b"H" * 32
        group = b"G" * 32
        self.assertEqual(
            preferred_device_priv_among(home, None, group),
            home,
        )
        self.assertNotEqual(home, group)

    def test_preference_group_when_only_group(self) -> None:
        group = b"G" * 32
        self.assertEqual(
            preferred_device_priv_among(None, None, group),
            group,
        )

    def test_preference_rejects_wrong_length(self) -> None:
        self.assertIsNone(preferred_device_priv_among(b"short", b"x", None))
        self.assertEqual(
            preferred_device_priv_among(b"short", None, b"G" * 32),
            b"G" * 32,
        )

    def test_channel_preseeds_before_start_and_surfaces_extension_errors(self) -> None:
        ch = CHANNEL.read_text(encoding="utf-8")
        self.assertIn("preseedSharedWritableSecretsForResidualHost", ch)
        self.assertIn("lastDisconnectErrorDescription", ch)
        self.assertIn("recreateProductVpnProfileAndStart", ch)
        # Host + tunnel identity honesty in fail path
        self.assertIn("host HELLO alone is not enough", ch)

    def test_packet_tunnel_logs_admission_and_home_exception(self) -> None:
        prov = PROVIDER.read_text(encoding="utf-8")
        self.assertIn("os_log", prov)
        self.assertIn("admission", prov.lower())
        ent = ENT.read_text(encoding="utf-8")
        self.assertIn(".restore-privacy/", ent)
        self.assertIn("temporary-exception.files.home-relative-path.read-only", ent)


if __name__ == "__main__":
    unittest.main()
