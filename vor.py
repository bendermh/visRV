# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
import time
import random
import os
from display_utils import fullscreen_mode


HORIZONTAL_SCREEN_RANGE_DEGREES = 45
VERTICAL_SCREEN_RANGE_DEGREES = 20


def debug_enabled():
    value = os.environ.get("VISRV_VOR_DEBUG", "")
    return value.strip().lower() in ("1", "true", "yes", "on", "debug")


def vor(targetSize="L", imuController=None, vorTrain=True,
        vRange=True, hRange=True, timeChange=1,
        totalTime=120, monitor=0, calibTime=5.0):
    """Entry point for launching the VOR/VORS exercise."""
    if imuController is None or not getattr(imuController, "connected", False):
        print("VOR exercise needs an already connected IMU controller")
        return

    main(targetSize=targetSize, imuController=imuController, vorTrain=vorTrain,
         vRange=vRange, hRange=hRange, timeChange=timeChange,
         totalTime=totalTime, monitor=monitor, calibTime=calibTime)


class Target():
    """Target object controlled by IMU head movements."""

    def __init__(self, targetSize, imuController, vorTrain, vRange, hRange):
        self.screen = pg.display.get_surface()
        self.imu = imuController
        self.reverse = vorTrain
        self.headPositionH = 90.0
        self.headPositionV = 90.0
        self.screenPositionH = self.screen.get_width() // 2
        self.screenPositionV = self.screen.get_height() // 2
        self.headRangeH = HORIZONTAL_SCREEN_RANGE_DEGREES
        self.headRangeV = VERTICAL_SCREEN_RANGE_DEGREES
        self.headRangeHEnable = hRange
        self.headRangeVEnable = vRange
        self.screenMaxH = self.screen.get_width()
        self.screenMaxV = self.screen.get_height()
        self.center = (self.screen.get_width() // 2, self.screen.get_height() // 2)
        self.x = self.center[0]
        self.y = self.center[1]
        self.debugLog = debug_enabled()
        self.debugLogInterval = 0.20
        self.debugLastLog = 0.0
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

        if self.imu is not None:
            self.imu.reset_bias()

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
        rawHeadPositionH = self.imu.head_position_h
        rawHeadPositionV = self.imu.head_position_v
        self.headPositionH = rawHeadPositionH
        self.headPositionV = rawHeadPositionV

        self.headPositionH = max(90 - self.headRangeH,
                                 min(self.headPositionH, 90 + self.headRangeH))
        self.headPositionV = max(90 - self.headRangeV,
                                 min(self.headPositionV, 90 + self.headRangeV))

        if self.headRangeHEnable:
            self.screenPositionH = self.angleToScreen(
                self.headPositionH, (90 - self.headRangeH),
                (90 + self.headRangeH), 0, self.screenMaxH, self.reverse)
        if self.headRangeVEnable:
            self.screenPositionV = self.angleToScreen(
                self.headPositionV, (90 - self.headRangeV),
                (90 + self.headRangeV), 0, self.screenMaxV, not self.reverse)

        self.x = self.screenPositionH
        self.y = self.screenPositionV
        self.logDebug(rawHeadPositionH, rawHeadPositionV)

    def setBias(self, duration=0.0):
        """Recenter target position manually."""
        self.imu.set_bias(duration=duration)

    def logDebug(self, rawHeadPositionH, rawHeadPositionV):
        """Print IMU input and screen mapping at a readable cadence."""
        if not self.debugLog:
            return

        now = time.time()
        if now - self.debugLastLog < self.debugLogInterval:
            return
        self.debugLastLog = now

        euler = getattr(self.imu, "euler", None)
        quaternion = getattr(self.imu, "quaternion", None)
        yaw = getattr(euler, "yaw", None)
        pitch = getattr(euler, "pitch", None)
        roll = getattr(euler, "roll", None)
        print(
            "VOR_DEBUG "
            f"qw={self.formatDebug(getattr(quaternion, 'w', None))} "
            f"qx={self.formatDebug(getattr(quaternion, 'x', None))} "
            f"qy={self.formatDebug(getattr(quaternion, 'y', None))} "
            f"qz={self.formatDebug(getattr(quaternion, 'z', None))} "
            f"yaw={self.formatDebug(yaw)} "
            f"pitch={self.formatDebug(pitch)} "
            f"roll={self.formatDebug(roll)} "
            f"biasH={self.formatDebug(getattr(self.imu, 'bias_h', None))} "
            f"biasV={self.formatDebug(getattr(self.imu, 'bias_v', None))} "
            f"horizontalDelta={self.formatDebug(getattr(self.imu, 'horizontal_yaw_delta', None))} "
            f"verticalDelta={self.formatDebug(getattr(self.imu, 'vertical_delta', None))} "
            f"tiltDelta={self.formatDebug(getattr(self.imu, 'tilt_delta', None))} "
            f"rawH={self.formatDebug(rawHeadPositionH)} "
            f"rawV={self.formatDebug(rawHeadPositionV)} "
            f"clampH={self.formatDebug(self.headPositionH)} "
            f"clampV={self.formatDebug(self.headPositionV)} "
            f"screenH={self.screenPositionH} "
            f"screenV={self.screenPositionV} "
            f"hEnabled={self.headRangeHEnable} "
            f"vEnabled={self.headRangeVEnable} "
            f"reverse={self.reverse}")

    def formatDebug(self, value):
        if value is None:
            return "--"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    def angleToScreen(self, angle, angleMin, angleMax,
                      screenMin, screenMax, inverse=True):
        """Map head angle range to screen pixel coordinates."""
        if inverse:
            return round(screenMax - (screenMin + (float(angle - angleMin) /
                         float(angleMax - angleMin) * (screenMax - screenMin))))
        else:
            return round(screenMin + (float(angle - angleMin) /
                         float(angleMax - angleMin) * (screenMax - screenMin)))


INITIAL_BIAS_DURATION = 1.5
MANUAL_BIAS_DURATION = 0.35


def main(targetSize, imuController, vorTrain, vRange, hRange,
         timeChange, totalTime, monitor, calibTime):
    """Main game loop for VOR/VORS exercise."""
    pg.init()
    screen = fullscreen_mode(monitor)
    screen.fill(color=(0, 0, 0))
    fps = 60
    pg.mouse.set_visible(False)

    background = pg.Surface(screen.get_size())
    background = background.convert()
    background.fill((0, 0, 0))
    screen.blit(background, (0, 0))

    vorGame = Target(targetSize, imuController, vorTrain, vRange, hRange)

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
                    vorGame.setBias(duration=MANUAL_BIAS_DURATION)
            if event.type == TEXTCHANGE_EVENT:
                vorGame.changeText()

        screen.blit(background, (0, 0))

        # Calibration phase
        if not calibrated:
            pg.draw.circle(screen, (255, 255, 255),
                           fixation_circle, fixation_radius)
            screen.blit(text, textRect)
            if time.time() - calibStart >= calibTime:
                vorGame.setBias(duration=INITIAL_BIAS_DURATION)
                calibrated = True
        else:
            vorGame.move()
            vorGame.drawTarget()

        pg.display.flip()

    pg.quit()
    print("VOR exercise finished. Bye !")


if __name__ == "__main__":
    vor()
