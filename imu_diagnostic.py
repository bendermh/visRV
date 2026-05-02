# -*- coding: utf-8 -*-
"""
Live quaternion IMU diagnostic helper for visRV.

Run this script with the IMU mounted in its normal position. It records the
same quaternion-based head positions used by VOR and VP.
"""

import argparse
import configparser
import csv
import math
import os
import sys
import time

try:
    import msvcrt
except ImportError:
    msvcrt = None

from imu_controller import IMUController
from mbientlab.warble import BleScanner


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config.ini")


def load_config_mac():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_PATH):
        return ""
    config.read(CONFIG_PATH)
    return config.get("IMU", "mac", fallback="")


def get_key():
    if msvcrt is None or not msvcrt.kbhit():
        return None
    key = msvcrt.getwch()
    if key in ("\x00", "\xe0") and msvcrt.kbhit():
        key = msvcrt.getwch()
    return key.lower()


def normalize_marker(marker):
    marker = marker.lower()
    if marker == "t":
        return "tilt"
    return marker


def finite_value(obj, name):
    raw = getattr(obj, name, None)
    if raw is None:
        return None
    raw = float(raw)
    if not math.isfinite(raw):
        return None
    return raw


def fmt(raw):
    if raw is None:
        return "   --  "
    return f"{raw:7.2f}"


def scan_devices(seconds):
    devices = {}

    def handler(result):
        devices[result.mac] = result.name

    print(f"Scanning BLE devices for {seconds:.1f}s...")
    BleScanner.set_handler(handler)
    BleScanner.start()
    time.sleep(seconds)
    BleScanner.stop()

    if not devices:
        print("No BLE devices found.")
        return

    for index, (mac, name) in enumerate(devices.items()):
        print(f"[{index}] {mac} ({name})")


def connect_with_retries(mac, mode, attempts, pause):
    for attempt in range(1, attempts + 1):
        controller = IMUController(mac, use_magnetometer=(mode == "NDOF"))
        print(f"Connecting to IMU {mac} in {mode} mode "
              f"(attempt {attempt}/{attempts})...")
        if controller.connect():
            return controller

        try:
            controller.disconnect()
        except Exception as exc:
            print(f"Disconnect after failed attempt warned: {exc}")

        if attempt < attempts:
            print(f"Retrying in {pause:.1f}s...")
            time.sleep(pause)

    return None


def diagnostic_row(controller, start_time, marker):
    quaternion = getattr(controller, "quaternion", None)
    if quaternion is None:
        return None

    euler = getattr(controller, "euler", None)
    return {
        "time_s": round(time.time() - start_time, 3),
        "marker": marker,
        "qw": finite_value(quaternion, "w"),
        "qx": finite_value(quaternion, "x"),
        "qy": finite_value(quaternion, "y"),
        "qz": finite_value(quaternion, "z"),
        "debug_yaw": finite_value(euler, "yaw") if euler else None,
        "debug_pitch": finite_value(euler, "pitch") if euler else None,
        "debug_roll": finite_value(euler, "roll") if euler else None,
        "horizontal_delta": controller.horizontal_yaw_delta,
        "vertical_delta": controller.vertical_delta,
        "tilt_delta": controller.tilt_delta,
        "app_head_h": controller.head_position_h,
        "app_head_v": controller.head_position_v,
        "app_head_tilt": controller.head_position_tilt,
    }


def print_header():
    print()
    print("IMU live diagnostic")
    print("Keys: c=center, h=horizontal, v=vertical, t=tilt, q=quit")
    print("Columns: quaternion, debug Euler, quaternion deltas, app positions")
    print("Keep the IMU mounted exactly as in a real VOR session.")
    print()


def print_row(row):
    line = (
        f"t={row['time_s']:7.2f}s "
        f"mark={row['marker'] or '-':4} "
        f"q=({fmt(row['qw'])},{fmt(row['qx'])},"
        f"{fmt(row['qy'])},{fmt(row['qz'])}) "
        f"yaw={fmt(row['debug_yaw'])} "
        f"pitch={fmt(row['debug_pitch'])} "
        f"roll={fmt(row['debug_roll'])} "
        f"dH={fmt(row['horizontal_delta'])} "
        f"dV={fmt(row['vertical_delta'])} "
        f"dTilt={fmt(row['tilt_delta'])} "
        f"appH={fmt(row['app_head_h'])} "
        f"appV={fmt(row['app_head_v'])} "
        f"appTilt={fmt(row['app_head_tilt'])}"
    )
    print(line)


