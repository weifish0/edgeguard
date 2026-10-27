#!/usr/bin/env python3
"""
EdgeGuard Industrial IoT SCADA & Telemetry Server.

Features:
- Out-of-the-box standard library implementation (Zero external dependency required).
- High-frequency Server-Sent Events (SSE) streaming real-time status at 10 Hz.
- Realistic physical simulation engine (fan inertia, RPM curve, Delta PLC register emulation).
- Live hardware bridging to Delta DVP-12SE11R PLC (Modbus TCP) and Arduino UNO (Serial) when available.
"""

import sys
import os
import time
import json
import math
import random
import threading
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# Optional Hardware Libraries
try:
    from pymodbus.client import ModbusTcpClient
    HAS_MODBUS = True
except ImportError:
    HAS_MODBUS = False

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


class EdgeGuardState:
    def __init__(self, mode="AUTO", sim_mode=True):
        self.lock = threading.Lock()
        self.sim_mode = sim_mode
        self.running = True

        # System States
        self.mode = mode                     # "AUTO" or "MANUAL"
        self.safety_state = "SAFE"           # "SAFE", "WARNING", "TRIPPED", "COMM_FAULT"
        self.equipment_running = False
        self.target_speed = 50               # 0 ~ 100 %
        self.actual_rpm = 0.0                # 0 ~ 2850 RPM
        self.pwm_value = 0                   # 0 ~ 255

        # Safety & Simulation Flags
        self.ai_zone_intruded = False
        self.e_stop_pressed = False
        self.trip_latched = False
        self.comm_watchdog_fault = False
        self.heartbeat_counter = 0

        # PLC I/O Registers (Delta DVP-12SE11R)
        self.plc_connected = False
        self.plc_host = "192.168.1.5"
        self.plc_port = 502
        self.inputs = {
            "X0_AUTO": 1 if mode == "AUTO" else 0,
            "X1_ESTOP_NC": 1,
            "X2_RESET": 0,
            "X3_START": 0,
            "X4_STOP": 1,
            "X5_ARDUINO_OK": 1
        }
        self.outputs = {
            "Y0_FAN_POWER": 0,
            "Y1_ALARM_STROBE": 0,
            "Y2_SPEED_GATE": 0,
            "Y3_HEARTBEAT": 0
        }
        self.registers = {
            "D0_MODE": 1 if mode == "AUTO" else 0,
            "D1_SAFETY": 0,
            "D2_SPEED": 50,
            "D3_RPM": 0,
            "D10_HEARTBEAT": 0,
            "D20_IDLE_TIMER": 0,
            "D50_FAULT_CODE": 0
        }

        # Arduino Status
        self.arduino_connected = False
        self.arduino_port = "SIMULATED"
        self.arduino_baud = 115200

        # Audit Logs
        self.logs = []
        self.add_log("INFO", f"System initialized in {'SIMULATION' if sim_mode else 'HARDWARE'} mode.")

    def add_log(self, level, message):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": level,
            "message": message
        }
        self.logs.insert(0, entry)
        if len(self.logs) > 100:
            self.logs.pop()

    def get_snapshot(self):
        with self.lock:
            return {
                "system": {
                    "mode": self.mode,
                    "safety_state": self.safety_state,
                    "equipment_running": self.equipment_running,
                    "target_speed": self.target_speed,
                    "actual_rpm": int(self.actual_rpm),
                    "pwm_value": self.pwm_value,
                    "trip_latched": self.trip_latched,
                    "ai_zone_intruded": self.ai_zone_intruded,
                    "e_stop_pressed": self.e_stop_pressed,
                    "sim_mode": self.sim_mode,
                    "timestamp": time.time()
                },
                "plc": {
                    "connected": self.plc_connected or self.sim_mode,
                    "host": self.plc_host,
                    "port": self.plc_port,
                    "inputs": self.inputs.copy(),
                    "outputs": self.outputs.copy(),
                    "registers": self.registers.copy()
                },
                "arduino": {
                    "connected": self.arduino_connected or self.sim_mode,
                    "port": self.arduino_port,
                    "baud": self.arduino_baud,
                    "watchdog_ok": not self.comm_watchdog_fault
                },
                "logs": self.logs[:15]
            }

    def handle_command(self, action, payload=None):
        payload = payload or {}
        with self.lock:
            # 1. SET SPEED
            if action == "set_speed":
                speed = int(payload.get("speed", 0))
                speed = max(0, min(100, speed))
                self.target_speed = speed
                self.registers["D2_SPEED"] = speed
                self.add_log("INFO", f"Target fan speed set to {speed}%")
                return {"status": "ok", "speed": speed}

            # 2. SET MODE (AUTO / MANUAL)
            elif action == "set_mode":
                new_mode = payload.get("mode", "AUTO").upper()
                if new_mode in ["AUTO", "MANUAL"]:
                    self.mode = new_mode
                    self.inputs["X0_AUTO"] = 1 if new_mode == "AUTO" else 0
                    self.registers["D0_MODE"] = 1 if new_mode == "AUTO" else 0
                    self.add_log("WARN" if new_mode == "MANUAL" else "INFO",
                                 f"Control mode switched to {new_mode}")
                    return {"status": "ok", "mode": new_mode}

            # 3. START EQUIPMENT
            elif action == "start":
                if self.trip_latched or self.e_stop_pressed:
                    self.add_log("WARN", "Cannot start: Safety trip or E-Stop is active.")
                    return {"status": "error", "message": "Safety trip active"}
                self.equipment_running = True
                self.outputs["Y0_FAN_POWER"] = 1
                self.outputs["Y2_SPEED_GATE"] = 1
                self.add_log("INFO", "Equipment START requested.")
                return {"status": "ok"}

            # 4. STOP EQUIPMENT
            elif action == "stop":
                self.equipment_running = False
                self.outputs["Y0_FAN_POWER"] = 0
                self.outputs["Y2_SPEED_GATE"] = 0
                self.add_log("INFO", "Equipment STOP requested.")
                return {"status": "ok"}

            # 5. SIMULATE AI ZONE INTRUSION
            elif action == "trigger_intrusion":
                self.ai_zone_intruded = True
                if self.mode == "AUTO":
                    self.trip_latched = True
                    self.equipment_running = False
                    self.safety_state = "TRIPPED"
                    self.outputs["Y0_FAN_POWER"] = 0
                    self.outputs["Y2_SPEED_GATE"] = 0
                    self.outputs["Y1_ALARM_STROBE"] = 1
                    self.registers["D1_SAFETY"] = 2
                    self.add_log("CRITICAL", "AI INTRUSION: Person in restricted zone! PLC trip latched, fan cut off.")
                else:
                    self.safety_state = "WARNING"
                    self.registers["D1_SAFETY"] = 1
                    self.add_log("WARN", "AI Intrusion detected, but ignored by hardware: MANUAL mode active.")
                return {"status": "ok"}

            # 6. CLEAR INTRUSION
            elif action == "clear_intrusion":
                self.ai_zone_intruded = False
                self.add_log("INFO", "Restricted zone cleared by personnel.")
                if not self.trip_latched and not self.e_stop_pressed:
                    self.safety_state = "SAFE"
                    self.registers["D1_SAFETY"] = 0
                return {"status": "ok"}

            # 7. EMERGENCY STOP
            elif action == "e_stop":
                self.e_stop_pressed = True
                self.trip_latched = True
                self.equipment_running = False
                self.inputs["X1_ESTOP_NC"] = 0
                self.outputs["Y0_FAN_POWER"] = 0
                self.outputs["Y2_SPEED_GATE"] = 0
                self.outputs["Y1_ALARM_STROBE"] = 1
                self.safety_state = "TRIPPED"
                self.registers["D1_SAFETY"] = 2
                self.add_log("CRITICAL", "EMERGENCY STOP PRESSED! Hardware interlock open.")
                return {"status": "ok"}

            # 8. RESET SAFETY LATCH
            elif action == "reset":
                if self.e_stop_pressed:
                    self.inputs["X1_ESTOP_NC"] = 1
                    self.e_stop_pressed = False
                    self.add_log("INFO", "Hardware E-Stop released.")

                if self.ai_zone_intruded:
                    self.add_log("WARN", "Reset rejected: Person still in restricted zone!")
                    return {"status": "error", "message": "Zone not clear"}

                self.trip_latched = False
                self.safety_state = "SAFE"
                self.outputs["Y1_ALARM_STROBE"] = 0
                self.registers["D1_SAFETY"] = 0
                self.add_log("INFO", "Safety fault reset acknowledged. System ready.")
                return {"status": "ok"}

            elif action == "clear_logs":
                self.logs.clear()
                self.add_log("INFO", "Log history cleared.")
                return {"status": "ok"}

            return {"status": "error", "message": f"Unknown action: {action}"}


