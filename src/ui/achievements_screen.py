"""
achievements_screen.py — Full achievement list viewer.
Click a card to focus it: others fade out, it flies to centre and expands.
"""
from __future__ import annotations

import math
import pygame

from .constants import (
    WIDTH, HEIGHT, BG,
    NEON, NEON_GLOW, NEON_DARK,
    PURPLE, PURPLE_DIM,
    GOLD, TEXT_MAIN, TEXT_DIM,
    BTN_RADIUS,
)
from .achievements import ACHIEVEMENTS, COMMON, RARE, EPIC, PLATINUM, get_global_stats
from .locale import t as _t
from .font_manager import get_fonts

_COLS     = 2
_CARD_W   = 510
_CARD_H   = 90
_CARD_GAP = 14
_PAD_X    = (WIDTH - _COLS * _CARD_W - (_COLS - 1) * _CARD_GAP) // 2
_TOP_Y    = 108
_ICON_W   = 58
_SCROLL_SPEED = 20

# Focused card dimensions
_FOCUS_W  = 660
_FOCUS_H  = 220
_FOCUS_X  = WIDTH  // 2 - _FOCUS_W // 2
_FOCUS_Y  = HEIGHT // 2 - _FOCUS_H // 2
_FOCUS_ICON_W = 90

# Animation duration in frames
_ANIM_DUR = 18

_TIER_COL = {
    COMMON:   (120, 90, 160),
    RARE:     (60,  140, 255),
    EPIC:     (255, 50,  120),
    PLATINUM: (255, 200, 80),
}
def _tier_label(tier: str) -> str:
    return _t(f"tier.{tier}")


