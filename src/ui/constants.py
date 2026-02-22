from __future__ import annotations

# ── window ────────────────────────────────────────────────────────────────────
WIDTH  = 1280
HEIGHT = 720
FPS    = 60
TITLE  = "Fool's Hand"

# ── palette ───────────────────────────────────────────────────────────────────
BLACK      = (0,   0,   0)
WHITE      = (255, 255, 255)
BG         = (12,  8,   20)
BG2        = (20,  13,  35)

NEON       = (255, 50,  120)
NEON_DARK  = (160, 20,  70)
NEON_GLOW  = (255, 80,  150)

GOLD       = (255, 200, 80)
PURPLE     = (90,  50,  140)
PURPLE_DIM = (45,  25,  70)

TEXT_MAIN  = (240, 230, 255)
TEXT_DIM   = (110, 90,  140)

# ── card colours ─────────────────────────────────────────────────────────────
CARD_BG     = (235, 225, 245)
CARD_BACK   = (40,  20,  80)
CARD_BORDER = (90,  50,  140)
CARD_RED    = (220, 40,  100)
CARD_BLACK  = (180, 160, 220)

# ── layout ────────────────────────────────────────────────────────────────────
BTN_W      = 340
BTN_H      = 52
BTN_GAP    = 16
BTN_RADIUS = 4

CARD_W     = 80
CARD_H     = 116

import os as _os
FONT_PATH = _os.path.join(_os.path.dirname(__file__), "assets", "fonts", "PressStart2P.ttf")