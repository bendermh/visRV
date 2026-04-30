# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
import time
import random
from display_utils import fullscreen_mode


def vor(targetSize="L", imuController=None, vorTrain=True,
        vRange=True, hRange=True, timeChange=1,
        totalTime=120, monitor=0, calibTime=3.0):
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
        self.reverse = not vorTrain
        self.headPositionH = 90.0
        self.headPositionV = 90.0
        self.screenPositionH = self.screen.get_width() // 2
        self.screenPositionV = self.screen.get_height() // 2
        self.headRangeH = 45
        self.headRangeV = 30
        self.headRangeHEnable = hRange
        self.headRangeVEnable = vRange
        self.screenMaxH = self.screen.get_width()
        self.screenMaxV = self.screen.get_height()
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
        self.headPositionH = self.imu.head_position_h
        self.headPositionV = self.imu.head_position_v

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

    def setBias(self):
        """Recenter target position manually."""
        self.imu.set_bias()

    def angleToScreen(self, angle, angleMin, angleMax,
                      screenMin, screenMax, inverse=True):
        """Map head angle range to screen pixel coordinates."""
        if inverse:
            return round(screenMax - (screenMin + (float(angle - angleMin) /
                         float(angleMax - angleMin) * (screenMax - screenMin))))
        else:
            return round(screenMin + (float(angle - angleMin) /
                         float(angleMax - angleMin) * (screenMax - screenMin)))

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
    print("VOR exercise finished. Bye !")


if __name__ == "__main__":
    vor()
