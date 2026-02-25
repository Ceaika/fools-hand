from __future__ import annotations

import pygame
from .constants import (
    WIDTH, HEIGHT,
    NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_GAP, BTN_RADIUS,
)
from .widgets import Button
from .locale import t

_OVERLAY_ALPHA = 180
_PANEL_W       = 380
_PANEL_H       = 340


class PauseScreen:
    """Returns: 'resume' | 'settings' | 'achievements' | 'main_menu' | None"""

    def __init__(self, fonts: dict) -> None:
        self.fonts = fonts
        cx     = WIDTH  // 2
        cy     = HEIGHT // 2
        bw     = BTN_W - 60
        btn_y0 = cy - (BTN_H + BTN_GAP) * 2 + BTN_H // 2

        self._resume_btn       = Button(cx, btn_y0,                          t("pause.resume"),
                                        w=bw, h=BTN_H, font=fonts["btn"])
        self._achievements_btn = Button(cx, btn_y0 + (BTN_H + BTN_GAP),     t("pause.achievements"),
                                        w=bw, h=BTN_H, font=fonts["btn"])
        self._settings_btn     = Button(cx, btn_y0 + (BTN_H + BTN_GAP) * 2, t("pause.settings"),
                                        w=bw, h=BTN_H, font=fonts["btn"])
        self._menu_btn         = Button(cx, btn_y0 + (BTN_H + BTN_GAP) * 3, t("pause.main_menu"),
                                        w=bw, h=BTN_H, font=fonts["btn"])

        self._panel_rect = pygame.Rect(cx - _PANEL_W // 2,
                                        cy - _PANEL_H // 2,
                                        _PANEL_W, _PANEL_H)
        self._overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, _OVERLAY_ALPHA))

    def rebuild_labels(self) -> None:
        """Call after a language change to refresh button text."""
        self._resume_btn.text       = t("pause.resume")
        self._achievements_btn.text = t("pause.achievements")
        self._settings_btn.text     = t("pause.settings")
        self._menu_btn.text         = t("pause.main_menu")

    def handle_event(self, event) -> str | None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "resume"
        if self._resume_btn.handle_event(event):       return "resume"
        if self._achievements_btn.handle_event(event): return "achievements"
        if self._settings_btn.handle_event(event):     return "settings"
        if self._menu_btn.handle_event(event):         return "main_menu"
        return None

    def update(self) -> None:
        mouse = pygame.mouse.get_pos()
        self._resume_btn.update(mouse)
        self._achievements_btn.update(mouse)
        self._settings_btn.update(mouse)
        self._menu_btn.update(mouse)

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(self._overlay, (0, 0))
        panel_surf = pygame.Surface((_PANEL_W, _PANEL_H), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 40, 220))
        surf.blit(panel_surf, self._panel_rect.topleft)
        pygame.draw.rect(surf, NEON, self._panel_rect, width=2, border_radius=10)
        f     = self.fonts["small"]
        label = f.render(t("pause.title"), False, NEON_GLOW)
        surf.blit(label, (self._panel_rect.centerx - label.get_width() // 2,
                           self._panel_rect.y + 22))
        dy = self._panel_rect.y + 22 + label.get_height() + 8
        pygame.draw.line(surf, PURPLE,
                         (self._panel_rect.x + 20, dy),
                         (self._panel_rect.right - 20, dy), 1)
        self._resume_btn.draw(surf)
        self._achievements_btn.draw(surf)
        self._settings_btn.draw(surf)
        self._menu_btn.draw(surf)