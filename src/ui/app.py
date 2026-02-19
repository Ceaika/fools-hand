from __future__ import annotations

import sys
import os
import pygame

os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '100,100')

from .constants import WIDTH, HEIGHT, FPS, TITLE, BG
from .menu import MainMenu


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

    fonts = _load_fonts()

    # ── screens ───────────────────────────────────────────────────────────────
    current = "menu"
    menu    = MainMenu(screen, fonts)

    while True:
        dt = clock.tick(FPS)

        # ── events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if current == "menu":
                action = menu.handle_event(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "play":
                    pass  # game screen — next commit
                elif action == "tutorial":
                    pass  # tutorial screen — next commit
                elif action == "settings":
                    pass  # settings screen — next commit

        # ── update ────────────────────────────────────────────────────────────
        if current == "menu":
            menu.update()

        # ── draw ──────────────────────────────────────────────────────────────
        if current == "menu":
            menu.draw()

        pygame.display.flip()