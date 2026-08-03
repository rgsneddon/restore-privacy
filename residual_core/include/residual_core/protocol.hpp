// RPT2 wire protocol constants and pure frame builders (product residual).
// Parity: node/protocol.py
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace residual_core {

// Product residual magic (bare RPT2; no geo gate).
inline constexpr char kMagic[4] = {'R', 'P', 'T', '2'};
inline constexpr std::size_t kHeaderLen = 5;
inline constexpr std::size_t kSessionIdLen = 8;
inline constexpr std::size_t kEphPubLen = 32;

enum class MsgType : std::uint8_t {
  kClientHello = 0x01,
  kServerHello = 0x02,
  kData = 0x03,
  kKeepalive = 0x04,
  kNodeStatus = 0x05,
  kUpdatePush = 0x06,
};

// Build KEEPALIVE: MAGIC || type || session_id (8 bytes).
// Returns empty vector on invalid session_id length.
std::vector<std::uint8_t> pack_keepalive(std::span<const std::uint8_t> session_id);

// Peek message type; returns false if frame too short or magic mismatch.
bool peek_type(std::span<const std::uint8_t> frame, MsgType* out);

// Parse keepalive session_id into out[8]; returns false on bad frame.
bool parse_keepalive(std::span<const std::uint8_t> frame,
                     std::uint8_t out_session_id[kSessionIdLen]);

}  // namespace residual_core
