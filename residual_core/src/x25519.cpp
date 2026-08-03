#include "residual_core/x25519.hpp"

#include <openssl/evp.h>

#include <vector>

namespace residual_core {

std::vector<std::uint8_t> x25519_shared_secret(
    std::span<const std::uint8_t> private_key,
    std::span<const std::uint8_t> peer_public) {
  if (private_key.size() != kX25519KeyLen ||
      peer_public.size() != kX25519KeyLen) {
    return {};
  }
  EVP_PKEY* priv = EVP_PKEY_new_raw_private_key(
      EVP_PKEY_X25519, nullptr, private_key.data(), private_key.size());
  if (!priv) return {};
  EVP_PKEY* peer = EVP_PKEY_new_raw_public_key(
      EVP_PKEY_X25519, nullptr, peer_public.data(), peer_public.size());
  if (!peer) {
    EVP_PKEY_free(priv);
    return {};
  }
  EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new(priv, nullptr);
  std::vector<std::uint8_t> out;
  if (ctx && EVP_PKEY_derive_init(ctx) == 1 &&
      EVP_PKEY_derive_set_peer(ctx, peer) == 1) {
    std::size_t len = 0;
    if (EVP_PKEY_derive(ctx, nullptr, &len) == 1 && len == kX25519KeyLen) {
      out.resize(len);
      if (EVP_PKEY_derive(ctx, out.data(), &len) != 1) {
        out.clear();
      }
    }
  }
  EVP_PKEY_CTX_free(ctx);
  EVP_PKEY_free(peer);
  EVP_PKEY_free(priv);
  return out;
}

std::vector<std::uint8_t> x25519_public_from_private(
    std::span<const std::uint8_t> private_key) {
  if (private_key.size() != kX25519KeyLen) return {};
  EVP_PKEY* priv = EVP_PKEY_new_raw_private_key(
      EVP_PKEY_X25519, nullptr, private_key.data(), private_key.size());
  if (!priv) return {};
  std::size_t len = kX25519KeyLen;
  std::vector<std::uint8_t> out(len);
  if (EVP_PKEY_get_raw_public_key(priv, out.data(), &len) != 1 ||
      len != kX25519KeyLen) {
    out.clear();
  }
  EVP_PKEY_free(priv);
  return out;
}

}  // namespace residual_core
