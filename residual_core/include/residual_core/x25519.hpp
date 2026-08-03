// Ephemeral X25519 for product residual PFS (parity node/pfs.py).
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace residual_core {

inline constexpr std::size_t kX25519KeyLen = 32;

// Compute X25519(shared) = scalar_mult(private, peer_public).
// private and peer_public must be 32 bytes. Returns 32-byte shared or empty.
std::vector<std::uint8_t> x25519_shared_secret(
    std::span<const std::uint8_t> private_key,
    std::span<const std::uint8_t> peer_public);

// Derive public key from 32-byte private scalar (clamp applied by OpenSSL).
// Returns 32-byte public or empty.
std::vector<std::uint8_t> x25519_public_from_private(
    std::span<const std::uint8_t> private_key);

}  // namespace residual_core
