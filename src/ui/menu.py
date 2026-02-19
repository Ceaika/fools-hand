from __future__ import annotations

import math
import random
import string
import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, BG2, NEON, NEON_GLOW, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_GAP, BTN_RADIUS,
)
from .widgets import Button

_REPEL_DIST  = 30
_REPEL_FORCE = 180
_LERP_HOME   = 0.04

_PANEL_W     = 280
_PANEL_LERP  = 0.12

_TITLE_NORMAL  = "FOOL'S HAND"
_TITLE_SECRET  = "DURAK OFFLINE"
_DECODE_CHARS  = string.ascii_uppercase + "!@#$%^&*?><~"
_DECODE_SPEED  = 20   # ticks per scramble step
_CLICKS_NEEDED = 14


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

        quit_btn        = self.buttons[-1][0]
        self._quit_btn  = quit_btn
        self._quit_home = (float(quit_btn.rect.centerx),
                           float(quit_btn.rect.centery))
        self._quit_fx   = float(quit_btn.rect.centerx)
        self._quit_fy   = float(quit_btn.rect.centery)

        # credits panel — slides in from the left
        self._panel_open   = False
        self._panel_x      = float(-_PANEL_W)   # current x (off screen when closed)
        self._credits_tab  = pygame.Rect(0, HEIGHT - 48, 110, 32)

        self.x_btn     = pygame.Rect(WIDTH - 48, 12, 36, 36)
        self._vignette = self._make_vignette()

        # title easter egg
        self._title_clicks  = 0
        self._title_decoded = False
        self._decoding      = False
        self._decode_tick   = 0
        self._decode_text   = list(_TITLE_NORMAL)  # current display chars
        self._title_rect    = pygame.Rect(0, 0, 0, 0)  # updated each draw

        self._credits = [
            ("DEVELOPER",  ""),
            ("",           "Dumitru Ceaicovschi"),
            ("",           ""),
            ("STAKEHOLDERS", ""),
            ("",           "Cassio L. B. Tripolino"),
            ("",           "  game design insight"),
            ("",           ""),
            ("",           "Hilary Fitzjohn"),
            ("",           "  cs teacher & advisor"),
            ("",           ""),
            ("",           "Durak Players"),
            ("",           "  target audience"),
        ]

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.QUIT:
            return "quit"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.x_btn.collidepoint(event.pos):
                return "quit"

            # title easter egg
            if self._title_rect.collidepoint(event.pos) and not self._decoding:
                self._title_clicks += 1
                if self._title_clicks >= _CLICKS_NEEDED and not self._title_decoded:
                    self._decoding    = True
                    self._decode_tick = 0

            # toggle credits panel via tab
            if self._credits_tab.collidepoint(event.pos):
                self._panel_open = not self._panel_open
                return None

            # close panel if clicking outside it while open
            panel_rect = pygame.Rect(0, 0, int(self._panel_x) + _PANEL_W, HEIGHT)
            if self._panel_open and not panel_rect.collidepoint(event.pos):
                self._panel_open = False
                return None

        for btn, action in self.buttons:
            if btn.handle_event(event):
                return action
        return None

    def update(self) -> None:
        self.tick += 1
        mouse = pygame.mouse.get_pos()
        self._update_quit_btn(mouse)
        self._update_panel()
        self._update_decode()
        for btn, _ in self.buttons:
            btn.update(mouse)

    def _update_decode(self) -> None:
        if not self._decoding:
            return

        target = list(_TITLE_SECRET)
        # pad/truncate to same length for decode sweep
        # each character resolves left to right based on decode_tick
        self._decode_tick += 1
        resolved = self._decode_tick // _DECODE_SPEED  # how many chars have settled

        new_text = []
        for i, ch in enumerate(target):
            if i < resolved:
                new_text.append(ch)  # settled
            elif ch == ' ' or ch == "'":
                new_text.append(ch)  # keep spaces/punctuation as-is
            else:
                new_text.append(random.choice(_DECODE_CHARS))  # still scrambling

        self._decode_text = new_text

        if resolved >= len(target):
            self._decoding      = False
            self._title_decoded = True
            self._decode_text   = list(_TITLE_SECRET)

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
        # panel drawn last so it sits on top
        self._draw_credits_panel()

    # ── credits panel ─────────────────────────────────────────────────────────

    def _update_panel(self) -> None:
        target = 0.0 if self._panel_open else float(-_PANEL_W)
        self._panel_x += (target - self._panel_x) * _PANEL_LERP

    def _draw_credits_panel(self) -> None:
        px = int(self._panel_x)

        # only draw if even slightly visible
        if px <= -_PANEL_W:
            self._draw_credits_tab(px)
            return

        # panel background
        panel_rect = pygame.Rect(px, 0, _PANEL_W, HEIGHT)
        panel_surf = pygame.Surface((_PANEL_W, HEIGHT), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 40, 230))
        self.screen.blit(panel_surf, (px, 0))

        # neon left border edge
        pygame.draw.line(self.screen, NEON,
                         (px + _PANEL_W, 0),
                         (px + _PANEL_W, HEIGHT), 2)

        # credits content
        small = self.fonts["small"]
        body  = self.fonts["body"]
        y     = 60
        pad   = px + 24

        title_surf = small.render("CREDITS", False, NEON_GLOW)
        self.screen.blit(title_surf, (pad, y))
        y += title_surf.get_height() + 4
        pygame.draw.rect(self.screen, NEON, (pad, y, _PANEL_W - 48, 2))
        y += 16

        for header, value in self._credits:
            if header:
                label = small.render(header, False, NEON)
                self.screen.blit(label, (pad, y))
                y += label.get_height() + 8
            elif value:
                label = body.render(value, False, TEXT_MAIN)
                self.screen.blit(label, (pad, y))
                y += label.get_height() + 6

        self._draw_credits_tab(px)

    def _draw_credits_tab(self, px: int) -> None:
        # tab sits on the right edge of the panel
        tab_x = px + _PANEL_W
        tab   = pygame.Rect(tab_x, HEIGHT // 2 - 24, 28, 48)
        self._credits_tab = tab

        mouse  = pygame.mouse.get_pos()
        colour = NEON if tab.collidepoint(mouse) else PURPLE

        tab_surf = pygame.Surface((tab.w, tab.h), pygame.SRCALPHA)
        tab_surf.fill((20, 10, 40, 210))
        self.screen.blit(tab_surf, (tab.x, tab.y))
        pygame.draw.rect(self.screen, colour, tab, width=1, border_radius=3)

        # arrow points right when closed, left when open
        arrow = ">" if not self._panel_open else "<"
        label = self.fonts["btn"].render(arrow, False, TEXT_MAIN)
        lx    = tab.centerx - label.get_width() // 2
        ly    = tab.centery - label.get_height() // 2
        self.screen.blit(label, (lx, ly))

    # ── quit repulsion ────────────────────────────────────────────────────────

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
        steps  = 24
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

        display = "".join(self._decode_text) if (self._decoding or self._title_decoded) else _TITLE_NORMAL
        colour  = NEON_GLOW if self._title_decoded else TEXT_MAIN

        for offset, alpha in [(10, 30), (6, 60), (3, 100)]:
            glow = title_font.render(display, False, NEON_GLOW)
            glow.set_alpha(alpha)
            gx = WIDTH // 2 - glow.get_width() // 2
            self.screen.blit(glow, (gx - offset // 2, ty + int(pulse)))
            self.screen.blit(glow, (gx + offset // 2, ty + int(pulse)))

        title = title_font.render(display, False, colour)
        tx    = WIDTH // 2 - title.get_width() // 2
        self.screen.blit(title, (tx, ty + int(pulse)))

        # store rect for click detection
        self._title_rect = pygame.Rect(tx, ty + int(pulse),
                                       title.get_width(), title.get_height())

        uw = title.get_width()
        ux = WIDTH // 2 - uw // 2
        uy = ty + title.get_height() + 10 + int(pulse)
        line_col = NEON_GLOW if self._title_decoded else NEON
        pygame.draw.rect(self.screen, line_col,  (ux, uy,     uw, 3))
        pygame.draw.rect(self.screen, NEON_GLOW, (ux, uy - 1, uw, 1))

        sub_text = "A  DURAK  CARD  GAME" if not self._title_decoded else "the original name"
        sub      = self.fonts["sub"].render(sub_text, False, TEXT_DIM)
        sx       = WIDTH // 2 - sub.get_width() // 2
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
        lx    = self.x_btn.centerx - label.get_width() // 2
        ly    = self.x_btn.centery - label.get_height() // 2
        self.screen.blit(label, (lx, ly))

    def _draw_footer(self) -> None:
        small = self.fonts["small"]
        ver   = small.render("pre-release", False, TEXT_DIM)
        self.screen.blit(ver, (12, HEIGHT - ver.get_height() - 10))
        rights = small.render("(c) 2025 Dumitru Ceaicovschi", False, TEXT_DIM)
        self.screen.blit(rights, (WIDTH - rights.get_width() - 12,
                                   HEIGHT - rights.get_height() - 10))