// ChaCha20-Poly1305 AEAD — product residual session crypto
// (parity node/crypto_session.py ChaCha20Poly1305, 12-byte nonce).
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace residual_core {

inline constexpr std::size_t kAeadKeyLen = 32;
inline constexpr std::size_t kAeadNonceLen = 12;
inline constexpr std::size_t kAeadTagLen = 16;

// Encrypt: returns ciphertext||tag (OpenSSL layout: ciphertext then 16-byte tag).
// Empty on error.
std::vector<std::uint8_t> chacha20_poly1305_seal(
    std::span<const std::uint8_t> key32,
    std::span<const std::uint8_t> nonce12,
    std::span<const std::uint8_t> plaintext,
    std::span<const std::uint8_t> aad = {});

// Decrypt ciphertext||tag. Empty on auth failure / bad lengths.
std::vector<std::uint8_t> chacha20_poly1305_open(
    std::span<const std::uint8_t> key32,
    std::span<const std::uint8_t> nonce12,
    std::span<const std::uint8_t> ciphertext_and_tag,
    std::span<const std::uint8_t> aad = {});

}  // namespace residual_core
