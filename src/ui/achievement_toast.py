"""
achievement_toast.py — Tiered achievement toast notifications

Slides DOWN from top-right corner.
Glow intensity based on tier:
  common   — no glow
  rare     — soft blue glow
  epic     — bright neon pink glow
  platinum — gold glow, bigger toast, screen flash
"""
from __future__ import annotations

import math
import pygame
from collections import deque

from .constants import (
    WIDTH, HEIGHT, NEON, NEON_GLOW, NEON_DARK,
    PURPLE, PURPLE_DIM, GOLD, TEXT_MAIN, TEXT_DIM, BG, BTN_RADIUS,
)
from .achievements import Achievement, COMMON, RARE, EPIC, PLATINUM
from .locale import t as _t
from .font_manager import get_fonts

# ── regular toast dims ────────────────────────────────────────────────────────
_W      = 360
_H      = 76
_PAD    = 14
_MARGIN = 18
_ICON_W = 54

# ── platinum toast dims ───────────────────────────────────────────────────────
_PW     = 440
_PH     = 96

# ── timing ───────────────────────────────────────────────────────────────────
_SLIDE_IN  = 24
_HOLD      = 200
_SLIDE_OUT = 20
_TOTAL     = _SLIDE_IN + _HOLD + _SLIDE_OUT

# ── tier colours ─────────────────────────────────────────────────────────────
_TIER_GLOW = {
    COMMON:   None,
    RARE:     (60, 140, 255),
    EPIC:     (255, 50,  120),
    PLATINUM: (255, 200, 80),
}
_TIER_BORDER = {
    COMMON:   (80, 50, 110),
    RARE:     (60, 140, 255),
    EPIC:     (255, 50,  120),
    PLATINUM: (255, 200, 80),
}
_TIER_HEADER_COL = {
    COMMON:   TEXT_DIM,
    RARE:     (60, 140, 255),
    EPIC:     NEON_GLOW,
    PLATINUM: GOLD,
}


def _tier_toast_label(tier: str) -> str:
    return _t(f"toast.{tier}")


