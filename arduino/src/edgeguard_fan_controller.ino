/* ==============================================================================
 * EdgeGuard Fan Actuator & Tachometer Controller
 * Target Board: Arduino UNO / Nano (ATmega328P)
 * Baud Rate: 115200 bps
 *
 * Safety Notice:
 * - 24V DC fan power must NEVER connect directly to Arduino pins.
 * - Pin D9 drives a 5V logic-level MOSFET module (optocoupled recommended).
 * - A 10k external pull-down resistor on D9 keeps the MOSFET OFF during reset.
 * - Pin D2 reads open-collector tachometer pulses via internal pull-up resistor.
 * - Hardware Watchdog cuts off PWM if serial communication halts > 3000 ms.
 * ============================================================================== */

#include <Arduino.h>

// --- Pin Definitions ---
const byte PIN_TACH_IN     = 2;   // External Interrupt INT0 (Fan RPM feedback)
const byte PIN_PLC_ENABLE  = 4;   // Input from Delta PLC Y2 (Active HIGH = Run allowed)
const byte PIN_FAULT_OUT   = 7;   // Output to Delta PLC X5 (Active HIGH = Healthy)
const byte PIN_FAN_PWM     = 9;   // Timer1 PWM Output to MOSFET Gate Driver
const byte PIN_LED_STATUS  = 13;  // Onboard Status LED

// --- Configuration Constants ---
const unsigned long DEFAULT_WATCHDOG_MS = 3000;
const byte PULSES_PER_REV = 2;                  // Standard 2 pulses per revolution
const unsigned long RPM_UPDATE_INTERVAL_MS = 500;

// --- System State Variables ---
volatile unsigned long g_pulseCount = 0;
unsigned long g_lastRpmCalcTime = 0;
unsigned int g_currentRpm = 0;

unsigned long g_lastHeartbeatTime = 0;
unsigned long g_watchdogTimeoutMs = DEFAULT_WATCHDOG_MS;
bool g_watchdogTripped = false;

byte g_targetSpeedPercent = 0;   // 0 ~ 100 %
byte g_currentPwmValue = 0;      // 0 ~ 255
bool g_outputActive = false;

// Serial Buffer
char g_serialBuffer[64];
byte g_serialIndex = 0;
bool g_lineOverflow = false;

// --- Interrupt Service Routine for Tachometer ---
void isrTachometer() {
  g_pulseCount++;
}

// --- Fan Output Control ---
void applyFanOutput(byte speedPercent) {
  // Check hardware PLC interlock first
  bool plcPermit = (digitalRead(PIN_PLC_ENABLE) == HIGH);

  if (!plcPermit || g_watchdogTripped || speedPercent == 0) {
    g_currentPwmValue = 0;
    g_outputActive = false;
    analogWrite(PIN_FAN_PWM, 0);
    digitalWrite(PIN_LED_STATUS, LOW);
  } else {
    if (speedPercent > 100) speedPercent = 100;
    // Map 1-100% to minimum operational PWM (typically 40/255 to overcome motor static friction)
    g_currentPwmValue = map(speedPercent, 1, 100, 45, 255);
    g_outputActive = true;
    analogWrite(PIN_FAN_PWM, g_currentPwmValue);
    digitalWrite(PIN_LED_STATUS, HIGH);
  }
}

// --- RPM Calculation Routine ---
void updateRpmCalculation() {
  unsigned long now = millis();
  unsigned long elapsed = now - g_lastRpmCalcTime;

  if (elapsed >= RPM_UPDATE_INTERVAL_MS) {
    // Atomically read and reset volatile pulse counter
    noInterrupts();
    unsigned long pulses = g_pulseCount;
    g_pulseCount = 0;
    interrupts();

    // Calculate RPM: (pulses / PULSES_PER_REV) * (60000 ms / elapsed ms)
    g_currentRpm = (unsigned int)((pulses * 60000UL) / (PULSES_PER_REV * elapsed));
    g_lastRpmCalcTime = now;
  }
}

// --- Status Reporter ---
void sendStatusResponse(const char* prefix = "STATUS") {
  bool plcPermit = (digitalRead(PIN_PLC_ENABLE) == HIGH);
  Serial.print(prefix);
  Serial.print(F(" STATE="));
  if (g_watchdogTripped) {
    Serial.print(F("FAULT_WATCHDOG"));
  } else if (!plcPermit) {
    Serial.print(F("HOLD_PLC_INTERLOCK"));
  } else if (g_outputActive) {
    Serial.print(F("RUN"));
  } else {
    Serial.print(F("STOP"));
  }

  Serial.print(F(" SPEED="));
  Serial.print(g_targetSpeedPercent);
  Serial.print(F(" PWM="));
  Serial.print(g_currentPwmValue);
  Serial.print(F(" RPM="));
  Serial.print(g_currentRpm);
  Serial.print(F(" PLC_EN="));
  Serial.print(plcPermit ? 1 : 0);
  Serial.print(F(" WD_MS="));
  Serial.println(millis() - g_lastHeartbeatTime);
}

