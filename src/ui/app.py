from __future__ import annotations

import sys
import os
import pygame

os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '100,100')

from .constants import WIDTH, HEIGHT, FPS, TITLE
from .menu import MainMenu
from .play_select import PlaySelectScreen
from .transition import ZoomTransition


def _load_fonts() -> dict:
    pygame.font.init()
    from .constants import FONT_PATH
    def f(size: int) -> pygame.font.Font:
        try:
            return pygame.font.Font(FONT_PATH, size)
        except FileNotFoundError:
            print(f"[warn] font not found at {FONT_PATH}, using fallback")
            return pygame.font.Font(None, size * 2)

    return {
        "title": f(32),
        "sub":   f(8),
        "btn":   f(16),
        "small": f(8),
        "body":  f(8),
    }


def run() -> None:
    pygame.init()
    pygame.display.set_caption(TITLE)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock  = pygame.time.Clock()

    fonts       = _load_fonts()
    current     = "menu"
    pending     = None
    menu        = MainMenu(screen, fonts)
    play_select = PlaySelectScreen(screen, fonts)
    transition  = ZoomTransition()

    screens = {
        "menu":        menu,
        "play_select": play_select,
    }

    def zoom_to(dest: str, origin_rect: pygame.Rect, direction: int = 1) -> None:
        nonlocal pending
        if transition.busy:
            return
        pending = dest
        screens[current].draw(transition.get_surface_a())
        screens[dest].draw(transition.get_surface_b())
        transition.start(origin_rect, direction=direction)

    while True:
        clock.tick(FPS)

        if pending and not transition.busy:
            current = pending
            pending = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if transition.busy:
                continue

            if current == "menu":
                action, rect = menu.handle_event_with_rect(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "play" and rect:
                    zoom_to("play_select", rect, direction=1)
                elif action == "tutorial":
                    pass
                elif action == "settings":
                    pass

            elif current == "play_select":
                action, rect = play_select.handle_event_with_rect(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "back" and rect:
                    zoom_to("menu", rect, direction=-1)
                elif action == "singleplayer":
                    pass

        if not transition.busy:
            screens[current].update()

        if transition.busy:
            transition.update()
            transition.draw(screen)
        else:
            screens[current].draw()

        pygame.display.flip()