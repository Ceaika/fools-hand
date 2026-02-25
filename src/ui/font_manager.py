"""
font_manager.py — Font loading for Fool's Hand.

PressStart2P covers all required characters including Cyrillic and Romanian
diacritics, so we use it for all languages. get_fonts() is cached per language
only so that invalidate_cache() after a language change triggers a fresh load
(useful if sizes ever diverge per language in future).
"""
from __future__ import annotations

import pygame
from .constants import FONT_PATH
from .locale import get_lang

_SIZES = {
    "title": 32,
    "sub":    8,
    "btn":   16,
    "small":  8,
    "body":   8,
}

_cache: dict[str, dict] = {}


def get_fonts() -> dict:
    """Return the font dict for the current language. Cached per language."""
    lang = get_lang()
    if lang in _cache:
        return _cache[lang]

    fonts = {}
    for key, size in _SIZES.items():
        try:
            fonts[key] = pygame.font.Font(FONT_PATH, size)
        except Exception:
            fonts[key] = pygame.font.Font(None, size * 2)

    _cache[lang] = fonts
    return fonts


def invalidate_cache() -> None:
    """Call after language change so next get_fonts() reloads."""
    _cache.clear()