// Unit tests for residual_core — call shipped functions with golden vectors
// aligned to node/pfs.py + node/crypto_session.py + node/protocol.py.
#include "residual_core/aead.hpp"
#include "residual_core/lean_residual.hpp"
#include "residual_core/pfs.hpp"
#include "residual_core/protocol.hpp"
#include "residual_core/residual_core.h"
#include "residual_core/x25519.hpp"

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

void test_x25519_rfc7748() {
  // RFC 7748 §6.1
  const auto alice_sk = hex_to_bytes(
      "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a");
  const auto bob_pk = hex_to_bytes(
      "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f");
  const auto expect_shared = hex_to_bytes(
      "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742");
  auto shared = residual_core::x25519_shared_secret(alice_sk, bob_pk);
  expect_true(shared == expect_shared,
              "X25519 shared secret matches RFC 7748 golden");

  const auto alice_pk_expect = hex_to_bytes(
      "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a");
  auto alice_pk = residual_core::x25519_public_from_private(alice_sk);
  expect_true(alice_pk == alice_pk_expect,
              "X25519 public-from-private matches RFC 7748");

  // Pipe into product PFS IKM (non-trivial: shared is real DH output).
  std::vector<std::uint8_t> client_nonce(32, 0x01);
  std::vector<std::uint8_t> server_nonce(32, 0x02);
  const std::uint8_t session_id[8] = {9, 8, 7, 6, 5, 4, 3, 2};
  std::vector<std::uint8_t> client_pub(32, 0x11);
  auto pfs = residual_core::derive_pfs_session_shared(
      client_nonce, server_nonce, session_id, client_pub, shared);
  expect_true(pfs.size() == 32, "PFS IKM from real X25519 shared is 32 bytes");
  auto key = residual_core::derive_session_key(
      pfs, std::span<const std::uint8_t>(client_nonce).subspan(0, 16));
  expect_true(key.size() == 32, "session key from X25519+PFS is 32 bytes");
}

void test_chacha20_poly1305_roundtrip() {
  std::vector<std::uint8_t> key(32);
  for (int i = 0; i < 32; ++i) key[static_cast<std::size_t>(i)] =
      static_cast<std::uint8_t>(i);
  std::vector<std::uint8_t> nonce(12);
  for (int i = 0; i < 12; ++i) nonce[static_cast<std::size_t>(i)] =
      static_cast<std::uint8_t>(i);
  // Product-style AAD prefix used on SERVER_HELLO path.
  std::vector<std::uint8_t> aad = {'R', 'P', 'T', '2', '-', 'S', 'E', 'R',
                                   'V', 'E', 'R', '-', 'H', 'E', 'L', 'L',
                                   'O', 1,   2,   3,   4,   5,   6,   7,  8};
  const std::vector<std::uint8_t> pt = {'h', 'e', 'l', 'l', 'o', ' ',
                                        'r', 'e', 's', 'i', 'd', 'u', 'a', 'l'};
  auto sealed = residual_core::chacha20_poly1305_seal(key, nonce, pt, aad);
  expect_true(sealed.size() == pt.size() + 16,
              "ChaCha20-Poly1305 seal length = pt + tag");
  auto opened = residual_core::chacha20_poly1305_open(key, nonce, sealed, aad);
  expect_true(opened == pt, "ChaCha20-Poly1305 open round-trips plaintext");

  // Tamper tag → open fails
  auto bad = sealed;
  bad.back() ^= 0xff;
  auto fail = residual_core::chacha20_poly1305_open(key, nonce, bad, aad);
  expect_true(fail.empty(), "ChaCha20-Poly1305 rejects tampered tag");

  // Wrong AAD fails
  auto wrong_aad = aad;
  wrong_aad[0] ^= 1;
  auto fail2 =
      residual_core::chacha20_poly1305_open(key, nonce, sealed, wrong_aad);
  expect_true(fail2.empty(), "ChaCha20-Poly1305 rejects wrong AAD");
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

  // C ABI seal/open drives real residual AEAD entry points
  std::uint8_t key[32]{};
  for (int i = 0; i < 32; ++i) key[static_cast<std::size_t>(i)] =
      static_cast<std::uint8_t>(i);
  std::uint8_t nonce[12]{};
  for (int i = 0; i < 12; ++i) nonce[static_cast<std::size_t>(i)] =
      static_cast<std::uint8_t>(i);
  const char* pt = "lean residual packet";
  const std::size_t pt_len = std::strlen(pt);
  std::uint8_t sealed[64]{};
  std::size_t sealed_len = 0;
  expect_true(rpt_chacha20_poly1305_seal(key, nonce,
                                         reinterpret_cast<const uint8_t*>(pt),
                                         pt_len, nullptr, 0, sealed,
                                         sizeof(sealed), &sealed_len) == 0 &&
                  sealed_len == pt_len + 16,
              "C ABI seal length pt+tag");
  std::uint8_t opened[64]{};
  std::size_t opened_len = 0;
  expect_true(rpt_chacha20_poly1305_open(key, nonce, sealed, sealed_len,
                                         nullptr, 0, opened, sizeof(opened),
                                         &opened_len) == 0 &&
                  opened_len == pt_len &&
                  std::memcmp(opened, pt, pt_len) == 0,
              "C ABI open round-trips plaintext");
}

void test_lean_residual_defaults() {
  using residual_core::kLeanResidualDefaults;
  using residual_core::kResidualUdpPort;
  using residual_core::lean_residual_path_active;

  expect_true(!kLeanResidualDefaults.traffic_shape,
              "lean default traffic_shape off");
  expect_true(!kLeanResidualDefaults.outer_obfuscation,
              "lean default outer_obfuscation off");
  expect_true(!kLeanResidualDefaults.multihop, "lean default multihop off");
  expect_true(kLeanResidualDefaults.require_pfs, "lean still requires PFS");
  expect_true(kLeanResidualDefaults.require_session_aead,
              "lean still requires session AEAD");
  expect_true(lean_residual_path_active(),
              "default LeanResidualDefaults is lean path");
  expect_true(!lean_residual_path_active(true, false, false),
              "shape on leaves lean path");
  expect_true(!lean_residual_path_active(false, true, false),
              "obfs on leaves lean path");
  expect_true(!lean_residual_path_active(false, false, true),
              "multihop on leaves lean path");
  expect_true(kResidualUdpPort == 44044, "residual UDP port 44044");

  int shape_off = 0, obfs_off = 0, mh_off = 0, port = 0;
  rpt_lean_residual_defaults(&shape_off, &obfs_off, &mh_off, &port);
  expect_true(shape_off == 1 && obfs_off == 1 && mh_off == 1 && port == 44044,
              "C ABI lean defaults all off + port 44044");
  expect_true(rpt_lean_residual_path_active(0, 0, 0) == 1,
              "C ABI lean path active when all off");
  expect_true(rpt_lean_residual_path_active(1, 0, 0) == 0,
              "C ABI lean path inactive when shape on");
  expect_true(std::strstr(residual_core::kNoDartDataplaneRule, "Dart") !=
                  nullptr,
              "no-Dart-dataplane rule string present");
}

}  // namespace

int main() {
  std::printf("residual_core unit tests (product residual primitives)\n");
  test_pfs_session_shared_golden();
  test_keepalive_frame();
  test_x25519_rfc7748();
  test_chacha20_poly1305_roundtrip();
  test_c_abi();
  test_lean_residual_defaults();
  if (g_fails != 0) {
    std::fprintf(stderr, "FAILED: %d assertion(s)\n", g_fails);
    return 1;
  }
  std::printf("ALL_PASS residual_core\n");
  return 0;
}
