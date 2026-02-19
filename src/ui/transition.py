from __future__ import annotations

import pygame
from .constants import WIDTH, HEIGHT

_DURATION = 40


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


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
            # back: screen splits in half, left slides left, right slides right
            t2   = _ease_out(self._frame / _DURATION)
            offset = int(t2 * (WIDTH // 2 + 10))

            # destination underneath
            screen.blit(self._surf_b, (0, 0))

            # left half of source slides left
            left = self._surf_a.subsurface(pygame.Rect(0, 0, WIDTH // 2, HEIGHT))
            screen.blit(left, (-offset, 0))

            # right half of source slides right
            right = self._surf_a.subsurface(pygame.Rect(WIDTH // 2, 0, WIDTH // 2, HEIGHT))
            screen.blit(right, (WIDTH // 2 + offset, 0))
            return

        # forward: source zooms INTO the button while destination rushes in from behind
        start_scale = 2.5
        scale = start_scale + (1.0 - start_scale) * t   # 2.5x -> 1.0x

        fx, fy = self._focus
        new_w  = int(WIDTH  * scale)
        new_h  = int(HEIGHT * scale)
        zoomed_b = pygame.transform.scale(self._surf_b, (new_w, new_h))

        # keep focus point anchored
        ox = int(fx * scale - fx)
        oy = int(fy * scale - fy)
        screen.blit(zoomed_b, (-ox, -oy))

        # source also zooms in toward the button centre
        src_scale = 1.0 + t * 1.5   # 1.0x -> 2.5x
        src_w     = int(WIDTH  * src_scale)
        src_h     = int(HEIGHT * src_scale)
        zoomed_a  = pygame.transform.scale(self._surf_a, (src_w, src_h))
        sox       = int(fx * src_scale - fx)
        soy       = int(fy * src_scale - fy)

        # fade source out as it zooms in
        zoomed_a.set_alpha(int((1.0 - t) * 255))
        screen.blit(zoomed_a, (-sox, -soy))