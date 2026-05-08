# -*- coding: utf-8 -*-
"""
Spyder IDE

visRV, code by Jorge Rey-Martinez & HAL 2023-25.
"""

import pathlib
import configparser
import os
import sys
import deviceSelect
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import pygubu
import time
import threading
from PIL import Image, ImageTk
from mbientlab.warble import *
import smoothPursuit
import saccades
import okn
import vor
import vp
import display_utils
from imu_controller import IMUController


# ========== Resource path helper ==========
def resource_path(relative_path):
    """ Get absolute path to resource (works for dev and PyInstaller) """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# ========== Project resources ==========
PROJECT_PATH = pathlib.Path(__file__).parent
PROJECT_UI = resource_path(os.path.join("GUI", "visVR.ui"))
PROJECT_CONFIG = resource_path("config.ini")
PROJECT_IMU_PIC = resource_path(os.path.join("GUI", "IMU.png"))
PROJECT_ICON = resource_path("GUI/VR_icon.ico")
BATTERY_LOW_THRESHOLD = 45
APP_VERSION = 1.0


class visRV:
    def __init__(self, master=None):
        # 1: Create a builder and setup resources path
        self.builder = builder = pygubu.Builder()
        builder.add_resource_path(PROJECT_PATH)

        # 2: Load UI file
        builder.add_from_file(PROJECT_UI)

        # 3: Create the mainwindow
        self.mainwindow = builder.get_object('mainWindow', master)

        # 3b: Set application icon
        try:
            self.mainwindow.iconbitmap(PROJECT_ICON)
        except Exception as e:
            print(f"Warning: could not set icon ({e})")

        # 4: Connect tk objects and callbacks
        builder.connect_callbacks(self)
        self.imuCanvas = builder.get_object("imuCanvas")
        self.scanButton = builder.get_object("scanButton")
        self.connectButton = builder.get_object("connectButton")
        self.resetButton = builder.get_object("button5")
        self.calibrateButton = builder.get_object("calibrateButton")
        self.batteryLabel = builder.get_object("batteryLabel")
        self.batteryBar = builder.get_object("batteryBar")
        self.imuPositionHelp = builder.get_object("imuPositionHelp")
        self.monitorSelector = builder.get_object("monitorSelector")
        self.startSPButton = builder.get_object("spStartButton")
        self.startSMButton = builder.get_object("smStartButton")
        self.startOKButton = builder.get_object("okStartButton")
        self.startVORButton = builder.get_object("vorStartButton")
        self.startVORSButton = builder.get_object("vorsStartButton")
        self.startVPButton = builder.get_object("vpStartButton")
        self.oknTiltButton = builder.get_object("OKN_tilt")
        self.oknTiltStatus = builder.get_variable("okTiltStatus")
        self.appVersion = builder.get_object("version_n")

        # Other variables
        self.imuMac = ""
        self.canConnect = False
        self.isIMUConected = False
        self.isClosing = False
        self.delayEvents = 150
        self.imuDevice = None
        self.imuController = None
        self.timeZero = time.time()
        self.timeLastBattery = 0
        self.lowBatteryWarningShown = False

        # Runtime IMU controls
        self.imuControls = self.connectButton.master
        self._setup_imu_styles()

        # Load images
        aux = Image.open(PROJECT_IMU_PIC)
        self.imuImg = ImageTk.PhotoImage(aux)
        self.imuCanvas.create_image(4, 4, image=self.imuImg, anchor="nw")
        self.appVersion.configure(text="Ver: " + str(APP_VERSION))
        self.imuPositionHelp.bind("<Button-1>", self.showIMUPositionHelp)
        self.oknTiltStatus.set(False)

        # Set & get GUI variables
        self.refreshMonitorSelector()
        self.guiVariables(onlyRead=False)

        callbacks = {
            "startSP": self.startSP,
            "startSM": self.startSM,
            "startOK": self.startOK,
            "startVOR": self.startVOR,
            "startVORS": self.startVORS,
            "startVP": self.startVP,
            "changeTemplate": self.changeTemplate,
            "connectIMU": self.connectIMU,
            "scanIMU": self.scanIMU,
            "resetIMU": self.resetIMU,
            "calibrateIMU": self.calibrateIMU,
            "showIMUPositionHelp": self.showIMUPositionHelp,
        }
        builder.connect_callbacks(callbacks)
        self._set_battery_bar(None)

        # Scan for devices
        BleScanner.start()
        time.sleep(2.0)
        BleScanner.stop()

    def _setup_imu_styles(self):
        style = ttk.Style(self.mainwindow)
        style.configure("Danger.TButton", foreground="#a3261f")
        style.map(
            "Danger.TButton",
            foreground=[("disabled", "#9a9a9a"), ("active", "#7f1d18")])

    def _set_battery_bar(self, charge):
        self.batteryBar.delete("all")
        width = int(self.batteryBar.cget("width"))
        height = int(self.batteryBar.cget("height"))
        self.batteryBar.create_rectangle(
            0, 0, width, height, outline="", fill="#d0d0d0")
        if charge is None:
            return
        charge = max(0, min(100, int(charge)))
        fill_width = int(width * charge / 100)
        color = "#b3261e" if charge <= BATTERY_LOW_THRESHOLD else "#2e7d32"
        if fill_width > 0:
            self.batteryBar.create_rectangle(
                0, 0, fill_width, height, outline="", fill=color)

    def _update_battery_display(self):
        if not self.isIMUConected or self.imuController is None:
            self.batteryLabel.configure(text="Battery: --")
            self._set_battery_bar(None)
            self.lowBatteryWarningShown = False
            return

        self.batteryLabel.configure(text=self.imuController.battery_text())
        charge = self.imuController.battery_charge
        self._set_battery_bar(charge)
        if charge is None:
            return

        charge = int(charge)
        if charge <= BATTERY_LOW_THRESHOLD and not self.lowBatteryWarningShown:
            self.lowBatteryWarningShown = True
            messagebox.showwarning(
                "Low IMU battery",
                f"IMU battery is at {charge}%. Charge the sensor before "
                "starting a rehabilitation session.")

    def showIMUPositionHelp(self, event=None):
        messagebox.showinfo(
            "IMU placement",
            "Place the IMU on the back of the subject's head "
            "(use an elastic headband).\n\n"
            "The examiner should stand behind the subject.\n\n"
            "The IMU button should face the examiner and point downward, "
            "matching the image shown in the main window.")

    def guiVariables(self, onlyRead = True):
        preMonitor = 0
        match self.builder.get_variable("monitorSelected").get():
            case "Main":
                preMonitor = 0
            case "Secondary_1":
                preMonitor = 1
            case "Secondary_2":
                preMonitor = 2
            case _:
                preMonitor = 0
                print("GUI monitor imput is unknown!")

        preSizeSP = "S"
        preSizeSM = "S"
        preSizeOK = "S"
        preSizeVOR ="S"
        preSizeVORS ="S"
        preSizeVP ="S"

        match self.builder.get_variable("targetSizeSP").get():
            case "Small":
                preSizeSP = "S"
            case "Medium":
                preSizeSP = "M"
            case "Large":
                preSizeSP = "L"
            case _:
                preSizeSP = "M"
                print("GUI Size imput is unknown for SP!")

        match self.builder.get_variable("targetSizeSM").get():
           case "Small":
               preSizeSM = "S"
           case "Medium":
               preSizeSM = "M"
           case "Large":
               preSizeSM = "L"
           case _:
               preSizeSM = "M"
               print("GUI Size imput is unknown for SM!")

        match self.builder.get_variable("targetSizeOK").get():
           case "Small":
               preSizeOK = "S"
           case "Medium":
               preSizeOK = "M"
           case "Large":
               preSizeOK = "L"
           case _:
               preSizeOK = "M"
               print("GUI Size imput is unknown for OKN!")

        match self.builder.get_variable("targetSizeVOR").get():
           case "Small":
               preSizeVOR = "S"
           case "Medium":
               preSizeVOR = "M"
           case "Large":
               preSizeVOR = "L"
           case _:
               preSizeVOR = "M"
               print("GUI Size imput is unknown for VOR adaptation!")

        match self.builder.get_variable("targetSizeVORS").get():
           case "Small":
               preSizeVORS = "S"
           case "Medium":
               preSizeVORS = "M"
           case "Large":
               preSizeVORS = "L"
           case _:
               preSizeVORS = "M"
               print("GUI Size imput is unknown for VOR suppression!")

        match self.builder.get_variable("targetSizeVP").get():
           case "Small":
               preSizeVP = "S"
           case "Medium":
               preSizeVP = "M"
           case "Large":
               preSizeVP = "L"
           case _:
               preSizeVP = "M"
               print("GUI Size imput is unknown for vis PONG!")

        self.monitorSelected = preMonitor
        self.targetSizeSP = preSizeSP
        self.targetSizeSM = preSizeSM
        self.targetSizeOK = preSizeOK
        self.targetSizeVOR = preSizeVOR
        self.targetSizeVORS = preSizeVORS
        self.targetSizeVP = preSizeVP

        self.timeDurationSP = self.builder.get_variable("timeDurationSP").get()
        self.horizontalSpeedSP = self.builder.get_variable("horizontalSpeedSP").get()
        self.verticalSpeedSP = self.builder.get_variable("verticalSpeedSP").get()
        self.targetChangeSP = self.builder.get_variable("targetChangeSP").get()


        self.timeDurationSM = self.builder.get_variable("timeDurationSM").get()
        self.horizontalSpeedSM = self.builder.get_variable("horizontalSpeedSM").get()
        self.verticalSpeedSM = self.builder.get_variable("verticalSpeedSM").get()
        self.targetChangeSM = self.builder.get_variable("targetChangeSM").get()


        self.timeDurationOK = self.builder.get_variable("timeDurationOK").get()
        self.barSpeedOK = self.builder.get_variable("barSpeedOK").get()
        self.directionOK = self.builder.get_variable("directionOK").get()
        self.tiltOK = self.oknTiltStatus.get()

        self.timeDurationVOR = self.builder.get_variable("timeDurationVOR").get()
        self.horizontalRangeVOR = self.builder.get_variable("horizontalRangeVOR").get()
        self.verticalRangeVOR = self.builder.get_variable("verticalRangeVOR").get()
        self.targetChangeVOR = self.builder.get_variable("targetChangeVOR").get()

        self.timeDurationVORS = self.builder.get_variable("timeDurationVORS").get()
        self.horizontalRangeVORS = self.builder.get_variable("horizontalRangeVORS").get()
        self.verticalRangeVORS = self.builder.get_variable("verticalRangeVORS").get()
        self.targetChangeVORS = self.builder.get_variable("targetChangeVORS").get()

        self.timeDurationVP = self.builder.get_variable("timeDurationVP").get()
        self.horizontalRangeVP = self.builder.get_variable("horizontalRangeVP").get()
        self.targetStillVP = self.builder.get_variable("targetStillVP").get()

        self.templateValue = self.builder.get_variable("templateValue").get()

        if not onlyRead:
        #default GUI menus values
           self.builder.get_variable("timeDurationSP").set(120)
           self.builder.get_variable("horizontalSpeedSP").set(10)
           self.builder.get_variable("verticalSpeedSP").set(0)
           self.builder.get_variable("targetChangeSP").set(1.5)

           self.builder.get_variable("timeDurationSM").set(120)
           self.builder.get_variable("horizontalSpeedSM").set(1900)
           self.builder.get_variable("verticalSpeedSM").set(0)
           self.builder.get_variable("targetChangeSM").set(1.5)

           self.builder.get_variable("timeDurationOK").set(90)
           self.builder.get_variable("barSpeedOK").set(12)
           self.builder.get_variable("directionOK").set("Right")

           self.builder.get_variable("timeDurationVOR").set(120)
           self.builder.get_variable("horizontalRangeVOR").set(1)
           self.builder.get_variable("verticalRangeVOR").set(0)
           self.builder.get_variable("targetChangeVOR").set(1.5)

           self.builder.get_variable("timeDurationVORS").set(120)
           self.builder.get_variable("horizontalRangeVORS").set(1)
           self.builder.get_variable("verticalRangeVORS").set(0)
           self.builder.get_variable("targetChangeVORS").set(1.5)

           self.builder.get_variable("timeDurationVP").set(120)
           self.builder.get_variable("horizontalRangeVP").set(5)
           self.builder.get_variable("targetStillVP").set(0.75)

           self.builder.get_variable("templateValue").set("Default")

           self.guiVariables()

    def refreshMonitorSelector(self):
        options = display_utils.monitor_options()
        current = self.builder.get_variable("monitorSelected").get()
        if current not in options:
            current = options[0]

        try:
            self.monitorSelector.set_menu(current, *options)
        except AttributeError:
            menu = self.monitorSelector["menu"]
            menu.delete(0, "end")
            for option in options:
                menu.add_command(
                    label=option,
                    command=tk._setit(
                        self.builder.get_variable("monitorSelected"), option))

        self.builder.get_variable("monitorSelected").set(current)
        print(f"Monitor options detected by pygame: {', '.join(options)}")

    def startSP(self):
        self.guiVariables()
        self.mainwindow.withdraw()
        smoothPursuit.smoothPursuit(self.targetSizeSP, self.horizontalSpeedSP,self.verticalSpeedSP, self.targetChangeSP, self.timeDurationSP, self.monitorSelected)
        self.mainwindow.deiconify()

    def startSM(self):
        self.guiVariables()
        self.mainwindow.withdraw()
        saccades.saccades(self.targetSizeSM, self.horizontalSpeedSM,self.verticalSpeedSM, self.targetChangeSM, self.timeDurationSM, self.monitorSelected)
        self.mainwindow.deiconify()

    def startOK(self):
        self.guiVariables()
        self.mainwindow.withdraw()
        okn.okn(
            self.targetSizeOK,
            self.barSpeedOK,
            self.directionOK[0],
            self.timeDurationOK,
            self.tiltOK,
            self.monitorSelected,
            imuController=self.imuController)
        self.mainwindow.deiconify()

    def startVOR(self):
        if self.isIMUConected:
            self.guiVariables()
            self.mainwindow.withdraw()
            vor.vor(self.targetSizeVOR,self.imuController,True,self.verticalRangeVOR,self.horizontalRangeVOR,self.targetChangeVOR,self.timeDurationVOR,self.monitorSelected)
            time.sleep(2)
            self.mainwindow.deiconify()
        else:
            messagebox.showinfo("Warning", "Unable to connec to with IMU, try to connect or setup a new IMU")

    def startVORS(self):
         if self.isIMUConected:
             self.guiVariables()
             self.mainwindow.withdraw()
             vor.vor(self.targetSizeVORS,self.imuController,False,self.verticalRangeVORS,self.horizontalRangeVORS,self.targetChangeVORS,self.timeDurationVORS,self.monitorSelected)
             time.sleep(2)
             self.mainwindow.deiconify()
         else:
             messagebox.showinfo("Warning", "Unable to connec to with IMU, try to connect or setup a new IMU")

    def startVP(self):
         if self.isIMUConected:
             self.guiVariables()
             self.mainwindow.withdraw()
             vp.vp(self.targetSizeVP,self.imuController,False,self.horizontalRangeVP,self.targetStillVP,self.timeDurationVP,self.monitorSelected)
             time.sleep(2)
             self.mainwindow.deiconify()
         else:
             messagebox.showinfo("Warning", "Unable to connec to with IMU, try to connect or setup a new IMU")

    def changeTemplate(self,selValue):
        self.templateValue = selValue
        self.set_template_values(self.templateValue)

    def loadConfig(self):
        config = configparser.ConfigParser()
        if not os.path.exists(PROJECT_CONFIG):
            print("Config file not found")
            config['IMU'] = {'mac': ''}
            with open(PROJECT_CONFIG, 'w') as f:
                config.write(f)
        else:
            print("Config file exists")
            config.read(PROJECT_CONFIG)

        self.imuMac = config.get("IMU", "mac", fallback="")
        if self.imuMac == "":
            print("No IMU mac, load search wizard")
            self.isClosing = True
            try:
                if self.mainwindow.winfo_exists():
                    self.mainwindow.destroy()
            except tk.TclError:
                pass
            devSel = deviceSelect.deviceSelect()
            devSel.reloadMain = True
            devSel.run()
        else:
            print(f"Using IMU MAC: {self.imuMac}")
            self.canConnect = True
            mac_label = self.builder.get_variable('mac_value')
            mac_label.set("IMU mac address to connect: " + self.imuMac)


    def scanIMU(self):
            if not self.isIMUConected:
                self.isClosing = True
                self.mainwindow.destroy()
                devSel = deviceSelect.deviceSelect()
                devSel.reloadMain = True
                devSel.run()

    def connectIMU(self):
        if self.canConnect:
            self.imuController = IMUController(self.imuMac)
            connected = self.imuController.connect()
            self.imuDevice = self.imuController.device
            self.canConnect = False
            if connected:
                self.scanButton.state(["disabled"])
                self.connectButton.state(["disabled"])
                self.isIMUConected = True
                self._update_battery_display()
            else:
                print("IMU is NOT connected")
                self.isIMUConected = False
                self.canConnect = True
                messagebox.showinfo("Warning", "Unable to connec to with IMU, try wake up or pair again current IMU, revise IMU battery level")

        else:
            print("IMU is already connected")

    def calibrateIMU(self):
        if not self.isIMUConected or self.imuController is None:
            messagebox.showinfo("Warning", "Connect IMU before calibration")
            return

        answer = messagebox.askokcancel(
            "IMU calibration warning",
            "This is the internal MetaWear sensor-fusion calibration, not "
            "the VOR center/bias.\n\n"
            "During calibration, move the IMU slowly through many "
            "orientations: place it flat, rotate it by about 45-degree "
            "steps, and turn it around all axes. Keep it away from speakers, "
            "magnets, phones, metal objects, and large currents.\n\n"
            "A = accelerometer: leave the IMU completely still on a flat "
            "surface for a few seconds, then place it still on several faces "
            "or angles.\n"
            "G = gyroscope: keep it still briefly, then rotate it slowly.\n"
            "M = magnetometer: make slow figure-eight / 3D rotations away "
            "from metal or speakers.\n\n"
            "The button will show A/G/M accuracy from 0 to 3. Calibration "
            "finishes only when A3 G3 M3 is reached, or stops after 60 s.\n\n"
            "Continue with IMU calibration?")
        if not answer:
            return

        self.calibrateButton.configure(text="Calibrating")
        self.calibrateButton.state(["disabled"])
        worker = threading.Thread(target=self._calibrateIMUWorker, daemon=True)
        worker.start()

    def _calibrateIMUWorker(self):
        ok = self.imuController.run_calibration_wizard(
            timeout=60.0,
            status_callback=self._calibrateIMUStatusFromWorker)
        self.mainwindow.after(0, lambda: self._calibrateIMUDone(ok))

    def _calibrateIMUStatusFromWorker(self, accuracy):
        self.mainwindow.after(
            0, lambda: self._calibrateIMUStatus(accuracy))

    def _calibrateIMUStatus(self, accuracy):
        if accuracy is None:
            self.calibrateButton.configure(text="Calibrating")
            return
        accel, gyro, mag = accuracy
        self.calibrateButton.configure(text=f"A{accel} G{gyro} M{mag}")

    def _calibrateIMUDone(self, ok):
        status = "A- G- M-"
        if self.imuController is not None:
            status = self.imuController.calibration_accuracy_text()
        self.calibrateButton.configure(text="Calibrate IMU")
        self.calibrateButton.state(["!disabled"])
        if ok:
            messagebox.showinfo(
                "IMU calibration",
                f"IMU calibration completed ({status})")
        else:
            messagebox.showinfo(
                "IMU calibration",
                "IMU calibration did not complete.\n\n"
                f"Last status: {status}\n\n"
                "If A stays at 0, do not keep moving continuously: place "
                "the IMU completely still on a flat surface for a few "
                "seconds, then repeat on several faces or angles. "
                "If it still stays at A0 after a full attempt, restart the "
                "IMU and try once more.")

    def resetIMU(self):
        if not self.isIMUConected or self.imuController is None:
            messagebox.showinfo("Warning", "Connect IMU before reset")
            return

        answer = messagebox.askokcancel(
            "Factory reset warning",
            "Factory reset clears IMU calibration/settings and closes "
            "visRV. Current session data can be lost.\n\n"
            "Cancel unless you are sure you want to reset the sensor.\n\n"
            "Continue with IMU factory reset?")
        if not answer:
            return

        self.imuController.factory_reset()
        self.isIMUConected = False
        print("IMU reseted, app will close")
        self.isClosing = True
        time.sleep(10)
        self.mainwindow.destroy()


    def loopEvents(self):
        if self.isClosing:
            return
        #print("Event " + str(time.localtime().tm_sec))
        if self.isIMUConected:
            self.imuCanvas.configure(bg='green')
            if self.imuController:
                self._update_battery_display()
                if time.time() - self.timeLastBattery > 60:
                    self.imuController.request_battery()
                    self.timeLastBattery = time.time()
        else:
            self.imuCanvas.configure(bg='red')
            self._update_battery_display()
        try:
            self.mainwindow.after(self.delayEvents, self.loopEvents)
        except tk.TclError:
            pass

    def safeIMUDisconnect(self):
        if self.imuController is not None:
            try:
                self.imuController.disconnect()
            finally:
                self.isIMUConected = False
                self.imuController = None
                self.imuDevice = None
        else:
            print("No IMU connection to close")

    def set_template_values(self, template):
        #  "Default"
        if template == "Default":
            self.guiVariables(False)
            return
        # Templates:
        elif template == "Easy":
            self.builder.get_variable("timeDurationSP").set(90)
            self.builder.get_variable("horizontalSpeedSP").set(6)
            self.builder.get_variable("verticalSpeedSP").set(0)
            self.builder.get_variable("targetChangeSP").set(1.25)
            self.builder.get_variable("targetSizeSP").set("Large")


            self.builder.get_variable("timeDurationSM").set(90)
            self.builder.get_variable("horizontalSpeedSM").set(1900)
            self.builder.get_variable("verticalSpeedSM").set(0)
            self.builder.get_variable("targetChangeSM").set(1.25)
            self.builder.get_variable("targetSizeSM").set("Large")

            self.builder.get_variable("timeDurationOK").set(60)
            self.builder.get_variable("barSpeedOK").set(8)
            self.builder.get_variable("directionOK").set("Right")
            self.builder.get_variable("targetSizeOK").set("Large")

            self.builder.get_variable("timeDurationVOR").set(90)
            self.builder.get_variable("horizontalRangeVOR").set(1)
            self.builder.get_variable("verticalRangeVOR").set(0)
            self.builder.get_variable("targetChangeVOR").set(1.25)
            self.builder.get_variable("targetSizeVOR").set("Large")

            self.builder.get_variable("timeDurationVORS").set(90)
            self.builder.get_variable("horizontalRangeVORS").set(1)
            self.builder.get_variable("verticalRangeVORS").set(0)
            self.builder.get_variable("targetChangeVORS").set(1.25)
            self.builder.get_variable("targetSizeVORS").set("Large")

            self.builder.get_variable("timeDurationVP").set(90)
            self.builder.get_variable("horizontalRangeVP").set(5)
            self.builder.get_variable("targetStillVP").set(1.0)
            self.builder.get_variable("targetSizeVP").set("Large")

        elif template == "Medium":
            self.builder.get_variable("timeDurationSP").set(120)
            self.builder.get_variable("horizontalSpeedSP").set(14)
            self.builder.get_variable("verticalSpeedSP").set(8)
            self.builder.get_variable("targetChangeSP").set(1)
            self.builder.get_variable("targetSizeSP").set("Medium")

            self.builder.get_variable("timeDurationSM").set(120)
            self.builder.get_variable("horizontalSpeedSM").set(1900)
            self.builder.get_variable("verticalSpeedSM").set(1080)
            self.builder.get_variable("targetChangeSM").set(1)
            self.builder.get_variable("targetSizeSM").set("Medium")

            self.builder.get_variable("timeDurationOK").set(90)
            self.builder.get_variable("barSpeedOK").set(12)
            self.builder.get_variable("directionOK").set("Right")
            self.builder.get_variable("targetSizeOK").set("Large")

            self.builder.get_variable("timeDurationVOR").set(120)
            self.builder.get_variable("horizontalRangeVOR").set(1)
            self.builder.get_variable("verticalRangeVOR").set(0)
            self.builder.get_variable("targetChangeVOR").set(1.0)
            self.builder.get_variable("targetSizeVOR").set("Large")

            self.builder.get_variable("timeDurationVORS").set(120)
            self.builder.get_variable("horizontalRangeVORS").set(1)
            self.builder.get_variable("verticalRangeVORS").set(0)
            self.builder.get_variable("targetChangeVORS").set(1.0)
            self.builder.get_variable("targetSizeVORS").set("Large")

            self.builder.get_variable("timeDurationVP").set(120)
            self.builder.get_variable("horizontalRangeVP").set(10)
            self.builder.get_variable("targetStillVP").set(0.75)
            self.builder.get_variable("targetSizeVP").set("Large")

        elif template == "Hard":
            self.builder.get_variable("timeDurationSP").set(120)
            self.builder.get_variable("horizontalSpeedSP").set(18)
            self.builder.get_variable("verticalSpeedSP").set(14)
            self.builder.get_variable("targetChangeSP").set(0.75)
            self.builder.get_variable("targetSizeSP").set("Medium")

            self.builder.get_variable("timeDurationSM").set(120)
            self.builder.get_variable("horizontalSpeedSM").set(1900)
            self.builder.get_variable("verticalSpeedSM").set(1080)
            self.builder.get_variable("targetChangeSM").set(0.75)
            self.builder.get_variable("targetSizeSM").set("Medium")

            self.builder.get_variable("timeDurationOK").set(120)
            self.builder.get_variable("barSpeedOK").set(18)
            self.builder.get_variable("directionOK").set("Right")
            self.builder.get_variable("targetSizeOK").set("Medium")

            self.builder.get_variable("timeDurationVOR").set(120)
            self.builder.get_variable("horizontalRangeVOR").set(1)
            self.builder.get_variable("verticalRangeVOR").set(1)
            self.builder.get_variable("targetChangeVOR").set(0.75)
            self.builder.get_variable("targetSizeVOR").set("Medium")

            self.builder.get_variable("timeDurationVORS").set(120)
            self.builder.get_variable("horizontalRangeVORS").set(1)
            self.builder.get_variable("verticalRangeVORS").set(1)
            self.builder.get_variable("targetChangeVORS").set(0.75)
            self.builder.get_variable("targetSizeVORS").set("Medium")

            self.builder.get_variable("timeDurationVP").set(120)
            self.builder.get_variable("horizontalRangeVP").set(15)
            self.builder.get_variable("targetStillVP").set(0.5)
            self.builder.get_variable("targetSizeVP").set("Medium")

        elif template == "Very hard":
            self.builder.get_variable("timeDurationSP").set(180)
            self.builder.get_variable("horizontalSpeedSP").set(18)
            self.builder.get_variable("verticalSpeedSP").set(14)
            self.builder.get_variable("targetChangeSP").set(0.5)
            self.builder.get_variable("targetSizeSP").set("Small")

            self.builder.get_variable("timeDurationSM").set(180)
            self.builder.get_variable("horizontalSpeedSM").set(1900)
            self.builder.get_variable("verticalSpeedSM").set(1080)
            self.builder.get_variable("targetChangeSM").set(0.75)
            self.builder.get_variable("targetSizeSM").set("Small")

            self.builder.get_variable("timeDurationOK").set(120)
            self.builder.get_variable("barSpeedOK").set(20)
            self.builder.get_variable("directionOK").set("Right")
            self.builder.get_variable("targetSizeOK").set("Medium")

            self.builder.get_variable("timeDurationVOR").set(180)
            self.builder.get_variable("horizontalRangeVOR").set(1)
            self.builder.get_variable("verticalRangeVOR").set(1)
            self.builder.get_variable("targetChangeVOR").set(0.5)
            self.builder.get_variable("targetSizeVOR").set("Small")

            self.builder.get_variable("timeDurationVORS").set(180)
            self.builder.get_variable("horizontalRangeVORS").set(1)
            self.builder.get_variable("verticalRangeVORS").set(1)
            self.builder.get_variable("targetChangeVORS").set(0.5)
            self.builder.get_variable("targetSizeVORS").set("Small")

            self.builder.get_variable("timeDurationVP").set(180)
            self.builder.get_variable("horizontalRangeVP").set(15)
            self.builder.get_variable("targetStillVP").set(0.25)
            self.builder.get_variable("targetSizeVP").set("Small")

        self.guiVariables()

    def on_exit(self):
        self.isClosing = True
        if self.imuController is not None:
            self.safeIMUDisconnect()
        try:
            if self.mainwindow.winfo_exists():
                self.mainwindow.destroy()
        except tk.TclError:
            pass


    def run(self):
        self.loadConfig()
        try:
            if not self.mainwindow.winfo_exists():
                return
        except tk.TclError:
            return
        self.mainwindow.after(2000, self.loopEvents)
        try:
            self.mainwindow.protocol("WM_DELETE_WINDOW", self.on_exit)
        except tk.TclError:
            pass
        self.mainwindow.mainloop()

if __name__ == '__main__':
    app = visRV()
    app.run()
