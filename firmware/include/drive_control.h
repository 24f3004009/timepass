#pragma once

#include <array>
#include <cerrno>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace robot {
using Wheels = std::array<int, 4>; // Front left, front right, rear left, rear right.

class DriveControl {
 public:
  static constexpr uint32_t timeoutMs = 600;
  static constexpr uint32_t reversalMs = 75;

  const Wheels &outputs() const { return output_; }

  void stop(uint32_t now) {
    target_.fill(0);
    armed_ = false;
    for (unsigned i = 0; i < output_.size(); ++i) {
      if (output_[i] != 0) stoppedAt_[i] = now;
      output_[i] = 0;
    }
  }

  void disconnect(uint32_t now) {
    stop(now);
    length_ = 0;
    dropping_ = false;
  }

  void feed(char byte, uint32_t now) {
    expire(now);
    if (byte == '\n') {
      if (!dropping_) {
        line_[length_] = '\0';
        if (!parse(now)) stop(now);
      }
      length_ = 0;
      dropping_ = false;
      return;
    }
    if (dropping_) return;
    if (length_ == sizeof(line_) - 1 || byte == '\0' ||
        (static_cast<unsigned char>(byte) < 32 && byte != '\r' && byte != '\t')) {
      stop(now);
      length_ = 0;
      dropping_ = true;
      return;
    }
    if (length_ == 0) lineStarted_ = now;
    line_[length_++] = byte;
  }

  void tick(uint32_t now, bool connected) {
    if (!connected) {
      disconnect(now);
      return;
    }
    expire(now);
    for (unsigned i = 0; i < output_.size(); ++i) {
      const int wanted = target_[i];
      const int direction = sign(wanted);
      if (wanted == 0 || (output_[i] != 0 && sign(output_[i]) != direction)) {
        if (output_[i] != 0) stoppedAt_[i] = now;
        output_[i] = 0;
      } else if (output_[i] == 0 && lastDirection_[i] != 0 &&
                 direction != lastDirection_[i] &&
                 static_cast<uint32_t>(now - stoppedAt_[i]) < reversalMs) {
        // Keep the bridge disabled while the previous direction settles.
      } else {
        output_[i] = wanted;
        lastDirection_[i] = direction;
      }
    }
  }

 private:
  Wheels target_{{0, 0, 0, 0}}, output_{{0, 0, 0, 0}}, lastDirection_{{0, 0, 0, 0}};
  std::array<uint32_t, 4> stoppedAt_{{0, 0, 0, 0}};
  uint32_t lastCommand_ = 0, lineStarted_ = 0;
  bool armed_ = false, dropping_ = false;
  char line_[64]{};
  unsigned length_ = 0;

  static int sign(int value) { return (value > 0) - (value < 0); }
  static const char *skipSpace(const char *p) {
    while (*p && std::isspace(static_cast<unsigned char>(*p))) ++p;
    return p;
  }

  void expire(uint32_t now) {
    const bool commandExpired = armed_ && static_cast<uint32_t>(now - lastCommand_) >= timeoutMs;
    const bool lineExpired = length_ != 0 && static_cast<uint32_t>(now - lineStarted_) >= timeoutMs;
    if (commandExpired || lineExpired) {
      stop(now);
      if (length_ != 0) dropping_ = true;
      length_ = 0;
    }
  }

  bool parse(uint32_t now) {
    const char *p = skipSpace(line_);
    if (std::strncmp(p, "STOP", 4) == 0 && *skipSpace(p + 4) == '\0') {
      stop(now);
      return true;
    }
    if (*p != 'M' || !std::isspace(static_cast<unsigned char>(p[1]))) return false;
    ++p;
    Wheels values{};
    for (auto &value : values) {
      p = skipSpace(p);
      char *end = nullptr;
      errno = 0;
      const long parsed = std::strtol(p, &end, 10);
      if (p == end || errno == ERANGE || parsed < -255 || parsed > 255 ||
          (*end && !std::isspace(static_cast<unsigned char>(*end)))) return false;
      value = static_cast<int>(parsed);
      p = end;
    }
    if (*skipSpace(p) != '\0') return false;
    target_ = values;
    lastCommand_ = now;
    armed_ = true;
    return true;
  }
};
} // namespace robot
