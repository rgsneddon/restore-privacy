import unittest

from node.rpai_learn import SOURCE_VPN, SOURCE_WALLET, RpaiLearner, learn_vpn_event


class RpaiLearnTests(unittest.TestCase):
    def test_learns_wallet_and_vpn_rejects_other(self):
        ned = RpaiLearner()
        wallet = ned.learn(SOURCE_WALLET, "tab_click", "wallet")
        vpn = ned.learn(SOURCE_VPN, "connect", "helsinki")
        denied = ned.learn("random-website", "scrape", "nope")
        self.assertTrue(wallet.accepted)
        self.assertTrue(vpn.accepted)
        self.assertFalse(denied.accepted)
        self.assertEqual(denied.reason, "source_not_permitted")
        stats = ned.stats()
        self.assertEqual(stats["walletEvents"], 1)
        self.assertEqual(stats["vpnEvents"], 1)
        self.assertEqual(stats["learned"], 2)
        self.assertEqual(stats["rejected"], 1)

    def test_vpn_hook_ingests_connect(self):
        result = learn_vpn_event("connect", "residual-helsinki")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["source"], SOURCE_VPN)


if __name__ == "__main__":
    unittest.main()
