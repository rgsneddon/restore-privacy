// Unit tests for residual_core — call shipped functions with golden vectors
// aligned to node/pfs.py + node/crypto_session.py + node/protocol.py.
#include "residual_core/pfs.hpp"
#include "residual_core/protocol.hpp"
#include "residual_core/residual_core.h"

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

int g_fails = 0;

void expect_true(bool cond, const char* msg) {
  if (!cond) {
    std::fprintf(stderr, "FAIL: %s\n", msg);
    ++g_fails;
  } else {
    std::printf("PASS: %s\n", msg);
  }
}

std::vector<std::uint8_t> hex_to_bytes(const char* hex) {
  std::vector<std::uint8_t> out;
  const std::size_t n = std::strlen(hex);
  out.reserve(n / 2);
  auto nibble = [](char c) -> int {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
  };
  for (std::size_t i = 0; i + 1 < n; i += 2) {
    const int hi = nibble(hex[i]);
    const int lo = nibble(hex[i + 1]);
    if (hi < 0 || lo < 0) break;
    out.push_back(static_cast<std::uint8_t>((hi << 4) | lo));
  }
  return out;
}

std::string to_hex(const std::vector<std::uint8_t>& v) {
  static const char* digits = "0123456789abcdef";
  std::string s;
  s.reserve(v.size() * 2);
  for (auto b : v) {
    s.push_back(digits[b >> 4]);
    s.push_back(digits[b & 0xf]);
  }
  return s;
}

void test_pfs_session_shared_golden() {
  // Golden from product Python (hashlib + cryptography HKDF match).
  std::vector<std::uint8_t> client_nonce(32);
  std::vector<std::uint8_t> server_nonce(32);
  for (int i = 0; i < 32; ++i) {
    client_nonce[static_cast<std::size_t>(i)] =
        static_cast<std::uint8_t>(i);
    server_nonce[static_cast<std::size_t>(i)] =
        static_cast<std::uint8_t>(i + 32);
  }
  const std::uint8_t session_id[8] = {0xAB, 0xCD, 0xEF, 0x01,
                                      0x02, 0x03, 0x04, 0x05};
  std::vector<std::uint8_t> client_pub(32, 0x11);
  std::vector<std::uint8_t> eph_shared(32, 0x22);

  auto pfs = residual_core::derive_pfs_session_shared(
      client_nonce, server_nonce, session_id, client_pub, eph_shared);
  const auto expect_pfs = hex_to_bytes(
      "8c21d9d3b63e74e54586cbbc4c5a34a9401f81a794146a6158b1d5c6811a406f");
  expect_true(pfs == expect_pfs,
              "derive_pfs_session_shared matches product golden");

  auto legacy = residual_core::derive_legacy_session_shared(
      client_nonce, server_nonce, session_id, client_pub);
  const auto expect_legacy = hex_to_bytes(
      "a76a6b3833151aea32bc4d4ad5863850be20d661b5c2f3732c6841f8d511f31c");
  expect_true(legacy == expect_legacy,
              "derive_legacy_session_shared matches product golden");
  expect_true(pfs != legacy, "PFS IKM differs from legacy nonces-only IKM");

  auto salt = std::span<const std::uint8_t>(client_nonce).subspan(0, 16);
  auto key = residual_core::derive_session_key(pfs, salt);
  const auto expect_key = hex_to_bytes(
      "356e5cfadf0a7e211491b20163a9faeb058b2260fcb858a91623086aa715e4df");
  expect_true(key == expect_key,
              "derive_session_key (HKDF-SHA256) matches product golden");

  // Different eph_shared must change PFS IKM (no constant stub).
  std::vector<std::uint8_t> eph2(32, 0x33);
  auto pfs2 = residual_core::derive_pfs_session_shared(
      client_nonce, server_nonce, session_id, client_pub, eph2);
  expect_true(pfs2.size() == 32 && pfs2 != pfs,
              "different eph_shared yields different PFS IKM");

  expect_true(residual_core::long_term_only_cannot_recover_pfs_key(
                  client_nonce, server_nonce, session_id, client_pub, key),
              "legacy path cannot recover real PFS session key");

  // Short eph rejected
  std::vector<std::uint8_t> short_eph(8, 0x01);
  auto bad = residual_core::derive_pfs_session_shared(
      client_nonce, server_nonce, session_id, client_pub, short_eph);
  expect_true(bad.empty(), "eph_shared < 16 bytes rejected");
}

void test_keepalive_frame() {
  const std::uint8_t session_id[8] = {0xAB, 0xCD, 0xEF, 0x01,
                                      0x02, 0x03, 0x04, 0x05};
  auto frame = residual_core::pack_keepalive(session_id);
  const auto expect = hex_to_bytes("5250543204abcdef0102030405");
  expect_true(frame == expect, "pack_keepalive matches product golden");

  residual_core::MsgType t{};
  expect_true(residual_core::peek_type(frame, &t) &&
                  t == residual_core::MsgType::kKeepalive,
              "peek_type KEEPALIVE");

  std::uint8_t sid[8]{};
  expect_true(residual_core::parse_keepalive(frame, sid) &&
                  std::memcmp(sid, session_id, 8) == 0,
              "parse_keepalive round-trip session_id");

  expect_true(residual_core::pack_keepalive(std::span<const std::uint8_t>(
                                               session_id, 4))
                  .empty(),
              "pack_keepalive rejects bad session_id length");
}

void test_c_abi() {
  std::vector<std::uint8_t> client_nonce(32);
  std::vector<std::uint8_t> server_nonce(32);
  for (int i = 0; i < 32; ++i) {
    client_nonce[static_cast<std::size_t>(i)] =
        static_cast<std::uint8_t>(i);
    server_nonce[static_cast<std::size_t>(i)] =
        static_cast<std::uint8_t>(i + 32);
  }
  const std::uint8_t session_id[8] = {0xAB, 0xCD, 0xEF, 0x01,
                                      0x02, 0x03, 0x04, 0x05};
  std::vector<std::uint8_t> client_pub(32, 0x11);
  std::vector<std::uint8_t> eph_shared(32, 0x22);
  std::uint8_t out[32]{};
  const int rc = rpt_derive_pfs_session_shared(
      client_nonce.data(), client_nonce.size(), server_nonce.data(),
      server_nonce.size(), session_id, 8, client_pub.data(), client_pub.size(),
      eph_shared.data(), eph_shared.size(), out);
  expect_true(rc == 0, "C ABI rpt_derive_pfs_session_shared success");
  const auto expect_pfs = hex_to_bytes(
      "8c21d9d3b63e74e54586cbbc4c5a34a9401f81a794146a6158b1d5c6811a406f");
  expect_true(std::memcmp(out, expect_pfs.data(), 32) == 0,
              "C ABI PFS matches golden");

  std::uint8_t ka[16]{};
  std::size_t ka_len = 0;
  expect_true(rpt_pack_keepalive(session_id, ka, sizeof(ka), &ka_len) == 0 &&
                  ka_len == 13,
              "C ABI pack_keepalive length 13");
  expect_true(std::memcmp(ka, "RPT2", 4) == 0 && ka[4] == RPT_MSG_KEEPALIVE,
              "C ABI keepalive magic+type");
}

}  // namespace

int main() {
  std::printf("residual_core unit tests (product residual primitives)\n");
  test_pfs_session_shared_golden();
  test_keepalive_frame();
  test_c_abi();
  if (g_fails != 0) {
    std::fprintf(stderr, "FAILED: %d assertion(s)\n", g_fails);
    return 1;
  }
  std::printf("ALL_PASS residual_core\n");
  return 0;
}
