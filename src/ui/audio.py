from __future__ import annotations

import os
import pygame

_SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "assets", "sounds")

# ── Volume levels ─────────────────────────────────────────────────────────────
MUSIC_VOL = 0.5
SFX_VOL   = 0.8

# ── Crossfade speed (volume units per update tick at 60fps) ──────────────────
_FADE_SPEED = 0.04   # ~25 ticks = ~0.4s to fully crossfade

# ── Sound effect filenames ────────────────────────────────────────────────────
_SFX_FILES = {
    "card_place"       : "card_place.wav",
    "card_discard"     : "card_discard.wav",
    "card_reject"      : "card_reject.wav",
    "card_take"        : "card_take.wav",
    "menu_click"       : "menu_click.wav",
    "transition_change": "transition_change.wav",
    "win"              : "win.wav",
    "loss"             : "loss.wav",
}

# ── Music track pairs (normal + muffled) ─────────────────────────────────────
_MUSIC_FILES = {
    "main_menu": ("main_menu.wav",  "main_menu_muffled.wav"),
    "in_game"  : ("in_game.wav",    "in_game_muffled.wav"),
}

# ── Dedicated mixer channels for music ───────────────────────────────────────
_CH_NORMAL  = 0
_CH_MUFFLED = 1

# ── State ─────────────────────────────────────────────────────────────────────
_sounds        : dict[str, pygame.mixer.Sound] = {}
_music_normal  : dict[str, pygame.mixer.Sound] = {}
_music_muffled : dict[str, pygame.mixer.Sound] = {}
_current_key   : str | None = None
_muffled        = False
_normal_vol     = MUSIC_VOL
_muffled_vol    = 0.0
_sfx_enabled    = True
_music_enabled  = True


def init() -> None:
    """Call once after pygame.init()."""
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(16)
    pygame.mixer.set_reserved(2)

    for key, filename in _SFX_FILES.items():
        path = os.path.join(_SOUNDS_DIR, filename)
        if os.path.exists(path):
            try:
                snd = pygame.mixer.Sound(path)
                snd.set_volume(SFX_VOL)
                _sounds[key] = snd
            except Exception as e:
                print(f"[audio] failed to load sfx '{key}': {e}")
        else:
            print(f"[audio] sfx not found: {path}")

    for key, (normal_f, muffled_f) in _MUSIC_FILES.items():
        for store, filename in [(_music_normal, normal_f),
                                 (_music_muffled, muffled_f)]:
            path = os.path.join(_SOUNDS_DIR, filename)
            if os.path.exists(path):
                try:
                    store[key] = pygame.mixer.Sound(path)
                except Exception as e:
                    print(f"[audio] failed to load music '{filename}': {e}")
            else:
                print(f"[audio] music not found: {path}")


def play(key: str) -> None:
    if not _sfx_enabled:
        return
    snd = _sounds.get(key)
    if snd:
        snd.play()


def play_music(key: str) -> None:
    """Switch to a music track. Both normal+muffled play; volumes controlled via channels."""
    global _current_key, _normal_vol, _muffled_vol
    if key == _current_key or not _music_enabled:
        return

    ch_n = pygame.mixer.Channel(_CH_NORMAL)
    ch_m = pygame.mixer.Channel(_CH_MUFFLED)

    ch_n.stop()
    ch_m.stop()

    _current_key = key
    _normal_vol  = 0.0       if _muffled else MUSIC_VOL
    _muffled_vol = MUSIC_VOL if _muffled else 0.0

    snd_n = _music_normal.get(key)
    snd_m = _music_muffled.get(key)

    if snd_n:
        snd_n.set_volume(1.0)          # IMPORTANT: never 0 here
        ch_n.play(snd_n, loops=-1)
        ch_n.set_volume(_normal_vol)   # fading happens on the channel
    if snd_m:
        snd_m.set_volume(1.0)          # IMPORTANT: never 0 here
        ch_m.play(snd_m, loops=-1)
        ch_m.set_volume(_muffled_vol)


def set_muffled(state: bool) -> None:
    """Switch between normal and muffled. Crossfade happens in update()."""
    global _muffled
    _muffled = state


def update() -> None:
    """Call every frame to tick the volume crossfade."""
    global _normal_vol, _muffled_vol
    if not _music_enabled or _current_key is None:
        return

    target_n = 0.0       if _muffled else MUSIC_VOL
    target_m = MUSIC_VOL if _muffled else 0.0

    changed = False
    if abs(_normal_vol - target_n) > 0.001:
        _normal_vol += _FADE_SPEED * (1 if target_n > _normal_vol else -1)
        _normal_vol  = max(0.0, min(MUSIC_VOL, _normal_vol))
        changed = True
    if abs(_muffled_vol - target_m) > 0.001:
        _muffled_vol += _FADE_SPEED * (1 if target_m > _muffled_vol else -1)
        _muffled_vol  = max(0.0, min(MUSIC_VOL, _muffled_vol))
        changed = True

    if changed:
        snd_n = _music_normal.get(_current_key)
        snd_m = _music_muffled.get(_current_key)
        if snd_n: pygame.mixer.Channel(_CH_NORMAL).set_volume(_normal_vol)
        if snd_m: pygame.mixer.Channel(_CH_MUFFLED).set_volume(_muffled_vol)


def stop_music() -> None:
    global _current_key
    pygame.mixer.Channel(_CH_NORMAL).stop()
    pygame.mixer.Channel(_CH_MUFFLED).stop()
    _current_key = None


def set_music_volume(vol: float) -> None:
    global MUSIC_VOL, _normal_vol, _muffled_vol
    MUSIC_VOL    = max(0.0, min(1.0, vol))
    _normal_vol  = 0.0       if _muffled else MUSIC_VOL
    _muffled_vol = MUSIC_VOL if _muffled else 0.0

    pygame.mixer.Channel(_CH_NORMAL).set_volume(_normal_vol)
    pygame.mixer.Channel(_CH_MUFFLED).set_volume(_muffled_vol)


def set_sfx_volume(vol: float) -> None:
    global SFX_VOL
    SFX_VOL = max(0.0, min(1.0, vol))
    for snd in _sounds.values():
        snd.set_volume(SFX_VOL)


def toggle_music() -> bool:
    global _music_enabled
    _music_enabled = not _music_enabled
    ch_n = pygame.mixer.Channel(_CH_NORMAL)
    ch_m = pygame.mixer.Channel(_CH_MUFFLED)
    if not _music_enabled:
        ch_n.pause()
        ch_m.pause()
    else:
        ch_n.unpause()
        ch_m.unpause()
    return _music_enabled


def toggle_sfx() -> bool:
    global _sfx_enabled
    _sfx_enabled = not _sfx_enabled
    return _sfx_enabled