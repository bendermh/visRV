# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
from mbientlab.metawear import MetaWear, libmetawear, parse_value
from mbientlab.metawear.cbindings import *
from mbientlab.warble import *
import time
import random


def vor(targetSize="L", macIMU="C7:0F:6B:58:F9:CB", vorTrain=True,
        vRange=True, hRange=True, timeChange=1,
        totalTime=120, monitor=0, calibTime=3.0):
    """Entry point for launching the VOR/VORS exercise."""
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0. Detected monitors: " +
              str(pg.display.get_num_displays()))

    main(targetSize=targetSize, mac=macIMU, vorTrain=vorTrain,
         vRange=vRange, hRange=hRange, timeChange=timeChange,
         totalTime=totalTime, monitor=monitor, calibTime=calibTime)


class Target():
    """Target object controlled by IMU head movements."""

    def __init__(self, targetSize, mac, vorTrain, vRange, hRange):
        self.screen = pg.display.get_surface()
        self.imuDevice = MetaWear(mac)
        self.readIMU = FnVoid_VoidP_DataP(self.streamIMU)
        self.reverse = vorTrain
        self.timeConnect = None
        self.timeLast = None
        self.signal = None
        self.sample = None
        self.headPositionH = 90.0
        self.headPositionV = 90.0
        self.biasH = 0
        self.biasV = 0
        self.samplingInterval = 0.01
        self.timeIMUSetup = 4.0
        self.screenPositionH = self.screen.get_width() // 2
        self.screenPositionV = self.screen.get_height() // 2
        self.headRangeH = 45
        self.headRangeV = 30
        self.headRangeHEnable = hRange
        self.headRangeVEnable = vRange
        self.screenMaxH = self.screen.get_width()
        self.screenMaxV = self.screen.get_height()
        self.timeConnect = time.time()
        self.timeLast = time.time()
        self.center = (self.screen.get_width() // 2, self.screen.get_height() // 2)
        self.x = self.center[0]
        self.y = self.center[1]
        # Extended list of letters (avoiding similar ones like O/Q/I/L)
        self.targetList = ["A", "D", "E", "F", "H", "J", "K", "L",
    "N", "P", "R", "S", "T", "V", "W", "X", "Y", "Z"]
        self.currentText = random.choice(self.targetList)

        # Target size presets
        match targetSize:
            case "S":
                self.typeSize = 32
                self.radius = 30
                self.border = 5
            case "M":
                self.typeSize = 62
                self.radius = 50
                self.border = 5
            case "L":
                self.typeSize = 98
                self.radius = 80
                self.border = 5
            case _:
                self.typeSize = 62
                self.radius = 50
                self.border = 5

        try:
            self.imuDevice.connect()
            time.sleep(3)
            self.isConected = True
            print("IMU connected, setting Up")
            self.configureIMU()
        except Exception:
            self.isConected = False
            print("IMU connection error")

    def drawTarget(self):
        """Draw current target (circle + letter)."""
        self.center = (self.x, self.y)
        pg.draw.circle(self.screen, (255, 255, 255),
                       self.center, self.radius, width=self.border)
        font = pg.font.SysFont(None, self.typeSize, bold=True)
        label = font.render(self.currentText, True, (255, 255, 255))
        labelPos = label.get_rect()
        labelPos.center = self.center
        self.screen.blit(label, labelPos)

    def changeText(self):
        """Change the current letter of the target."""
        self.currentText = random.choice(self.targetList)
        print("Target:", self.currentText)

    def move(self):
        """Update target position from IMU head positions."""
        self.x = self.screenPositionH
        self.y = self.screenPositionV

    def setBias(self):
        """Recenter target position manually."""
        self.biasH += 90 - self.headPositionH
        self.biasV += 90 - self.headPositionV

    def configureIMU(self):
        """Configure and start IMU streaming."""
        print("Setting up IMU...")
        # Optimize connection
        libmetawear.mbl_mw_settings_set_connection_parameters(
            self.imuDevice.board, 7.5, 7.5, 0, 6000)
    
        # Configure fusion mode and ranges
        libmetawear.mbl_mw_sensor_fusion_set_mode(
            self.imuDevice.board, SensorFusionMode.IMU_PLUS)
        libmetawear.mbl_mw_sensor_fusion_set_acc_range(
            self.imuDevice.board, SensorFusionAccRange._4G)
        libmetawear.mbl_mw_sensor_fusion_set_gyro_range(
            self.imuDevice.board, SensorFusionGyroRange._2000DPS)
        libmetawear.mbl_mw_sensor_fusion_write_config(self.imuDevice.board)
    
        # Subscribe to Euler angle data
        self.signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(
            self.imuDevice.board, SensorFusionData.EULER_ANGLE)
        libmetawear.mbl_mw_datasignal_subscribe(self.signal, None, self.readIMU)
    
        # Start fusion
        libmetawear.mbl_mw_sensor_fusion_enable_data(
            self.imuDevice.board, SensorFusionData.EULER_ANGLE)
        libmetawear.mbl_mw_sensor_fusion_start(self.imuDevice.board)
    
        # Short delay to let data stream stabilize
        time.sleep(1.0)
        print("IMU setup done.")

    def streamIMU(self, ctx, data):
        """Stream IMU euler angles and map them to screen coordinates."""
        timeNow = time.time()
        if (timeNow - self.timeLast) > self.samplingInterval:
            if self.isConected:
                if (self.timeLast - self.timeConnect) > self.timeIMUSetup:
                    euler = parse_value(data)
                    self.sample = ((self.timeLast - self.timeConnect) - self.timeIMUSetup, euler)
            self.timeLast = time.time()

            self.headPositionH = round(self.sample[1].yaw + 90.0)
            self.headPositionV = round(self.sample[1].pitch * -1 + 90.0)

            if self.headPositionH > 360:
                self.headPositionH -= 360

            self.headPositionH += self.biasH
            self.headPositionV += self.biasV

            # Clamp head positions
            self.headPositionH = max(90 - self.headRangeH,
                                     min(self.headPositionH, 90 + self.headRangeH))
            self.headPositionV = max(90 - self.headRangeV,
                                     min(self.headPositionV, 90 + self.headRangeV))

            # Map head position to screen coordinates
            if self.headRangeHEnable:
                self.screenPositionH = self.angleToScreen(
                    self.headPositionH, (90 - self.headRangeH),
                    (90 + self.headRangeH), 0, self.screenMaxH, self.reverse)
            if self.headRangeVEnable:
                self.screenPositionV = self.angleToScreen(
                    self.headPositionV, (90 - self.headRangeV),
                    (90 + self.headRangeV), 0, self.screenMaxV, not self.reverse)

    def angleToScreen(self, angle, angleMin, angleMax,
                      screenMin, screenMax, inverse=True):
        """Map head angle range to screen pixel coordinates."""
        if inverse:
            return round(screenMax - (screenMin + (float(angle - angleMin) /
                         float(angleMax - angleMin) * (screenMax - screenMin))))
        else:
            return round(screenMin + (float(angle - angleMin) /
                         float(angleMax - angleMin) * (screenMax - screenMin)))

    def safeIMUDisconnect(self):
        """Safely stop and disconnect the IMU."""
        if self.isConected:
            print("Closing IMU connection...")
            libmetawear.mbl_mw_sensor_fusion_stop(self.imuDevice.board)
            libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)
            time.sleep(0.5)
            self.imuDevice.disconnect()
            time.sleep(3)
            self.isConected = False
            print("IMU connection closed")
        else:
            print("No IMU connection to close")


