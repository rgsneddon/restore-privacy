#include "residual_core/residual_core.h"

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

}  // extern "C"