def _ease(t: float) -> float:
    """Cubic ease in-out."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class AchievementsScreen:
    def __init__(self, screen, fonts, vignette):
        self.screen    = screen
        self.fonts     = fonts
        self._vignette = vignette
        self.tick      = 0

        self._scroll        = 0.0
        self._scroll_target = 0.0
        rows = math.ceil(len(ACHIEVEMENTS) / _COLS)
        content_h = rows * (_CARD_H + _CARD_GAP) + _CARD_GAP
        self._max_scroll = max(0, content_h - (HEIGHT - _TOP_Y - 64))

        bw, bh = 140, 40
        self._back_rect = pygame.Rect(20, HEIGHT - bh - 14, bw, bh)

        # Focus animation state
        self._focus_ach  = None   # Achievement currently focused
        self._focus_t    = 0.0   # 0.0 = list view, 1.0 = fully focused
        self._focusing   = False  # animating toward focus
        self._unfocusing = False  # animating back to list

        # Saved scroll position when entering focus
        self._scroll_before_focus = 0.0

        # Pre-compute each card's rest position (col, row index)
        self._card_positions = []
        for i in range(len(ACHIEVEMENTS)):
            col = i % _COLS
            row = i // _COLS
            x   = _PAD_X + col * (_CARD_W + _CARD_GAP)
            y   = _TOP_Y + _CARD_GAP + row * (_CARD_H + _CARD_GAP)
            self._card_positions.append((x, y))

    def _unlocked(self) -> set:
        return get_global_stats().unlocked

    def refresh(self) -> None:
        pass

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event) -> str | None:
        animating = self._focusing or self._unfocusing

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                if self._focus_ach and not animating:
                    self._start_unfocus()
                    return None
                if not self._focus_ach:
                    return "back"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if animating:
                return None
            if self._focus_ach:
                self._start_unfocus()
                return None
            if self._back_rect.collidepoint(event.pos):
                return "back"
            card = self._card_at(event.pos)
            if card is not None:
                self._start_focus(card)
                return None

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
            if not self._focus_ach and not animating:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4:
                        self._scroll_target = max(0, self._scroll_target - _SCROLL_SPEED * 3)
                    if event.button == 5:
                        self._scroll_target = min(self._max_scroll, self._scroll_target + _SCROLL_SPEED * 3)
                else:
                    self._scroll_target = max(0, min(self._max_scroll,
                                                     self._scroll_target - event.y * _SCROLL_SPEED))
        return None

    def _card_at(self, pos):
        for i, ach in enumerate(ACHIEVEMENTS):
            x, y = self._card_positions[i]
            y -= int(self._scroll)
            if y + _CARD_H < _TOP_Y or y > HEIGHT - 64:
                continue
            if pygame.Rect(x, y, _CARD_W, _CARD_H).collidepoint(pos):
                return ach
        return None

    def _start_focus(self, ach):
        self._focus_ach            = ach
        self._focus_t              = 0.0
        self._focusing             = True
        self._unfocusing           = False
        self._scroll_before_focus  = self._scroll

    def _start_unfocus(self):
        self._focusing   = False
        self._unfocusing = True

    # ── update ────────────────────────────────────────────────────────────────

    def update(self) -> None:
        self.tick += 1
        self._scroll += (self._scroll_target - self._scroll) * 0.18

        if self._focusing:
            self._focus_t += 1 / _ANIM_DUR
            if self._focus_t >= 1.0:
                self._focus_t  = 1.0
                self._focusing = False

        if self._unfocusing:
            self._focus_t -= 1 / _ANIM_DUR
            if self._focus_t <= 0.0:
                self._focus_t    = 0.0
                self._unfocusing = False
                self._focus_ach  = None

    # ── draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface=None) -> None:
        t = surface or self.screen
        t.fill(BG)
        self._draw_grid(t)
        self._draw_header(t)
        self._draw_all_cards(t)
        self._draw_back_btn(t)
        t.blit(self._vignette, (0, 0))

    def _draw_grid(self, t):
        for x in range(0, WIDTH, 40):
            pygame.draw.line(t, (22, 12, 38), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 40):
            pygame.draw.line(t, (22, 12, 38), (0, y), (WIDTH, y))

    def _draw_header(self, t):
        unlocked = self._unlocked()
        count    = len(unlocked)
        total    = len(ACHIEVEMENTS)
        cx       = WIDTH // 2
        f        = get_fonts()
        f_title  = f["title"]
        f_sm     = f["small"]

        title = f_title.render(_t("ach_screen.title"), False, TEXT_MAIN)
        glow  = f_title.render(_t("ach_screen.title"), False, NEON_GLOW)
        glow.set_alpha(35)
        t.blit(glow, (cx - glow.get_width() // 2 - 2, 20))
        t.blit(title, (cx - title.get_width() // 2, 20))

        bar_w, bar_h = 280, 7
        bx = cx - bar_w // 2
        by = 64
        pygame.draw.rect(t, PURPLE_DIM, (bx, by, bar_w, bar_h), border_radius=4)
        if count > 0:
            fill = max(4, int(bar_w * count / total))
            col  = GOLD if count == total else NEON
            pygame.draw.rect(t, col, (bx, by, fill, bar_h), border_radius=4)
            gs = pygame.Surface((fill + 8, bar_h + 8), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*col, 30), gs.get_rect(), border_radius=6)
            t.blit(gs, (bx - 4, by - 4))

        lbl_col = GOLD if count == total else TEXT_DIM
        lbl = f_sm.render(f"{count} / {total}  {_t('ach_screen.unlocked')}", False, lbl_col)
        t.blit(lbl, (cx - lbl.get_width() // 2, by + bar_h + 5))
        pygame.draw.line(t, PURPLE_DIM, (40, _TOP_Y - 6), (WIDTH - 40, _TOP_Y - 6), 1)

    def _draw_all_cards(self, t):
        p        = _ease(self._focus_t)
        unlocked = self._unlocked()

        # Clip to content area for scrolling cards
        clip = pygame.Rect(0, _TOP_Y, WIDTH, HEIGHT - _TOP_Y - 64)

        # Draw non-focused cards first (faded when focus > 0)
        t.set_clip(clip)
        for i, ach in enumerate(ACHIEVEMENTS):
            if self._focus_ach and ach.key == self._focus_ach.key:
                continue
            rest_x, rest_y = self._card_positions[i]
            y = rest_y - int(self._scroll)
            if y + _CARD_H < _TOP_Y or y > HEIGHT - 64:
                continue
            alpha = int(255 * (1.0 - p * 0.85))
            is_unlocked = ach.key in unlocked
            self._draw_card(t, rest_x, y, _CARD_W, _CARD_H, ach, is_unlocked, i,
                            alpha=alpha)
        t.set_clip(None)

        # Fade edges
        for gy, flip in [(_TOP_Y, False), (HEIGHT - 64, True)]:
            fade = pygame.Surface((WIDTH, 28), pygame.SRCALPHA)
            for j in range(28):
                a = int(200 * (j / 28 if not flip else 1 - j / 28))
                pygame.draw.line(fade, (12, 8, 20, a), (0, j), (WIDTH, j))
            t.blit(fade, (0, gy if not flip else gy - 28))

        # Draw focused card last (on top, animating to centre)
        if self._focus_ach:
            idx = next(i for i, a in enumerate(ACHIEVEMENTS)
                       if a.key == self._focus_ach.key)
            rest_x, rest_y = self._card_positions[idx]
            rest_y_scrolled = rest_y - int(self._scroll_before_focus)

            # Interpolate position and size
            cx = int(rest_x + (_FOCUS_X - rest_x) * p)
            cy = int(rest_y_scrolled + (_FOCUS_Y - rest_y_scrolled) * p)
            cw = int(_CARD_W  + (_FOCUS_W  - _CARD_W)  * p)
            ch = int(_CARD_H  + (_FOCUS_H  - _CARD_H)  * p)

            # Dark overlay that fades in behind the focused card
            if p > 0:
                ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                ov.fill((0, 0, 0, int(180 * p)))
                t.blit(ov, (0, 0))

            is_unlocked = self._focus_ach.key in unlocked
            self._draw_card(t, cx, cy, cw, ch, self._focus_ach, is_unlocked, idx,
                            alpha=255, focused_p=p)

            # Dismiss hint fades in at end of animation
            if p > 0.6:
                f_sm    = get_fonts()["small"]
                hint_a  = int(200 * ((p - 0.6) / 0.4))
                hint    = f_sm.render(_t("ach_screen.click_close"), False, (80, 55, 110))
                hint.set_alpha(hint_a)
                t.blit(hint, (WIDTH // 2 - hint.get_width() // 2, cy + ch + 14))

    def _draw_card(self, t, x, y, w, h, ach, unlocked, idx,
                   alpha=255, focused_p=0.0):
        tier_col   = _TIER_COL[ach.tier]
        f          = get_fonts()
        f_name     = f["btn"]
        f_desc     = f["small"]
        icon_w     = int(_ICON_W + (_FOCUS_ICON_W - _ICON_W) * focused_p)

        # Panel
        bg_col     = (28, 16, 48, 215) if unlocked else (14, 8, 24, 200)
        border_col = (*tier_col, 180) if unlocked else (50, 30, 80, 150)

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, bg_col,     panel.get_rect(), border_radius=BTN_RADIUS + 2)
        pygame.draw.rect(panel, border_col, panel.get_rect(), width=1, border_radius=BTN_RADIUS + 2)
        if alpha < 255:
            panel.set_alpha(alpha)
        t.blit(panel, (x, y))

        # Icon box
        icon_bg   = (*tier_col, 200) if unlocked else (20, 10, 36, 200)
        icon_surf = pygame.Surface((icon_w, h), pygame.SRCALPHA)
        pygame.draw.rect(icon_surf, icon_bg, icon_surf.get_rect(), border_radius=BTN_RADIUS + 2)
        if alpha < 255:
            icon_surf.set_alpha(alpha)
        t.blit(icon_surf, (x, y))

        sym   = "?" if not unlocked else ("★" if ach.tier == PLATINUM else "◆")
        sym_c = tier_col if unlocked else PURPLE_DIM
        sym_s = f_name.render(sym, False, sym_c)
        if alpha < 255:
            sym_s.set_alpha(alpha)
        t.blit(sym_s, (x + icon_w // 2 - sym_s.get_width() // 2,
                        y + h // 2 - sym_s.get_height() // 2))

        # Text area
        tx    = x + icon_w + 12
        ty    = y + 12
        max_w = w - icon_w - 24

        # Name
        name_col = (GOLD if ach.tier == PLATINUM else TEXT_MAIN) if unlocked else TEXT_DIM
        name_s   = f_name.render(ach.name.upper(), False, name_col)
        if name_s.get_width() > max_w:
            scale  = max_w / name_s.get_width()
            name_s = name_s.convert_alpha()
            name_s = pygame.transform.smoothscale(
                name_s, (max_w, max(1, int(name_s.get_height() * scale))))
        if alpha < 255:
            name_s.set_alpha(alpha)
        t.blit(name_s, (tx, ty))

        # Description — word-wrap when focused, single truncated line otherwise
        desc_text = ach.description if unlocked else "???"
        desc_col  = TEXT_DIM if unlocked else PURPLE_DIM

        if focused_p > 0.5:
            # Word-wrapped full description
            words = desc_text.split()
            lines = []
            line  = ""
            for word in words:
                test = (line + " " + word).strip()
                if f_desc.size(test)[0] <= max_w:
                    line = test
                else:
                    if line:
                        lines.append(line)
                    line = word
            if line:
                lines.append(line)

            desc_y = ty + name_s.get_height() + 10
            for ln in lines:
                ln_s = f_desc.render(ln, False, desc_col)
                ln_a = int(alpha * ((focused_p - 0.5) / 0.5))
                ln_s.set_alpha(ln_a)
                t.blit(ln_s, (tx, desc_y))
                desc_y += ln_s.get_height() + 4
        else:
            # Single truncated line
            desc_s = f_desc.render(desc_text, False, desc_col)
            if desc_s.get_width() > max_w:
                d = desc_text
                while d and f_desc.render(d + "...", False, desc_col).get_width() > max_w:
                    d = d[:-1]
                desc_s = f_desc.render(d + "...", False, desc_col)
            if alpha < 255:
                desc_s.set_alpha(alpha)
            t.blit(desc_s, (tx, ty + name_s.get_height() + 6))

        # Tier label (bottom right)
        tier_lbl = f_desc.render(_tier_label(ach.tier), False,
                                  tier_col if unlocked else PURPLE_DIM)
        if alpha < 255:
            tier_lbl.set_alpha(alpha)
        t.blit(tier_lbl, (x + w - tier_lbl.get_width() - 10,
                           y + h - tier_lbl.get_height() - 8))

        # Shimmer on unlocked
        if unlocked and alpha > 180:
            a = int(10 + abs(math.sin(self.tick * 0.02 + idx * 0.4)) * 14)
            gs = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*tier_col, a), gs.get_rect(), border_radius=BTN_RADIUS + 2)
            t.blit(gs, (x, y))

    def _draw_back_btn(self, t):
        f     = get_fonts()["btn"]
        mouse = pygame.mouse.get_pos()
        hov   = self._back_rect.collidepoint(mouse) and not self._focus_ach
        pygame.draw.rect(t, NEON_DARK if hov else PURPLE_DIM,
                          self._back_rect, border_radius=BTN_RADIUS)
        pygame.draw.rect(t, NEON if hov else PURPLE,
                          self._back_rect, width=1, border_radius=BTN_RADIUS)
        lbl = f.render(_t("ach_screen.back"), False, TEXT_MAIN)
        t.blit(lbl, (self._back_rect.centerx - lbl.get_width() // 2,
                      self._back_rect.centery - lbl.get_height() // 2))