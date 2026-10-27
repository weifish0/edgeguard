#!/usr/bin/env python3
"""
Delta DVP-12SE11R PLC Modbus TCP Verification & Diagnostic Tool.

Allows querying inputs/outputs, reading safety registers, sending simulated
AI trip events, and testing reset commands over Ethernet Modbus TCP.
"""

import sys
import time
import argparse

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("[WARN] pymodbus is not installed. Run 'pip install pymodbus' to connect to physical PLC.")
    ModbusTcpClient = None

# Modbus register addresses for Delta DVP-12SE
REG_MODE = 4096           # D0: Mode (0=MANUAL, 1=AUTO)
REG_SAFETY = 4097         # D1: Safety State (0=SAFE, 1=WARN, 2=TRIPPED)
REG_FAN_SPEED = 4098      # D2: Target Fan Speed (0-100%)
REG_FAN_RPM = 4099        # D3: Actual Fan RPM
REG_HEARTBEAT = 4106      # D10: Heartbeat Counter

COIL_AI_TRIP = 2048       # M0: AI Intrusion Trip Request
COIL_RESET = 2069         # M21: Software Reset Pulse
COIL_REMOTE_START = 2078  # M30: Remote Start
COIL_REMOTE_STOP = 2079   # M31: Remote Stop

DI_AUTO_SWITCH = 1024     # X0: Auto Switch
DI_ESTOP = 1025           # X1: Hardware E-Stop (NC)
DO_FAN_POWER = 1280       # Y0: Fan Power Relay
DO_ALARM_STROBE = 1281    # Y1: Alarm Strobe


def run_diagnostic(host: str, port: int, unit_id: int = 1):
    if ModbusTcpClient is None:
        print("[FAIL] Cannot run without pymodbus. Please install pymodbus.")
        return

    print(f"Connecting to Delta DVP-12SE at {host}:{port}...")
    client = ModbusTcpClient(host=host, port=port)
    if not client.connect():
        print(f"[ERROR] Failed to connect to PLC at {host}:{port}. Is the PLC powered and networked?")
        return

    try:
        print("[OK] Connected to PLC via Modbus TCP!\n")
        print("=" * 60)
        print(" Delta PLC Diagnostic Readout")
        print("=" * 60)

        # 1. Read Holding Registers (D0 ~ D4)
        rr = client.read_holding_registers(address=REG_MODE, count=4, slave=unit_id)
        if not rr.is_error():
            d0, d1, d2, d3 = rr.registers
            mode_str = {0: "MANUAL", 1: "AUTO", 2: "FAULT"}.get(d0, f"UNKNOWN({d0})")
            safety_str = {0: "SAFE", 1: "WARNING", 2: "TRIPPED", 3: "COMM_FAULT"}.get(d1, f"UNKNOWN({d1})")
            print(f"[*] Control Mode (D0)      : {d0} [{mode_str}]")
            print(f"[*] Safety State (D1)      : {d1} [{safety_str}]")
            print(f"[*] Target Fan Speed (D2)  : {d2} %")
            print(f"[*] Actual Fan Speed (D3)  : {d3} RPM")
        else:
            print(f"[ERROR] Failed to read holding registers: {rr}")

        # 2. Read Physical Discrete Inputs (X0 ~ X5)
        r_di = client.read_discrete_inputs(address=DI_AUTO_SWITCH, count=6, slave=unit_id)
        if not r_di.is_error():
            x = r_di.bits
            print(f"[*] Hardware Inputs        : X0(AUTO)={int(x[0])}, X1(ESTOP_NC)={int(x[1])}, "
                  f"X2(RESET)={int(x[2])}, X3(START)={int(x[3])}, X4(STOP)={int(x[4])}, X5(ARDUINO)={int(x[5])}")
        else:
            print(f"[ERROR] Failed to read inputs: {r_di}")

        # 3. Read Coils (Outputs Y0 ~ Y3)
        r_do = client.read_coils(address=DO_FAN_POWER, count=4, slave=unit_id)
        if not r_do.is_error():
            y = r_do.bits
            print(f"[*] Physical Outputs       : Y0(FAN_PWR)={int(y[0])}, Y1(ALARM)={int(y[1])}, "
                  f"Y2(SPEED_GATE)={int(y[2])}, Y3(PLC_ALIVE)={int(y[3])}")
        else:
            print(f"[ERROR] Failed to read outputs: {r_do}")

        print("=" * 60)

    finally:
        client.close()
        print("[INFO] Connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delta PLC Modbus TCP Verification Tool")
    parser.add_argument("--host", type=str, default="192.168.1.5", help="Delta PLC IP Address")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP Port (default: 502)")
    args = parser.parse_args()
    run_diagnostic(args.host, args.port)
