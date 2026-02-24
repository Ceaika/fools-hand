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
from .tutorial_screen import TutorialScreen
from .achievements_screen import AchievementsScreen
from .transition import ZoomTransition, CardSweepTransition
from . import audio

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
    tutorial    = TutorialScreen(screen, fonts, vignette)
    achievements = AchievementsScreen(screen, fonts, vignette)
    pause       = PauseScreen(fonts)
    transition  = ZoomTransition()
    card_sweep  = CardSweepTransition()
    game_screen = None

    screens = {
        "menu":         menu,
        "play_select":  play_select,
        "settings":     settings,
        "tutorial":     tutorial,
        "achievements": achievements,
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
        nonlocal game_screen
        if card_sweep.busy:
            return
        if game_screen:
            game_screen.draw(card_sweep.get_surface_src())
        menu.draw(card_sweep.get_surface_dst())
        def _on_switch():
            set_screen("menu")
            audio.play_music("main_menu")
            achievements.refresh()
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

            if current == "menu":
                action, rect = menu.handle_event_with_rect(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "play" and rect:
                    zoom_to("play_select", rect, direction=1)
                elif action == "tutorial" and rect:
                    # Fresh tutorial each time
                    tutorial = TutorialScreen(screen, fonts, vignette)
                    screens["tutorial"] = tutorial
                    zoom_to("tutorial", rect, direction=1)
                elif action == "achievements" and rect:
                    achievements.refresh()
                    zoom_to("achievements", rect, direction=1)
                elif action == "settings" and rect:
                    go_settings_from_menu(rect)

            elif current == "achievements":
                action = achievements.handle_event(event)
                if action == "back":
                    zoom_to("menu", pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2, 160, 42), direction=-1)

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

            elif current == "settings":
                settings.handle_event(event)

            elif current == "tutorial":
                action = tutorial.handle_event(event)
                if action == "menu":
                    zoom_to("menu", pygame.Rect(WIDTH // 2 - 60, HEIGHT // 2, 120, 40), direction=-1)
                elif action == "play":
                    if not card_sweep.busy:
                        from .game_screen import GameScreen
                        from ..core.game import Game
                        game_obj = Game()
                        game_obj.setup_no_deal(num_players=2)
                        game_screen = GameScreen(screen, fonts, game_obj)
                        screens["game"] = game_screen
                        tutorial.draw(card_sweep.get_surface_src())
                        game_screen.draw(card_sweep.get_surface_dst())
                        def _on_switch_from_tut():
                            set_screen("game")
                            audio.play_music("in_game")
                        audio.play("transition_change")
                        card_sweep.start(on_switch=_on_switch_from_tut)

            elif current == "game":
                action = game_screen.handle_event(event)
                if action == "quit":
                    pygame.quit()
                    sys.exit()
                elif action == "back":
                    sweep_to_menu()
                elif action == "pause":
                    set_screen("pause")

            elif current == "pause":
                action = pause.handle_event(event)
                if action == "resume":
                    set_screen("game")
                elif action == "settings":
                    go_settings_from_pause()
                elif action == "achievements":
                    achievements.refresh()
                    set_screen("achievements")
                elif action == "main_menu":
                    sweep_to_menu()

            elif current == "game_settings":
                settings.handle_event(event)

        audio.update()

        if not transition.busy and not card_sweep.busy:
            if current == "game":
                game_screen.update()
            elif current == "pause":
                pause.update()
            elif current in ("settings", "game_settings"):
                settings.update()
            elif current in screens:
                screens[current].update()

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