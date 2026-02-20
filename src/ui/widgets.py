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

    def draw(self, surface: pygame.Surface) -> None:
        # dark fill
        fill = NEON_DARK if self.hovered else PURPLE_DIM
        pygame.draw.rect(surface, fill, self.rect, border_radius=BTN_RADIUS)

        # neon border — thicker + brighter on hover
        border_col   = NEON_GLOW if self.hovered else NEON
        border_width = 2 if not self.hovered else 3
        pygame.draw.rect(surface, border_col, self.rect,
                         width=border_width, border_radius=BTN_RADIUS)

        # glow effect: draw a slightly larger transparent rect underneath
        if self.hovered and self.font:
            glow_surf = pygame.Surface(
                (self.rect.w + 12, self.rect.h + 12), pygame.SRCALPHA
            )
            pygame.draw.rect(
                glow_surf, (*NEON, 40),
                glow_surf.get_rect(), border_radius=BTN_RADIUS + 4
            )
            surface.blit(glow_surf, (self.rect.x - 6, self.rect.y - 6))

        if self.font:
            col   = NEON_GLOW if self.hovered else TEXT_MAIN
            label = self.font.render(self.text, False, col)
            lx    = self.rect.centerx - label.get_width() // 2
            ly    = self.rect.centery - label.get_height() // 2
            surface.blit(label, (lx, ly))