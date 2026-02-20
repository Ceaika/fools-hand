from __future__ import annotations

import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_GAP, BTN_RADIUS,
)
from .widgets import Button
from . import audio

# ── Segmented volume bar ──────────────────────────────────────────────────────

_SEG_COUNT  = 20       # number of blocks
_SEG_W      = 18       # block width
_SEG_H      = 32       # block height
_SEG_GAP    = 4        # gap between blocks
_BAR_W      = _SEG_COUNT * (_SEG_W + _SEG_GAP) - _SEG_GAP


class SegmentedSlider:
    """Row of rectangular segments that light up — click or drag to set level."""

    def __init__(self, cx: int, y: int, initial: float = 1.0) -> None:
        self._cx       = cx
        self._y        = y
        self._value    = max(0.0, min(1.0, initial))
        self._dragging = False
        self._x0       = cx - _BAR_W // 2   # left edge of first segment

    @property
    def value(self) -> float:
        return self._value

    def _seg_rect(self, i: int) -> pygame.Rect:
        x = self._x0 + i * (_SEG_W + _SEG_GAP)
        return pygame.Rect(x, self._y - _SEG_H // 2, _SEG_W, _SEG_H)

    def _value_from_mouse(self, mx: int) -> float:
        rel = mx - self._x0
        seg = rel / (_SEG_W + _SEG_GAP)
        # snap to nearest segment boundary
        snapped = round(seg) / _SEG_COUNT
        return max(0.0, min(1.0, snapped))

    def _hit(self, pos) -> bool:
        hit_rect = pygame.Rect(self._x0 - 4, self._y - _SEG_H // 2 - 4,
                               _BAR_W + 8, _SEG_H + 8)
        return hit_rect.collidepoint(pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hit(event.pos):
                self._dragging = True
                new = self._value_from_mouse(event.pos[0])
                changed = abs(new - self._value) > 0.001
                self._value = new
                return changed
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False
        if event.type == pygame.MOUSEMOTION and self._dragging:
            new = self._value_from_mouse(event.pos[0])
            changed = abs(new - self._value) > 0.001
            self._value = new
            return changed
        return False

    def draw(self, surf: pygame.Surface) -> None:
        lit = round(self._value * _SEG_COUNT)   # how many segments are on
        mouse = pygame.mouse.get_pos()

        for i in range(_SEG_COUNT):
            r      = self._seg_rect(i)
            filled = i < lit

            # colour: lit segments glow neon, unlit are dim purple
            if filled:
                # gradient: earlier segments slightly dimmer
                t      = i / max(_SEG_COUNT - 1, 1)
                r_val  = int(NEON[0] * (0.6 + 0.4 * t))
                g_val  = int(NEON[1] * (0.6 + 0.4 * t))
                b_val  = int(NEON[2] * (0.6 + 0.4 * t))
                col    = (r_val, g_val, b_val)
                border = NEON_GLOW
            else:
                col    = PURPLE_DIM
                border = PURPLE

            pygame.draw.rect(surf, col,    r, border_radius=3)
            pygame.draw.rect(surf, border, r, width=1, border_radius=3)

        # hover: show which segment the mouse would snap to
        if self._hit(mouse):
            preview = round(self._value_from_mouse(mouse[0]) * _SEG_COUNT)
            for i in range(_SEG_COUNT):
                if i == preview - 1:   # highlight the edge segment
                    r = self._seg_rect(i)
                    pygame.draw.rect(surf, TEXT_MAIN, r, width=2, border_radius=3)


# ── SettingsScreen ────────────────────────────────────────────────────────────

class SettingsScreen:
    """
    Shared settings screen — opened from main menu or in-game pause.
    `on_back` callback is called when the back button is pressed.
    """

    def __init__(self, screen: pygame.Surface, fonts: dict,
                 vignette: pygame.Surface) -> None:
        self.screen   = screen
        self.fonts    = fonts
        self._vignette = vignette
        self.tick      = 0

        cx = WIDTH // 2

        # ── Sliders ───────────────────────────────────────────────────────
        slider_start_y = HEIGHT // 2 - 60
        slider_gap     = 100

        self._slider_master = SegmentedSlider(cx, slider_start_y,
                                              initial=audio.MUSIC_VOL)
        self._slider_sfx    = SegmentedSlider(cx, slider_start_y + slider_gap,
                                              initial=audio.SFX_VOL)
        self._slider_bgm    = SegmentedSlider(cx, slider_start_y + slider_gap * 2,
                                              initial=audio.MUSIC_VOL)

        # ── Language (WIP) ────────────────────────────────────────────────
        self._lang_rect    = pygame.Rect(cx - 120, slider_start_y + slider_gap * 3 + 20,
                                         240, BTN_H)
        self._lang_options = ["ENGLISH"]   # WIP — more to come
        self._lang_idx     = 0

        # ── Back button ───────────────────────────────────────────────────
        self._back_btn = Button(90, 24, "< BACK", w=140, h=36, font=fonts["small"])

        self._on_back : callable | None = None

    def set_on_back(self, fn: callable) -> None:
        self._on_back = fn

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._go_back()
            return None

        if self._back_btn.handle_event(event):
            self._go_back()
            return None

        # Sliders
        if self._slider_master.handle_event(event):
            v = self._slider_master.value
            audio.set_music_volume(v)
            audio.set_sfx_volume(v)
            self._slider_sfx._value    = v
            self._slider_bgm._value    = v

        if self._slider_sfx.handle_event(event):
            audio.set_sfx_volume(self._slider_sfx.value)

        if self._slider_bgm.handle_event(event):
            audio.set_music_volume(self._slider_bgm.value)

        # Language dropdown (WIP — just cycles for now)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._lang_rect.collidepoint(event.pos):
                self._lang_idx = (self._lang_idx + 1) % len(self._lang_options)

        return None

    def _go_back(self) -> None:
        if self._on_back:
            self._on_back()

    def update(self) -> None:
        self.tick += 1
        self._back_btn.update(pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface | None = None) -> None:
        t = surface or self.screen
        W, H = t.get_width(), t.get_height()
        cx   = W // 2

        t.fill(BG)
        self._draw_bg_grid(t, W, H)
        t.blit(self._vignette, (0, 0))

        # ── Title ─────────────────────────────────────────────────────────
        import math
        title_f   = self.fonts["title"]
        title_s   = title_f.render("SETTINGS", False, TEXT_MAIN)
        ty        = H // 4 - 30
        pulse     = abs(math.sin(self.tick * 0.03)) * 4

        for offset, alpha in [(8, 30), (4, 70)]:
            glow = title_f.render("SETTINGS", False, NEON_GLOW)
            glow.set_alpha(alpha)
            t.blit(glow, (cx - glow.get_width() // 2 - offset // 2,
                           ty + int(pulse)))
            t.blit(glow, (cx - glow.get_width() // 2 + offset // 2,
                           ty + int(pulse)))
        t.blit(title_s, (cx - title_s.get_width() // 2, ty + int(pulse)))

        # underline
        uw = title_s.get_width()
        ux = cx - uw // 2
        uy = ty + title_s.get_height() + 10 + int(pulse)
        pygame.draw.rect(t, NEON, (ux, uy, uw, 3))

        # ── Sliders ───────────────────────────────────────────────────────
        f = self.fonts["small"]

        entries = [
            ("MASTER AUDIO", self._slider_master),
            ("SFX",          self._slider_sfx),
            ("BGM",          self._slider_bgm),
        ]
        for label, slider in entries:
            lbl = f.render(label, False, TEXT_DIM)
            t.blit(lbl, (cx - _BAR_W // 2, slider._y - 28))

            pct = f.render(f"{int(slider.value * 100)}", False, TEXT_MAIN)
            t.blit(pct, (cx + _BAR_W // 2 + 16,
                          slider._y - pct.get_height() // 2))

            slider.draw(t)

        # ── Language ──────────────────────────────────────────────────────
        lang_label = f.render("LANGUAGE", False, TEXT_DIM)
        t.blit(lang_label, (cx - _BAR_W // 2,
                              self._lang_rect.y - 28))

        mouse = pygame.mouse.get_pos()
        is_hover = self._lang_rect.collidepoint(mouse)
        pygame.draw.rect(t, NEON_DARK if is_hover else PURPLE_DIM,
                          self._lang_rect, border_radius=BTN_RADIUS)
        pygame.draw.rect(t, NEON if is_hover else PURPLE,
                          self._lang_rect, width=2, border_radius=BTN_RADIUS)

        lang_val = f.render(
            self._lang_options[self._lang_idx] + "  v  (WIP)",
            False, TEXT_DIM)
        t.blit(lang_val, (self._lang_rect.centerx - lang_val.get_width() // 2,
                            self._lang_rect.centery - lang_val.get_height() // 2))

        # ── Back button ───────────────────────────────────────────────────
        self._back_btn.draw(t)

    # ── internal ─────────────────────────────────────────────────────────────

    def _draw_bg_grid(self, t, W, H) -> None:
        for x in range(0, W, 40):
            pygame.draw.line(t, (30, 15, 50), (x, 0), (x, H))
        for y in range(0, H, 40):
            pygame.draw.line(t, (30, 15, 50), (0, y), (W, y))