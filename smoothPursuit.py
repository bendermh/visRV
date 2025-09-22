# -*- coding: utf-8 -*-
"""
Smooth pursuit exercise for visRV
Author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
import random


def smoothPursuit(targetSize="S", x_vel=8, y_vel=2,
                  timeChange=1, totalTime=120, monitor=0,
                  variationRange=0.15):
    # Check monitor availability
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0. Detected monitors: " +
              str(pg.display.get_num_displays()))

    main(targetSize=targetSize, x_vel=x_vel, y_vel=y_vel,
         timeChange=timeChange, totalTime=totalTime,
         monitor=monitor, variationRange=variationRange)


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
        self.center = (self.x, self.y)
        pg.draw.circle(self.screen, (255, 255, 255),
                       self.center, self.radius, width=self.border)
        self.labelPos.center = self.center
        self.screen.blit(self.label, self.labelPos)

    def move(self, vx, vy, base_x_vel, base_y_vel, variationRange):
        min_speed = 1.5  # minimum velocity to avoid sticking at borders

        hitX = (self.x - self.radius) <= 0 or (self.x + self.radius) >= self.screen.get_width()
        hitY = (self.y - self.radius) <= 0 or (self.y + self.radius) >= self.screen.get_height()

        if hitX:
            self.dirX *= -1
            if base_x_vel != 0 and base_y_vel != 0:
                factor_x = random.uniform(1 - variationRange, 1 + variationRange)
                vx = max(abs(base_x_vel * factor_x), min_speed) * (1 if vx >= 0 else -1)

        if hitY:
            self.dirY *= -1
            if base_x_vel != 0 and base_y_vel != 0:
                factor_y = random.uniform(1 - variationRange, 1 + variationRange)
                vy = max(abs(base_y_vel * factor_y), min_speed) * (1 if vy >= 0 else -1)

        self.x += self.dirX * vx
        self.y += self.dirY * vy

        return vx, vy

    def changeText(self):
        self.currentText = random.choice(self.targetList)
        self.label = self.font.render(self.currentText, True, (255, 255, 255))
        self.labelPos = self.label.get_rect()
        self.labelPos.center = (self.x, self.y)
        print("Target: " + self.currentText)


def main(targetSize="S", x_vel=8, y_vel=2,
         timeChange=1, totalTime=120, monitor=0,
         variationRange=0.2):
    pg.init()
    screen = pg.display.set_mode(
        size=(1920, 1080),
        flags=pg.FULLSCREEN | pg.NOFRAME | pg.DOUBLEBUF,
        display=monitor,
        vsync=1
    )
    fps = 120  # higher refresh for smoother motion
    pg.mouse.set_visible(False)

    # Prepare target
    game_target = Target(targetSize)

    # Store base velocities
    base_x_vel = x_vel
    base_y_vel = y_vel

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
            x_vel, y_vel, base_x_vel, base_y_vel, variationRange)
        game_target.draw()

        # Print position every frame
        #print(f"Position: X={game_target.x}, Y={game_target.y}")

        pg.display.flip()

    pg.quit()
    print("Smooth pursuit exercise finished. Bye!")


# For standalone testing
if __name__ == "__main__":
    smoothPursuit()
