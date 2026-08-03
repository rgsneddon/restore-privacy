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

/* ChaCha20-Poly1305 seal (IETF, 12-byte nonce). out_cap must hold pt_len+16.
 * Returns 0 and sets *out_len on success. */
int rpt_chacha20_poly1305_seal(const uint8_t key32[32], const uint8_t nonce12[12],
                               const uint8_t* plaintext, size_t pt_len,
                               const uint8_t* aad, size_t aad_len, uint8_t* out,
                               size_t out_cap, size_t* out_len);

/* ChaCha20-Poly1305 open. ct_and_tag_len is ciphertext||tag. Returns 0 on success. */
int rpt_chacha20_poly1305_open(const uint8_t key32[32], const uint8_t nonce12[12],
                               const uint8_t* ct_and_tag, size_t ct_and_tag_len,
                               const uint8_t* aad, size_t aad_len, uint8_t* out,
                               size_t out_cap, size_t* out_len);

/* Product lean residual defaults (1 = true). Traffic shape / outer obfs /
 * multihop product defaults are off for low-ping residual. */
void rpt_lean_residual_defaults(int* traffic_shape_off, int* outer_obfs_off,
                                int* multihop_off, int* residual_udp_port);

/* 1 if all three privacy-scale flags are off (lean residual path). */
int rpt_lean_residual_path_active(int traffic_shape, int outer_obfs,
                                  int multihop);

#ifdef __cplusplus
}
#endif

#endif /* RESIDUAL_CORE_RESIDUAL_CORE_H_ */
