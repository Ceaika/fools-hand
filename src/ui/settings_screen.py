from __future__ import annotations

import math
import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    GOLD, TEXT_MAIN, TEXT_DIM,
    BTN_W, BTN_H, BTN_GAP, BTN_RADIUS,
)
from .widgets import Button
from . import audio
from .locale import t, get_lang, set_lang
from .font_manager import get_fonts, invalidate_cache

_SEG_COUNT = 20
_SEG_W     = 18
_SEG_H     = 32
_SEG_GAP   = 4
_BAR_W     = _SEG_COUNT * (_SEG_W + _SEG_GAP) - _SEG_GAP

_LANG_CODES   = ["en", "ru", "ro"]
_LANG_FLAGS   = ["EN", "RU", "RO"]
_PILL_W       = 100
_PILL_H       = 44
_PILL_GAP     = 8


class SegmentedSlider:
    def __init__(self, cx: int, y: int, initial: float = 1.0) -> None:
        self._cx       = cx
        self._y        = y
        self._value    = max(0.0, min(1.0, initial))
        self._dragging = False
        self._x0       = cx - _BAR_W // 2

    @property
    def value(self) -> float:
        return self._value

    def _seg_rect(self, i: int) -> pygame.Rect:
        x = self._x0 + i * (_SEG_W + _SEG_GAP)
        return pygame.Rect(x, self._y - _SEG_H // 2, _SEG_W, _SEG_H)

    def _value_from_mouse(self, mx: int) -> float:
        rel     = mx - self._x0
        seg     = rel / (_SEG_W + _SEG_GAP)
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
        lit   = round(self._value * _SEG_COUNT)
        mouse = pygame.mouse.get_pos()
        for i in range(_SEG_COUNT):
            r      = self._seg_rect(i)
            filled = i < lit
            if filled:
                tv  = i / max(_SEG_COUNT - 1, 1)
                col = (int(NEON[0] * (0.6 + 0.4 * tv)),
                       int(NEON[1] * (0.6 + 0.4 * tv)),
                       int(NEON[2] * (0.6 + 0.4 * tv)))
                border = NEON_GLOW
            else:
                col    = PURPLE_DIM
                border = PURPLE
            pygame.draw.rect(surf, col,    r, border_radius=3)
            pygame.draw.rect(surf, border, r, width=1, border_radius=3)
        if self._hit(mouse):
            preview = round(self._value_from_mouse(mouse[0]) * _SEG_COUNT)
            for i in range(_SEG_COUNT):
                if i == preview - 1:
                    r = self._seg_rect(i)
                    pygame.draw.rect(surf, TEXT_MAIN, r, width=2, border_radius=3)


class SettingsScreen:
    def __init__(self, screen: pygame.Surface, fonts: dict,
                 vignette: pygame.Surface) -> None:
        self.screen    = screen
        self.fonts     = fonts
        self._vignette = vignette
        self.tick      = 0
        self._on_back: callable | None = None
        self._on_lang_change: callable | None = None

        cx = WIDTH // 2
        slider_start_y = HEIGHT // 2 - 80
        slider_gap     = 90

        self._slider_master = SegmentedSlider(cx, slider_start_y,           initial=audio.MUSIC_VOL)
        self._slider_sfx    = SegmentedSlider(cx, slider_start_y + slider_gap,   initial=audio.SFX_VOL)
        self._slider_bgm    = SegmentedSlider(cx, slider_start_y + slider_gap*2, initial=audio.MUSIC_VOL)

        # Language pill selector
        total_w = len(_LANG_CODES) * _PILL_W + (len(_LANG_CODES) - 1) * _PILL_GAP
        pill_y  = slider_start_y + slider_gap * 3 + 30
        self._pill_rects = []
        for i in range(len(_LANG_CODES)):
            x = cx - total_w // 2 + i * (_PILL_W + _PILL_GAP)
            self._pill_rects.append(pygame.Rect(x, pill_y, _PILL_W, _PILL_H))

        self._back_btn = Button(90, 24, "< BACK", w=140, h=36, font=fonts["small"])

    def set_on_back(self, fn: callable) -> None:
        self._on_back = fn

    def set_on_lang_change(self, fn: callable) -> None:
        self._on_lang_change = fn

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._go_back()
            return None

        if self._back_btn.handle_event(event):
            self._go_back()
            return None

        if self._slider_master.handle_event(event):
            v = self._slider_master.value
            audio.set_music_volume(v)
            audio.set_sfx_volume(v)
            self._slider_sfx._value = v
            self._slider_bgm._value = v
        if self._slider_sfx.handle_event(event):
            audio.set_sfx_volume(self._slider_sfx.value)
        if self._slider_bgm.handle_event(event):
            audio.set_music_volume(self._slider_bgm.value)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._pill_rects):
                if rect.collidepoint(event.pos):
                    new_lang = _LANG_CODES[i]
                    if new_lang != get_lang():
                        set_lang(new_lang)
                        invalidate_cache()
                        if self._on_lang_change:
                            self._on_lang_change(new_lang)
                    break

        return None

    def _go_back(self) -> None:
        if self._on_back:
            self._on_back()

    def update(self) -> None:
        self.tick += 1
        f = get_fonts()
        self._back_btn.font  = f["small"]
        self._back_btn.update(pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface | None = None) -> None:
        t    = surface or self.screen
        W, H = t.get_width(), t.get_height()
        cx   = W // 2
        f    = get_fonts()

        t.fill(BG)
        self._draw_bg_grid(t, W, H)
        t.blit(self._vignette, (0, 0))

        title_f = f["title"]
        title_s = title_f.render(t_("settings.title"), False, TEXT_MAIN)
        ty      = H // 4 - 30
        pulse   = abs(math.sin(self.tick * 0.03)) * 4

        for offset, alpha in [(8, 30), (4, 70)]:
            glow = title_f.render(t_("settings.title"), False, NEON_GLOW)
            glow.set_alpha(alpha)
            t.blit(glow, (cx - glow.get_width() // 2 - offset // 2, ty + int(pulse)))
            t.blit(glow, (cx - glow.get_width() // 2 + offset // 2, ty + int(pulse)))
        t.blit(title_s, (cx - title_s.get_width() // 2, ty + int(pulse)))

        uw = title_s.get_width()
        ux = cx - uw // 2
        uy = ty + title_s.get_height() + 10 + int(pulse)
        pygame.draw.rect(t, NEON, (ux, uy, uw, 3))

        fsm = f["small"]
        for label_key, slider in [("settings.master", self._slider_master),
                                   ("settings.sfx",    self._slider_sfx),
                                   ("settings.bgm",    self._slider_bgm)]:
            lbl = fsm.render(t_(label_key), False, TEXT_DIM)
            t.blit(lbl, (cx - _BAR_W // 2, slider._y - 28))
            pct = fsm.render(f"{int(slider.value * 100)}", False, TEXT_MAIN)
            t.blit(pct, (cx + _BAR_W // 2 + 16, slider._y - pct.get_height() // 2))
            slider.draw(t)

        # Language label
        lang_lbl = fsm.render(t_("settings.language"), False, TEXT_DIM)
        pill_top = self._pill_rects[0].y
        t.blit(lang_lbl, (cx - _BAR_W // 2, pill_top - 28))

        # Pill selector
        mouse    = pygame.mouse.get_pos()
        cur_lang = get_lang()
        for i, rect in enumerate(self._pill_rects):
            code    = _LANG_CODES[i]
            active  = (code == cur_lang)
            hov     = rect.collidepoint(mouse) and not active

            if active:
                bg_col  = NEON_DARK
                bdr_col = NEON
                txt_col = TEXT_MAIN
            elif hov:
                bg_col  = (30, 15, 55)
                bdr_col = PURPLE
                txt_col = TEXT_DIM
            else:
                bg_col  = (18, 8, 32)
                bdr_col = PURPLE_DIM
                txt_col = (60, 40, 90)

            pygame.draw.rect(t, bg_col,  rect, border_radius=BTN_RADIUS + 2)
            pygame.draw.rect(t, bdr_col, rect, width=2 if active else 1,
                             border_radius=BTN_RADIUS + 2)

            # Active glow
            if active:
                gs = pygame.Surface((rect.w + 10, rect.h + 10), pygame.SRCALPHA)
                pygame.draw.rect(gs, (*NEON, 25), gs.get_rect(),
                                 border_radius=BTN_RADIUS + 6)
                t.blit(gs, (rect.x - 5, rect.y - 5))

            # Short code large + full name small below
            code_s = f["btn"].render(_LANG_FLAGS[i], False, txt_col if not active else NEON_GLOW)
            name_key = f"settings.lang_{code}"
            name_s   = fsm.render(t_(name_key), False, txt_col)

            # Scale name if too wide
            if name_s.get_width() > rect.w - 8:
                scale  = (rect.w - 8) / name_s.get_width()
                name_s = name_s.convert_alpha()
                name_s = pygame.transform.smoothscale(
                    name_s, (rect.w - 8, max(1, int(name_s.get_height() * scale))))

            total_h = code_s.get_height() + 2 + name_s.get_height()
            base_y  = rect.centery - total_h // 2

            t.blit(code_s, (rect.centerx - code_s.get_width() // 2, base_y))
            t.blit(name_s, (rect.centerx - name_s.get_width() // 2,
                             base_y + code_s.get_height() + 2))

        self._back_btn.text  = t_("settings.back")
        self._back_btn.draw(t)

    def _draw_bg_grid(self, t, W, H) -> None:
        for x in range(0, W, 40):
            pygame.draw.line(t, (30, 15, 50), (x, 0), (x, H))
        for y in range(0, H, 40):
            pygame.draw.line(t, (30, 15, 50), (0, y), (W, y))


def t_(key: str) -> str:
    """Local alias so the surface variable 't' doesn't shadow locale.t()"""
    return t(key)