// --- Serial Command Processor ---
void processCommand() {
  // 1. PING (Heartbeat from Dashboard/Gateway)
  if (strcmp(g_serialBuffer, "PING") == 0) {
    g_lastHeartbeatTime = millis();
    if (g_watchdogTripped) {
      // Automatic recovery on verified heartbeat
      g_watchdogTripped = false;
      digitalWrite(PIN_FAULT_OUT, HIGH);
    }
    Serial.println(F("PONG"));
    return;
  }

  // 2. STATUS query
  if (strcmp(g_serialBuffer, "STATUS") == 0 || strcmp(g_serialBuffer, "GET") == 0) {
    sendStatusResponse("OK");
    return;
  }

  // 3. SET <0-100> (Speed Command)
  int speedVal = 0;
  if (sscanf(g_serialBuffer, "SET %d", &speedVal) == 1) {
    g_lastHeartbeatTime = millis();
    if (speedVal < 0) speedVal = 0;
    if (speedVal > 100) speedVal = 100;
    g_targetSpeedPercent = (byte)speedVal;
    applyFanOutput(g_targetSpeedPercent);
    sendStatusResponse("ACK");
    return;
  }

  // 4. STOP (Immediate Stop)
  if (strcmp(g_serialBuffer, "STOP") == 0) {
    g_lastHeartbeatTime = millis();
    g_targetSpeedPercent = 0;
    applyFanOutput(0);
    sendStatusResponse("ACK");
    return;
  }

  // 5. START (Start at default 50% or previous speed)
  if (strcmp(g_serialBuffer, "START") == 0) {
    g_lastHeartbeatTime = millis();
    if (g_targetSpeedPercent == 0) g_targetSpeedPercent = 50;
    applyFanOutput(g_targetSpeedPercent);
    sendStatusResponse("ACK");
    return;
  }

  // 6. SET_WD <ms> (Adjust Watchdog timeout)
  unsigned long timeoutMs = 0;
  if (sscanf(g_serialBuffer, "SET_WD %lu", &timeoutMs) == 1 && timeoutMs >= 500) {
    g_watchdogTimeoutMs = timeoutMs;
    Serial.print(F("ACK WATCHDOG_MS="));
    Serial.println(g_watchdogTimeoutMs);
    return;
  }

  // Unknown command
  Serial.println(F("ERR UNKNOWN_COMMAND"));
}

// --- Arduino Setup ---
void setup() {
  // Configure pins safely before activating outputs
  pinMode(PIN_FAN_PWM, OUTPUT);
  digitalWrite(PIN_FAN_PWM, LOW);

  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, LOW);

  pinMode(PIN_FAULT_OUT, OUTPUT);
  digitalWrite(PIN_FAULT_OUT, HIGH); // High = Healthy

  pinMode(PIN_PLC_ENABLE, INPUT_PULLUP);
  pinMode(PIN_TACH_IN, INPUT_PULLUP);

  // Attach tachometer interrupt on Falling edge
  attachInterrupt(digitalPinToInterrupt(PIN_TACH_IN), isrTachometer, FALLING);

  // Initialize Serial
  Serial.begin(115200);
  g_lastHeartbeatTime = millis();
  g_lastRpmCalcTime = millis();

  Serial.println(F("EDGEGUARD_ARDUINO_CONTROLLER_V1 READY"));
}

// --- Main Loop ---
void loop() {
  unsigned long now = millis();

  // 1. Check Watchdog Timer (if output active or pending)
  if (g_outputActive && (now - g_lastHeartbeatTime > g_watchdogTimeoutMs)) {
    g_watchdogTripped = true;
    digitalWrite(PIN_FAULT_OUT, LOW); // Signal fault to Delta PLC X5
    applyFanOutput(0);
    Serial.println(F("EVENT FAULT_WATCHDOG_TIMEOUT"));
  }

  // 2. Check PLC Hardware Interlock (PIN_PLC_ENABLE)
  bool plcPermit = (digitalRead(PIN_PLC_ENABLE) == HIGH);
  if (!plcPermit && g_outputActive) {
    // Interlock opened by PLC (e.g. E-Stop or AI zone trip)
    applyFanOutput(0);
  }

  // 3. Update RPM calculation
  updateRpmCalculation();

  // 4. Non-blocking Serial Processing (bounded loop to prevent starvation)
  byte maxCharsPerPass = 32;
  while (maxCharsPerPass-- && Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!g_lineOverflow) {
        g_serialBuffer[g_serialIndex] = '\0';
        processCommand();
      } else {
        Serial.println(F("ERR LINE_OVERFLOW"));
      }
      g_serialIndex = 0;
      g_lineOverflow = false;
    } else {
      if (g_serialIndex < sizeof(g_serialBuffer) - 1) {
        g_serialBuffer[g_serialIndex++] = c;
      } else {
        g_lineOverflow = true;
      }
    }
  }
}
