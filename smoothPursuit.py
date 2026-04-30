# -*- coding: utf-8 -*-
"""
Smooth pursuit exercise for visRV
Author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
import random
from display_utils import fullscreen_mode


def varied_speed(base_speed, variationUnits):
    """Return a subtle speed variation around the configured base speed."""
    base_speed = abs(float(base_speed))
    if base_speed == 0:
        return 0

    low, high = sorted(variationUnits)
    if high <= 1:
        delta = base_speed * random.uniform(low, high)
    else:
        delta = random.uniform(low, high)

    return max(base_speed + random.choice([-delta, delta]), 0.1)


def smoothPursuit(targetSize="S", x_vel=8, y_vel=2,
                  timeChange=1, totalTime=120, monitor=0,
                  variationUnits=(0.10, 0.15), changeProb=0.6):
    main(targetSize=targetSize, x_vel=x_vel, y_vel=y_vel,
         timeChange=timeChange, totalTime=totalTime,
         monitor=monitor, variationUnits=variationUnits,
         changeProb=changeProb)


class Target:
    def __init__(self, targetSize):
        self.screen = pg.display.get_surface()
        self.targetList = ["A", "D", "E", "F", "H", "J", "K", "L",
                           "N", "P", "R", "S", "T", "V", "W", "X", "Y", "Z"]

        self.currentText = random.choice(self.targetList)
        self.center = (self.screen.get_width() // 2,
                       self.screen.get_height() // 2)
        self.x = self.center[0]
        self.y = self.center[1]
        self.dirX = 1
        self.dirY = 1

        # Select size parameters depending on targetSize
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

        # Create font once and cache text surface
        self.font = pg.font.SysFont(None, self.typeSize, bold=True)
        self.label = self.font.render(self.currentText, True, (255, 255, 255))
        self.labelPos = self.label.get_rect()
        self.labelPos.center = self.center

    def draw(self):
        """Draw circle and letter on screen."""
        self.center = (self.x, self.y)
        pg.draw.circle(self.screen, (255, 255, 255),
                       self.center, self.radius, width=self.border)
        self.labelPos.center = self.center
        self.screen.blit(self.label, self.labelPos)

    def bounce_axis(self, pos, speed, direction, min_pos, max_pos,
                    base_speed, variationUnits, changeProb):
        if speed == 0:
            return pos, speed, direction

        next_pos = pos + direction * speed
        if next_pos < min_pos:
            next_pos = min_pos
            direction = 1
            if random.random() < changeProb:
                speed = varied_speed(base_speed, variationUnits)
        elif next_pos > max_pos:
            next_pos = max_pos
            direction = -1
            if random.random() < changeProb:
                speed = varied_speed(base_speed, variationUnits)

        return next_pos, speed, direction

    def move(self, vx, vy, base_x_vel, base_y_vel, variationUnits, changeProb):
        """
        Update target position and handle wall collisions.

        vx, vy: current velocities
        base_x_vel, base_y_vel: original velocities from parameters
        variationUnits: fractional range by default (e.g. 0.10-0.15), or
                        absolute units if values are greater than 1
        changeProb: probability that speed changes on each rebound
        """
        min_x = self.radius
        max_x = self.screen.get_width() - self.radius
        min_y = self.radius
        max_y = self.screen.get_height() - self.radius

        self.x, vx, self.dirX = self.bounce_axis(
            self.x, vx, self.dirX, min_x, max_x,
            base_x_vel, variationUnits, changeProb)
        self.y, vy, self.dirY = self.bounce_axis(
            self.y, vy, self.dirY, min_y, max_y,
            base_y_vel, variationUnits, changeProb)

        return vx, vy

    def changeText(self):
        """Pick a new random letter for the target."""
        self.currentText = random.choice(self.targetList)
        self.label = self.font.render(self.currentText, True, (255, 255, 255))
        self.labelPos = self.label.get_rect()
        self.labelPos.center = (self.x, self.y)
        print("Target: " + self.currentText)


def main(targetSize="S", x_vel=8, y_vel=2,
         timeChange=1, totalTime=120, monitor=0,
         variationUnits=(0.10, 0.15), changeProb=0.6):
    pg.init()
    screen = fullscreen_mode(monitor)
    fps = 60  # high refresh rate for smooth motion
    pg.mouse.set_visible(False)

    # Prepare target
    game_target = Target(targetSize)

    # Store base velocities
    base_x_vel = abs(float(x_vel))
    base_y_vel = abs(float(y_vel))
    x_vel = base_x_vel
    y_vel = base_y_vel

    # Events
    TEXTCHANGE_EVENT = pg.USEREVENT + 1
    EXIT_EVENT = pg.USEREVENT + 2

    pg.time.set_timer(TEXTCHANGE_EVENT, int(timeChange * 1000))
    pg.time.set_timer(EXIT_EVENT, totalTime * 1000, 1)

    going = True
    clock = pg.time.Clock()
    while going:
        clock.tick(fps)

        for event in pg.event.get():
            if event.type == pg.QUIT or event.type == EXIT_EVENT:
                going = False
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                going = False
            if event.type == TEXTCHANGE_EVENT:
                game_target.changeText()

        # Clear screen
        screen.fill((0, 0, 0))

        # Move and draw
        x_vel, y_vel = game_target.move(
            x_vel, y_vel, base_x_vel, base_y_vel, variationUnits, changeProb)
        game_target.draw()

        pg.display.flip()

    pg.quit()
    print("Smooth pursuit exercise finished. Bye!")


# For standalone testing
if __name__ == "__main__":
    smoothPursuit()
