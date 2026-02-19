from __future__ import annotations

# ── window ────────────────────────────────────────────────────────────────────
WIDTH  = 1280
HEIGHT = 720
FPS    = 60
TITLE  = "Fool's Hand"

# ── palette ───────────────────────────────────────────────────────────────────
BLACK      = (0,   0,   0)
WHITE      = (255, 255, 255)
BG         = (12,  8,   20)    # deep purple-black
BG2        = (20,  13,  35)    # slightly lighter for panels

NEON       = (255, 50,  120)   # hot pink/red — primary accent (Balatro)
NEON_DARK  = (160, 20,  70)    # dimmed neon for hover fill
NEON_GLOW  = (255, 80,  150)   # lighter for glow/bloom edge

GOLD       = (255, 200, 80)    # secondary accent — highlights
PURPLE     = (90,  50,  140)   # mid purple for borders/dividers
PURPLE_DIM = (45,  25,  70)    # dark purple for subtle elements

TEXT_MAIN  = (240, 230, 255)   # slightly purple-tinted white
TEXT_DIM   = (110, 90,  140)   # muted purple-grey

# ── card colours ─────────────────────────────────────────────────────────────
CARD_BG     = (235, 225, 245)  # pale purple-white face
CARD_BACK   = (40,  20,  80)   # deep purple back
CARD_BORDER = (90,  50,  140)
CARD_RED    = (220, 40,  100)  # neon-ish red for hearts/diamonds
CARD_BLACK  = (180, 160, 220)  # soft purple for clubs/spades

# ── layout ────────────────────────────────────────────────────────────────────
BTN_W      = 340
BTN_H      = 52
BTN_GAP    = 16
BTN_RADIUS = 4

CARD_W     = 72
CARD_H     = 100

import os as _os
FONT_PATH = _os.path.join(_os.path.dirname(__file__), "assets", "fonts", "PressStart2P.ttf")