def main(targetSize, mac, vorTrain, vRange, hRange,
         timeChange, totalTime, monitor, calibTime):
    """Main game loop for VOR/VORS exercise."""
    pg.init()
    screen = pg.display.set_mode(
        size=(1920, 1080),
        flags=pg.FULLSCREEN | pg.NOFRAME | pg.DOUBLEBUF,
        display=monitor,
        vsync=1
    )
    screen.fill(color=(0, 0, 0))
    fps = 60
    pg.mouse.set_visible(False)

    background = pg.Surface(screen.get_size())
    background = background.convert()
    background.fill((0, 0, 0))
    screen.blit(background, (0, 0))

    vorGame = Target(targetSize, mac, vorTrain, vRange, hRange)

    # Initial fixation message
    font = pg.font.SysFont(None, 72, bold=True)
    text = font.render("Look at front", True, (255, 255, 255))
    textRect = text.get_rect(center=(screen.get_width() // 2,
                                     screen.get_height() // 2 + 100))
    fixation_circle = (screen.get_width() // 2, screen.get_height() // 2)
    fixation_radius = 20

    calibStart = time.time()
    calibrated = False

    going = True
    clock = pg.time.Clock()
    pg.time.set_timer(pg.QUIT, (totalTime * 1000), 1)
    TEXTCHANGE_EVENT = pg.USEREVENT + 1
    pg.time.set_timer(TEXTCHANGE_EVENT, (round(timeChange * 10) * 100))

    while going:
        clock.tick(fps)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                going = False
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    going = False
                if event.key == pg.K_SPACE:
                    vorGame.setBias()
            if event.type == TEXTCHANGE_EVENT:
                vorGame.changeText()

        screen.blit(background, (0, 0))

        # Calibration phase
        if not calibrated:
            pg.draw.circle(screen, (255, 255, 255),
                           fixation_circle, fixation_radius)
            screen.blit(text, textRect)
            if time.time() - calibStart >= calibTime:
                vorGame.setBias()
                calibrated = True
        else:
            vorGame.move()
            vorGame.drawTarget()

        pg.display.flip()

    pg.quit()
    vorGame.safeIMUDisconnect()
    print("VOR exercise finished. Bye !")


if __name__ == "__main__":
    vor()
