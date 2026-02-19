from __future__ import annotations

import math
import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_RADIUS,
)
from .widgets import Button

_AMBER      = (220, 140, 20)
_AMBER_DARK = (160, 100, 10)
_BLACK      = (10,  10,  10)


class PlaySelectScreen:
    """
    Mode selection. Returns: 'singleplayer' | 'back' | 'quit'
    """

    def __init__(self, screen: pygame.Surface, fonts: dict) -> None:
        self.screen = screen
        self.fonts  = fonts
        self.tick   = 0

        cx      = WIDTH // 2
        card_w  = 340
        card_h  = 260
        gap     = 60
        total_w = card_w * 2 + gap
        left_x  = cx - total_w // 2
        right_x = left_x + card_w + gap
        card_y  = HEIGHT // 2 - card_h // 2 + 20

        self._sp_rect  = pygame.Rect(left_x,  card_y, card_w, card_h)
        self._mp_rect  = pygame.Rect(right_x, card_y, card_w, card_h)
        self._sp_hover = False
        self._mp_hover = False

        self._back_btn = Button(90, 24, "< BACK", w=140, h=36, font=fonts["small"])
        self._vignette = self._make_vignette()

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event_with_rect(self, event: pygame.event.Event) -> tuple:
        if event.type == pygame.QUIT:
            return "quit", None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._back_btn.handle_event(event):
                return "back", self._back_btn.rect.copy()
            if self._sp_rect.collidepoint(event.pos):
                return "singleplayer", self._sp_rect.copy()
        return None, None

    def handle_event(self, event: pygame.event.Event) -> str | None:
        action, _ = self.handle_event_with_rect(event)
        return action

    def update(self) -> None:
        self.tick += 1
        mouse = pygame.mouse.get_pos()
        self._sp_hover = self._sp_rect.collidepoint(mouse)
        self._mp_hover = self._mp_rect.collidepoint(mouse)
        self._back_btn.update(mouse)

    def draw(self, surface: pygame.Surface | None = None) -> None:
        target = surface if surface is not None else self.screen
        target.fill(BG)
        self._draw_bg_grid(target)
        target.blit(self._vignette, (0, 0))
        self._draw_header(target)
        self._draw_sp_card(target)
        self._draw_mp_card(target)
        self._back_btn.draw(target)

    # ── cards ─────────────────────────────────────────────────────────────────

    def _draw_sp_card(self, target: pygame.Surface) -> None:
        r     = self._sp_rect
        hover = self._sp_hover

        surf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        surf.fill((30, 15, 55, 220) if hover else (20, 10, 38, 200))
        target.blit(surf, r.topleft)

        border_col = NEON_GLOW if hover else NEON
        pygame.draw.rect(target, border_col, r, width=2 if not hover else 3,
                         border_radius=6)

        if hover:
            gs = pygame.Surface((r.w + 16, r.h + 16), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*NEON, 35), gs.get_rect(), border_radius=10)
            target.blit(gs, (r.x - 8, r.y - 8))

        # person icon
        ic  = r.centerx
        iy  = r.y + 52
        col = NEON_GLOW if hover else PURPLE
        pygame.draw.circle(target, col, (ic, iy), 22)
        pygame.draw.ellipse(target, col, pygame.Rect(ic - 26, iy + 26, 52, 30))

        title = self.fonts["btn"].render("FOOL'S DUEL", False,
                                          NEON_GLOW if hover else TEXT_MAIN)
        target.blit(title, (r.centerx - title.get_width() // 2,
                             r.y + r.h // 2 + 14))
        sub = self.fonts["small"].render("1 BOT  |  SINGLEPLAYER", False, TEXT_DIM)
        target.blit(sub, (r.centerx - sub.get_width() // 2,
                           r.y + r.h // 2 + 14 + title.get_height() + 10))

    def _draw_mp_card(self, target: pygame.Surface) -> None:
        r = self._mp_rect

        surf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        surf.fill((22, 12, 35, 180))
        target.blit(surf, r.topleft)
        pygame.draw.rect(target, PURPLE, r, width=1, border_radius=6)

        # two person icons, dimmed
        for ox in (-22, 22):
            cx = r.centerx + ox
            iy = r.y + 52
            pygame.draw.circle(target, PURPLE, (cx, iy), 16)
            pygame.draw.ellipse(target, PURPLE,
                                pygame.Rect(cx - 18, iy + 20, 36, 22))

        title = self.fonts["btn"].render("MULTI BOT", False, TEXT_DIM)
        target.blit(title, (r.centerx - title.get_width() // 2,
                             r.y + r.h // 2 + 14))
        sub = self.fonts["small"].render("2+ BOTS  |  COMING SOON", False, TEXT_DIM)
        target.blit(sub, (r.centerx - sub.get_width() // 2,
                           r.y + r.h // 2 + 14 + title.get_height() + 10))

        self._draw_road_sign(target, r)

    def _draw_road_sign(self, target: pygame.Surface, card: pygame.Rect) -> None:
        import math
        pulse    = abs(math.sin(self.tick * 0.06)) * 0.4 + 0.6   # 0.6–1.0
        amber    = tuple(int(c * pulse) for c in _AMBER)
        wip      = self.fonts["btn"].render("WIP", False, amber)

        x   = card.right - wip.get_width() - 14
        y   = card.y + 14
        pad = 8
        pill = pygame.Rect(x - pad, y - pad // 2,
                           wip.get_width() + pad * 2, wip.get_height() + pad)

        # glow halo
        gsurf = pygame.Surface((pill.w + 12, pill.h + 12), pygame.SRCALPHA)
        glow_alpha = int(pulse * 80)
        pygame.draw.rect(gsurf, (*_AMBER, glow_alpha), gsurf.get_rect(), border_radius=8)
        target.blit(gsurf, (pill.x - 6, pill.y - 6))

        # dark fill
        pygame.draw.rect(target, (50, 28, 0), pill, border_radius=4)
        # amber border, brightness pulses
        pygame.draw.rect(target, amber, pill, width=2, border_radius=4)
        target.blit(wip, (x, y))

    # ── visual helpers ────────────────────────────────────────────────────────

    def _draw_header(self, target: pygame.Surface) -> None:
        pulse = abs(math.sin(self.tick * 0.03)) * 4
        title = self.fonts["title"].render("SELECT MODE", False, TEXT_MAIN)
        tx    = WIDTH // 2 - title.get_width() // 2
        ty    = HEIGHT // 4 - title.get_height() // 2 - 20 + int(pulse)
        target.blit(title, (tx, ty))
        uw = title.get_width()
        ux = WIDTH // 2 - uw // 2
        uy = ty + title.get_height() + 8
        pygame.draw.rect(target, NEON,      (ux, uy,     uw, 3))
        pygame.draw.rect(target, NEON_GLOW, (ux, uy - 1, uw, 1))

    def _draw_bg_grid(self, target: pygame.Surface) -> None:
        for x in range(0, WIDTH, 40):
            pygame.draw.line(target, (30, 15, 50), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 40):
            pygame.draw.line(target, (30, 15, 50), (0, y), (WIDTH, y))

    def _make_vignette(self) -> pygame.Surface:
        surf  = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        cx, cy = WIDTH // 2, HEIGHT // 2
        max_r  = int(math.hypot(cx, cy))
        for i in range(24, 0, -1):
            ratio = i / 24
            alpha = int((ratio ** 1.6) * 200)
            pygame.draw.circle(surf, (0, 0, 0, alpha), (cx, cy), int(max_r * ratio))
        return surf