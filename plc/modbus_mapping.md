# Delta DVP-12SE11R PLC - Modbus TCP & I/O Mapping Specification

## 1. Controller Overview
- **Model**: Delta DVP-12SE11R (Slim Type Ethernet PLC)
- **Power**: 24V DC (-15% ~ +20%)
- **Inputs**: 8 Digital Inputs (X0 ~ X7, 24VDC Sink/Source)
- **Outputs**: 4 Relay Outputs (Y0 ~ Y3, 250VAC/24VDC, 2A per point)
- **Ethernet Port**: 10/100 Mbps RJ45
- **Default IP Address**: `192.168.1.5` (Port: 502)
- **Modbus Protocol**: Modbus TCP (Slave / Server ID: 1)

---

## 2. Physical I/O Allocation

| Point | Type | Signal Name | Description | Normal State |
|---|---|---|---|---|
| **X0** | DI | `SW_MODE` | AUTO / MANUAL Mode Switch (1=AUTO, 0=MANUAL) | Toggle Switch |
| **X1** | DI | `E_STOP_PB` | Emergency Stop Button (NC Contact: 1=OK, 0=Pressed) | Normally Closed (1) |
| **X2** | DI | `RESET_PB` | Physical Fault Reset Pushbutton (NO Contact) | Normally Open (0) |
| **X3** | DI | `START_PB` | Workstation Local Start Pushbutton (NO Contact) | Normally Open (0) |
| **X4** | DI | `STOP_PB` | Workstation Local Stop Pushbutton (NC Contact) | Normally Closed (1) |
| **X5** | DI | `ARDUINO_OK` | Arduino Controller Watchdog / Health Output | High (1) |
| **Y0** | DO | `FAN_POWER_RELAY` | 24V Fan Main Power Contactor Relay | Active High |
| **Y1** | DO | `ALARM_STROBE` | Safety Alarm / Strobe Beacon / Buzzer | Active High (Tripped) |
| **Y2** | DO | `SPEED_GATE` | Speed Enable Signal to Arduino Fan Controller | Active High |
| **Y3** | DO | `HEARTBEAT_LED` | PLC Alive / Running Heartbeat Blinker (1 Hz) | Flashing |

---

## 3. Modbus TCP Register Map

Delta DVP series utilizes standard Modbus addressing offsets:
- **Discrete Coils (M)**: Offset `0x0800` (Decimal 2048) -> M0 = Address 2048
- **Discrete Inputs (X)**: Offset `0x0400` (Decimal 1024) -> X0 = Address 1024
- **Discrete Outputs (Y)**: Offset `0x0500` (Decimal 1280) -> Y0 = Address 1280
- **Holding Registers (D)**: Offset `0x1000` (Decimal 4096) -> D0 = Address 4096

### 3.1 Holding Registers (Function Code 03 / 06 / 16)

| Modbus Addr | Delta Reg | Data Type | Access | Description | Range / Unit |
|---|---|---|---|---|---|
| **4096** (`0x1000`) | `D0` | INT16 | R/W | Control Mode Status | 0: MANUAL, 1: AUTO, 2: FAULT |
| **4097** (`0x1001`) | `D1` | INT16 | R | Safety System State | 0: SAFE, 1: WARNING, 2: TRIPPED, 3: COMM_FAULT |
| **4098** (`0x1002`) | `D2` | INT16 | R/W | Fan Target Speed Setpoint | 0 ~ 100 (%) |
| **4099** (`0x1003`) | `D3` | INT16 | R | Fan Actual Speed Feedback | 0 ~ 3000 (RPM) |
| **4106** (`0x100A`) | `D10` | UINT16 | R/W | AI Gateway Watchdog Heartbeat Counter | Increments every 1s |
| **4107** (`0x100B`) | `D11` | UINT16 | R | PLC Internal Previous Heartbeat Record | Used for delta check |
| **4116** (`0x1014`) | `D20` | INT16 | R | Energy Saving Idle Timer Remaining | Seconds |
| **4146** (`0x1032`) | `D50` | UINT16 | R | System Fault Code Bitmask | Bit0: E-Stop, Bit1: AI Trip, Bit2: Comm Timeout |

### 3.2 Discrete Coils (Function Code 01 / 05 / 15)

| Modbus Addr | Delta Coil | Access | Description | Trigger Condition |
|---|---|---|---|---|
| **2048** (`0x0800`) | `M0` | R/W | AI Restricted Zone Trip Request | Written High (1) by AI model on intrusion |
| **2049** (`0x0801`) | `M1` | R/W | AI Standby / Idle Energy Saving Request | High when area clear for > 10s |
| **2050** (`0x0802`) | `M2` | R/W | AI Fan Speed Override Permit | 1 = Allow AI dynamic speed regulation |
| **2058** (`0x080A`) | `M10` | R | AUTO Mode Active Status Flag | Reflected from X0 and interlocks |
| **2059** (`0x080B`) | `M11` | R | MANUAL Mode Active Status Flag | High when X0 is OFF |
| **2068** (`0x0814`) | `M20` | R | Safety Trip Latched Status | Latched until manual reset |
| **2069** (`0x0815`) | `M21` | R/W | Remote Software Reset Pulse | Pulse 1 to acknowledge and unlatch |
| **2078** (`0x081E`) | `M30` | R/W | Remote Start Command | Starts fan in AUTO mode |
| **2079** (`0x081F`) | `M31` | R/W | Remote Stop Command | Stops fan safely |
| **2148** (`0x0864`) | `M100` | R | Comm Watchdog Timeout Alarm Coil | High if D10 freezes for > 3.0s |
