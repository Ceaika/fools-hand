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

    small = f(8)
    return {
        "title": f(32),
        "sub":   small,
        "btn":   f(16),
        "small": small,
        "body":  small,
    }


def _make_vignette() -> pygame.Surface:
    import math
    surf   = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx, cy = WIDTH // 2, HEIGHT // 2
    max_r  = int(math.hypot(cx, cy))
    for i in range(24, 0, -1):
        ratio = i / 24
        alpha = int((ratio ** 1.6) * 200)
        pygame.draw.circle(surf, (0, 0, 0, alpha), (cx, cy), int(max_r * ratio))
    return surf


def run() -> None:
    pygame.init()
    pygame.display.set_caption(TITLE)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock  = pygame.time.Clock()

    screen.fill((12, 8, 20))
    pygame.display.flip()

    fonts       = _load_fonts()
    vignette    = _make_vignette()
    current     = "menu"
    pending     = None
    menu        = MainMenu(screen, fonts, vignette)
    play_select = PlaySelectScreen(screen, fonts, vignette)
    transition  = ZoomTransition()
    game_screen = None

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

            elif current == "play_select":
                action, rect = play_select.handle_event_with_rect(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "back" and rect:
                    zoom_to("menu", rect, direction=-1)
                elif action == "singleplayer":
                    from .game_screen import GameScreen
                    from ..core.game import Game
                    game_obj    = Game()
                    game_obj.setup_no_deal(num_players=2)  # <-- important for animated deal
                    game_screen = GameScreen(screen, fonts, game_obj)
                    screens["game"] = game_screen
                    current = "game"

            elif current == "game":
                action = game_screen.handle_event(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "back":
                    current = "play_select"

        if not transition.busy:
            if current == "game":
                game_screen.update()
            else:
                screens[current].update()

        if transition.busy:
            transition.update()
            transition.draw(screen)
        else:
            if current == "game":
                game_screen.draw()
            else:
                screens[current].draw()

        pygame.display.flip()