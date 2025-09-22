# -*- coding: utf-8 -*-
"""
Saccades exercise for visRV
Author: Jorge Rey-Martinez & HAL
"""

import pygame as pg
import random


def saccades(targetSize="M", x_vel=0, y_vel=1920,
             timeChange=1.0, totalTime=120, monitor=0):
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0. Detected monitors: " +
              str(pg.display.get_num_displays()))

    main(targetSize=targetSize, x_vel=x_vel, y_vel=y_vel,
         timeChange=timeChange, totalTime=totalTime, monitor=monitor)


class Target:
    def __init__(self, targetSize):
        self.screen = pg.display.get_surface()
        self.targetList = [
            "A", "D", "E", "F", "H", "J", "K", "L",
            "N", "P", "R", "S", "T", "V", "W", "X", "Y", "Z"
        ]
        self.currentText = random.choice(self.targetList)
        self.center = (self.screen.get_width() // 2,
                       self.screen.get_height() // 2)
        self.x = self.center[0]
        self.y = self.center[1]

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

        # Cache font and label
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

    def changeTarget(self, dis_x, dis_y):
        self.currentText = random.choice(self.targetList)
        self.label = self.font.render(self.currentText, True, (255, 255, 255))
        self.labelPos = self.label.get_rect()

        # Ensure target fully inside screen
        self.x = random.uniform(self.radius, dis_x - self.radius)
        self.y = random.uniform(self.radius, dis_y - self.radius)

        self.labelPos.center = (self.x, self.y)
        print("Target:", self.currentText)


def main(targetSize, x_vel, y_vel, timeChange, totalTime, monitor):
    pg.init()
    screen = pg.display.set_mode(
        size=(1920, 1080),
        flags=pg.FULLSCREEN | pg.NOFRAME | pg.DOUBLEBUF,
        display=monitor,
        vsync=1
    )
    fps = 60
    pg.mouse.set_visible(False)

    background = pg.Surface(screen.get_size()).convert()
    background.fill((0, 0, 0))

    game_target = Target(targetSize)

    going = True
    clock = pg.time.Clock()

    TEXTCHANGE_EVENT = pg.USEREVENT + 1
    EXIT_EVENT = pg.USEREVENT + 2

    pg.time.set_timer(TEXTCHANGE_EVENT, int(timeChange * 1000))
    pg.time.set_timer(EXIT_EVENT, totalTime * 1000, 1)

    while going:
        clock.tick(fps)

        for event in pg.event.get():
            if event.type == pg.QUIT or event.type == EXIT_EVENT:
                going = False
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                going = False
            if event.type == TEXTCHANGE_EVENT:
                game_target.changeTarget(screen.get_width(), screen.get_height())

        screen.blit(background, (0, 0))
        game_target.draw()
        pg.display.flip()

    pg.quit()
    print("Saccades exercise finished. Bye!")


# For standalone testing
if __name__ == "__main__":
    saccades()