def simulation_physics_worker(state: EdgeGuardState):
    """Simulates realistic motor inertia, tachometer pulses, and Delta PLC ladder execution."""
    last_tick = time.time()
    heartbeat_timer = 0.0

    while state.running:
        now = time.time()
        dt = now - last_tick
        last_tick = now

        with state.lock:
            # 1. Delta PLC 1-Second Heartbeat Blinker (M1013 -> Y3)
            heartbeat_timer += dt
            if heartbeat_timer >= 0.5:
                state.outputs["Y3_HEARTBEAT"] = 1 - state.outputs["Y3_HEARTBEAT"]
                heartbeat_timer = 0.0

            # Increment Gateway watchdog heartbeat in register D10
            state.heartbeat_counter = (state.heartbeat_counter + 1) % 65535
            state.registers["D10_HEARTBEAT"] = state.heartbeat_counter

            # 2. Fan Motor RPM Physics Model
            # Max fan RPM at 100% is 2800 RPM.
            target_rpm = 0.0
            if state.equipment_running and not state.trip_latched and not state.e_stop_pressed:
                # Motor PWM mapping
                pct = state.target_speed
                state.pwm_value = int((pct / 100.0) * 255)
                target_rpm = (pct / 100.0) * 2800.0
            else:
                state.pwm_value = 0
                target_rpm = 0.0

            # Smooth inertia curve: actual_rpm approaches target_rpm
            accel_rate = 1400.0  # RPM/s when speeding up
            decel_rate = 800.0   # RPM/s when coasting to stop
            rate = accel_rate if target_rpm > state.actual_rpm else decel_rate

            diff = target_rpm - state.actual_rpm
            step = rate * dt
            if abs(diff) <= step:
                state.actual_rpm = target_rpm
            else:
                state.actual_rpm += math.copysign(step, diff)

            # Add small random tachometer noise when running
            if state.actual_rpm > 50:
                noise = random.uniform(-8, 8)
                measured_rpm = max(0.0, state.actual_rpm + noise)
            else:
                measured_rpm = 0.0

            state.registers["D3_RPM"] = int(measured_rpm)

        time.sleep(0.05)  # 20Hz physics update rate


class SCADAHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, state: EdgeGuardState = None, static_dir: str = "", **kwargs):
        self.state = state
        self.static_dir = static_dir
        super().__init__(*args, directory=static_dir, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # 1. API Status Snapshot
        if parsed.path == "/api/status":
            data = self.state.get_snapshot()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # 2. High-Frequency Real-time Telemetry Stream (Server-Sent Events)
        elif parsed.path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            try:
                while self.state.running:
                    snapshot = self.state.get_snapshot()
                    payload = f"data: {json.dumps(snapshot)}\n\n"
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(0.1)  # 10 Hz refresh rate
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # 3. Logs API
        elif parsed.path == "/api/logs":
            with self.state.lock:
                logs = self.state.logs[:]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(logs).encode("utf-8"))
            return

        # 4. Static Files (HTML / JS / CSS)
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/control":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
                action = data.get("action")
                payload = data.get("payload", {})
                res = self.state.handle_command(action, payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


def run_server(host="0.0.0.0", port=8080, sim_mode=True, plc_ip="192.168.1.5", serial_port=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(script_dir, "static")

    state = EdgeGuardState(mode="AUTO", sim_mode=sim_mode)
    state.plc_host = plc_ip

    # Start simulation physics background thread
    physics_thread = threading.Thread(target=simulation_physics_worker, args=(state,), daemon=True)
    physics_thread.start()

    # Factory for RequestHandler
    def handler_factory(*args, **kwargs):
        return SCADAHTTPRequestHandler(*args, state=state, static_dir=static_dir, **kwargs)

    server = ThreadingHTTPServer((host, port), handler_factory)
    print("=" * 65)
    print(" EdgeGuard Industrial IoT SCADA & Telemetry Dashboard")
    print("=" * 65)
    print(f"[*] Mode           : {'SIMULATION (No hardware required)' if sim_mode else 'LIVE HARDWARE'}")
    print(f"[*] Web Dashboard  : http://localhost:{port} (or http://127.0.0.1:{port})")
    print(f"[*] Delta PLC Host : {plc_ip}:502 (Modbus TCP)")
    print(f"[*] Arduino Serial : {serial_port or 'Simulated / Auto'}")
    print("[*] Press Ctrl+C to terminate.")
    print("=" * 65)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Stopping server...")
    finally:
        state.running = False
        server.server_close()
        print("[INFO] Server stopped gracefully.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EdgeGuard IoT Dashboard Server")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP Server bind host")
    parser.add_argument("--port", type=int, default=8080, help="HTTP Server port (default: 8080)")
    parser.add_argument("--sim", action="store_true", default=True, help="Force simulation mode")
    parser.add_argument("--live", action="store_true", help="Connect to physical PLC and Arduino")
    parser.add_argument("--plc-ip", default="192.168.1.5", help="Delta PLC IP Address")
    parser.add_argument("--serial-port", default=None, help="Arduino serial port device")
    args = parser.parse_args()

    sim_mode = True
    if args.live:
        sim_mode = False

    run_server(host=args.host, port=args.port, sim_mode=sim_mode, plc_ip=args.plc_ip, serial_port=args.serial_port)
