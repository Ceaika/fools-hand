from __future__ import annotations

import math
import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_GAP, BTN_RADIUS,
)
from .widgets import Button

_REPEL_DIST   = 30    # px from button edge that triggers repulsion
_REPEL_FORCE  = 180   # how far it jumps away
_LERP_HOME    = 0.04  # how fast it drifts back home when cursor is away


class MainMenu:
    def __init__(self, screen: pygame.Surface, fonts: dict) -> None:
        self.screen = screen
        self.fonts  = fonts
        self.tick   = 0

        cx = WIDTH // 2
        total_h = 4 * BTN_H + 3 * BTN_GAP
        start_y = HEIGHT // 2 - total_h // 2 + 60

        self.buttons: list[tuple[Button, str]] = []
        for i, (label, action) in enumerate([
            ("PLAY",     "play"),
            ("TUTORIAL", "tutorial"),
            ("SETTINGS", "settings"),
            ("QUIT",     "quit"),
        ]):
            y   = start_y + i * (BTN_H + BTN_GAP)
            btn = Button(cx, y, label, font=fonts["btn"])
            self.buttons.append((btn, action))

        quit_btn          = self.buttons[-1][0]
        self._quit_btn    = quit_btn
        self._quit_home   = (float(quit_btn.rect.centerx),
                             float(quit_btn.rect.centery))
        self._quit_fx     = float(quit_btn.rect.centerx)
        self._quit_fy     = float(quit_btn.rect.centery)

        self.x_btn     = pygame.Rect(WIDTH - 48, 12, 36, 36)
        self._vignette = self._make_vignette()

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.x_btn.collidepoint(event.pos):
                return "quit"
        for btn, action in self.buttons:
            if btn.handle_event(event):
                return action
        return None

    def update(self) -> None:
        self.tick += 1
        mouse = pygame.mouse.get_pos()
        self._update_quit_btn(mouse)
        for btn, _ in self.buttons:
            btn.update(mouse)

    def draw(self) -> None:
        self.screen.fill(BG)
        self._draw_bg_grid()
        self.screen.blit(self._vignette, (0, 0))
        self._draw_title()
        self._draw_divider()
        for btn, _ in self.buttons:
            btn.draw(self.screen)
        self._draw_x_button()
        self._draw_footer()

    # ── quit repulsion logic ──────────────────────────────────────────────────

    def _update_quit_btn(self, mouse: tuple) -> None:
        mx, my = float(mouse[0]), float(mouse[1])
        bx, by = self._quit_fx, self._quit_fy
        hw     = self._quit_btn.rect.w / 2
        hh     = self._quit_btn.rect.h / 2

        dx   = max(0.0, abs(mx - bx) - hw)
        dy   = max(0.0, abs(my - by) - hh)
        dist = math.hypot(dx, dy)

        if dist < _REPEL_DIST:
            vec_x    = bx - mx
            vec_y    = by - my
            length   = math.hypot(vec_x, vec_y) or 1.0
            strength = (1.0 - dist / _REPEL_DIST) * _REPEL_FORCE
            target_x = bx + (vec_x / length) * strength
            target_y = by + (vec_y / length) * strength
            lerp     = 0.18
        else:
            target_x, target_y = self._quit_home
            lerp = _LERP_HOME

        margin_x = self._quit_btn.rect.w // 2 + 10
        margin_y = self._quit_btn.rect.h // 2 + 10
        target_x = max(margin_x, min(WIDTH  - margin_x, target_x))
        target_y = max(margin_y, min(HEIGHT - margin_y, target_y))

        self._quit_fx += (target_x - self._quit_fx) * lerp
        self._quit_fy += (target_y - self._quit_fy) * lerp

        self._quit_btn.rect.centerx = int(self._quit_fx)
        self._quit_btn.rect.centery = int(self._quit_fy)

    # ── visual helpers ────────────────────────────────────────────────────────

    def _make_vignette(self) -> pygame.Surface:
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        cx, cy = WIDTH // 2, HEIGHT // 2
        max_r  = int(math.hypot(cx, cy))
        # draw concentric circles from edge inward, each more transparent
        steps = 24
        for i in range(steps, 0, -1):
            ratio = i / steps
            alpha = int((ratio ** 1.6) * 200)
            r     = int(max_r * ratio)
            pygame.draw.circle(surf, (0, 0, 0, alpha), (cx, cy), r)
        return surf

    def _draw_bg_grid(self) -> None:
        grid_col = (30, 15, 50)
        spacing  = 40
        for x in range(0, WIDTH, spacing):
            pygame.draw.line(self.screen, grid_col, (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, spacing):
            pygame.draw.line(self.screen, grid_col, (0, y), (WIDTH, y))

    def _draw_title(self) -> None:
        pulse      = abs(math.sin(self.tick * 0.03)) * 6
        title_font = self.fonts["title"]
        ty         = HEIGHT // 4 - 30

        for offset, alpha in [(10, 30), (6, 60), (3, 100)]:
            glow = title_font.render("FOOL'S HAND", False, NEON_GLOW)
            glow.set_alpha(alpha)
            gx = WIDTH // 2 - glow.get_width() // 2
            self.screen.blit(glow, (gx - offset // 2, ty + int(pulse)))
            self.screen.blit(glow, (gx + offset // 2, ty + int(pulse)))

        title = title_font.render("FOOL'S HAND", False, TEXT_MAIN)
        tx = WIDTH // 2 - title.get_width() // 2
        self.screen.blit(title, (tx, ty + int(pulse)))

        uw = title.get_width()
        ux = WIDTH // 2 - uw // 2
        uy = ty + title.get_height() + 10 + int(pulse)
        pygame.draw.rect(self.screen, NEON,      (ux, uy,     uw, 3))
        pygame.draw.rect(self.screen, NEON_GLOW, (ux, uy - 1, uw, 1))

        sub = self.fonts["sub"].render("A  DURAK  CARD  GAME", False, TEXT_DIM)
        sx  = WIDTH // 2 - sub.get_width() // 2
        self.screen.blit(sub, (sx, uy + 14))

    def _draw_divider(self) -> None:
        y  = HEIGHT // 2 + 10
        x0 = WIDTH // 2 - BTN_W // 2
        x1 = WIDTH // 2 + BTN_W // 2
        pygame.draw.line(self.screen, PURPLE, (x0, y), (x1, y), 1)

    def _draw_x_button(self) -> None:
        mouse  = pygame.mouse.get_pos()
        colour = NEON if self.x_btn.collidepoint(mouse) else PURPLE
        pygame.draw.rect(self.screen, PURPLE_DIM, self.x_btn, border_radius=4)
        pygame.draw.rect(self.screen, colour, self.x_btn, width=1, border_radius=4)
        label = self.fonts["small"].render("X", False, TEXT_MAIN)
        lx = self.x_btn.centerx - label.get_width() // 2
        ly = self.x_btn.centery - label.get_height() // 2
        self.screen.blit(label, (lx, ly))

    def _draw_footer(self) -> None:
        ver = self.fonts["small"].render("v0.1", False, TEXT_DIM)
        self.screen.blit(ver, (12, HEIGHT - ver.get_height() - 10))