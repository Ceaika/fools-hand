from __future__ import annotations

import sys
import os
import pygame

os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '100,100')

from .constants import WIDTH, HEIGHT, FPS, TITLE
from .menu import MainMenu
from .play_select import PlaySelectScreen
from .settings_screen import SettingsScreen
from .pause_screen import PauseScreen
from .transition import ZoomTransition, CardSweepTransition
from . import audio

# Screens where music should be muffled
_MUFFLED_SCREENS = {"play_select", "pause", "settings", "game_settings"}


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
    return {"title": f(32), "sub": small, "btn": f(16), "small": small, "body": small}


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

    audio.init()
    audio.play_music("main_menu")

    fonts       = _load_fonts()
    vignette    = _make_vignette()
    current     = "menu"
    prev_menu   = "menu"
    pending     = None
    menu        = MainMenu(screen, fonts, vignette)
    play_select = PlaySelectScreen(screen, fonts, vignette)
    settings    = SettingsScreen(screen, fonts, vignette)
    pause       = PauseScreen(fonts)
    transition  = ZoomTransition()
    card_sweep  = CardSweepTransition()
    game_screen = None

    screens = {
        "menu":        menu,
        "play_select": play_select,
        "settings":    settings,
    }

    def set_screen(name: str) -> None:
        nonlocal current
        current = name
        audio.set_muffled(name in _MUFFLED_SCREENS)

    def zoom_to(dest: str, origin_rect: pygame.Rect, direction: int = 1) -> None:
        nonlocal pending
        if transition.busy:
            return
        pending = dest
        src = screens.get(current)
        dst = screens.get(dest)
        if src: src.draw(transition.get_surface_a())
        if dst: dst.draw(transition.get_surface_b())
        transition.start(origin_rect, direction=direction)
        audio.set_muffled(dest in _MUFFLED_SCREENS)

    def go_settings_from_menu(rect: pygame.Rect) -> None:
        nonlocal prev_menu
        prev_menu = current
        settings.set_on_back(lambda: zoom_to(prev_menu, rect, direction=-1))
        zoom_to("settings", rect, direction=1)

    def go_settings_from_pause() -> None:
        settings.set_on_back(_back_from_game_settings)
        set_screen("game_settings")

    def _back_from_game_settings() -> None:
        set_screen("pause")

    def sweep_to_menu() -> None:
        """Reverse card sweep from game/pause back to main menu."""
        nonlocal game_screen
        if card_sweep.busy:
            return
        # src = current game view, dst = menu
        if game_screen:
            game_screen.draw(card_sweep.get_surface_src())
        menu.draw(card_sweep.get_surface_dst())
        def _on_switch():
            set_screen("menu")
            audio.play_music("main_menu")
            nonlocal game_screen
            game_screen = None
        audio.play("transition_change")
        card_sweep.start(on_switch=_on_switch)

    while True:
        clock.tick(FPS)

        if pending and not transition.busy:
            current = pending
            pending = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if transition.busy or card_sweep.busy:
                continue

            # ── Main menu ─────────────────────────────────────────────────
            if current == "menu":
                action, rect = menu.handle_event_with_rect(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "play" and rect:
                    zoom_to("play_select", rect, direction=1)
                elif action == "settings" and rect:
                    go_settings_from_menu(rect)

            # ── Play select ───────────────────────────────────────────────
            elif current == "play_select":
                action, rect = play_select.handle_event_with_rect(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "back" and rect:
                    zoom_to("menu", rect, direction=-1)
                elif action == "singleplayer":
                    if not card_sweep.busy:
                        from .game_screen import GameScreen
                        from ..core.game import Game
                        game_obj = Game()
                        game_obj.setup_no_deal(num_players=2)
                        game_screen = GameScreen(screen, fonts, game_obj)
                        screens["game"] = game_screen
                        play_select.draw(card_sweep.get_surface_src())
                        game_screen.draw(card_sweep.get_surface_dst())
                        def _on_switch():
                            set_screen("game")
                            audio.play_music("in_game")
                        audio.play("transition_change")
                        card_sweep.start(on_switch=_on_switch)

            # ── Settings (from menu) ──────────────────────────────────────
            elif current == "settings":
                settings.handle_event(event)

            # ── Game ──────────────────────────────────────────────────────
            elif current == "game":
                action = game_screen.handle_event(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "back":
                    set_screen("play_select")
                    audio.play_music("main_menu")
                elif action == "pause":
                    set_screen("pause")

            # ── Pause overlay ─────────────────────────────────────────────
            elif current == "pause":
                action = pause.handle_event(event)
                if action == "resume":
                    set_screen("game")
                elif action == "settings":
                    go_settings_from_pause()
                elif action == "main_menu":
                    sweep_to_menu()

            # ── Settings (from pause) ─────────────────────────────────────
            elif current == "game_settings":
                settings.handle_event(event)

        # ── Audio update (crossfade tick) ─────────────────────────────────
        audio.update()

        # ── Update ────────────────────────────────────────────────────────
        if not transition.busy and not card_sweep.busy:
            if current == "game":
                game_screen.update()
            elif current == "pause":
                pause.update()
            elif current in ("settings", "game_settings"):
                settings.update()
            elif current in screens:
                screens[current].update()

        # ── Draw ──────────────────────────────────────────────────────────
        if transition.busy:
            transition.update()
            transition.draw(screen)
        elif card_sweep.busy:
            card_sweep.update()
            card_sweep.draw(screen)
        elif current == "game":
            game_screen.draw()
        elif current == "pause":
            game_screen.draw()
            pause.draw(screen)
        elif current in ("settings", "game_settings"):
            settings.draw()
        elif current in screens:
            screens[current].draw()

        pygame.display.flip()