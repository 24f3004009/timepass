#include <Arduino.h>
#include "robot_config.h"

#if ROBOT_CAMERA
#include <WiFi.h>
#include <ESPmDNS.h>
#include "camera_server.h"
#endif

#if !defined(CONFIG_IDF_TARGET_ESP32)
#error "This GPIO map and Bluetooth Classic SPP require the original ESP32."
#endif

#if ROBOT_MOTORS
#include <BluetoothSerial.h>
#include <atomic>
#include "drive_control.h"

namespace {
BluetoothSerial bluetooth;
std::atomic<uint32_t> sessionGeneration{0};

void bluetoothEvent(esp_spp_cb_event_t event, esp_spp_cb_param_t *) {
  if (event == ESP_SPP_CLOSE_EVT || event == ESP_SPP_SRV_OPEN_EVT)
    sessionGeneration.fetch_add(1, std::memory_order_relaxed);
}

bool initMotors() {
  bool ok = true;
  for (unsigned motor = 0; motor < 4; ++motor) {
    const int enable = config::motorEnablePins[motor];
    digitalWrite(enable, LOW);
    pinMode(enable, OUTPUT);
    for (unsigned input = 0; input < 2; ++input) {
      const int pin = config::motorPins[motor][input];
      digitalWrite(pin, LOW);
      pinMode(pin, OUTPUT);
    }
    if (ledcSetup(motor, config::motorPwmHz, 8) == 0) ok = false;
    ledcWrite(motor, 0);
    ledcAttachPin(enable, motor);
  }
  return ok;
}

void applyMotors(const robot::Wheels &speeds) {
  static robot::Wheels previous{{0, 0, 0, 0}};
  for (unsigned motor = 0; motor < 4; ++motor) {
    const int speed = speeds[motor] * config::motorPolarity[motor];
    if (speed == previous[motor]) continue;
    // Disable the bridge while changing direction; zero means coast.
    ledcWrite(motor, 0);
    digitalWrite(config::motorPins[motor][0], speed > 0 ? HIGH : LOW);
    digitalWrite(config::motorPins[motor][1], speed < 0 ? HIGH : LOW);
    ledcWrite(motor, abs(speed));
    previous[motor] = speed;
  }
}

void motorTask(void *) {
  robot::DriveControl drive;
  uint32_t generation = sessionGeneration.load(std::memory_order_relaxed);
  for (;;) {
    const uint32_t now = millis();
    const uint32_t current = sessionGeneration.load(std::memory_order_relaxed);
    if (current != generation) {
      drive.disconnect(now);
      applyMotors(drive.outputs());
      // Purge fragments/commands left by a previous Bluetooth session.
      for (int i = 0; i < 512 && bluetooth.available(); ++i) bluetooth.read();
      generation = current;
    }
    const bool connected = bluetooth.hasClient();
    drive.tick(now, connected);
    if (connected) {
      // Bounded work keeps timeout checks responsive even with a noisy sender.
      for (int i = 0; i < 64 && bluetooth.available(); ++i)
        drive.feed(static_cast<char>(bluetooth.read()), now);
      drive.tick(now, bluetooth.hasClient());
    }
    applyMotors(drive.outputs());
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
} // namespace
#endif

#if ROBOT_CAMERA
namespace {
bool ready = false, serversStarted = false, announced = false;
uint32_t lastNetworkAttempt = 0;
}
#endif

void setup() {
  Serial.begin(115200);
#if ROBOT_MOTORS
  if (!initMotors()) {
    Serial.println("Motor PWM initialization failed; reboot after checking hardware.");
    return;
  }
  bluetooth.register_callback(bluetoothEvent);
  bluetooth.setPin(ROBOT_BT_PIN);
  if (!bluetooth.begin(config::bluetoothName)) {
    Serial.println("Bluetooth failed; motors remain stopped.");
    return;
  }
  if (xTaskCreatePinnedToCore(motorTask, "motor-control", 4096, nullptr, 3, nullptr, 1) != pdPASS) {
    Serial.println("Motor task could not start; motors remain stopped.");
    return;
  }
  Serial.printf("Bluetooth SPP: %s\n", config::bluetoothName);
#endif
#if ROBOT_CAMERA
  Serial.printf("Starting %s (AI-Thinker ESP32-CAM / OV2640)\n", config::hostname);
  if (!initCamera()) return;
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(config::hostname);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  WiFi.begin(ROBOT_WIFI_SSID, ROBOT_WIFI_PASSWORD);
  lastNetworkAttempt = millis();
  ready = true;
#endif
}

void loop() {
#if ROBOT_CAMERA
  if (ready) {
    if (WiFi.status() == WL_CONNECTED) {
      if (!serversStarted && millis() - lastNetworkAttempt >= 2000) {
        lastNetworkAttempt = millis();
        serversStarted = startCameraServers();
        if (!serversStarted) Serial.println("HTTP start failed; retrying.");
      }
      if (serversStarted && !announced) {
        MDNS.end();
        if (MDNS.begin(config::hostname)) MDNS.addService("http", "tcp", 80);
        Serial.printf("Camera: http://%s:81/stream (http://%s.local:81/stream)\n",
                      WiFi.localIP().toString().c_str(), config::hostname);
        Serial.printf("Free heap: %u bytes\n", static_cast<unsigned>(ESP.getFreeHeap()));
        announced = true;
      }
    } else {
      announced = false;
      if (millis() - lastNetworkAttempt >= 10000) {
        lastNetworkAttempt = millis();
        Serial.println("Waiting for 2.4 GHz Wi-Fi; reconnecting.");
        WiFi.reconnect(); // No blocking wait in the motor task.
      }
    }
  }
#endif
  delay(5);
}
