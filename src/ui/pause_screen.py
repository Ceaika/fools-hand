from __future__ import annotations

import pygame
from .constants import (
    WIDTH, HEIGHT,
    NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_GAP, BTN_RADIUS,
)
from .widgets import Button

_OVERLAY_ALPHA = 180
_PANEL_W       = 380
_PANEL_H       = 300


class PauseScreen:
    """
    Semi-transparent overlay drawn on top of the frozen game.
    Returns: 'resume' | 'settings' | 'main_menu' | None
    """

    def __init__(self, fonts: dict) -> None:
        self.fonts = fonts

        cx     = WIDTH  // 2
        cy     = HEIGHT // 2
        btn_y0 = cy - BTN_H - BTN_GAP   # centre 3 buttons vertically in panel

        self._resume_btn   = Button(cx, btn_y0,                       "RESUME",
                                    w=BTN_W - 60, h=BTN_H, font=fonts["btn"])
        self._settings_btn = Button(cx, btn_y0 + BTN_H + BTN_GAP,    "SETTINGS",
                                    w=BTN_W - 60, h=BTN_H, font=fonts["btn"])
        self._menu_btn     = Button(cx, btn_y0 + (BTN_H + BTN_GAP)*2, "MAIN MENU",
                                    w=BTN_W - 60, h=BTN_H, font=fonts["btn"])

        self._panel_rect = pygame.Rect(
            cx - _PANEL_W // 2,
            cy - _PANEL_H // 2,
            _PANEL_W, _PANEL_H,
        )

        # Pre-build overlay surface once
        self._overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, _OVERLAY_ALPHA))

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "resume"
        if self._resume_btn.handle_event(event):
            return "resume"
        if self._settings_btn.handle_event(event):
            return "settings"
        if self._menu_btn.handle_event(event):
            return "main_menu"
        return None

    def update(self) -> None:
        mouse = pygame.mouse.get_pos()
        self._resume_btn.update(mouse)
        self._settings_btn.update(mouse)
        self._menu_btn.update(mouse)

    def draw(self, surf: pygame.Surface) -> None:
        """Draw the overlay on top of whatever is already on surf."""
        surf.blit(self._overlay, (0, 0))

        # Panel background
        panel_surf = pygame.Surface((_PANEL_W, _PANEL_H), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 40, 220))
        surf.blit(panel_surf, self._panel_rect.topleft)
        pygame.draw.rect(surf, NEON, self._panel_rect, width=2, border_radius=10)

        # "PAUSED" label
        f     = self.fonts["small"]
        label = f.render("PAUSED", False, NEON_GLOW)
        surf.blit(label, (self._panel_rect.centerx - label.get_width()  // 2,
                           self._panel_rect.y       + 24))

        # divider
        dy = self._panel_rect.y + 24 + label.get_height() + 10
        pygame.draw.line(surf, PURPLE,
                         (self._panel_rect.x + 20, dy),
                         (self._panel_rect.right - 20, dy), 1)

        self._resume_btn.draw(surf)
        self._settings_btn.draw(surf)
        self._menu_btn.draw(surf)