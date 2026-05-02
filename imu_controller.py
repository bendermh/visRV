# -*- coding: utf-8 -*-
"""
Shared MetaWear IMU controller for visRV.

The GUI owns this object for the whole application lifetime. Exercises receive
it already connected and configured, avoiding repeated BLE reconnect/setup
cycles between exercises.
"""

import time
import math
from threading import Event
from types import SimpleNamespace

from mbientlab.metawear import MetaWear, libmetawear, parse_value
from mbientlab.metawear.cbindings import *


class IMUController:
    def __init__(
        self,
        mac,
        use_magnetometer=False,
    ):
        self.mac = mac

        # True  = NDOF: gyro + accelerometer + magnetometer
        # False = IMU_PLUS: gyro + accelerometer only
        self.use_magnetometer = bool(use_magnetometer)

        self.device = None
        self.signal = None
        self.orientation_signal = None
        self.battery_signal = None
        self.calibration_signal = None
        self.connected = False
        self.configured = False
        self.streaming = False
        self.mode = None

        self.read_orientation = FnVoid_VoidP_DataP(self._stream_orientation)
        self.read_battery = FnVoid_VoidP_DataP(self._stream_battery)
        self.read_calibration = FnVoid_VoidP_DataP(self._stream_calibration)
        try:
            self.read_calibration_data = FnVoid_VoidP_VoidP_CalibrationDataP(
                self._calibration_data_handler)
        except NameError:
            self.read_calibration_data = None

        self.sample = None
        self.raw_sample = None
        self.euler = None
        self.quaternion = None
        self.time_connect = None
        self.time_last = None
        self.sampling_interval = 0.01
        self.time_imu_setup = 3.0

        self.bias_h = 0.0
        self.bias_v = 0.0
        self.bias_tilt = 0.0

        # Head movement is derived from the quaternion relative to center.
        self.center_quaternion = None
        self.horizontal_center_yaw = None
        self.horizontal_yaw_delta = 0.0

        self.vertical_delta = 0.0
        self.tilt_delta = 0.0

        self.horizontal_motion_gain = 1.0
        self.vertical_motion_gain = 1.5
        self.tilt_motion_gain = 1.5

        self.head_position_h = 90.0
        self.head_position_v = 90.0
        self.head_position_tilt = 90.0
        self.prev_head_position_h = 90.0

        self.battery_charge = None
        self.battery_voltage = None
        self.calibration_state = None
        self.last_calibration_accuracy = None
        self.last_nonzero_calibration_accuracy = None
        self._last_calibration_print = None
        self._calibration_event = Event()
        self._calibration_status_event = Event()

    def connect(self):
        if self.connected and self.device and self.device.is_connected:
            print("IMU is already connected")
            return True

        self.device = MetaWear(self.mac)
        try:
            self.device.on_disconnect = self._handle_disconnect
        except Exception:
            pass

        try:
            self.device.connect()
        except Exception as exc:
            print(f"IMU connection error: {exc}")
            self.connected = False
            return False

        time.sleep(2.5)
        self.connected = bool(self.device.is_connected)
        if not self.connected:
            print("IMU is NOT connected")
            return False

        print("IMU connected")
        if not self.configure():
            self.disconnect()
            return False

        self.request_battery()
        return True

    def configure(self):
        if not self.connected or not self.device or not self.device.is_connected:
            return False
        if self.configured:
            return True

        try:
            self.time_connect = time.time()
            self.time_last = self.time_connect
            print("Setting up shared IMU controller...")

            self._stop_sensor_fusion()
            self._clear_sensor_fusion_outputs()

            libmetawear.mbl_mw_settings_set_connection_parameters(
                self.device.board, 7.5, 7.5, 0, 6000)
            time.sleep(1.5)

            self.mode = self._select_fusion_mode()
            libmetawear.mbl_mw_sensor_fusion_set_mode(
                self.device.board, self.mode)
            libmetawear.mbl_mw_sensor_fusion_set_acc_range(
                self.device.board, SensorFusionAccRange._2G)
            libmetawear.mbl_mw_sensor_fusion_set_gyro_range(
                self.device.board, SensorFusionGyroRange._2000DPS)
            libmetawear.mbl_mw_sensor_fusion_write_config(self.device.board)
            time.sleep(0.5)

            self._clear_sensor_fusion_outputs()
            self.orientation_signal = (
                libmetawear.mbl_mw_sensor_fusion_get_data_signal(
                    self.device.board, SensorFusionData.QUATERNION)
            )
            self.signal = self.orientation_signal
            libmetawear.mbl_mw_datasignal_subscribe(
                self.orientation_signal, None, self.read_orientation)
            libmetawear.mbl_mw_sensor_fusion_enable_data(
                self.device.board, SensorFusionData.QUATERNION)
            libmetawear.mbl_mw_sensor_fusion_start(self.device.board)

            self.configured = True
            self.streaming = True
            print("Shared IMU setup done.")
            return True

        except Exception as exc:
            print(f"Shared IMU setup error: {exc}")
            self.configured = False
            self.streaming = False
            return False

    def _stop_sensor_fusion(self):
        if not self.device:
            return
        try:
            libmetawear.mbl_mw_sensor_fusion_stop(self.device.board)
        except Exception:
            pass

    def _clear_sensor_fusion_outputs(self):
        if not self.device:
            return
        try:
            libmetawear.mbl_mw_sensor_fusion_clear_enabled_mask(
                self.device.board)
        except Exception:
            pass

    def _handle_disconnect(self, status):
        self.connected = False
        self.configured = False
        self.streaming = False
        print(f"IMU disconnected: {status}")

    def _select_fusion_mode(self):
        if not self.use_magnetometer:
            for attr in ("IMU_PLUS", "IMUPlus", "IMU_PLUS_MODE"):
                if hasattr(SensorFusionMode, attr):
                    print("Using SensorFusionMode.IMU_PLUS for head motion")
                    return getattr(SensorFusionMode, attr)

            print(
                "Requested IMU_PLUS, but it is not available in this SDK. "
                "Falling back to SensorFusionMode.NDOF."
            )

        print("Using SensorFusionMode.NDOF for head motion")
        return SensorFusionMode.NDOF

    def _stream_orientation(self, ctx, data):
        now = time.time()
        if self.time_last is None:
            self.time_last = now

        if (now - self.time_last) <= self.sampling_interval:
            return

        if self.connected and self.time_connect:
            if (self.time_last - self.time_connect) > self.time_imu_setup:
                raw_sample = parse_value(data)
                clean_sample = self._clean_quaternion(raw_sample)
                if clean_sample is None:
                    self.time_last = time.time()
                    return

                self.raw_sample = raw_sample
                self.quaternion = clean_sample
                self.euler = self._quaternion_to_euler(clean_sample)
                self.sample = (
                    (self.time_last - self.time_connect) - self.time_imu_setup,
                    self.quaternion
                )
                self._update_head_positions()

        self.time_last = time.time()

    def _clean_quaternion(self, quaternion):
        try:
            w = float(quaternion.w)
            x = float(quaternion.x)
            y = float(quaternion.y)
            z = float(quaternion.z)
        except (AttributeError, TypeError, ValueError):
            return None

        values = (w, x, y, z)
        if not all(math.isfinite(value) for value in values):
            return None

        norm = math.sqrt(sum(value * value for value in values))
        if norm < 0.000001:
            return None

        return SimpleNamespace(
            w=w / norm,
            x=x / norm,
            y=y / norm,
            z=z / norm
        )

    def _update_head_positions(self):
        self.prev_head_position_h = self.head_position_h
        if self.quaternion is None:
            return

        self._ensure_motion_centers()

        head_h = self._horizontal_head_position()
        head_v = self._vertical_head_position()
        head_tilt = self._tilt_head_position()

        self.head_position_h = head_h
        self.head_position_v = head_v
        self.head_position_tilt = head_tilt

    def _ensure_motion_centers(self):
        if self.quaternion is None:
            return

        if self.center_quaternion is None:
            self.center_quaternion = self.quaternion
            self.horizontal_center_yaw = 0.0
            self.horizontal_yaw_delta = 0.0
            self.vertical_delta = 0.0
            self.tilt_delta = 0.0
            self.head_position_h = 90.0
            self.head_position_v = 90.0
            self.head_position_tilt = 90.0

    def _horizontal_head_position(self):
        relative = self._relative_quaternion()
        self.horizontal_yaw_delta = self._quaternion_axis_angle(relative, "z")

        return 90.0 - (
            self.horizontal_yaw_delta * self.horizontal_motion_gain
        ) + self.bias_h

    def _vertical_head_position(self):
        relative = self._relative_quaternion()
        self.vertical_delta = self._quaternion_axis_angle(relative, "y")

        return 90.0 - (
            self.vertical_delta * self.vertical_motion_gain
        ) + self.bias_v

    def _tilt_head_position(self):
        relative = self._relative_quaternion()
        self.tilt_delta = self._quaternion_axis_angle(relative, "x")
        return 90.0 + (self.tilt_delta * self.tilt_motion_gain) + self.bias_tilt

    def _relative_quaternion(self):
        if self.center_quaternion is None or self.quaternion is None:
            return SimpleNamespace(w=1.0, x=0.0, y=0.0, z=0.0)
        return self._quaternion_multiply(
            self.quaternion,
            self._quaternion_conjugate(self.center_quaternion)
        )

    def _quaternion_axis_angle(self, quaternion, axis):
        component = getattr(quaternion, axis)
        angle = math.degrees(2.0 * math.atan2(component, quaternion.w))
        return self._signed_angle_delta(angle, 0.0)

    def _quaternion_conjugate(self, quaternion):
        return SimpleNamespace(
            w=quaternion.w,
            x=-quaternion.x,
            y=-quaternion.y,
            z=-quaternion.z
        )

    def _quaternion_multiply(self, left, right):
        return SimpleNamespace(
            w=(
                left.w * right.w
                - left.x * right.x
                - left.y * right.y
                - left.z * right.z
            ),
            x=(
                left.w * right.x
                + left.x * right.w
                + left.y * right.z
                - left.z * right.y
            ),
            y=(
                left.w * right.y
                - left.x * right.z
                + left.y * right.w
                + left.z * right.x
            ),
            z=(
                left.w * right.z
                + left.x * right.y
                - left.y * right.x
                + left.z * right.w
            )
        )

    def _quaternion_to_euler(self, quaternion):
        w = quaternion.w
        x = quaternion.x
        y = quaternion.y
        z = quaternion.z

        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.degrees(math.copysign(math.pi / 2.0, sinp))
        else:
            pitch = math.degrees(math.asin(sinp))

        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))

        return SimpleNamespace(yaw=yaw, pitch=pitch, roll=roll)

    def _normalize_degrees(self, angle):
        return float(angle) % 360.0

    def _signed_angle_delta(self, angle, center):
        return ((float(angle) - float(center) + 180.0) % 360.0) - 180.0

    def _circular_mean_degrees(self, angles):
        if not angles:
            return None

        sin_sum = 0.0
        cos_sum = 0.0
        for angle in angles:
            radians = math.radians(self._normalize_degrees(angle))
            sin_sum += math.sin(radians)
            cos_sum += math.cos(radians)

        if abs(sin_sum) < 0.000001 and abs(cos_sum) < 0.000001:
            return self._normalize_degrees(angles[-1])

        return math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0

    def _average_quaternions(self, quaternions):
        if not quaternions:
            return None

        reference = quaternions[0]
        w_sum = 0.0
        x_sum = 0.0
        y_sum = 0.0
        z_sum = 0.0

        for quaternion in quaternions:
            dot = (
                reference.w * quaternion.w
                + reference.x * quaternion.x
                + reference.y * quaternion.y
                + reference.z * quaternion.z
            )
            sign = -1.0 if dot < 0.0 else 1.0
            w_sum += quaternion.w * sign
            x_sum += quaternion.x * sign
            y_sum += quaternion.y * sign
            z_sum += quaternion.z * sign

        norm = math.sqrt(
            w_sum * w_sum
            + x_sum * x_sum
            + y_sum * y_sum
            + z_sum * z_sum
        )
        if norm < 0.000001:
            return quaternions[-1]

        return SimpleNamespace(
            w=w_sum / norm,
            x=x_sum / norm,
            y=y_sum / norm,
            z=z_sum / norm
        )

    def set_bias(self, duration=0.0):
        head_h = self.head_position_h
        head_v = self.head_position_v
        head_tilt = self.head_position_tilt

        quaternion_samples = []

        if self.quaternion is not None:
            quaternion_samples.append(self.quaternion)

        if duration > 0:
            samples = []
            deadline = time.time() + duration

            while time.time() < deadline:
                samples.append((
                    self.head_position_h,
                    self.head_position_v,
                    self.head_position_tilt
                ))

                if self.quaternion is not None:
                    quaternion_samples.append(self.quaternion)

                time.sleep(max(self.sampling_interval, 0.01))

            if samples:
                head_h = sum(sample[0] for sample in samples) / len(samples)
                head_v = sum(sample[1] for sample in samples) / len(samples)
                head_tilt = sum(sample[2] for sample in samples) / len(samples)

        center_quaternion = self._average_quaternions(quaternion_samples)
        if center_quaternion is not None:
            self.center_quaternion = center_quaternion
            self.horizontal_center_yaw = 0.0
            self.bias_h = 0.0
            self.horizontal_yaw_delta = 0.0
            self.head_position_h = 90.0
            self.bias_v = 0.0
            self.vertical_delta = 0.0
            self.head_position_v = 90.0
            self.bias_tilt = 0.0
            self.tilt_delta = 0.0
            self.head_position_tilt = 90.0
        else:
            self.bias_h += 90.0 - head_h
            self.bias_v += 90.0 - head_v
            self.bias_tilt += 90.0 - head_tilt

        print(
            f"IMU bias set: H={self.bias_h}, V={self.bias_v}, "
            f"Tilt={self.bias_tilt}, QuaternionCenter={self.center_quaternion}"
        )

    def reset_bias(self):
        self.bias_h = 0.0
        self.bias_v = 0.0
        self.bias_tilt = 0.0

        self.horizontal_center_yaw = None
        self.horizontal_yaw_delta = 0.0

        self.center_quaternion = None
        self.vertical_delta = 0.0
        self.tilt_delta = 0.0

        self.head_position_h = 90.0
        self.head_position_v = 90.0
        self.head_position_tilt = 90.0

        print("IMU bias reset")

    def request_battery(self):
        if not self.connected or not self.device:
            return False

        try:
            if self.battery_signal is None:
                self.battery_signal = (
                    libmetawear.mbl_mw_settings_get_battery_state_data_signal(
                        self.device.board))
                libmetawear.mbl_mw_datasignal_subscribe(
                    self.battery_signal, None, self.read_battery)

            libmetawear.mbl_mw_datasignal_read(self.battery_signal)
            return True

        except Exception as exc:
            print(f"Unable to request IMU battery: {exc}")
            return False

    def _stream_battery(self, ctx, data):
        try:
            battery = parse_value(data)
            self.battery_charge = getattr(battery, "charge", None)
            self.battery_voltage = getattr(battery, "voltage", None)
            print(
                f"IMU battery: {self.battery_charge}% "
                f"({self.battery_voltage} mV)"
            )
        except Exception as exc:
            print(f"Unable to parse IMU battery: {exc}")

    def battery_text(self):
        if self.battery_charge is None:
            return "Battery: --"
        return f"Battery: {self.battery_charge}%"

    def request_calibration_state(self):
        if not self.connected or not self.device:
            return None

        try:
            self._calibration_status_event.clear()

            if self.calibration_signal is None:
                self.calibration_signal = (
                    libmetawear
                    .mbl_mw_sensor_fusion_calibration_state_data_signal(
                        self.device.board))
                libmetawear.mbl_mw_datasignal_subscribe(
                    self.calibration_signal, None, self.read_calibration)

            libmetawear.mbl_mw_datasignal_read(self.calibration_signal)
            self._calibration_status_event.wait(3.0)
            return self.calibration_state

        except Exception as exc:
            print(f"Unable to request IMU calibration state: {exc}")
            return None

    def _stream_calibration(self, ctx, data):
        self.calibration_state = parse_value(data)
        self.last_calibration_accuracy = self.calibration_accuracy()

        if (
            self.last_calibration_accuracy is not None and
            any(value > 0 for value in self.last_calibration_accuracy)
        ):
            self.last_nonzero_calibration_accuracy = (
                self.last_calibration_accuracy)

        if self.last_calibration_accuracy != self._last_calibration_print:
            print(
                "IMU calibration state: "
                f"{self.calibration_accuracy_text()}"
            )
            self._last_calibration_print = self.last_calibration_accuracy

        self._calibration_status_event.set()

    def run_calibration_wizard(self, timeout=60.0, status_callback=None):
        """
        Read sensor-fusion calibration state until high accuracy is reached,
        then write calibration data back to the sensor when supported.
        """
        if not self.connected or not self.device:
            return False

        try:
            if self.calibration_signal is None:
                self.calibration_signal = (
                    libmetawear
                    .mbl_mw_sensor_fusion_calibration_state_data_signal(
                        self.device.board))
                libmetawear.mbl_mw_datasignal_subscribe(
                    self.calibration_signal, None, self.read_calibration)

        except Exception as exc:
            print(f"Unable to start calibration wizard: {exc}")
            return False

        deadline = time.time() + timeout

        while time.time() < deadline:
            self._calibration_status_event.clear()
            libmetawear.mbl_mw_datasignal_read(self.calibration_signal)
            self._calibration_status_event.wait(2.0)

            if status_callback:
                status_callback(self.calibration_accuracy())

            if self.is_calibrated():
                return self._read_and_write_calibration_data()

            time.sleep(1.0)

        print(
            "IMU calibration wizard timed out: "
            f"{self.calibration_accuracy_text()}"
        )
        return False

    def calibration_accuracy(self, state=None):
        state = self.calibration_state if state is None else state
        if state is None:
            return None

        return (
            getattr(state, "accelrometer",
                    getattr(state, "accelerometer", 0)),
            getattr(state, "gyroscope", 0),
            getattr(state, "magnetometer", 0),
        )

    def calibration_accuracy_text(self, state=None):
        if state is None:
            accuracy = (
                self.last_calibration_accuracy or
                self.last_nonzero_calibration_accuracy or
                self.calibration_accuracy()
            )
        else:
            accuracy = self.calibration_accuracy(state)

        if accuracy is None:
            return "A- G- M-"

        accel, gyro, mag = accuracy
        return f"A{accel} G{gyro} M{mag}"

    def is_calibrated(self):
        accuracy = self.calibration_accuracy()
        if accuracy is None:
            return False

        high = Const.SENSOR_FUSION_CALIBRATION_ACCURACY_HIGH

        if self.use_magnetometer:
            return accuracy == (high, high, high)

        accel, gyro, _mag = accuracy
        return accel == high and gyro == high

    def _read_and_write_calibration_data(self):
        if self.read_calibration_data is None:
            print("Calibration data callback is not available in this SDK")
            return False

        try:
            self._calibration_event.clear()
            libmetawear.mbl_mw_sensor_fusion_read_calibration_data(
                self.device.board, None, self.read_calibration_data)
            self._calibration_event.wait(5.0)
            print("IMU calibration data saved")
            return True

        except Exception as exc:
            print(f"Unable to save IMU calibration data: {exc}")
            return False

    def _calibration_data_handler(self, ctx, board, pointer):
        print(f"IMU calibration data: {pointer.contents}")
        libmetawear.mbl_mw_sensor_fusion_write_calibration_data(
            board, pointer)
        libmetawear.mbl_mw_memory_free(pointer)
        self._calibration_event.set()

    def disconnect(self):
        if not self.device:
            print("No IMU connection to close")
            return

        print("Closing shared IMU connection...")

        if self.connected and self.device.is_connected:
            try:
                self._stop_sensor_fusion()
                self._clear_sensor_fusion_outputs()

                if self.signal:
                    libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)

                if self.battery_signal:
                    libmetawear.mbl_mw_datasignal_unsubscribe(
                        self.battery_signal)

                if self.calibration_signal:
                    libmetawear.mbl_mw_datasignal_unsubscribe(
                        self.calibration_signal)

                time.sleep(0.5)
                self.device.disconnect()
                time.sleep(1.0)

            except Exception as exc:
                print(f"IMU disconnect warning: {exc}")

        self.signal = None
        self.orientation_signal = None
        self.battery_signal = None
        self.calibration_signal = None
        self.connected = False
        self.configured = False
        self.streaming = False

        print("Shared IMU connection closed")

    def factory_reset(self):
        if not self.device or not self.connected:
            print("No IMU, no reset")
            return False

        print("Erase logger, state, and macros")

        try:
            self._stop_sensor_fusion()
            self._clear_sensor_fusion_outputs()

            if self.signal:
                libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)

            time.sleep(0.5)

            libmetawear.mbl_mw_logging_stop(self.device.board)
            libmetawear.mbl_mw_logging_clear_entries(self.device.board)
            libmetawear.mbl_mw_macro_erase_all(self.device.board)
            libmetawear.mbl_mw_debug_reset_after_gc(self.device.board)
            libmetawear.mbl_mw_debug_disconnect(self.device.board)

            self.connected = False
            self.configured = False
            self.streaming = False

            return True

        except Exception as exc:
            print(f"IMU reset error: {exc}")
            return False
