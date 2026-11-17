#pragma once

#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

#if !defined(ROBOT_CAMERA) || !defined(ROBOT_MOTORS)
#error "Select the front, rear or motors PlatformIO environment."
#endif

namespace config {
constexpr const char *bluetoothName = "SurveillanceRobot";

#if ROBOT_CAMERA
constexpr const char *hostname = ROBOT_FRONT ? "robot-front" : "robot-rear";
// Standard AI-Thinker ESP32-CAM with OV2640 and PSRAM.
// These signals are already wired on the camera board.
constexpr int cameraData[] = {5, 18, 19, 21, 36, 39, 34, 35}; // Y2..Y9
constexpr int cameraXclk = 0, cameraPclk = 22, cameraVsync = 25;
constexpr int cameraHref = 23, cameraSda = 26, cameraScl = 27;
constexpr int cameraPwdn = 32, cameraReset = -1;
#endif

#if ROBOT_MOTORS
// NodeMCU ESP32S / classic ESP32-WROOM. No camera on this board.
// Wheel order: front left, front right, rear left, rear right.
constexpr int motorPins[4][2] = {{16, 17}, {18, 19}, {21, 22}, {23, 32}};
constexpr int motorEnablePins[4] = {25, 26, 27, 33};
constexpr int motorPolarity[4] = {1, 1, 1, 1}; // Change to -1 for reversed wiring.
constexpr int motorPwmHz = 15000;

constexpr bool distinctMotorPins() {
  const int pins[] = {motorPins[0][0], motorPins[0][1], motorPins[1][0], motorPins[1][1],
                     motorPins[2][0], motorPins[2][1], motorPins[3][0], motorPins[3][1],
                     motorEnablePins[0], motorEnablePins[1], motorEnablePins[2], motorEnablePins[3]};
  for (unsigned i = 0; i < sizeof(pins) / sizeof(pins[0]); ++i)
    for (unsigned j = i + 1; j < sizeof(pins) / sizeof(pins[0]); ++j)
      if (pins[i] == pins[j]) return false;
  return true;
}
static_assert(distinctMotorPins(), "Motor GPIO assignments must be unique");
#endif
} // namespace config
