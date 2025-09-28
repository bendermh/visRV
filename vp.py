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


def vp(targetSize="L", macIMU="C7:0F:6B:58:F9:CB", vorTrain=False,
       hRange=10, timeStill=0.5, totalTime=120, monitor=0,
       tolerance=2, direction="out", calibTime=3.0):
    """Entry point for launching VP exercise (horizontal)."""
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, auto-reset to 0. Detected monitors: " +
              str(pg.display.get_num_displays()))
    main(targetSize=targetSize, mac=macIMU, vorTrain=vorTrain,
         hRange=hRange, timeStill=timeStill, totalTime=totalTime,
         monitor=monitor, tolerance=tolerance, direction=direction,
         calibTime=calibTime)


class Target():
    def __init__(self, targetSize, mac, vorTrain, hRange):
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
        self.prev_headPositionH = 90.0
        self.biasH = 0
        self.biasV = 0
        self.samplingInterval = 0.01
        self.timeIMUSetup = 2.1
        self.screenPositionH = self.screen.get_width() // 2
        self.screenPositionV = self.screen.get_height() // 2
        self.headRangeH = hRange
        self.screenMaxH = self.screen.get_width()
        self.screenMaxV = self.screen.get_height()
        self.timeConnect = time.time()
        self.timeLast = time.time()
        self.center = (self.screen.get_width() // 2,
                       self.screen.get_height() // 2)
        self.x = self.center[0]
        self.y = self.center[1]
        self.targetList = [
            "A", "D", "E", "F", "H", "J", "K", "L",
            "N", "P", "R", "S", "T", "V", "W", "X", "Y", "Z"
        ]
        self.currentText = random.choice(self.targetList)

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
            self.isConnected = True
            print("IMU connected, setting up")
            self.configureIMU()
        except Exception:
            self.isConnected = False
            print("IMU connection error")

    def checkHead(self, background, timeStill, show_target,
                  show_target_until, tolerance=2, direction="out"):
        """Check head position and show target when crossing threshold."""
        if self.headRangeH > 0:
            targetH = 90 + self.headRangeH
        else:
            targetH = 90 - abs(self.headRangeH)

        collision = False
        if targetH != 90:
            if self.headRangeH > 0:
                # Right side
                if direction == "in":
                    if (self.prev_headPositionH < (targetH - tolerance)) and \
                       (self.headPositionH >= (targetH - tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True
                else:  # "out"
                    if (self.prev_headPositionH > (targetH + tolerance)) and \
                       (self.headPositionH <= (targetH + tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True
            elif self.headRangeH < 0:
                # Left side
                if direction == "in":
                    if (self.prev_headPositionH > (targetH + tolerance)) and \
                       (self.headPositionH <= (targetH + tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True
                else:  # "out"
                    if (self.prev_headPositionH < (targetH - tolerance)) and \
                       (self.headPositionH >= (targetH - tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True

        now = time.time()
        if collision:
            show_target[0] = True
            show_target_until[0] = now + timeStill
        if show_target[0] and now < show_target_until[0]:
            self.drawTarget()
        elif show_target[0] and now >= show_target_until[0]:
            show_target[0] = False

        self.prev_headPositionH = self.headPositionH

    def drawTarget(self):
        """Draw target circle + letter."""
        self.center = (self.x, self.y)
        pg.draw.circle(self.screen, (255, 255, 255),
                       self.center, self.radius, width=self.border)
        font = pg.font.SysFont(None, self.typeSize, bold=True)
        label = font.render(self.currentText, True, (255, 255, 255))
        labelPos = label.get_rect()
        labelPos.center = self.center
        self.screen.blit(label, labelPos)

    def setBias(self):
        """Manual recenter (space key)."""
        self.biasH += 90 - self.headPositionH
        self.biasV += 90 - self.headPositionV

    def configureIMU(self):
        """Setup IMU and start streaming."""
        print("Setting up IMU...")
        libmetawear.mbl_mw_settings_set_connection_parameters(
            self.imuDevice.board, 7.5, 7.5, 0, 6000)
        time.sleep(1.5)
        libmetawear.mbl_mw_sensor_fusion_set_mode(
            self.imuDevice.board, SensorFusionMode.NDOF)
        libmetawear.mbl_mw_sensor_fusion_set_acc_range(
            self.imuDevice.board, SensorFusionAccRange._2G)
        libmetawear.mbl_mw_sensor_fusion_set_gyro_range(
            self.imuDevice.board, SensorFusionGyroRange._2000DPS)
        libmetawear.mbl_mw_sensor_fusion_write_config(self.imuDevice.board)
        time.sleep(0.5)
        self.signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(
            self.imuDevice.board, SensorFusionData.EULER_ANGLE)
        libmetawear.mbl_mw_datasignal_subscribe(self.signal, None, self.readIMU)
        libmetawear.mbl_mw_sensor_fusion_enable_data(
            self.imuDevice.board, SensorFusionData.EULER_ANGLE)
        libmetawear.mbl_mw_sensor_fusion_start(self.imuDevice.board)
        print("IMU setup done.")
        time.sleep(0.5)

    def streamIMU(self, ctx, data):
        """Update head angles from IMU."""
        timeNow = time.time()
        if (timeNow - self.timeLast) > self.samplingInterval:
            if self.isConnected:
                if (self.timeLast - self.timeConnect) > self.timeIMUSetup:
                    euler = parse_value(data)
                    self.sample = ((self.timeLast - self.timeConnect) -
                                   self.timeIMUSetup, euler)
            self.timeLast = time.time()
            self.headPositionH = round(self.sample[1].yaw + 90.0)
            self.headPositionV = round(self.sample[1].pitch * -1)
            if self.headPositionH > 360:
                self.headPositionH -= 360
            self.headPositionH += self.biasH
            self.headPositionV += self.biasV

    def safeIMUDisconnect(self):
        """Safe IMU disconnect."""
        if self.isConnected:
            print("Closing IMU connection...")
            libmetawear.mbl_mw_sensor_fusion_stop(self.imuDevice.board)
            libmetawear.mbl_mw_datasignal_unsubscribe(self.signal)
            time.sleep(0.5)
            self.imuDevice.disconnect()
            time.sleep(3)
            self.isConnected = False
            print("IMU connection closed")
        else:
            print("No IMU connection to close")


def main(targetSize, mac, vorTrain, hRange, timeStill,
         totalTime, monitor, tolerance=2, direction="out",
         calibTime=3.0):
    """Main loop for VP exercise."""
    pg.init()
    screen = pg.display.set_mode(size=(1920, 1080),
                                 flags=pg.FULLSCREEN | pg.NOFRAME | pg.DOUBLEBUF,
                                 display=monitor, vsync=1)
    screen.fill((0, 0, 0))
    fps = 60
    pg.mouse.set_visible(False)

    background = pg.Surface(screen.get_size()).convert()
    background.fill((0, 0, 0))
    screen.blit(background, (0, 0))

    vpGame = Target(targetSize, mac, vorTrain, hRange)

    # Initial fixation screen
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

    show_target = [False]
    show_target_until = [0]

    try:
        while going:
            clock.tick(fps)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    going = False
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_ESCAPE:
                        going = False
                    if event.key == pg.K_SPACE:
                        vpGame.setBias()
                    if event.key == pg.K_r:
                        vpGame.headRangeH = -vpGame.headRangeH
                        print(f"Direction reversed: {vpGame.headRangeH}")

            screen.blit(background, (0, 0))

            if not calibrated:
                # Calibration phase (IMU still streaming)
                pg.draw.circle(screen, (255, 255, 255),
                               fixation_circle, fixation_radius)
                screen.blit(text, textRect)
                if time.time() - calibStart >= calibTime:
                    vpGame.setBias()
                    calibrated = True
            else:
                # Normal target logic
                vpGame.checkHead(background, timeStill,
                                 show_target, show_target_until,
                                 tolerance=tolerance, direction=direction)

            pg.display.flip()
    finally:
        pg.quit()
        vpGame.safeIMUDisconnect()
        print("Exercise finished. Bye!")


if __name__ == "__main__":
    vp()
