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
from PIL import Image, ImageTk
from mbientlab.metawear import MetaWear, libmetawear, parse_value
from mbientlab.metawear.cbindings import *
from mbientlab.warble import *
import six
import collections
import numpy as np
from scipy.spatial.transform import Rotation
import smoothPursuit
import saccades
import okn
import vor
import vp


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
        self.startSPButton = builder.get_object("spStartButton")
        self.startSMButton = builder.get_object("smStartButton")
        self.startOKButton = builder.get_object("okStartButton")
        self.startVORButton = builder.get_object("vorStartButton")
        self.startVORSButton = builder.get_object("vorsStartButton")
        self.startVPButton = builder.get_object("vpStartButton")
        # IMU Callback
        self.readIMU = FnVoid_VoidP_DataP(self.streamIMU)

        # Other variables
        self.imuMac = ""
        self.canConnect = False
        self.isIMUConected = False
        self.delayEvents = 150
        self.imuDevice = None
        self.signal = None
        self.rawSample = None
        self.sample = None
        self.timeZero = time.time()
        self.timeRecord = None
        self.timeConnect = None
        self.timeNow = None
        self.timeLast = None
        self.samplingInterval = 0.01
        self.timeIMUSetup = 2.1
        self.livePlotBuffer = 500
        self.lPlotYmin = -360
        self.lPlotYmax = 360
        self.plotLiveTime = collections.deque(np.zeros(self.livePlotBuffer))
        self.plotLiveX = collections.deque(np.zeros(self.livePlotBuffer))
        self.plotLiveY = collections.deque(np.zeros(self.livePlotBuffer))
        self.plotLiveZ = collections.deque(np.zeros(self.livePlotBuffer))

        # Load images
        aux = Image.open(PROJECT_IMU_PIC)
        self.imuImg = ImageTk.PhotoImage(aux)
        self.imuCanvas.create_image(4, 4, image=self.imuImg, anchor="nw")

        # Set & get GUI variables
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
        }
        builder.connect_callbacks(callbacks)

        # Scan for devices
        BleScanner.start()
        time.sleep(2.0)
        BleScanner.stop()

    # (rest of tu clase se queda igual)
    # ...

        
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
        
        self.timeDurationVOR = self.builder.get_variable("timeDurationVOR").get()
        self.horizontalRangeVOR = self.builder.get_variable("horizontalRangeVOR").get()
        self.verticalRangeVOR = self.builder.get_variable("verticalRangeVOR").get()
        self.targetChangeVOR = self.builder.get_variable("targetChangeVOR").get()
        
        self.timeDurationVORS = self.builder.get_variable("timeDurationVORS").get()
        self.horizontalRangeVORS = self.builder.get_variable("horizontalRangeVORS").get()
        self.verticalRangeVORS = self.builder.get_variable("verticalRangeVORS").get()
        self.targetChangeVORS = self.builder.get_variable("targetChangeVORS").get()
        
        self.timeDurationVP = self.builder.get_variable("timeDurationVP").get()
        self.horizontalRangeVP = (self.builder.get_variable("horizontalRangeVP").get())*-1 #IMU direction appear to be inverted in vp module
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
        okn.okn(self.targetSizeOK, self.barSpeedOK,self.directionOK[0], self.timeDurationOK, self.monitorSelected)
        self.mainwindow.deiconify()
        
    def startVOR(self):
        if self.isIMUConected:
            self.guiVariables()
            self.safeIMUDisconnect()
            self.mainwindow.withdraw()
            vor.vor(self.targetSizeVOR,self.imuMac,True,self.verticalRangeVOR,self.horizontalRangeVOR,self.targetChangeVOR,self.timeDurationVOR,self.monitorSelected)
            time.sleep(2)
            self.mainwindow.deiconify()
            self.canConnect = True
            time.sleep(2)
            self.connectIMU()
        else:
            messagebox.showinfo("Warning", "Unable to connec to with IMU, try to connect or setup a new IMU")
            
    def startVORS(self):
         if self.isIMUConected:
             self.guiVariables()
             self.safeIMUDisconnect()
             self.mainwindow.withdraw()
             vor.vor(self.targetSizeVORS,self.imuMac,False,self.verticalRangeVORS,self.horizontalRangeVORS,self.targetChangeVORS,self.timeDurationVORS,self.monitorSelected)
             time.sleep(2)
             self.mainwindow.deiconify()
             self.canConnect = True
             time.sleep(2)
             self.connectIMU()
         else:
             messagebox.showinfo("Warning", "Unable to connec to with IMU, try to connect or setup a new IMU")
    
    def startVP(self):
         if self.isIMUConected:
             self.guiVariables()
             self.safeIMUDisconnect()
             self.mainwindow.withdraw()
             vp.vp(self.targetSizeVP,self.imuMac,False,self.horizontalRangeVP,self.targetStillVP,self.timeDurationVP,self.monitorSelected)
             time.sleep(2)
             self.mainwindow.deiconify()
             self.canConnect = True
             time.sleep(2)
             self.connectIMU()
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
                self.mainwindow.destroy()
                devSel = deviceSelect.deviceSelect()
                devSel.reloadMain = True
                devSel.run()
            
    def connectIMU(self):
        if self.canConnect:
            self.imuDevice = MetaWear(self.imuMac)
            try:
                self.imuDevice.connect()
            except:
                print("IMU connection error")
            time.sleep(2.5)
            self.canConnect = False
            if self.imuDevice.is_connected:
                print("IMU connected")
                self.scanButton.state(["disabled"])
                self.connectButton.state(["disabled"])
                self.isIMUConected = True
                self.configureIMU()
            else:
                print("IMU is NOT connected")
                self.isIMUConected = False
                self.canConnect = True
                messagebox.showinfo("Warning", "Unable to connec to with IMU, try wake up or pair again current IMU, revise IMU battery level")
                
        else:
            print("IMU is already connected")
    
    def configureIMU(self):
        if self.imuDevice.is_connected:
            self.timeConnect = time.time() 
            self.timeLast = time.time()
            print("Setting up IMU...")
            # confiure connection
            libmetawear.mbl_mw_settings_set_connection_parameters(self.imuDevice.board, 7.5, 7.5, 0, 6000)
            time.sleep(1.5)
            # setup quaternion
            libmetawear.mbl_mw_sensor_fusion_set_mode(self.imuDevice.board, SensorFusionMode.NDOF);
            libmetawear.mbl_mw_sensor_fusion_set_acc_range(self.imuDevice.board, SensorFusionAccRange._8G)
            libmetawear.mbl_mw_sensor_fusion_set_gyro_range(self.imuDevice.board, SensorFusionGyroRange._2000DPS)
            libmetawear.mbl_mw_sensor_fusion_write_config(self.imuDevice.board)
            time.sleep(0.5)
            # get quat signal and subscribe
            self.signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(self.imuDevice.board, SensorFusionData.QUATERNION);
            libmetawear.mbl_mw_datasignal_subscribe(self.signal, None, self.readIMU)
            # start acc, gyro, mag
            libmetawear.mbl_mw_sensor_fusion_enable_data(self.imuDevice.board, SensorFusionData.QUATERNION);
            libmetawear.mbl_mw_sensor_fusion_start(self.imuDevice.board);
            print("IMU setup done.")
            time.sleep(0.25)

    
    def resetIMU(self):
        answer = messagebox.askokcancel("Be aware","Reset procedure will lost IMU callibration, do not continue if you do not know to callibrate the IMU. Do you want to continue ?")
        if not answer:
            return
        
        if self.isIMUConected:
            answer = messagebox.askokcancel("Be aware","Reset procedure will close the program and data will be lost. Do you want to continue ?")
            if answer:
                print("Erase logger, state, and macros")
                self.isIMUConected = False
                # stop
                libmetawear.mbl_mw_sensor_fusion_stop(self.imuDevice.board)
                libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)
                time.sleep(0.5)
                #reset procedure
                libmetawear.mbl_mw_logging_stop(self.imuDevice.board)
                # Clear the logger of saved entries
                libmetawear.mbl_mw_logging_clear_entries(self.imuDevice.board)
                # Remove all macros on the flash memory
                libmetawear.mbl_mw_macro_erase_all(self.imuDevice.board)
                # Restarts the board after performing garbage collection
                libmetawear.mbl_mw_debug_reset_after_gc(self.imuDevice.board)
                libmetawear.mbl_mw_debug_disconnect(self.imuDevice.board)
                print("IMU reseted, app will close")
                time.sleep(10)
                self.imuDevice.disconnect()
                self.mainwindow.destroy()
        else:
            print("No IMU, no reset, man")
                    

    
    def streamIMU(self, ctx, data):
        self.timeNow = time.time()
        if (self.timeNow-self.timeLast) > self.samplingInterval: 
            if self.isIMUConected:
                if (self.timeLast-self.timeConnect) > self.timeIMUSetup: # add a little delay to stream data to avoid setup empty samples
                    self.rawSample = parse_value(data)
                    euler = self.quat_to_euler(self.rawSample.w,self.rawSample.x, self.rawSample.y,self.rawSample.z)
                    self.sample = ((self.timeLast-self.timeConnect)-self.timeIMUSetup,euler)
            self.timeLast = time.time()
        
    def quat_to_euler(self, w, x, y, z):
        quater = [x,y,z,w]
        rot = Rotation.from_quat(quater)
        euler = rot.as_euler('xyz', degrees = True)
        return euler
    
    def loopEvents(self):
        #print("Event " + str(time.localtime().tm_sec))
        if self.isIMUConected:
            self.imuCanvas.configure(bg='green')
        else:
            self.imuCanvas.configure(bg='red')
        self.mainwindow.after(self.delayEvents, self.loopEvents)
    
    def safeIMUDisconnect(self):            
        if not self.imuDevice is None:
                print("Closing IMU connection...")
                #stop
                libmetawear.mbl_mw_sensor_fusion_stop(self.imuDevice.board)
                libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)
                time.sleep(0.5)
                # disconnect
                self.imuDevice.disconnect()
                time.sleep(3)
                self.isIMUConected = False
                print("IMU connection closed")
                
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
        if self.isIMUConected:
            self.safeIMUDisconnect()
        try:
            if self.mainwindow.winfo_exists():
                self.mainwindow.destroy()
        except tk.TclError:
            pass

        
    def run(self):
        self.loadConfig()
        self.mainwindow.after(2000, self.loopEvents)
        try:
            self.mainwindow.protocol("WM_DELETE_WINDOW", self.on_exit)
        except tk.TclError:
            pass
        self.mainwindow.mainloop()

if __name__ == '__main__':
    app = visRV()
    app.run()