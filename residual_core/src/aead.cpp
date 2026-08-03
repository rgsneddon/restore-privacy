#include "residual_core/aead.hpp"

#include <openssl/evp.h>

#include <vector>

namespace residual_core {

std::vector<std::uint8_t> chacha20_poly1305_seal(
    std::span<const std::uint8_t> key32,
    std::span<const std::uint8_t> nonce12,
    std::span<const std::uint8_t> plaintext,
    std::span<const std::uint8_t> aad) {
  if (key32.size() != kAeadKeyLen || nonce12.size() != kAeadNonceLen) {
    return {};
  }
  EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
  if (!ctx) return {};
  std::vector<std::uint8_t> out;
  do {
    if (EVP_EncryptInit_ex(ctx, EVP_chacha20_poly1305(), nullptr, nullptr,
                           nullptr) != 1) {
      break;
    }
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_IVLEN,
                            static_cast<int>(nonce12.size()), nullptr) != 1) {
      break;
    }
    if (EVP_EncryptInit_ex(ctx, nullptr, nullptr, key32.data(),
                           nonce12.data()) != 1) {
      break;
    }
    int len = 0;
    if (!aad.empty()) {
      if (EVP_EncryptUpdate(ctx, nullptr, &len, aad.data(),
                            static_cast<int>(aad.size())) != 1) {
        break;
      }
    }
    out.resize(plaintext.size() + kAeadTagLen);
    int outl = 0;
    if (!plaintext.empty()) {
      if (EVP_EncryptUpdate(ctx, out.data(), &outl, plaintext.data(),
                            static_cast<int>(plaintext.size())) != 1) {
        out.clear();
        break;
      }
    }
    int fin = 0;
    if (EVP_EncryptFinal_ex(ctx, out.data() + outl, &fin) != 1) {
      out.clear();
      break;
    }
    outl += fin;
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_GET_TAG,
                            static_cast<int>(kAeadTagLen),
                            out.data() + outl) != 1) {
      out.clear();
      break;
    }
    out.resize(static_cast<std::size_t>(outl) + kAeadTagLen);
  } while (false);
  EVP_CIPHER_CTX_free(ctx);
  return out;
}

std::vector<std::uint8_t> chacha20_poly1305_open(
    std::span<const std::uint8_t> key32,
    std::span<const std::uint8_t> nonce12,
    std::span<const std::uint8_t> ciphertext_and_tag,
    std::span<const std::uint8_t> aad) {
  if (key32.size() != kAeadKeyLen || nonce12.size() != kAeadNonceLen ||
      ciphertext_and_tag.size() < kAeadTagLen) {
    return {};
  }
  const std::size_t ct_len = ciphertext_and_tag.size() - kAeadTagLen;
  EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
  if (!ctx) return {};
  std::vector<std::uint8_t> out;
  do {
    if (EVP_DecryptInit_ex(ctx, EVP_chacha20_poly1305(), nullptr, nullptr,
                           nullptr) != 1) {
      break;
    }
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_IVLEN,
                            static_cast<int>(nonce12.size()), nullptr) != 1) {
      break;
    }
    if (EVP_DecryptInit_ex(ctx, nullptr, nullptr, key32.data(),
                           nonce12.data()) != 1) {
      break;
    }
    int len = 0;
    if (!aad.empty()) {
      if (EVP_DecryptUpdate(ctx, nullptr, &len, aad.data(),
                            static_cast<int>(aad.size())) != 1) {
        break;
      }
    }
    out.resize(ct_len);
    int outl = 0;
    if (ct_len > 0) {
      if (EVP_DecryptUpdate(ctx, out.data(), &outl, ciphertext_and_tag.data(),
                            static_cast<int>(ct_len)) != 1) {
        out.clear();
        break;
      }
    }
    if (EVP_CIPHER_CTX_ctrl(
            ctx, EVP_CTRL_AEAD_SET_TAG, static_cast<int>(kAeadTagLen),
            const_cast<std::uint8_t*>(ciphertext_and_tag.data() + ct_len)) !=
        1) {
      out.clear();
      break;
    }
    int fin = 0;
    if (EVP_DecryptFinal_ex(ctx, out.data() + outl, &fin) != 1) {
      out.clear();
      break;
    }
    out.resize(static_cast<std::size_t>(outl + fin));
  } while (false);
  EVP_CIPHER_CTX_free(ctx);
  return out;
}

}  // namespace residual_core