def main():
    parser = argparse.ArgumentParser(
        description="Record and print MetaWear quaternion diagnostics.")
    parser.add_argument("--mac", default=load_config_mac(),
                        help="IMU MAC address. Defaults to config.ini.")
    parser.add_argument("--mode", default="IMU_PLUS",
                        choices=("NDOF", "IMU_PLUS"),
                        help="MetaWear sensor fusion mode.")
    parser.add_argument("--csv", default="imu_diagnostic_log.csv",
                        help="CSV output path.")
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="Stop after this many seconds. 0 means manual.")
    parser.add_argument("--interval", type=float, default=0.05,
                        help="Console/CSV sampling interval in seconds.")
    parser.add_argument("--center-seconds", type=float, default=0.0,
                        help="Wait, then recenter the IMU before recording.")
    parser.add_argument("--center-duration", type=float, default=0.6,
                        help="Averaging duration for diagnostic recentering.")
    parser.add_argument("--guided", action="store_true",
                        help="Run center/horizontal/center/vertical/center/tilt phases.")
    parser.add_argument("--fixed-marker", default="",
                        choices=("", "c", "h", "v", "t", "tilt"),
                        help="Mark all samples as center, horizontal, vertical, or tilt.")
    parser.add_argument("--scan", action="store_true",
                        help="Scan BLE devices and exit.")
    parser.add_argument("--scan-seconds", type=float, default=10.0,
                        help="BLE scan duration when --scan is used.")
    parser.add_argument("--retries", type=int, default=4,
                        help="Connection attempts before giving up.")
    parser.add_argument("--retry-pause", type=float, default=2.0,
                        help="Seconds to wait between connection attempts.")
    args = parser.parse_args()

    if args.scan:
        scan_devices(args.scan_seconds)
        return 0

    if not args.mac:
        print("No IMU MAC found. Pass --mac or set [IMU] mac in config.ini.")
        return 2

    controller = connect_with_retries(
        args.mac, args.mode, args.retries, args.retry_pause)
    if controller is None:
        return 1

    controller.sampling_interval = min(controller.sampling_interval,
                                       args.interval)

    if args.center_seconds > 0:
        print(f"Hold center for {args.center_seconds:.1f}s...")
        time.sleep(args.center_seconds)
        print(f"Centering IMU over {args.center_duration:.1f}s...")
        controller.set_bias(duration=args.center_duration)

    fields = [
        "time_s", "marker", "qw", "qx", "qy", "qz",
        "debug_yaw", "debug_pitch", "debug_roll",
        "horizontal_delta", "vertical_delta", "tilt_delta",
        "app_head_h", "app_head_v", "app_head_tilt",
    ]
    phases = [
        ("c", 5.0, "CENTER: look straight ahead"),
        ("h", 15.0, "HORIZONTAL: turn head left/right"),
        ("c", 5.0, "CENTER: look straight ahead"),
        ("v", 15.0, "VERTICAL: nod head up/down"),
        ("c", 5.0, "CENTER: look straight ahead"),
        ("tilt", 15.0, "TILT: bring each ear toward the shoulder"),
        ("c", 5.0, "CENTER: look straight ahead"),
    ]
    start_time = time.time()
    last_print = 0.0
    marker = ""
    phase_marker = ""
    phase_index = 0
    phase_started = start_time
    rows_written = 0

    try:
        print_header()
        if args.guided:
            phase_marker, _, phase_text = phases[phase_index]
            print(f"Guided phase: {phase_text}")

        with open(args.csv, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fields)
            writer.writeheader()

            while True:
                if args.guided:
                    elapsed_phase = time.time() - phase_started
                    _, phase_duration, _ = phases[phase_index]
                    if elapsed_phase >= phase_duration:
                        phase_index += 1
                        if phase_index >= len(phases):
                            break
                        phase_marker, _, phase_text = phases[phase_index]
                        phase_started = time.time()
                        print(f"\nGuided phase: {phase_text}")

                key = get_key()
                if key == "q":
                    break
                if key in ("h", "v", "c", "t"):
                    marker = normalize_marker(key)
                    print(f"\nMarker set: {marker}")

                if args.seconds > 0 and time.time() - start_time >= args.seconds:
                    break

                if time.time() - last_print < args.interval:
                    time.sleep(0.005)
                    continue

                row = diagnostic_row(
                    controller, start_time,
                    marker or normalize_marker(args.fixed_marker)
                    or phase_marker)
                last_print = time.time()
                if row is None:
                    continue

                print_row(row)
                writer.writerow(row)
                csv_file.flush()
                rows_written += 1
                marker = ""

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        controller.disconnect()

    print(f"Saved {rows_written} samples to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
