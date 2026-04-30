# -*- coding: utf-8 -*-
"""
Shared MetaWear IMU controller for visRV.

The GUI owns this object for the whole application lifetime. Exercises receive
it already connected and configured, avoiding repeated BLE reconnect/setup
cycles between exercises.
"""

import time
from threading import Event

from mbientlab.metawear import MetaWear, libmetawear, parse_value
from mbientlab.metawear.cbindings import *


class IMUController:
    def __init__(self, mac, preferred_mode="NDOF"):
        self.mac = mac
        self.preferred_mode = preferred_mode
        self.device = None
        self.signal = None
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
        self.time_connect = None
        self.time_last = None
        self.sampling_interval = 0.01
        self.time_imu_setup = 2.1

        self.bias_h = 0.0
        self.bias_v = 0.0
        self.head_position_h = 90.0
        self.head_position_v = 90.0
        self.prev_head_position_h = 90.0

        self.battery_charge = None
        self.battery_voltage = None
        self.calibration_state = None
        self._calibration_event = Event()
        self._calibration_status_event = Event()

    def connect(self):
        if self.connected and self.device and self.device.is_connected:
            print("IMU is already connected")
            return True

        self.device = MetaWear(self.mac)
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

            self.signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(
                self.device.board, SensorFusionData.EULER_ANGLE)
            libmetawear.mbl_mw_datasignal_subscribe(
                self.signal, None, self.read_orientation)
            libmetawear.mbl_mw_sensor_fusion_enable_data(
                self.device.board, SensorFusionData.EULER_ANGLE)
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

    def _select_fusion_mode(self):
        if self.preferred_mode == "IMU_PLUS":
            for attr in ("IMU_PLUS", "IMUPlus", "IMU_PLUS_MODE"):
                if hasattr(SensorFusionMode, attr):
                    print("Using SensorFusionMode.IMU_PLUS for head motion")
                    return getattr(SensorFusionMode, attr)

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
                self.raw_sample = parse_value(data)
                self.euler = self.raw_sample
                self.sample = (
                    (self.time_last - self.time_connect) - self.time_imu_setup,
                    self.euler)
                self._update_head_positions()

        self.time_last = time.time()

    def _update_head_positions(self):
        if self.euler is None:
            return

        self.prev_head_position_h = self.head_position_h
        head_h = round(self.euler.yaw + 90.0)
        if head_h > 360:
            head_h -= 360
        self.head_position_h = head_h + self.bias_h
        self.head_position_v = round(self.euler.pitch * -1 + 90.0) + self.bias_v

    def set_bias(self):
        self.bias_h += 90 - self.head_position_h
        self.bias_v += 90 - self.head_position_v
        print(f"IMU bias set: H={self.bias_h}, V={self.bias_v}")

    def reset_bias(self):
        self.bias_h = 0.0
        self.bias_v = 0.0
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
                f"({self.battery_voltage} mV)")
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
        print(f"IMU calibration state: {self.calibration_state}")
        self._calibration_status_event.set()

    def run_calibration_wizard(self, timeout=90.0):
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
            if self.is_calibrated():
                return self._read_and_write_calibration_data()
            time.sleep(1.0)

        print("IMU calibration wizard timed out")
        return False

    def is_calibrated(self):
        state = self.calibration_state
        if state is None:
            return False
        return (
            getattr(state, "accelrometer", 0) ==
            Const.SENSOR_FUSION_CALIBRATION_ACCURACY_HIGH and
            getattr(state, "gyroscope", 0) ==
            Const.SENSOR_FUSION_CALIBRATION_ACCURACY_HIGH and
            getattr(state, "magnetometer", 0) ==
            Const.SENSOR_FUSION_CALIBRATION_ACCURACY_HIGH
        )

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
                if self.streaming:
                    libmetawear.mbl_mw_sensor_fusion_stop(self.device.board)
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
            libmetawear.mbl_mw_sensor_fusion_stop(self.device.board)
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
