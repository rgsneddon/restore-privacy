#include "residual_core/protocol.hpp"

#include <cstring>

namespace residual_core {

std::vector<std::uint8_t> pack_keepalive(
    std::span<const std::uint8_t> session_id) {
  if (session_id.size() != kSessionIdLen) {
    return {};
  }
  std::vector<std::uint8_t> out;
  out.reserve(kHeaderLen + kSessionIdLen);
  out.push_back(static_cast<std::uint8_t>(kMagic[0]));
  out.push_back(static_cast<std::uint8_t>(kMagic[1]));
  out.push_back(static_cast<std::uint8_t>(kMagic[2]));
  out.push_back(static_cast<std::uint8_t>(kMagic[3]));
  out.push_back(static_cast<std::uint8_t>(MsgType::kKeepalive));
  out.insert(out.end(), session_id.begin(), session_id.end());
  return out;
}

bool peek_type(std::span<const std::uint8_t> frame, MsgType* out) {
  if (out == nullptr || frame.size() < kHeaderLen) return false;
  if (frame[0] != static_cast<std::uint8_t>(kMagic[0]) ||
      frame[1] != static_cast<std::uint8_t>(kMagic[1]) ||
      frame[2] != static_cast<std::uint8_t>(kMagic[2]) ||
      frame[3] != static_cast<std::uint8_t>(kMagic[3])) {
    return false;
  }
  *out = static_cast<MsgType>(frame[4]);
  return true;
}

bool parse_keepalive(std::span<const std::uint8_t> frame,
                     std::uint8_t out_session_id[kSessionIdLen]) {
  if (out_session_id == nullptr || frame.size() < kHeaderLen + kSessionIdLen) {
    return false;
  }
  MsgType t{};
  if (!peek_type(frame, &t) || t != MsgType::kKeepalive) return false;
  std::memcpy(out_session_id, frame.data() + kHeaderLen, kSessionIdLen);
  return true;
}

}  // namespace residual_core
