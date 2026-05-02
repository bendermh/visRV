# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:06:34 2024

@author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
import time
import random
from display_utils import fullscreen_mode


def vp(targetSize="L", imuController=None, vorTrain=False,
       hRange=10, timeStill=0.5, totalTime=120, monitor=0,
       tolerance=2, direction="out", calibTime=5.0):
    """Entry point for launching VP exercise (horizontal)."""
    if imuController is None or not getattr(imuController, "connected", False):
        print("VP exercise needs an already connected IMU controller")
        return

    main(targetSize=targetSize, imuController=imuController, vorTrain=vorTrain,
         hRange=hRange, timeStill=timeStill, totalTime=totalTime,
         monitor=monitor, tolerance=tolerance, direction=direction,
         calibTime=calibTime)


class Target():
    def __init__(self, targetSize, imuController, vorTrain, hRange):
        self.screen = pg.display.get_surface()
        self.imu = imuController
        self.reverse = vorTrain
        self.headPositionH = 90.0
        self.headPositionV = 90.0
        self.prev_headPositionH = 90.0
        self.screenPositionH = self.screen.get_width() // 2
        self.screenPositionV = self.screen.get_height() // 2
        self.headRangeH = hRange
        self.screenMaxH = self.screen.get_width()
        self.screenMaxV = self.screen.get_height()
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

        if self.imu is not None:
            self.imu.reset_bias()

    def checkHead(self, background, timeStill, show_target,
                  show_target_until, tolerance=2, direction="out"):
        """Check head position and show target when crossing threshold."""
        self.prev_headPositionH = self.headPositionH
        self.headPositionH = self.imu.head_position_h
        self.headPositionV = self.imu.head_position_v

        if self.headRangeH > 0:
            targetH = 90 + self.headRangeH
        else:
            targetH = 90 - abs(self.headRangeH)

        collision = False
        if targetH != 90:
            if self.headRangeH > 0:
                # Right side
                if direction == "out":
                    if (self.prev_headPositionH < (targetH - tolerance)) and \
                       (self.headPositionH >= (targetH - tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True
                else:  # "in"
                    if (self.prev_headPositionH > (targetH + tolerance)) and \
                       (self.headPositionH <= (targetH + tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True
            elif self.headRangeH < 0:
                # Left side
                if direction == "out":
                    if (self.prev_headPositionH > (targetH + tolerance)) and \
                       (self.headPositionH <= (targetH + tolerance)):
                        self.currentText = random.choice(self.targetList)
                        print("Target:", self.currentText)
                        collision = True
                else:  # "in"
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

    def setBias(self, duration=0.0):
        """Manual recenter (space key)."""
        self.imu.set_bias(duration=duration)


INITIAL_BIAS_DURATION = 1.5
MANUAL_BIAS_DURATION = 0.35


def main(targetSize, imuController, vorTrain, hRange, timeStill,
         totalTime, monitor, tolerance=2, direction="out",
         calibTime=4.0):
    """Main loop for VP exercise."""
    pg.init()
    screen = fullscreen_mode(monitor)
    screen.fill((0, 0, 0))
    fps = 60
    pg.mouse.set_visible(False)

    background = pg.Surface(screen.get_size()).convert()
    background.fill((0, 0, 0))
    screen.blit(background, (0, 0))

    vpGame = Target(targetSize, imuController, vorTrain, hRange)

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
                        vpGame.setBias(duration=MANUAL_BIAS_DURATION)
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
                    vpGame.setBias(duration=INITIAL_BIAS_DURATION)
                    calibrated = True
            else:
                # Normal target logic
                vpGame.checkHead(background, timeStill,
                                 show_target, show_target_until,
                                 tolerance=tolerance, direction=direction)

            pg.display.flip()
    finally:
        pg.quit()
        print("Exercise finished. Bye!")


if __name__ == "__main__":
    vp()
