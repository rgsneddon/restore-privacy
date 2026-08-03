// Perfect-forward-secrecy session IKM + AEAD key derivation (product residual).
// Parity: node/pfs.py + node/crypto_session.py derive_session_key (HKDF-SHA256).
//
// Long-term ElGamal/Ed25519 remain for admission only. Session traffic keys use
// ephemeral X25519 shared material mixed into the handshake transcript.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace residual_core {

inline constexpr char kPfsLabel[] = "|pfs-x25519|";
inline constexpr char kSessionInfo[] = "rpt-v2-session";
inline constexpr std::size_t kSha256Len = 32;
inline constexpr std::size_t kHkdfKeyLen = 32;

// derive_pfs_session_shared (node/pfs.py):
//   SHA256(client_nonce || server_nonce || session_id || client_pub ||
//          "|pfs-x25519|" || eph_shared)
// Returns 32-byte digest; empty on length error (eph_shared < 16).
std::vector<std::uint8_t> derive_pfs_session_shared(
    std::span<const std::uint8_t> client_nonce,
    std::span<const std::uint8_t> server_nonce,
    std::span<const std::uint8_t> session_id,
    std::span<const std::uint8_t> client_pub,
    std::span<const std::uint8_t> eph_shared);

// Pre-PFS derivation (nonces only) — analysis / attacker-visible material.
std::vector<std::uint8_t> derive_legacy_session_shared(
    std::span<const std::uint8_t> client_nonce,
    std::span<const std::uint8_t> server_nonce,
    std::span<const std::uint8_t> session_id,
    std::span<const std::uint8_t> client_pub);

// HKDF-SHA256 extract+expand → 32-byte session AEAD key.
// salt = client_nonce[:16]; default info = "rpt-v2-session" when info empty.
std::vector<std::uint8_t> derive_session_key(
    std::span<const std::uint8_t> shared_secret,
    std::span<const std::uint8_t> salt,
    std::span<const std::uint8_t> info = {});

// True when legacy (non-PFS) key derivation cannot recover the real PFS key.
bool long_term_only_cannot_recover_pfs_key(
    std::span<const std::uint8_t> client_nonce,
    std::span<const std::uint8_t> server_nonce,
    std::span<const std::uint8_t> session_id,
    std::span<const std::uint8_t> client_pub,
    std::span<const std::uint8_t> real_session_key);

}  // namespace residual_core
