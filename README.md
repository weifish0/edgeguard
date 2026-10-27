# EdgeGuard — Industrial Safety Interlock & IoT SCADA Dashboard

> **EdgeGuard: Offline AI Safety Copilot for Legacy Industrial Equipment**  
> An edge-native industrial safety interlock, high-frequency telemetry dashboard, and physical control bridge designed for retrofit on existing industrial machinery.  
> Target Platform: **ASUS UGen AI League** (Battlefield Lightning Track / Stage I & Stage II).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Delta PLC](https://img.shields.io/badge/PLC-Delta%20DVP--12SE11R-red.svg)](plc/)
[![MCU: Arduino](https://img.shields.io/badge/MCU-Arduino%20UNO%20(ATmega328P)-00979D.svg)](arduino/)
[![Dashboard: Python SSE](https://img.shields.io/badge/Dashboard-Python%20%2F%20HTML5%20SCADA-emerald.svg)](dashboard/)

---

## 1. System Architecture & Philosophy

The guiding thesis of EdgeGuard is:
> **"Understand the scene. Act through existing PLCs. Never bypass physical safety interlocks."**

In industrial environments, remote cloud software or AI models must **never** possess arbitrary, unconstrained authority to directly actuate factory equipment. EdgeGuard establishes a tiered architecture:
1. **Perception Layer**: Edge vision detects hazardous situations (e.g., personnel entering restricted machine zones).
2. **Decision Gateway**: Predefined safety rules formulate constrained control requests.
3. **Hardware Interlock Layer (Delta PLC)**: Physical logic accepts or rejects AI requests based on physical mode switches (`AUTO` vs `MANUAL`), fail-safe emergency circuits, and watchdog timers.
4. **Actuator & Telemetry Layer (Arduino UNO & Fan)**: Microcontroller executes PWM speed regulation, hardware watchdog monitoring, and reads real-time tachometer RPM pulses.
5. **Supervisory Layer (SCADA Dashboard)**: Pushes 10 Hz real-time telemetry, visualizes PLC I/O rack states, and records an immutable safety audit trail.

```mermaid
flowchart TD
    subgraph UI_Layer ["Supervisory & Telemetry Layer (SCADA Web Dashboard)"]
        Dashboard["EdgeGuard Web SCADA\n(HTML5 / Canvas Gauge / Chart.js)"]
        SSE_Stream["Real-time Telemetry Stream\n(Server-Sent Events @ 10 Hz)"]
        Rest_API["Operator Command Interface\n(REST /api/control)"]
    end

    subgraph Gateway_Layer ["Edge Gateway & Perception Layer"]
        Gateway["Python Gateway Core\n(Telemetry, Physics Engine, Watchdog)"]
        AI_Vision["Local Vision Model / Electronic Fence\n(Person & Danger Zone Detection)"]
    end

    subgraph Controller_Layer ["Industrial Control & Physical Interlock Layer (PLC)"]
        PLC["Delta Electronics DVP-12SE11R PLC\n(Modbus TCP Server : 502)"]
        Mode_SW["Physical Mode Switch X0\n(1=AUTO / 0=MANUAL)"]
        E_Stop["Physical E-Stop Button X1\n(Normally Closed NC Circuit)"]
        Reset_PB["Physical Reset Pushbutton X2"]
    end

    subgraph Actuator_Layer ["Actuator & Sensor Feedback Layer (Arduino & Fan)"]
        Arduino["Arduino UNO (ATmega328P)\n(115200 bps Serial / D9 PWM)"]
        MOSFET["LR7843 MOSFET Driver\n(Optocoupled + 10kΩ Gate Pull-Down)"]
        Fan["24V DC Industrial Fan Load\n(Isolated 24V Switch Mode PSU)"]
        Tach["Fan Tachometer Feedback\n(Pin D2 / INT0: 2 Pulses/Rev)"]
    end

    %% Communication Links
    Dashboard <--> SSE_Stream & Rest_API
    SSE_Stream & Rest_API <--> Gateway
    AI_Vision -.->|Trip Request M0| Gateway

    Gateway <-->|Modbus TCP / Ethernet (Port 502)| PLC
    Gateway <-->|USB CDC Serial (115200 baud)| Arduino

    Mode_SW -->|DI X0| PLC
    E_Stop -->|DI X1| PLC
    Reset_PB -->|DI X2| PLC

    PLC -->|DO Y0 Main Contactor Relay| MOSFET
    PLC -->|DO Y2 Speed Gate Signal| Arduino
    PLC -->|DO Y1 Alarm Strobe / Buzzer| Alarms[Physical Alarm Horn / Strobe]
    Arduino -->|D7 Heartbeat / Health Signal| PLC

    Arduino -->|Pin D9 5V PWM| MOSFET
    MOSFET -->|24V PWM Power Drive| Fan
    Fan -->|Frequency Feedback| Tach
    Tach -->|Hardware Interrupt INT0| Arduino
```

---

## 2. Repository Layout

```text
edgeguard/
├── README.md                      # Complete system documentation, wiring guide & verification procedures
├── run_dashboard.py               # Standalone runner for SCADA dashboard (Simulated & Live modes)
├── .gitignore                     # Git filter rules for Python, Arduino, and Delta PLC binaries
│
├── plc/                           # Delta Electronics DVP-12SE11R PLC assets
│   ├── README.md                  # Ladder logic design rules & ISPSoft / WPLSoft upload guide
│   ├── edgeguard_dvp12se_ladder.il# Standard Instruction List (Mnemonic representation)
│   ├── edgeguard_dvp12se_ladder.txt# ASCII visualized ladder logic diagram with annotations
│   ├── modbus_mapping.md          # Full Modbus TCP register map (D registers, M coils, X/Y I/O)
│   ├── modbus_mapping.json        # Machine-readable Modbus schema for software gateways
│   └── test_plc_modbus.py         # Python Modbus TCP diagnostic & verification tool
│
├── arduino/                       # Arduino UNO fan actuator & tachometer firmware
│   ├── src/
│   │   └── edgeguard_fan_controller.ino # C++ firmware (PWM drive, tachometer ISR, 3s watchdog)
│   ├── wiring_guide.md            # Electrical schematics, MOSFET isolation & pull-down safety
│   └── test_serial.py             # Serial protocol CLI test utility & RPM monitor
│
└── dashboard/                     # Industrial SCADA Web Telemetry Center
    ├── server.py                  # Python HTTP & SSE server (Built-in motor physics model)
    ├── requirements.txt           # Optional drivers for physical hardware (pymodbus, pyserial)
    └── static/
        └── index.html             # High-performance SCADA Single Page App (Tailwind + Canvas + Chart.js)
```

---

## 3. Delta PLC System Specification & Modbus Map

### 3.1 Physical I/O Allocation (Delta DVP-12SE11R)

The Delta DVP-12SE11R is an Ethernet-enabled industrial slim PLC providing 8 digital inputs and 4 relay outputs:

| Terminal | Type | Tag Name | Function Description | Normal State |
|---|---|---|---|---|
| **X0** | DI | `SW_MODE` | Operation mode selector (1 = AUTO mode, 0 = MANUAL mode) | Selector Switch |
| **X1** | DI | `E_STOP_PB` | Emergency Stop button (**Normally Closed NC**: 1 = Healthy, 0 = Tripped/Broken) | Normally Closed (1) |
| **X2** | DI | `RESET_PB` | Physical safety latch acknowledgment pushbutton (NO) | Normally Open (0) |
| **X3** | DI | `START_PB` | Workstation local start pushbutton | Normally Open (0) |
| **X4** | DI | `STOP_PB` | Workstation local stop pushbutton | Normally Closed (1) |
| **X5** | DI | `ARDUINO_OK`| Arduino MCU health & watchdog feedback signal | Optocoupled (1) |
| **Y0** | DO | `FAN_POWER` | 24V Fan main power contactor relay | Active High (Run) |
| **Y1** | DO | `ALARM_LAMP`| Physical strobe beacon & alarm buzzer | Active High (Tripped) |
| **Y2** | DO | `SPEED_GATE`| Hardware speed permit signal forwarded to Arduino | Active High (Permit) |
| **Y3** | DO | `HEARTBEAT` | PLC running indicator (Driven by Delta M1013 1.0 Hz clock pulse) | Flashing (1 Hz) |

### 3.2 Modbus TCP Memory Mapping

- **Default IP Address**: `192.168.1.5`
- **Port**: `502`
- **Modbus Unit ID**: `1`
- **Offset Standard**: Holding Registers start at `4096` (`0x1000`), Coils start at `2048` (`0x0800`).

| Modbus Address | Delta Register | Type | Access | Description | Range / Unit |
|---|---|---|---|---|---|
| **4096** (`0x1000`) | `D0` | INT16 | R/W | Control Mode Status | `0`: MANUAL, `1`: AUTO, `2`: FAULT |
| **4097** (`0x1001`) | `D1` | INT16 | R | System Safety State | `0`: SAFE, `1`: WARNING, `2`: TRIPPED, `3`: COMM_FAULT |
| **4098** (`0x1002`) | `D2` | INT16 | R/W | Fan Target Speed Setpoint | `0` ~ `100` (%) |
| **4099** (`0x1003`) | `D3` | INT16 | R | Fan Actual Measured Speed | `0` ~ `3000` (RPM) |
| **4106** (`0x100A`) | `D10` | UINT16 | R/W | Edge Gateway Watchdog Heartbeat | Increments every 1.0 s |
| **2048** (`0x0800`) | `M0` | Coil | R/W | AI Restricted Zone Trip Request | `1`: Request Emergency Trip |
| **2058** (`0x080A`) | `M10` | Coil | R | AUTO Mode Active Status Flag | Hardware reflected from X0 |
| **2059** (`0x080B`) | `M11` | Coil | R | MANUAL Mode Active Status Flag | Reflected when X0 is OFF |
| **2068** (`0x0814`) | `M20` | Coil | R | Safety Trip Latched Alarm | Latch requires manual reset |
| **2069** (`0x0815`) | `M21` | Coil | R/W | Remote Software Reset Pulse | Pulse `1` to unlatch fault |
| **2078** (`0x081E`) | `M30` | Coil | R/W | Remote Start Command | Starts load in AUTO mode |
| **2079** (`0x081F`) | `M31` | Coil | R/W | Remote Stop Command | Stops load safely |
| **2148** (`0x0864`) | `M100`| Coil | R | Communication Watchdog Timeout Alarm | Set if D10 freezes > 3.0 s |

---

## 4. Arduino UNO Firmware & Fan Actuator Subsystem

### 4.1 Electrical Safety & Protection Rules

> [!CAUTION]
> **Never connect 24V DC directly to any Arduino pin.** All Arduino GPIO pins operate strictly at **5V TTL logic**. Exceeding 5V will permanently damage the microcontroller.

1. **Gate Pull-Down Resistor**:
   - During power-on or bootloader reset, Arduino pin D9 defaults to a high-impedance input state.
   - **An external 10kΩ pull-down resistor between D9 and GND is mandatory** to prevent floating gate voltages from unintentionally triggering the MOSFET.
2. **Optocoupled Isolation**:
   - An optocoupled MOSFET module (e.g., LR7843 / PC817) completely isolates the 5V logic ground from the noisy 24V motor inductive switching transients.
3. **Tachometer Pull-Up**:
   - The fan tachometer line (yellow wire) is open-collector. It connects to Arduino Pin D2 (INT0) with an internal `INPUT_PULLUP` enabled, capturing 2 pulses per revolution.

### 4.2 Serial Command Protocol (115200 baud, 8N1)

| Command | Function | Response Format |
|---|---|---|
| `PING` | Watchdog heartbeat renewal | `PONG` |
| `SET <0-100>` | Adjust fan speed percentage | `ACK STATE=RUN SPEED=50 PWM=128 RPM=1420 ...` |
| `STOP` | Immediate zero-PWM shutdown | `ACK STATE=STOP SPEED=0 PWM=0 ...` |
| `STATUS` / `GET` | Query state, PWM, and measured RPM | `OK STATE=RUN SPEED=50 PWM=128 RPM=1420 ...` |
| `SET_WD <ms>` | Configure communication watchdog timeout | `ACK WATCHDOG_MS=3000` |

---

## 5. SCADA Telemetry Dashboard Quickstart

The EdgeGuard SCADA Dashboard is engineered to run **out-of-the-box using the Python standard library**, requiring zero external dependencies for demonstration!

### Step 1: Launch the Dashboard Server (Demo Simulation Mode)

```bash
# Navigate to repository directory
cd edgeguard

# Launch the unified dashboard server
python3 run_dashboard.py
```

Console Output:
```text
=================================================================
 EdgeGuard Industrial IoT SCADA & Telemetry Dashboard
=================================================================
[*] Mode           : SIMULATION (No hardware required)
[*] Web Dashboard  : http://localhost:8080 (or http://127.0.0.1:8080)
[*] Delta PLC Host : 192.168.1.5:502 (Modbus TCP)
[*] Arduino Serial : Simulated / Auto
[*] Press Ctrl+C to terminate.
=================================================================
```

### Step 2: Open Dashboard in Browser

Open Google Chrome or Microsoft Edge:  
👉 **`http://localhost:8080`**

- **Live Tachometer Gauge**: High-fidelity circular canvas needle displaying 0–2800 RPM.
- **Real-Time Telemetry Trend**: Chart.js graph plotting Fan RPM vs Speed Setpoint % at 10 Hz via Server-Sent Events.
- **Interactive Control Desk**: Speed presets (0%, 25%, 50%, 75%, 100%), START/STOP controls, and AUTO/MANUAL toggle.
- **PLC I/O Rack Inspector**: Live indicator bits for Discrete Inputs (X0–X5), Relay Outputs (Y0–Y3), and Holding Registers (D0, D1, D2, D3, D10).
- **PoC AI Simulation Panel**: Trigger simulated zone intrusions to verify safety interlocks without needing an external camera.

### Step 3: Connect Physical Hardware (Live Deployment Mode)

When physical Delta PLC and Arduino hardware are connected:

```bash
# Install optional hardware communication drivers
pip install -r dashboard/requirements.txt

# Run in live mode with PLC IP and Arduino serial port
python3 run_dashboard.py --live --plc-ip 192.168.1.5 --serial-port /dev/ttyACM0
```

---

## 6. Safety Verification & Fail-Safe Test Procedures

The EdgeGuard system demonstrates four non-negotiable industrial safety behaviors:

| Test Case | Operator Action | Expected Interlock Behavior | Verification Value |
|---|---|---|---|
| **1. Restricted Zone Intrusion Trip** | Click **"Simulate Zone Ingress"** on the dashboard (or camera detects person in restricted zone). | 1. Gateway writes PLC coil `M0 = 1`.<br>2. PLC Ladder sets latch coil `M20 = 1`.<br>3. `Y0` opens (cutting fan power), `Y1` activates alarm strobe.<br>4. Fan RPM drops smoothly to 0 via inertia. | Verifies that AI perception events reliably actuate physical machinery trip sequences. |
| **2. Mandatory Operator Reset (Anti-Auto-Restart)** | Click **"Personnel Clear Zone"**. | 1. Zone status reverts to `CLEAR`.<br>2. **Equipment remains strictly locked in STOP** (`D1 = 2 TRIPPED`).<br>3. Operator must explicitly click **RESET** to acknowledge clearance before restarting. | Adheres to ISO 13849 / OSHA machine guarding standards: clearing a hazard zone must **never** cause equipment to self-restart. |
| **3. MANUAL Mode Rejects AI Override** | Switch mode to **`MANUAL`** (`X0 = 0`), then click **"Simulate Zone Ingress"**. | 1. PLC Network 3 interlock isolates `M0`.<br>2. AI trip request is rejected by hardware logic.<br>3. Dashboard flags an operator warning, but machine control is retained by manual operators. | Proves that human operators retain ultimate authority; AI cannot override manual maintenance mode. |
| **4. Communication Watchdog Timeout** | Terminate the dashboard process or disconnect Ethernet for > 3.0 seconds. | 1. PLC Timer `T0` reaches preset 3000 ms.<br>2. PLC trips `M100` comm fault, tripping `M20` and de-energizing `Y0`.<br>3. Arduino watchdog also shuts down PWM. | Guarantees fail-safe shutdown if the edge host hangs or cables disconnect. |

---

## 7. Competition Roadmap & Stage II Integration

- **Stage I (Preliminary PoC)**:
  - Verified physical control chain: Local AI Perception ➔ Modbus TCP Gateway ➔ Delta DVP-12SE11R PLC Interlock ➔ Arduino PWM Actuation ➔ Tachometer RPM Feedback ➔ SCADA Web Telemetry.
- **Stage II (Finals Deployment on ASUS UGen300)**:
  - Deploy lightweight vision detectors and contextual Vision-Language Models (VLM) directly onto the **ASUS UGen300 (Hailo-10H NPU, 40 TOPS INT4, 8GB dedicated memory)**.
  - Benchmark inference latency, frames-per-second, and complete 100% offline, zero-cloud operations for safety-critical factory deployments.

---

## 8. License

This project is licensed under the [MIT License](LICENSE).
