"""
font_manager.py — Font loading with Cyrillic fallback for Russian.

The game's custom font doesn't cover Cyrillic. When Russian is active we
swap to a system font that does. Call get_fonts() to get the active font dict.
"""
from __future__ import annotations

import os
import pygame
from .locale import get_lang

# Path to the game's custom font (same as app.py uses)
_FONT_DIR  = os.path.join(os.path.dirname(__file__), "assets", "fonts")
_CUSTOM    = os.path.join(_FONT_DIR, "game_font.ttf")   # adjust if name differs

# Sizes matching the existing font dict in app.py
_SIZES = {
    "title": 36,
    "sub":   18,
    "btn":   16,
    "small": 13,
    "body":  14,
}

_cache: dict[str, dict] = {}


def _find_cyrillic_font() -> str | None:
    """Return a system font path that supports Cyrillic, or None."""
    candidates = [
        "dejavusans",
        "freesans",
        "liberationsans",
        "arial",
        "segoeui",
        "tahoma",
    ]
    for name in candidates:
        path = pygame.font.match_font(name)
        if path:
            return path
    return None


def get_fonts() -> dict:
    """Return the font dict for the current language. Cached per language."""
    lang = get_lang()
    if lang in _cache:
        return _cache[lang]

    fonts = {}
    if lang == "ru":
        path = _find_cyrillic_font()
        if path is None:
            path = None   # will fall back to SysFont below
        for key, size in _SIZES.items():
            if path:
                try:
                    fonts[key] = pygame.font.Font(path, size)
                    continue
                except Exception:
                    pass
            fonts[key] = pygame.font.SysFont("sans", size)
    else:
        # Use the original custom font for EN and RO
        custom_exists = os.path.exists(_CUSTOM)
        for key, size in _SIZES.items():
            if custom_exists:
                try:
                    fonts[key] = pygame.font.Font(_CUSTOM, size)
                    continue
                except Exception:
                    pass
            fonts[key] = pygame.font.SysFont("sans", size)

    _cache[lang] = fonts
    return fonts


def invalidate_cache() -> None:
    """Call after language change so next get_fonts() reloads."""
    _cache.clear()