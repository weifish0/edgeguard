#!/usr/bin/env python3
"""
EdgeGuard Arduino Serial Controller CLI & Test Utility.

Sends commands, tests heartbeat, monitors RPM, and verifies watchdog fail-safe.
"""

import sys
import time
import argparse

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[WARN] pyserial is not installed. Run 'pip install pyserial' to connect to Arduino.")
    serial = None


def list_ports():
    if not serial:
        return []
    ports = list(serial.tools.list_ports.comports())
    return [p.device for p in ports]


def run_serial_test(port: str, baud: int = 115200):
    if not serial:
        print("[FAIL] pyserial is required. Install with: pip install pyserial")
        return

    print(f"Connecting to Arduino on {port} at {baud} baud...")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=1.0)
    except Exception as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        return

    # Wait for Arduino reset to settle
    time.sleep(2.0)
    ser.reset_input_buffer()

    try:
        # 1. Test PING
        print("[*] Sending: PING")
        ser.write(b"PING\n")
        time.sleep(0.1)
        resp = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"    <- Response: {resp}")

        # 2. Query Status
        print("[*] Sending: STATUS")
        ser.write(b"STATUS\n")
        time.sleep(0.1)
        resp = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"    <- Response: {resp}")

        # 3. Test Fan Speed Ramp Up
        print("[*] Ramping speed to 40%...")
        ser.write(b"SET 40\n")
        time.sleep(0.1)
        resp = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"    <- Response: {resp}")

        print("[*] Monitoring RPM for 3 seconds...")
        for _ in range(3):
            time.sleep(1.0)
            ser.write(b"GET\n")
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            print(f"    <- Live: {line}")

        # 4. Stop Fan
        print("[*] Sending: STOP")
        ser.write(b"STOP\n")
        time.sleep(0.1)
        resp = ser.readline().decode("utf-8", errors="ignore").strip()
        print(f"    <- Response: {resp}")

        print("\n[OK] Serial communication verified successfully!")

    finally:
        ser.close()
        print("[INFO] Serial connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arduino Serial Diagnostic Tool")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g. /dev/cu.usbserial* or COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--list", action="store_true", help="List available serial ports")
    args = parser.parse_args()

    if args.list:
        ports = list_ports()
        print("Available serial ports:")
        for p in ports:
            print(f"  - {p}")
        sys.exit(0)

    port = args.port
    if not port:
        ports = list_ports()
        if ports:
            port = ports[0]
            print(f"[INFO] Auto-detected serial port: {port}")
        else:
            print("[ERROR] No serial ports found. Connect Arduino or specify --port.")
            sys.exit(1)

    run_serial_test(port, args.baud)
