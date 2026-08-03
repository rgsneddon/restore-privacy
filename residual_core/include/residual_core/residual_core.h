/* C ABI surface for residual_core (future Flutter FFI).
 * C++ implementation: residual_core::derive_pfs_session_shared, pack_keepalive.
 */
#ifndef RESIDUAL_CORE_RESIDUAL_CORE_H_
#define RESIDUAL_CORE_RESIDUAL_CORE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Magic "RPT2" */
extern const uint8_t rpt_magic[4];

/* Msg type KEEPALIVE = 0x04 */
enum { RPT_MSG_KEEPALIVE = 0x04 };

/* Out must be 32 bytes. Returns 0 on success, -1 on error. */
int rpt_derive_pfs_session_shared(
    const uint8_t* client_nonce, size_t client_nonce_len,
    const uint8_t* server_nonce, size_t server_nonce_len,
    const uint8_t* session_id, size_t session_id_len,
    const uint8_t* client_pub, size_t client_pub_len,
    const uint8_t* eph_shared, size_t eph_shared_len,
    uint8_t out32[32]);

/* Out must be 32 bytes. Returns 0 on success, -1 on error. */
int rpt_derive_session_key(
    const uint8_t* shared_secret, size_t shared_secret_len,
    const uint8_t* salt, size_t salt_len,
    const uint8_t* info, size_t info_len,
    uint8_t out32[32]);

/* Writes MAGIC||0x04||session_id into out; out_cap must be >= 13.
 * Sets *out_len. Returns 0 on success. */
int rpt_pack_keepalive(const uint8_t session_id[8], uint8_t* out, size_t out_cap,
                       size_t* out_len);

#ifdef __cplusplus
}
#endif

#endif /* RESIDUAL_CORE_RESIDUAL_CORE_H_ */
