# -*- coding: utf-8 -*-
"""
OKN exercise for visRV
Author: Jorge Rey-Martinez & HAL
"""

import pygame as pg


def okn(targetSize="L", vel=20, direction="D", totalTime=120, monitor=0,
        fixation_radius=10):
    # Validate monitor index
    if monitor > pg.display.get_num_displays():
        monitor = 0
        print("Monitor is out of range, autoreset to 0. Detected monitors: " +
              str(pg.display.get_num_displays()))

    # Map target size to bar width (border)
    match targetSize:
        case "S":
            ts = 120
        case "M":
            ts = 160
        case "L":
            ts = 240
        case _:
            ts = 240

    # Limit velocity to half the bar width to keep pattern coherent
    if vel >= ts // 2:
        vel = ts // 2
        print("Velocity reset to:", vel)

    main(targetSize=ts, vel=vel, direction=direction,
         totalTime=totalTime, monitor=monitor,
         fixation_radius=fixation_radius)


class OKNBars:
    """Draws moving bar pattern using a phase offset instead of a bar list."""
    def __init__(self, screen, border: int, direction: str):
        self.screen = screen
        self.border = int(border)              # bar width in px
        self.dir = direction.upper() if direction else "D"
        if self.dir not in ("R", "L", "U", "D"):
            self.dir = "D"
        self.phase = 0                         # movement phase in px
        self.step = self.border * 2            # bar + gap (50% duty cycle)

    def draw(self, speed: int):
        """Advance phase and draw the periodic bar pattern."""
        # Update phase according to direction
        if self.dir == "R":
            self.phase += speed
        elif self.dir == "L":
            self.phase -= speed
        elif self.dir == "D":
            self.phase += speed
        elif self.dir == "U":
            self.phase -= speed

        # Normalize phase
        self.phase %= self.step

        w, h = self.screen.get_width(), self.screen.get_height()
        # Draw horizontal-moving bars (vertical rectangles)
        if self.dir in ("R", "L"):
            start_x = -self.border + self.phase
            x = int(start_x)
            while x < w:
                pg.draw.rect(self.screen, (255, 255, 255),
                             pg.Rect(x, 0, self.border, h))
                x += self.step
        # Draw vertical-moving bars (horizontal rectangles)
        else:
            start_y = -self.border + self.phase
            y = int(start_y)
            while y < h:
                pg.draw.rect(self.screen, (255, 255, 255),
                             pg.Rect(0, y, w, self.border))
                y += self.step


def main(targetSize, vel, direction, totalTime, monitor,
         fixation_radius=10):
    pg.init()
    screen = pg.display.set_mode(
        size=(1920, 1080),
        flags=pg.FULLSCREEN | pg.NOFRAME | pg.DOUBLEBUF,
        display=monitor,
        vsync=1
    )
    fps = 60
    pg.mouse.set_visible(False)

    # Prepare background surface (solid black)
    background = pg.Surface(screen.get_size()).convert()
    background.fill((0, 0, 0))

    # Prepare OKN bars
    bars = OKNBars(screen, border=targetSize, direction=direction)

    # Timing / control
    EXIT_EVENT = pg.USEREVENT + 1
    pg.time.set_timer(EXIT_EVENT, totalTime * 1000, 1)

    # Fixation point state
    show_fixation = False
    fixation_fill = (255, 255, 255)  # white
    fixation_outline = (0, 0, 0)     # subtle black outline
    fixation_outline_w = 2

    clock = pg.time.Clock()
    going = True
    while going:
        clock.tick(fps)

        # Events
        for event in pg.event.get():
            if event.type == pg.QUIT or event.type == EXIT_EVENT:
                going = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    going = False
                elif event.key == pg.K_SPACE:
                    show_fixation = not show_fixation
                    if show_fixation:
                        print("Fixation point ON")
                    else:
                        print("Fixation point OFF")

        # Clear screen
        screen.blit(background, (0, 0))

        # Draw bars and optional fixation point
        bars.draw(vel)
        if show_fixation:
            cx, cy = screen.get_width() // 2, screen.get_height() // 2
            pg.draw.circle(screen, fixation_fill, (cx, cy), fixation_radius)
            pg.draw.circle(screen, fixation_outline, (cx, cy),
                           fixation_radius, fixation_outline_w)

        pg.display.flip()

    pg.quit()
    print("OKN exercise finished. Bye!")


# For standalone testing
if __name__ == "__main__":
    okn()
