#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "camera_server.h"
#include "robot_config.h"

namespace {
httpd_handle_t infoServer = nullptr, streamServer = nullptr;

esp_err_t home(httpd_req_t *request) {
  httpd_resp_set_type(request, "text/html");
  return httpd_resp_sendstr(request,
      "<!doctype html><meta name='viewport' content='width=device-width'>"
      "<title>Robot camera</title><h1>Robot camera</h1>"
      "<p>One viewer per camera. Close this page before using the PC app.</p>"
      "<img id='feed' alt='Live camera' style='max-width:100%'>"
      "<script>document.getElementById('feed').src='http://'+location.hostname+':81/stream'</script>");
}

esp_err_t health(httpd_req_t *request) {
  char body[160];
  snprintf(body, sizeof(body),
           "{\"name\":\"%s\",\"motor_controller\":%s,\"free_heap\":%u,\"rssi\":%d}",
           config::hostname, "false",
           static_cast<unsigned>(ESP.getFreeHeap()), WiFi.RSSI());
  httpd_resp_set_type(request, "application/json");
  return httpd_resp_sendstr(request, body);
}

esp_err_t stream(httpd_req_t *request) {
  httpd_resp_set_type(request, "multipart/x-mixed-replace;boundary=robotframe");
  httpd_resp_set_hdr(request, "Cache-Control", "no-store");
  while (WiFi.status() == WL_CONNECTED) {
    camera_fb_t *frame = esp_camera_fb_get();
    if (!frame) return ESP_FAIL;
    char header[100];
    const int length = snprintf(header, sizeof(header),
        "\r\n--robotframe\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
        static_cast<unsigned>(frame->len));
    esp_err_t result = httpd_resp_send_chunk(request, header, length);
    if (result == ESP_OK)
      result = httpd_resp_send_chunk(request, reinterpret_cast<const char *>(frame->buf), frame->len);
    esp_camera_fb_return(frame); // Also return buffers on socket errors.
    if (result != ESP_OK) return result;
    // Cap at roughly 10 fps; Wi-Fi and Bluetooth share a 2.4 GHz radio.
    vTaskDelay(pdMS_TO_TICKS(100));
  }
  return ESP_FAIL;
}

bool addRoute(httpd_handle_t server, const char *uri, esp_err_t (*handler)(httpd_req_t *)) {
  httpd_uri_t route{};
  route.uri = uri;
  route.method = HTTP_GET;
  route.handler = handler;
  return httpd_register_uri_handler(server, &route) == ESP_OK;
}

void stopServers() {
  if (streamServer) httpd_stop(streamServer);
  if (infoServer) httpd_stop(infoServer);
  streamServer = infoServer = nullptr;
}
} // namespace

bool initCamera() {
  camera_config_t camera{};
  camera.ledc_channel = LEDC_CHANNEL_0;
  camera.ledc_timer = LEDC_TIMER_0;
  camera.pin_d0 = config::cameraData[0];
  camera.pin_d1 = config::cameraData[1];
  camera.pin_d2 = config::cameraData[2];
  camera.pin_d3 = config::cameraData[3];
  camera.pin_d4 = config::cameraData[4];
  camera.pin_d5 = config::cameraData[5];
  camera.pin_d6 = config::cameraData[6];
  camera.pin_d7 = config::cameraData[7];
  camera.pin_xclk = config::cameraXclk;
  camera.pin_pclk = config::cameraPclk;
  camera.pin_vsync = config::cameraVsync;
  camera.pin_href = config::cameraHref;
  camera.pin_sccb_sda = config::cameraSda;
  camera.pin_sccb_scl = config::cameraScl;
  camera.pin_pwdn = config::cameraPwdn;
  camera.pin_reset = config::cameraReset;
  camera.xclk_freq_hz = 20000000;
  camera.pixel_format = PIXFORMAT_JPEG;
  camera.frame_size = FRAMESIZE_QVGA; // 320x240 for modest bandwidth and latency.
  camera.jpeg_quality = 18;
  camera.fb_count = 1;
  camera.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  camera.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  const esp_err_t result = esp_camera_init(&camera);
  if (result != ESP_OK) Serial.printf("Camera init failed: 0x%x; check model/ribbon/power.\n", result);
  return result == ESP_OK;
}

bool startCameraServers() {
  if (infoServer && streamServer) return true;
  httpd_config_t server = HTTPD_DEFAULT_CONFIG();
  server.server_port = 80;
  server.max_uri_handlers = 2;
  server.max_open_sockets = 2;
  server.recv_wait_timeout = 2;
  server.send_wait_timeout = 2;
  if (httpd_start(&infoServer, &server) != ESP_OK) return false;
  if (!addRoute(infoServer, "/", home) || !addRoute(infoServer, "/health", health)) {
    stopServers();
    return false;
  }
  server.server_port = 81;
  server.ctrl_port += 1; // Each HTTP server needs a different control socket.
  server.max_uri_handlers = 1;
  if (httpd_start(&streamServer, &server) != ESP_OK ||
      !addRoute(streamServer, "/stream", stream)) {
    stopServers();
    return false;
  }
  return true;
}