class AchievementToast:
    def __init__(self, fonts: dict) -> None:
        self._fonts   = fonts
        self._queue: deque[Achievement] = deque()
        self._current: Achievement | None = None
        self._tick    = 0
        self._surf    = None
        self._glow_t  = 0.0
        self._flash   = 0      # platinum screen flash countdown

    def push(self, ach: Achievement) -> None:
        self._queue.append(ach)

    def update(self) -> None:
        self._glow_t += 0.055
        if self._flash > 0:
            self._flash -= 1

        if self._current is None:
            if not self._queue:
                return
            self._current = self._queue.popleft()
            self._tick    = 0
            self._surf    = self._render(self._current)
            if self._current.tier == PLATINUM:
                self._flash = 40
        else:
            self._tick += 1
            if self._tick >= _TOTAL:
                self._current = None
                self._surf    = None

    def draw(self, surface: pygame.Surface) -> None:
        # Platinum screen flash
        if self._flash > 0:
            alpha = int(180 * (self._flash / 40))
            fl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fl.fill((255, 200, 80, alpha))
            surface.blit(fl, (0, 0))

        if self._current is None or self._surf is None:
            return

        is_plat = (self._current.tier == PLATINUM)
        tw = _PW if is_plat else _W
        th = _PH if is_plat else _H

        t   = self._tick
        # slide DOWN from off-screen top-right
        if t < _SLIDE_IN:
            p   = t / _SLIDE_IN
            p   = 1 - (1 - p) ** 3
            off = (th + _MARGIN) * (1 - p)
        elif t < _SLIDE_IN + _HOLD:
            off = 0.0
        else:
            p   = (t - _SLIDE_IN - _HOLD) / _SLIDE_OUT
            p   = p ** 2
            off = (th + _MARGIN) * p

        x = WIDTH - tw - _MARGIN
        y = _MARGIN - int(off) + int(off * (1 - (t / _SLIDE_IN if t < _SLIDE_IN else 1)))
        # Simplify: slide down means y goes from -th-margin to margin
        if t < _SLIDE_IN:
            p  = t / _SLIDE_IN
            p  = 1 - (1 - p) ** 3
            y  = int(-(th + _MARGIN) * (1 - p)) + _MARGIN
        elif t < _SLIDE_IN + _HOLD:
            y  = _MARGIN
        else:
            p  = (t - _SLIDE_IN - _HOLD) / _SLIDE_OUT
            p  = p ** 2
            y  = int(-(th + _MARGIN) * p) + _MARGIN

        glow_col = _TIER_GLOW[self._current.tier]
        if glow_col:
            pulse = abs(math.sin(self._glow_t))
            base_a = 30 if self._current.tier == RARE else 50
            a = int(base_a + pulse * 40)
            gs = pygame.Surface((tw + 20, th + 20), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*glow_col, a), gs.get_rect(),
                             border_radius=BTN_RADIUS + 8)
            surface.blit(gs, (x - 10, y - 10))

        surface.blit(self._surf, (x, y))

    def _render(self, ach: Achievement) -> pygame.Surface:
        is_plat = (ach.tier == PLATINUM)
        tw = _PW if is_plat else _W
        th = _PH if is_plat else _H

        surf = pygame.Surface((tw, th), pygame.SRCALPHA)

        border_col = _TIER_BORDER[ach.tier]
        pygame.draw.rect(surf, (14, 8, 26, 240), surf.get_rect(),
                         border_radius=BTN_RADIUS + 2)
        pygame.draw.rect(surf, (*border_col, 200), surf.get_rect(),
                         width=1, border_radius=BTN_RADIUS + 2)

        # Icon box
        icon_bg = (40, 20, 70) if ach.tier == COMMON else border_col
        pygame.draw.rect(surf, (*icon_bg, 255) if len(icon_bg) == 3 else icon_bg,
                         pygame.Rect(0, 0, _ICON_W, th),
                         border_radius=BTN_RADIUS + 2)

        f_icon = get_fonts()["btn"]
        icon_sym = "★" if is_plat else "?"
        icon_s = f_icon.render(icon_sym, False,
                                GOLD if is_plat else _TIER_HEADER_COL[ach.tier])
        surf.blit(icon_s, (_ICON_W // 2 - icon_s.get_width() // 2,
                            th // 2 - icon_s.get_height() // 2))

        f_sm  = get_fonts()["small"]
        f_btn = get_fonts()["btn"]
        tx    = _ICON_W + _PAD
        header_col = _TIER_HEADER_COL[ach.tier]

        header = f_sm.render(_tier_toast_label(ach.tier), False, header_col)
        surf.blit(header, (tx, 10))

        name_col = GOLD if is_plat else TEXT_MAIN
        name_s = f_btn.render(ach.name.upper(), False, name_col)
        max_w = tw - tx - _PAD
        if name_s.get_width() > max_w:
            scale  = max_w / name_s.get_width()
            new_w  = max(1, int(name_s.get_width() * scale))
            new_h  = max(1, int(name_s.get_height() * scale))
            name_s = name_s.convert_alpha()
            name_s = pygame.transform.smoothscale(name_s, (new_w, new_h))
        surf.blit(name_s, (tx, 10 + header.get_height() + 4))

        max_w   = tw - tx - _PAD
        desc    = ach.description
        desc_s  = f_sm.render(desc, False, TEXT_DIM)
        if desc_s.get_width() > max_w:
            while desc and f_sm.render(desc + "...", False, TEXT_DIM).get_width() > max_w:
                desc = desc[:-1]
            desc_s = f_sm.render(desc + "...", False, TEXT_DIM)
        surf.blit(desc_s, (tx, 10 + header.get_height() + 4 + name_s.get_height() + 4))

        # Bottom accent line
        line_col = GOLD if is_plat else (*border_col, 80)
        if len(line_col) == 3:
            line_col = (*line_col, 80)
        pygame.draw.line(surf, line_col,
                         (_ICON_W + 4, th - 4), (tw - 4, th - 4), 1)
        return surf