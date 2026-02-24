from __future__ import annotations

import math
import random
import string
import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, BG2, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    GOLD, TEXT_MAIN, TEXT_DIM,
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
    def __init__(self, screen: pygame.Surface, fonts: dict,
                 vignette: pygame.Surface) -> None:
        self.screen = screen
        self.fonts  = fonts
        self.tick   = 0

        cx = WIDTH // 2
        total_h = 4 * BTN_H + 3 * BTN_GAP
        start_y = HEIGHT // 2 - total_h // 2 + 60

        self.buttons: list[tuple[Button, str]] = []
        for i, (label, action) in enumerate([
            ("PLAY",         "play"),
            ("TUTORIAL",     "tutorial"),
            ("SETTINGS",     "settings"),
            ("QUIT",         "quit"),
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

        self.x_btn        = pygame.Rect(WIDTH - 48, 12, 36, 36)
        self._trophy_btn  = pygame.Rect(WIDTH - 56, HEIGHT - 56, 40, 40)
        self._vignette    = vignette
        self._draw_target = self.screen

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

        # ── intro animation ───────────────────────────────────────────────────
        # Phase 1 (0–40):   black → scanline sweeps down revealing grid
        # Phase 2 (40–90):  title flickers on like a neon sign
        # Phase 3 (90–160): buttons spark in one by one with a left trail
        # Phase 4 (160+):   fully interactive, intro done
        self._intro_tick  = 0
        self._intro_done  = False
        import random as _r
        self._flicker_seq = [_r.choice([0, 0, 80, 0, 255, 180, 255, 0, 255, 255])
                             for _ in range(60)]

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event_with_rect(self, event: pygame.event.Event) -> tuple:
        """Like handle_event but also returns the clicked button's rect."""
        if event.type == pygame.QUIT:
            return "quit", None
        # Skip all interaction until intro is done; click/key skips it
        if not self._intro_done:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self._intro_tick  = 999
                self._intro_done  = True
            return None, None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.x_btn.collidepoint(event.pos):
                return "quit", self.x_btn
            if self._trophy_btn.collidepoint(event.pos):
                return "achievements", self._trophy_btn
            if self._title_rect.collidepoint(event.pos) and not self._decoding:
                self._title_clicks += 1
                if self._title_clicks >= _CLICKS_NEEDED and not self._title_decoded:
                    self._decoding    = True
                    self._decode_tick = 0
            if self._credits_tab.collidepoint(event.pos):
                self._panel_open = not self._panel_open
                return None, None
            panel_rect = pygame.Rect(0, 0, int(self._panel_x) + _PANEL_W, HEIGHT)
            if self._panel_open and not panel_rect.collidepoint(event.pos):
                self._panel_open = False
                return None, None
        for btn, action in self.buttons:
            if btn.handle_event(event):
                return action, btn.rect.copy()
        return None, None

    def handle_event(self, event: pygame.event.Event) -> str | None:
        action, _ = self.handle_event_with_rect(event)
        return action

    def update(self) -> None:
        self.tick += 1
        if not self._intro_done:
            self._intro_tick += 1
            if self._intro_tick >= 160:
                self._intro_done = True
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

    def draw(self, surface: pygame.Surface | None = None) -> None:
        self._draw_target = surface if surface is not None else self.screen
        t  = self._draw_target
        it = self._intro_tick

        t.fill(BG)

        # Phase 1: scanline reveals the grid progressively
        if it < 40:
            reveal_y = int((it / 40) * HEIGHT)
            self._draw_bg_grid(clip_y=reveal_y)
        else:
            self._draw_bg_grid()

        t.blit(self._vignette, (0, 0))

        # Phase 1: scanline beam
        if it < 40:
            self._draw_scanline(it)

        # Title: flickers on in phase 2
        title_alpha = self._intro_title_alpha(it)
        self._draw_title(alpha_override=title_alpha)
        self._draw_divider()

        # Buttons: spark in during phase 3
        for i, (btn, _) in enumerate(self.buttons):
            btn_alpha, btn_offset = self._intro_btn_state(it, i)
            btn.draw(t, alpha_override=btn_alpha, x_offset=btn_offset)

        self._draw_x_button()
        self._draw_footer()
        self._draw_credits_panel()
        self._draw_trophy_btn()

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
        self._draw_target.blit(panel_surf, (px, 0))

        # neon left border edge
        pygame.draw.line(self._draw_target, NEON,
                         (px + _PANEL_W, 0),
                         (px + _PANEL_W, HEIGHT), 2)

        # credits content
        small = self.fonts["small"]
        body  = self.fonts["body"]
        y     = 60
        pad   = px + 24

        title_surf = small.render("CREDITS", False, NEON_GLOW)
        self._draw_target.blit(title_surf, (pad, y))
        y += title_surf.get_height() + 4
        pygame.draw.rect(self._draw_target, NEON, (pad, y, _PANEL_W - 48, 2))
        y += 16

        for header, value in self._credits:
            if header:
                label = small.render(header, False, NEON)
                self._draw_target.blit(label, (pad, y))
                y += label.get_height() + 8
            elif value:
                label = body.render(value, False, TEXT_MAIN)
                self._draw_target.blit(label, (pad, y))
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
        self._draw_target.blit(tab_surf, (tab.x, tab.y))
        pygame.draw.rect(self._draw_target, colour, tab, width=1, border_radius=3)

        # arrow points right when closed, left when open
        arrow = ">" if not self._panel_open else "<"
        label = self.fonts["btn"].render(arrow, False, TEXT_MAIN)
        lx    = tab.centerx - label.get_width() // 2
        ly    = tab.centery - label.get_height() // 2
        self._draw_target.blit(label, (lx, ly))

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

    # ── intro helpers ─────────────────────────────────────────────────────────

    def _draw_scanline(self, it: int) -> None:
        t  = self._draw_target
        sy = int((it / 40) * HEIGHT)
        beam = pygame.Surface((WIDTH, 4), pygame.SRCALPHA)
        beam.fill((180, 100, 255, 200))
        t.blit(beam, (0, sy))
        for trail, alpha in [(8, 60), (20, 25), (40, 10)]:
            glow = pygame.Surface((WIDTH, trail), pygame.SRCALPHA)
            glow.fill((140, 60, 220, alpha))
            t.blit(glow, (0, max(0, sy - trail)))

    def _intro_title_alpha(self, it: int) -> int:
        if it < 40:
            return 0
        if it >= 90:
            return 255
        fi = min(it - 40, len(self._flicker_seq) - 1)
        return self._flicker_seq[fi]

    def _intro_btn_state(self, it: int, btn_idx: int) -> tuple:
        start = 90 + btn_idx * 14
        if it < start:
            return 0, -60
        elapsed = it - start
        if elapsed >= 20:
            return 255, 0
        progress = elapsed / 20
        ease     = 1 - (1 - progress) ** 3
        return int(255 * ease), int(-60 * (1 - ease))

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

    def _draw_bg_grid(self, clip_y: int = None) -> None:
        grid_col = (30, 15, 50)
        spacing  = 40
        max_y    = clip_y if clip_y is not None else HEIGHT
        for x in range(0, WIDTH, spacing):
            pygame.draw.line(self._draw_target, grid_col, (x, 0), (x, max_y))
        for y in range(0, max_y, spacing):
            pygame.draw.line(self._draw_target, grid_col, (0, y), (WIDTH, y))

    def _draw_title(self, alpha_override: int = 255, x_offset: int = 0) -> None:
        if alpha_override == 0:
            return
        pulse      = abs(math.sin(self.tick * 0.03)) * 6
        title_font = self.fonts["title"]
        ty         = HEIGHT // 4 - 30

        display = "".join(self._decode_text) if (self._decoding or self._title_decoded) else _TITLE_NORMAL
        colour  = NEON_GLOW if self._title_decoded else TEXT_MAIN

        tx_base = WIDTH // 2

        for offset, glow_alpha in [(10, 30), (6, 60), (3, 100)]:
            glow = title_font.render(display, False, NEON_GLOW)
            glow.set_alpha(int(glow_alpha * alpha_override / 255))
            gx = tx_base - glow.get_width() // 2 + x_offset
            self._draw_target.blit(glow, (gx - offset // 2, ty + int(pulse)))
            self._draw_target.blit(glow, (gx + offset // 2, ty + int(pulse)))

        title = title_font.render(display, False, colour)
        title.set_alpha(alpha_override)
        tx    = tx_base - title.get_width() // 2 + x_offset
        self._draw_target.blit(title, (tx, ty + int(pulse)))

        self._title_rect = pygame.Rect(tx, ty + int(pulse),
                                       title.get_width(), title.get_height())

        uw = title.get_width()
        ux = tx
        uy = ty + title.get_height() + 10 + int(pulse)
        line_col  = NEON_GLOW if self._title_decoded else NEON
        line_surf = pygame.Surface((uw, 3), pygame.SRCALPHA)
        line_surf.fill((*line_col, alpha_override))
        self._draw_target.blit(line_surf, (ux, uy))

        sub_text = "A  DURAK  CARD  GAME" if not self._title_decoded else "the original name"
        sub      = self.fonts["sub"].render(sub_text, False, TEXT_DIM)
        sub.set_alpha(alpha_override)
        sx       = tx_base - sub.get_width() // 2 + x_offset
        self._draw_target.blit(sub, (sx, uy + 14))

    def _draw_divider(self) -> None:
        y  = HEIGHT // 2 + 10
        x0 = WIDTH // 2 - BTN_W // 2
        x1 = WIDTH // 2 + BTN_W // 2
        pygame.draw.line(self._draw_target, PURPLE, (x0, y), (x1, y), 1)

    def _draw_x_button(self) -> None:
        mouse  = pygame.mouse.get_pos()
        colour = NEON if self.x_btn.collidepoint(mouse) else PURPLE
        pygame.draw.rect(self._draw_target, PURPLE_DIM, self.x_btn, border_radius=4)
        pygame.draw.rect(self._draw_target, colour, self.x_btn, width=1, border_radius=4)
        label = self.fonts["small"].render("X", False, TEXT_MAIN)
        lx    = self.x_btn.centerx - label.get_width() // 2
        ly    = self.x_btn.centery - label.get_height() // 2
        self._draw_target.blit(label, (lx, ly))

    def _draw_footer(self) -> None:
        small = self.fonts["small"]
        ver   = small.render("demo-release | DO NOT REDISTRIBUTE", False, TEXT_DIM)
        self._draw_target.blit(ver, (12, HEIGHT - ver.get_height() - 10))
        rights = small.render("(c) 2026 Dumitru Ceaicovschi", False, TEXT_DIM)
        self._draw_target.blit(rights, (WIDTH - rights.get_width() - 12,
                                   HEIGHT - rights.get_height() - 10))

    def _draw_trophy_btn(self) -> None:
        from .achievements import get_global_stats, ACHIEVEMENTS
        mouse    = pygame.mouse.get_pos()
        hov      = self._trophy_btn.collidepoint(mouse)
        stats    = get_global_stats()
        count    = len(stats.unlocked)
        total    = len(ACHIEVEMENTS)
        is_full  = (count == total)

        col_bg  = (40, 20, 70, 200)  if not hov else (60, 30, 100, 220)
        col_bdr = GOLD               if is_full  else (NEON if hov else PURPLE_DIM)

        panel = pygame.Surface((self._trophy_btn.width, self._trophy_btn.height),
                                pygame.SRCALPHA)
        pygame.draw.rect(panel, col_bg,  panel.get_rect(), border_radius=6)
        pygame.draw.rect(panel, (*col_bdr, 220), panel.get_rect(),
                         width=1, border_radius=6)
        self._draw_target.blit(panel, self._trophy_btn.topleft)

        # Trophy symbol
        f   = self.fonts["btn"]
        sym = f.render("*", False, GOLD if is_full else TEXT_DIM)
        self._draw_target.blit(sym, (
            self._trophy_btn.centerx - sym.get_width()  // 2,
            self._trophy_btn.centery - sym.get_height() // 2 - 4,
        ))

        # Counter badge
        f_sm  = self.fonts["small"]
        badge = f_sm.render(f"{count}/{total}", False,
                             GOLD if is_full else TEXT_DIM)
        self._draw_target.blit(badge, (
            self._trophy_btn.centerx - badge.get_width() // 2,
            self._trophy_btn.bottom  - badge.get_height() - 2,
        ))