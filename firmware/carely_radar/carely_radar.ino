// Carely radar node: ESP32 + HLK-LD2410C (+ optional MC-38 door switch)
// Mount the radar on the ceiling, pointing straight down.
// Sends one JSON reading per second to the Carely server over Wi-Fi.
//
// Wiring (ESP32 DevKit):
//   LD2410C VCC -> 5V, GND -> GND, TX -> GPIO16 (RX2), RX -> GPIO17 (TX2)
//   MC-38 door switch (optional): one wire -> GPIO4, other -> GND
//
// Arduino IDE: board "ESP32 Dev Module", no extra libraries needed.

#include <WiFi.h>
#include <HTTPClient.h>

// ---- change these ----
const char* WIFI_SSID   = "your-wifi";
const char* WIFI_PASS   = "your-password";
const char* SERVER_URL  = "http://192.168.1.10:8000/api/radar";  // computer running Carely
const char* RADAR_TOKEN = "change-me";                            // same as RADAR_TOKEN in .env
const char* DEVICE_ID   = "bathroom";                             // bathroom | living | bedroom
const bool  HAS_DOOR    = false;                                  // true if the MC-38 is wired
// -----------------------

const int RADAR_RX = 16, RADAR_TX = 17, DOOR_PIN = 4;
HardwareSerial radar(2);

struct Target {
  bool present = false;
  uint8_t movingEnergy = 0, stillEnergy = 0;
  uint16_t distanceCm = 0;
  unsigned long at = 0;
} latest;

uint8_t buf[64];
int len = 0;

// LD2410C frame: F4 F3 F2 F1 | len(2) | 02 AA state mdist(2) menergy sdist(2) senergy ddist(2) 55 00 | F8 F7 F6 F5
void parseFrame(const uint8_t* d, int n) {
  if (n < 13 || (d[0] != 0x01 && d[0] != 0x02) || d[1] != 0xAA) return;
  uint8_t state = d[2];
  uint16_t movingCm = d[3] | (d[4] << 8);
  uint16_t stillCm = d[6] | (d[7] << 8);
  bool moving = state == 1 || state == 3;
  latest.present = state != 0;
  latest.movingEnergy = moving ? d[5] : 0;
  latest.stillEnergy = (state == 2 || state == 3) ? d[8] : 0;
  latest.distanceCm = (moving && movingCm) ? movingCm : stillCm;
  latest.at = millis();
}

void readRadar() {
  while (radar.available()) {
    uint8_t b = radar.read();
    // resync on the header
    static const uint8_t HEAD[4] = {0xF4, 0xF3, 0xF2, 0xF1};
    if (len < 4 && b != HEAD[len]) { len = (b == HEAD[0]) ? 1 : 0; if (len) buf[0] = b; continue; }
    buf[len++] = b;
    if (len >= 6) {
      int dataLen = buf[4] | (buf[5] << 8);
      int total = 6 + dataLen + 4;
      if (total > (int)sizeof(buf)) { len = 0; continue; }
      if (len == total) {
        if (buf[total - 4] == 0xF8 && buf[total - 1] == 0xF5) parseFrame(buf + 6, dataLen);
        len = 0;
      }
    }
  }
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
}

void sendReading() {
  connectWifi();
  if (WiFi.status() != WL_CONNECTED) return;
  bool fresh = millis() - latest.at < 2000;  // radar stopped talking -> report no presence
  String json = String("{\"device\":\"") + DEVICE_ID + "\",\"presence\":" + (fresh && latest.present ? "true" : "false");
  if (fresh && latest.present) {
    json += ",\"moving_energy\":" + String(latest.movingEnergy) +
            ",\"still_energy\":" + String(latest.stillEnergy) +
            ",\"distance_cm\":" + String(latest.distanceCm);
  }
  if (HAS_DOOR) json += String(",\"door_open\":") + (digitalRead(DOOR_PIN) == HIGH ? "true" : "false");
  json += "}";

  HTTPClient http;
  http.setTimeout(3000);
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Radar-Token", RADAR_TOKEN);
  int code = http.POST(json);
  Serial.printf("%s -> %d\n", json.c_str(), code);
  http.end();
}

void setup() {
  Serial.begin(115200);
  radar.setRxBufferSize(1024);  // keep frames while an HTTP request is in flight
  radar.begin(256000, SERIAL_8N1, RADAR_RX, RADAR_TX);
  pinMode(DOOR_PIN, INPUT_PULLUP);
  WiFi.mode(WIFI_STA);
  connectWifi();
}

unsigned long lastSend = 0;
void loop() {
  readRadar();
  if (millis() - lastSend >= 1000) {
    lastSend = millis();
    sendReading();
  }
}
