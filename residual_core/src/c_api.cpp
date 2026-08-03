#include "residual_core/residual_core.h"

#include "residual_core/aead.hpp"
#include "residual_core/lean_residual.hpp"
#include "residual_core/pfs.hpp"
#include "residual_core/protocol.hpp"

#include <cstring>

extern "C" {

const uint8_t rpt_magic[4] = {'R', 'P', 'T', '2'};

int rpt_derive_pfs_session_shared(
    const uint8_t* client_nonce, size_t client_nonce_len,
    const uint8_t* server_nonce, size_t server_nonce_len,
    const uint8_t* session_id, size_t session_id_len,
    const uint8_t* client_pub, size_t client_pub_len,
    const uint8_t* eph_shared, size_t eph_shared_len, uint8_t out32[32]) {
  if (!client_nonce || !server_nonce || !session_id || !client_pub ||
      !eph_shared || !out32) {
    return -1;
  }
  auto v = residual_core::derive_pfs_session_shared(
      {client_nonce, client_nonce_len}, {server_nonce, server_nonce_len},
      {session_id, session_id_len}, {client_pub, client_pub_len},
      {eph_shared, eph_shared_len});
  if (v.size() != 32) return -1;
  std::memcpy(out32, v.data(), 32);
  return 0;
}

int rpt_derive_session_key(const uint8_t* shared_secret,
                           size_t shared_secret_len, const uint8_t* salt,
                           size_t salt_len, const uint8_t* info, size_t info_len,
                           uint8_t out32[32]) {
  if (!shared_secret || !out32) return -1;
  std::span<const uint8_t> info_span;
  if (info && info_len) {
    info_span = {info, info_len};
  } else {
    info_span = {reinterpret_cast<const uint8_t*>(residual_core::kSessionInfo),
                 sizeof(residual_core::kSessionInfo) - 1};
  }
  auto v = residual_core::derive_session_key(
      {shared_secret, shared_secret_len},
      {salt ? salt : reinterpret_cast<const uint8_t*>(""), salt_len},
      info_span);
  if (v.size() != 32) return -1;
  std::memcpy(out32, v.data(), 32);
  return 0;
}

int rpt_pack_keepalive(const uint8_t session_id[8], uint8_t* out, size_t out_cap,
                       size_t* out_len) {
  if (!session_id || !out || !out_len) return -1;
  auto v = residual_core::pack_keepalive({session_id, 8});
  if (v.empty() || v.size() > out_cap) return -1;
  std::memcpy(out, v.data(), v.size());
  *out_len = v.size();
  return 0;
}

int rpt_chacha20_poly1305_seal(const uint8_t key32[32], const uint8_t nonce12[12],
                               const uint8_t* plaintext, size_t pt_len,
                               const uint8_t* aad, size_t aad_len, uint8_t* out,
                               size_t out_cap, size_t* out_len) {
  if (!key32 || !nonce12 || !out || !out_len) return -1;
  if (pt_len && !plaintext) return -1;
  auto v = residual_core::chacha20_poly1305_seal(
      {key32, residual_core::kAeadKeyLen},
      {nonce12, residual_core::kAeadNonceLen},
      {plaintext ? plaintext : reinterpret_cast<const uint8_t*>(""), pt_len},
      {aad ? aad : reinterpret_cast<const uint8_t*>(""), aad_len});
  if (v.empty() || v.size() > out_cap) return -1;
  std::memcpy(out, v.data(), v.size());
  *out_len = v.size();
  return 0;
}

int rpt_chacha20_poly1305_open(const uint8_t key32[32], const uint8_t nonce12[12],
                               const uint8_t* ct_and_tag, size_t ct_and_tag_len,
                               const uint8_t* aad, size_t aad_len, uint8_t* out,
                               size_t out_cap, size_t* out_len) {
  if (!key32 || !nonce12 || !ct_and_tag || !out || !out_len) return -1;
  auto v = residual_core::chacha20_poly1305_open(
      {key32, residual_core::kAeadKeyLen},
      {nonce12, residual_core::kAeadNonceLen}, {ct_and_tag, ct_and_tag_len},
      {aad ? aad : reinterpret_cast<const uint8_t*>(""), aad_len});
  if (v.empty() || v.size() > out_cap) return -1;
  std::memcpy(out, v.data(), v.size());
  *out_len = v.size();
  return 0;
}

void rpt_lean_residual_defaults(int* traffic_shape_off, int* outer_obfs_off,
                                int* multihop_off, int* residual_udp_port) {
  const auto& d = residual_core::kLeanResidualDefaults;
  if (traffic_shape_off) *traffic_shape_off = d.traffic_shape ? 0 : 1;
  if (outer_obfs_off) *outer_obfs_off = d.outer_obfuscation ? 0 : 1;
  if (multihop_off) *multihop_off = d.multihop ? 0 : 1;
  if (residual_udp_port) *residual_udp_port = residual_core::kResidualUdpPort;
}

int rpt_lean_residual_path_active(int traffic_shape, int outer_obfs,
                                  int multihop) {
  return residual_core::lean_residual_path_active(traffic_shape != 0,
                                                  outer_obfs != 0,
                                                  multihop != 0)
             ? 1
             : 0;
}

}  // extern "C"
