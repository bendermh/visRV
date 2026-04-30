# -*- coding: utf-8 -*-
"""
Display helpers shared by visRV pygame exercises.
"""

import pygame as pg


DEFAULT_SCREEN_SIZE = (1920, 1080)


def init_display():
    """Initialize only pygame's display module before monitor queries."""
    if not pg.display.get_init():
        pg.display.init()


def get_desktop_sizes():
    """Return configured desktop sizes, falling back safely if unavailable."""
    init_display()
    try:
        sizes = pg.display.get_desktop_sizes()
    except Exception as exc:
        print(f"Unable to read pygame desktop sizes: {exc}")
        sizes = []

    return sizes


def get_display_count():
    """Return the best available count of pygame-selectable displays."""
    init_display()
    sizes = get_desktop_sizes()
    try:
        num_displays = pg.display.get_num_displays()
    except Exception as exc:
        print(f"Unable to read pygame display count: {exc}")
        num_displays = 1

    return max(len(sizes), num_displays, 1)


def monitor_options():
    """Return GUI monitor option labels for the currently detected displays."""
    count = get_display_count()
    options = ["Main"]
    options.extend(f"Secondary_{idx}" for idx in range(1, count))
    return options


def validate_monitor(monitor):
    """Return a valid pygame display index, logging detected displays."""
    init_display()
    sizes = get_desktop_sizes()
    count = get_display_count()

    try:
        monitor = int(monitor)
    except (TypeError, ValueError):
        monitor = 0

    print(
        f"Pygame display driver: {pg.display.get_driver()}; "
        f"detected displays: {count}; desktop sizes: {sizes}"
    )

    if monitor < 0 or monitor >= count:
        print(f"Monitor {monitor} is out of range, auto-reset to 0.")
        return 0

    return monitor


def fullscreen_mode(monitor=0, fallback_size=DEFAULT_SCREEN_SIZE):
    """
    Create a fullscreen pygame surface on the selected monitor.

    The exercise surface intentionally stays fixed at 1920x1080 because the
    current exercise coordinates are built around that treatment resolution.
    """
    monitor = validate_monitor(monitor)

    return pg.display.set_mode(
        size=fallback_size,
        flags=pg.FULLSCREEN | pg.NOFRAME | pg.DOUBLEBUF,
        display=monitor,
        vsync=1
    )
