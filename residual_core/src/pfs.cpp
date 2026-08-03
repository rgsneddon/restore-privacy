#include "residual_core/pfs.hpp"

#include "sha256.hpp"

#include <cstring>
#include <vector>

namespace residual_core {

namespace {

std::vector<std::uint8_t> concat_all(
    std::initializer_list<std::span<const std::uint8_t>> parts) {
  std::size_t n = 0;
  for (auto p : parts) n += p.size();
  std::vector<std::uint8_t> out;
  out.reserve(n);
  for (auto p : parts) {
    out.insert(out.end(), p.begin(), p.end());
  }
  return out;
}

}  // namespace

std::vector<std::uint8_t> derive_pfs_session_shared(
    std::span<const std::uint8_t> client_nonce,
    std::span<const std::uint8_t> server_nonce,
    std::span<const std::uint8_t> session_id,
    std::span<const std::uint8_t> client_pub,
    std::span<const std::uint8_t> eph_shared) {
  if (eph_shared.size() < 16) {
    return {};
  }
  const auto* label =
      reinterpret_cast<const std::uint8_t*>(kPfsLabel);
  const std::size_t label_len = sizeof(kPfsLabel) - 1;
  auto buf = concat_all({client_nonce, server_nonce, session_id, client_pub,
                         std::span<const std::uint8_t>(label, label_len),
                         eph_shared});
  return detail::sha256(buf.data(), buf.size());
}

std::vector<std::uint8_t> derive_legacy_session_shared(
    std::span<const std::uint8_t> client_nonce,
    std::span<const std::uint8_t> server_nonce,
    std::span<const std::uint8_t> session_id,
    std::span<const std::uint8_t> client_pub) {
  auto buf = concat_all({client_nonce, server_nonce, session_id, client_pub});
  return detail::sha256(buf.data(), buf.size());
}

std::vector<std::uint8_t> derive_session_key(
    std::span<const std::uint8_t> shared_secret,
    std::span<const std::uint8_t> salt,
    std::span<const std::uint8_t> info) {
  if (shared_secret.empty()) return {};
  const auto* info_ptr = info.data();
  std::size_t info_len = info.size();
  if (info_len == 0) {
    info_ptr = reinterpret_cast<const std::uint8_t*>(kSessionInfo);
    info_len = sizeof(kSessionInfo) - 1;
  }
  return detail::hkdf_sha256(shared_secret.data(), shared_secret.size(),
                             salt.data(), salt.size(), info_ptr, info_len,
                             kHkdfKeyLen);
}

bool long_term_only_cannot_recover_pfs_key(
    std::span<const std::uint8_t> client_nonce,
    std::span<const std::uint8_t> server_nonce,
    std::span<const std::uint8_t> session_id,
    std::span<const std::uint8_t> client_pub,
    std::span<const std::uint8_t> real_session_key) {
  if (real_session_key.size() != kHkdfKeyLen || client_nonce.size() < 16) {
    return false;
  }
  auto legacy = derive_legacy_session_shared(client_nonce, server_nonce,
                                             session_id, client_pub);
  if (legacy.size() != kSha256Len) return false;
  auto salt = client_nonce.subspan(0, 16);
  auto guess = derive_session_key(legacy, salt);
  if (guess.size() != kHkdfKeyLen) return false;
  return std::memcmp(guess.data(), real_session_key.data(), kHkdfKeyLen) != 0;
}

}  // namespace residual_core
