from __future__ import annotations

import math
import pygame
from .constants import WIDTH, HEIGHT, CARD_BACK, PURPLE, NEON, NEON_GLOW, TEXT_MAIN

_DURATION = 40


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3

def _ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


class ZoomTransition:
    def __init__(self) -> None:
        self._surf_a      = pygame.Surface((WIDTH, HEIGHT))
        self._surf_b      = pygame.Surface((WIDTH, HEIGHT))
        self._active      = False
        self._frame       = 0
        self._direction   = 1
        self._focus       = (WIDTH // 2, HEIGHT // 2)
        self._on_complete = None

    @property
    def busy(self) -> bool:
        return self._active

    def start(self, focus_rect: pygame.Rect, direction: int = 1,
              on_complete=None) -> None:
        self._focus       = (focus_rect.centerx, focus_rect.centery)
        self._direction   = direction
        self._frame       = 0
        self._active      = True
        self._on_complete = on_complete

    def get_surface_a(self) -> pygame.Surface:
        return self._surf_a

    def get_surface_b(self) -> pygame.Surface:
        return self._surf_b

    def update(self) -> None:
        if not self._active:
            return
        self._frame += 1
        if self._frame >= _DURATION:
            self._frame  = _DURATION
            self._active = False
            if self._on_complete:
                self._on_complete()

    def draw(self, screen: pygame.Surface) -> None:
        if not self._active:
            screen.blit(self._surf_b, (0, 0))
            return

        t = _ease_out(self._frame / _DURATION)

        if self._direction != 1:
            t2   = _ease_out(self._frame / _DURATION)
            offset = int(t2 * (WIDTH // 2 + 10))
            screen.blit(self._surf_b, (0, 0))
            left = self._surf_a.subsurface(pygame.Rect(0, 0, WIDTH // 2, HEIGHT))
            screen.blit(left, (-offset, 0))
            right = self._surf_a.subsurface(pygame.Rect(WIDTH // 2, 0, WIDTH // 2, HEIGHT))
            screen.blit(right, (WIDTH // 2 + offset, 0))
            return

        start_scale = 2.5
        scale = start_scale + (1.0 - start_scale) * t
        fx, fy = self._focus
        new_w  = int(WIDTH  * scale)
        new_h  = int(HEIGHT * scale)
        zoomed_b = pygame.transform.scale(self._surf_b, (new_w, new_h))
        ox = int(fx * scale - fx)
        oy = int(fy * scale - fy)
        screen.blit(zoomed_b, (-ox, -oy))

        src_scale = 1.0 + t * 1.5
        src_w     = int(WIDTH  * src_scale)
        src_h     = int(HEIGHT * src_scale)
        zoomed_a  = pygame.transform.scale(self._surf_a, (src_w, src_h))
        sox       = int(fx * src_scale - fx)
        soy       = int(fy * src_scale - fy)
        zoomed_a.set_alpha(int((1.0 - t) * 255))
        screen.blit(zoomed_a, (-sox, -soy))


# ── Card Sweep Transition ─────────────────────────────────────────────────────
# Phase 1 (0.00–0.40): Giant card flies in from right, slight CCW rotation,
#                       lands covering the whole screen
# Phase 2 (0.40–0.55): Card holds, screen behind switches to destination
# Phase 3 (0.55–1.00): Card flips (squash X to 0, expand as game side/face)
#                       then shoots off-screen to the left

_CS_DURATION = 90   # total frames (~1.5s at 60fps)
_CS_FLY_END  = 0.40
_CS_HOLD_END = 0.55

# Card is 1.5× the screen so it fully covers when centred
_CS_W = int(WIDTH  * 1.5)
_CS_H = int(HEIGHT * 1.5)


def _make_card_back_surf() -> pygame.Surface:
    """Draw a large decorative card back matching the game's style."""
    surf = pygame.Surface((_CS_W, _CS_H), pygame.SRCALPHA)

    # Base fill
    pygame.draw.rect(surf, CARD_BACK, (0, 0, _CS_W, _CS_H), border_radius=32)
    pygame.draw.rect(surf, PURPLE,    (0, 0, _CS_W, _CS_H), width=4, border_radius=32)

    # Diamond pattern grid
    step = 48
    for gx in range(0, _CS_W + step, step):
        for gy in range(0, _CS_H + step, step):
            pts = [(gx, gy - 18), (gx + 18, gy), (gx, gy + 18), (gx - 18, gy)]
            pygame.draw.polygon(surf, PURPLE, pts)
            pygame.draw.polygon(surf, (60, 30, 100), pts, 1)

    # Centre ornament — large diamond outline
    cx, cy = _CS_W // 2, _CS_H // 2
    for size, col in [(180, PURPLE), (140, NEON), (100, NEON_GLOW), (60, TEXT_MAIN)]:
        pts = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
        pygame.draw.polygon(surf, col, pts, 3)

    # Corner pips
    pip_size = 30
    for px, py in [(60, 60), (_CS_W - 60, 60), (60, _CS_H - 60), (_CS_W - 60, _CS_H - 60)]:
        pts = [(px, py - pip_size), (px + pip_size, py),
               (px, py + pip_size), (px - pip_size, py)]
        pygame.draw.polygon(surf, NEON, pts, 2)

    return surf


def _make_card_face_surf(game_surf: pygame.Surface) -> pygame.Surface:
    """Card front = the actual game screen scaled to card size."""
    surf = pygame.Surface((_CS_W, _CS_H), pygame.SRCALPHA)
    scaled = pygame.transform.scale(game_surf, (_CS_W, _CS_H))
    surf.blit(scaled, (0, 0))
    # Rounded border on top
    pygame.draw.rect(surf, NEON, (0, 0, _CS_W, _CS_H), width=5, border_radius=32)
    return surf


class CardSweepTransition:
    """A giant card flies in from the right, covers the screen, flips to
    reveal the destination, then flies off to the left.
    
    All scaled/rotated frames are pre-baked at start() so draw() only does blits."""

    def __init__(self) -> None:
        self._surf_src  = pygame.Surface((WIDTH, HEIGHT))
        self._surf_dst  = pygame.Surface((WIDTH, HEIGHT))
        self._active    = False
        self._frame     = 0
        self._on_switch : callable | None = None
        self._switched  = False

        # Pre-baked frame caches
        self._fly_frames  : list = []
        self._full_back   : pygame.Surface | None = None

    @property
    def busy(self) -> bool:
        return self._active

    def get_surface_src(self) -> pygame.Surface:
        return self._surf_src

    def get_surface_dst(self) -> pygame.Surface:
        return self._surf_dst

    def start(self, on_switch=None) -> None:
        self._frame     = 0
        self._active    = True
        self._switched  = False
        self._on_switch = on_switch

        back = _make_card_back_surf()
        self._full_back = back

        # ── Pre-bake fly-in frames (phase 1) ─────────────────────────────
        # Only the rotation changes; we bake each unique angle
        fly_frame_count = int(_CS_DURATION * _CS_FLY_END) + 1
        self._fly_frames = []
        seen_angles = {}
        for f in range(fly_frame_count):
            t     = _ease_out(f / max(fly_frame_count - 1, 1))
            angle = round((1 - t) * -18, 1)
            if angle not in seen_angles:
                seen_angles[angle] = pygame.transform.rotate(back, angle)
            self._fly_frames.append(seen_angles[angle])

    def update(self) -> None:
        if not self._active:
            return
        self._frame += 1
        p = self._frame / _CS_DURATION

        if not self._switched and p >= _CS_HOLD_END:
            self._switched = True
            if self._on_switch:
                self._on_switch()

        if self._frame >= _CS_DURATION:
            self._frame  = _CS_DURATION
            self._active = False

    def draw(self, screen: pygame.Surface) -> None:
        p  = self._frame / _CS_DURATION
        cx = WIDTH  // 2
        cy = HEIGHT // 2

        # Background
        screen.blit(self._surf_src if p < _CS_HOLD_END else self._surf_dst, (0, 0))

        if p < _CS_FLY_END:
            # ── Phase 1: fly in ───────────────────────────────────────────
            t      = _ease_out(p / _CS_FLY_END)
            start_x = WIDTH + _CS_W // 2 + 40
            card_x  = start_x + (cx - start_x) * t
            fi      = min(len(self._fly_frames) - 1,
                          int(t * len(self._fly_frames)))
            surf    = self._fly_frames[fi]
            screen.blit(surf, (int(card_x) - surf.get_width()  // 2,
                                cy          - surf.get_height() // 2))

        elif p < _CS_HOLD_END:
            # ── Phase 2: hold ─────────────────────────────────────────────
            surf = self._full_back
            screen.blit(surf, (cx - surf.get_width()  // 2,
                                cy - surf.get_height() // 2))

        else:
            # ── Phase 3: slide off to the left ────────────────────────────
            slide_t = _ease_in_out((p - _CS_HOLD_END) / (1.0 - _CS_HOLD_END))
            card_x  = cx - slide_t * (WIDTH + _CS_W // 2 + 40)
            surf    = self._full_back
            screen.blit(surf, (int(card_x) - surf.get_width()  // 2,
                                cy          - surf.get_height() // 2))