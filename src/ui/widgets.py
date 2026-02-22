from __future__ import annotations

import pygame
from .constants import (
    NEON, NEON_DARK, NEON_GLOW, PURPLE, PURPLE_DIM,
    TEXT_MAIN, BTN_W, BTN_H, BTN_RADIUS, BG2
)
from . import audio


class Button:
    def __init__(
        self,
        x: int, y: int,
        text: str,
        w: int = BTN_W,
        h: int = BTN_H,
        font: pygame.font.Font | None = None,
    ) -> None:
        self.rect    = pygame.Rect(0, 0, w, h)
        self.rect.centerx = x
        self.rect.y  = y
        self.text    = text
        self.font    = font
        self.hovered = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                audio.play("menu_click")
                return True
        return False

    def update(self, mouse_pos: tuple) -> None:
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface,
             alpha_override: int = 255, x_offset: int = 0) -> None:
        if alpha_override <= 0:
            return

        r = self.rect.move(x_offset, 0)

        # Render to a temp surface so we can alpha the whole button
        tmp = pygame.Surface((r.w, r.h), pygame.SRCALPHA)

        fill = NEON_DARK if self.hovered else PURPLE_DIM
        pygame.draw.rect(tmp, fill, tmp.get_rect(), border_radius=BTN_RADIUS)

        border_col   = NEON_GLOW if self.hovered else NEON
        border_width = 2 if not self.hovered else 3
        pygame.draw.rect(tmp, border_col, tmp.get_rect(),
                         width=border_width, border_radius=BTN_RADIUS)

        if self.font:
            col   = NEON_GLOW if self.hovered else TEXT_MAIN
            label = self.font.render(self.text, False, col)
            lx    = tmp.get_width()  // 2 - label.get_width()  // 2
            ly    = tmp.get_height() // 2 - label.get_height() // 2
            tmp.blit(label, (lx, ly))

        if alpha_override < 255:
            tmp.set_alpha(alpha_override)

        # Spark trail: a horizontal smear to the left during slide-in
        if x_offset < 0:
            trail_w = min(60, -x_offset)
            trail   = pygame.Surface((trail_w, r.h), pygame.SRCALPHA)
            for tx in range(trail_w):
                a = int(alpha_override * (tx / trail_w) * 0.4)
                pygame.draw.line(trail, (*NEON, a), (tx, 0), (tx, r.h))
            surface.blit(trail, (r.x - trail_w, r.y))

        if self.hovered and self.font and alpha_override >= 200:
            glow_surf = pygame.Surface((r.w + 12, r.h + 12), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*NEON, 40),
                             glow_surf.get_rect(), border_radius=BTN_RADIUS + 4)
            surface.blit(glow_surf, (r.x - 6, r.y - 6))

        surface.blit(tmp, (r.x, r.y))