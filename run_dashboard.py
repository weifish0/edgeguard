#!/usr/bin/env python3
"""
EdgeGuard IoT Dashboard & Gateway Launcher.

Usage:
  # 1. Simulation Demo Mode (Out-of-the-box, zero setup needed):
  python3 run_dashboard.py

  # 2. Live Hardware Mode (Connects to Delta PLC & Arduino):
  python3 run_dashboard.py --live --plc-ip 192.168.1.5 --serial-port /dev/ttyACM0
"""

import os
import sys

# Ensure dashboard package directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
sys.path.insert(0, DASHBOARD_DIR)

from server import run_server
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EdgeGuard SCADA Dashboard Launcher")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP Server bind host")
    parser.add_argument("--port", type=int, default=8080, help="HTTP Server port (default: 8080)")
    parser.add_argument("--live", action="store_true", help="Connect to physical PLC and Arduino")
    parser.add_argument("--plc-ip", default="192.168.1.5", help="Delta PLC IP Address")
    parser.add_argument("--serial-port", default=None, help="Arduino serial port device")
    args = parser.parse_args()

    sim_mode = not args.live
    run_server(
        host=args.host,
        port=args.port,
        sim_mode=sim_mode,
        plc_ip=args.plc_ip,
        serial_port=args.serial_port
    )
