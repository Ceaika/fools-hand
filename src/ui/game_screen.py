from __future__ import annotations

import math
import random
import pygame
from ..core.game import _ai_choose_attack, _ai_choose_defence, _ai_should_stop_attacking
from ..core.move_validator import MoveValidator
from . import audio
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM, GOLD,
    CARD_BG, CARD_BACK, CARD_BORDER, CARD_RED, CARD_BLACK,
    CARD_W, CARD_H,
)
from .achievements import AchievementTracker, ACHIEVEMENTS, ACH
from .achievement_toast import AchievementToast
from .font_manager import get_fonts
from .locale import t as _t

_BOT_DELAY    = 90
_ROUND_DELAY  = 90
_ATTACK_COMMIT_DELAY = 180

S_HUMAN_ATTACK = "human_attack"
S_HUMAN_DEFEND = "human_defend"
S_PILE_ON      = "pile_on"
S_BOT_THINKING = "bot_thinking"
S_ROUND_OVER   = "round_over"
S_GAME_OVER    = "game_over"
S_DEALING      = "dealing"
S_DRAWING      = "drawing"

# game-over result
R_WIN  = "win"
R_LOSS = "loss"
R_TIE  = "tie"

_STATUS_KEYS = {
    S_DEALING:      "game.status_deal",
    S_DRAWING:      "game.status_deal",
    S_HUMAN_ATTACK: "game.status_attack",
    S_HUMAN_DEFEND: "game.status_defend",
    S_PILE_ON:      "game.status_pile_on",
    S_BOT_THINKING: "game.status_bot",
    S_ROUND_OVER:   "",
    S_GAME_OVER:    "game.status_game_over",
}

# Cheat code: first 12 digits of pi = 3 1 4 1 5 9 2 6 5 3 5 8
_CHEAT_SEQUENCE = [pygame.K_3, pygame.K_1, pygame.K_4, pygame.K_1, pygame.K_5,
                   pygame.K_9, pygame.K_2, pygame.K_6, pygame.K_5, pygame.K_3,
                   pygame.K_5, pygame.K_8]


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


# ── Flying card sprite ────────────────────────────────────────────────────────

class FlyingCard:
    def __init__(self, surf, src, dst, duration=22,
                 src_angle=0.0, dst_angle=0.0, on_done=None):
        self.surf      = surf
        self.src       = src
        self.dst       = dst
        self.duration  = duration
        self.elapsed   = 0
        self.src_angle = src_angle
        self.dst_angle = dst_angle
        self.on_done   = on_done
        self.done      = False

    def update(self):
        self.elapsed += 1
        if self.elapsed >= self.duration:
            self.elapsed = self.duration
            self.done    = True
            if self.on_done:
                self.on_done()

    @property
    def t(self):
        return _ease_out(self.elapsed / self.duration)

    @property
    def pos(self):
        return (self.src[0] + (self.dst[0] - self.src[0]) * self.t,
                self.src[1] + (self.dst[1] - self.src[1]) * self.t)

    @property
    def angle(self):
        return self.src_angle + (self.dst_angle - self.src_angle) * self.t

    def draw(self, target):
        rotated = pygame.transform.rotate(self.surf, self.angle)
        x, y    = self.pos
        target.blit(rotated, (int(x) - rotated.get_width()  // 2,
                               int(y) - rotated.get_height() // 2))


# ── GameScreen ────────────────────────────────────────────────────────────────

class GameScreen:
    def __init__(self, screen, fonts, game):
        self.screen = screen
        self.fonts  = fonts
        self.game   = game
        self.tick   = 0

        self._state        = None
        self._message      = ""
        self._invalid_card = None
        self._invalid_tick = 0
        self._bot_timer    = 0
        self._bot_action   = None
        self._round_timer  = 0
        self._attack_commit_timer = 0   # ticks after last attack card lands before defence begins

        # visual table state — list of (atk_str, dfn_str|None)
        # updated incrementally as cards land, so settled cards always show
        self._vis_table: list[tuple] = []

        # animation
        self._flying   : list[FlyingCard] = []
        self._discards : list[dict]       = []
        self._hover    : dict             = {}
        self._animating = False

        # status fade
        self._status_label = ""
        self._status_alpha = 0
        self._status_fade  = 0

        self._cards = self._load_card_images()

        # ── achievement system ────────────────────────────────────────────────
        self._ach_tracker = AchievementTracker()
        self._ach_toast   = AchievementToast(fonts)
        self._ach_tracker.add_listener(self._ach_toast.push)

        # ── cheat code state ──────────────────────────────────────────────────
        self._cheat_pos          = 0     # how many correct digits typed so far
        self._cheat_queue        = []    # achievements queued to drip-feed
        self._cheat_timer        = 0

        # ── game-over state ───────────────────────────────────────────────────
        self._result             = None  # R_WIN | R_LOSS | R_TIE
        self._result_tick        = 0
        self._falling_cards: list[dict] = []  # for loss screen animation
        self._result_stats       = {}    # stats snapshot for end screen

        # ── per-game stats ────────────────────────────────────────────────────
        self._stat_rounds        = 0
        self._stat_piles_taken   = 0
        self._stat_biggest_pile  = 0
        self._stat_trumps_played = 0
        self._stat_passes        = 0

        # --- intro shuffle+deal animation state ---
        self._shuffling    = False
        self._shuffle_tick = 0
        self._deal_queue   = []
        self._deal_i       = 0

        # --- trump reveal animation state ---
        self._trump_reveal_phase = 0
        self._reveal_tick        = 0
        self._trump_tucked       = False
        self._reveal_surf_front  = None
        self._reveal_surf_back   = None
        self._reveal_pos         = (0, 0)
        self._reveal_x_scale     = 1.0

        # --- role reveal animation state ---
        self._role_reveal_active = False
        self._role_tick          = 0
        self._role_final         = ""   # "ATTACKING" or "DEFENDING"

        # If the game was started with setup_no_deal(), hands are empty and we animate dealing.
        if all(len(p.hand) == 0 for p in self.game.players):
            self._begin_initial_deal()
        else:
            self._start_round()

    # ── position helpers ─────────────────────────────────────────────────────

    def _hand_rect(self, idx, total):
        max_w   = WIDTH - 40          # leave 20px margin each side
        gap     = 10
        total_w = total * CARD_W + (total - 1) * gap
        if total_w > max_w and total > 1:
            gap     = max(-(CARD_W - 8), (max_w - total * CARD_W) // (total - 1))
            total_w = total * CARD_W + (total - 1) * gap
        sx = WIDTH // 2 - total_w // 2
        return pygame.Rect(sx + idx * (CARD_W + gap), HEIGHT - CARD_H - 20, CARD_W, CARD_H)

    def _table_pos(self, pair_idx, total_pairs, is_defence):
        gap    = CARD_W + 20
        offset = 16
        sx     = WIDTH // 2 - total_pairs * gap // 2
        x      = sx + pair_idx * gap + (offset if is_defence else 0)
        y      = HEIGHT // 2 - CARD_H // 2 - (offset if is_defence else 0)
        return (x + CARD_W // 2, y + CARD_H // 2)

    def _discard_pos(self):
        return (random.randint(WIDTH - 160, WIDTH - 80),
                random.randint(HEIGHT // 2 - 90, HEIGHT // 2 + 90))

    def _bot_hand_centre(self):
        return (WIDTH // 2, 20 + CARD_H // 2)

    # ── intro shuffle+deal animation ─────────────────────────────────────────

    def _deck_centre(self):
        # matches _draw_deck_and_trump position (top-left at x=110, y=H//2 - CARD_H//2)
        x = 110 + CARD_W // 2
        y = HEIGHT // 2
        return (x, y)

    def _trump_tucked_pos(self):
        """Centre position of the trump card when tucked sideways under the deck.
        Offset right so it clearly peeks out from under the deck stack."""
        x = 110 + CARD_W + CARD_H // 2 - 10   # right edge of deck + half the rotated card width
        y = HEIGHT // 2
        return (x, y)

    def _bot_card_centre(self, idx, total, W=None):
        gap     = 6
        W = W if W is not None else WIDTH
        total_w = total * CARD_W + (total - 1) * gap
        sx      = W // 2 - total_w // 2
        x       = sx + idx * (CARD_W + gap) + CARD_W // 2
        y       = 20 + CARD_H // 2
        return (x, y)

    def _begin_initial_deal(self):
        """Shuffle-while-dealing intro. Requires Game.setup_no_deal()."""
        g = self.game

        self._set(S_DEALING, "")
        self._animating    = True
        self._shuffling    = True
        self._shuffle_tick = 0

        # Build the deal order (player indices only — cards stay in deck until each flies)
        self._deal_queue = []
        players = list(range(len(g.players)))
        for _ in range(3):
            for p_idx in players:
                for _ in range(2):
                    if g.deck.remaining() > 1:   # leave the trump card (bottom) in deck
                        self._deal_queue.append(p_idx)

        self._deal_i = 0
        self._deal_fly_next()

    def _deal_fly_next(self):
        g = self.game

        if self._deal_i >= len(self._deal_queue):
            for p in g.players:
                p.sort_hand(g.deck.trump)
            g._assign_first_attacker()
            self._animating = False
            # Fire game-start achievement check now that hands are full
            self._ach_tracker.on_game_start(g.players[0].hand, g.deck.trump)
            self._begin_trump_reveal()
            return

        p_idx  = self._deal_queue[self._deal_i]
        player = g.players[p_idx]
        card   = g.deck.draw()   # draw one card now, deck shrinks visibly

        src = self._deck_centre()

        if p_idx == 0:
            slot        = len(player.hand)
            total_after = slot + 1
            rect        = self._hand_rect(slot, total_after)
            dst         = (rect.x + CARD_W // 2, rect.y + CARD_H // 2)
        else:
            slot        = len(player.hand)
            total_after = slot + 1
            dst         = self._bot_card_centre(slot, total_after)

        def on_land(p=player, c=card):
            p.hand.append(c)
            self._deal_i += 1
            self._deal_fly_next()

        self._fly_card(
            "back", src, dst,
            duration=16,
            src_angle=random.uniform(-12, 12),
            dst_angle=random.uniform(-6, 6),
            on_done=on_land,
            sound="card_take",
        )

    # ── trump reveal animation ────────────────────────────────────────────────

    # Phase timings (in ticks)
    _REVEAL_FLY_IN   = 30   # deck → centre
    _REVEAL_SPIN     = 50   # dramatic spin + flip at centre
    _REVEAL_HOLD     = 40   # hold face-up so player can read it
    _REVEAL_FLY_OUT  = 35   # centre → under deck

    def _begin_trump_reveal(self):
        g          = self.game
        trump_card = g.deck.peek_bottom()
        trump_str  = str(trump_card)

        self._reveal_surf_front  = self._scaled(self._card_surf_by_str(trump_str))
        self._reveal_surf_back   = self._scaled(self._get_back_surf((CARD_W, CARD_H)))
        self._reveal_tick        = 0
        self._trump_reveal_phase = 1
        self._animating          = True
        # _shuffling stays True from the deal phase — we stop it when card tucks

    def _update_trump_reveal(self):
        if self._trump_reveal_phase == 0:
            return

        self._reveal_tick += 1
        phase = self._trump_reveal_phase

        deck_pos   = self._deck_centre()
        centre_pos = (WIDTH // 2, HEIGHT // 2)

        if phase == 1:
            # fly from deck to centre
            if self._reveal_tick >= self._REVEAL_FLY_IN:
                self._trump_reveal_phase = 2
                self._reveal_tick = 0

        elif phase == 2:
            # spin + flip
            if self._reveal_tick >= self._REVEAL_SPIN + self._REVEAL_HOLD:
                self._trump_reveal_phase = 3
                self._reveal_tick = 0

        elif phase == 3:
            # fly back to deck, rotate to 90°
            if self._reveal_tick >= self._REVEAL_FLY_OUT:
                self._trump_reveal_phase = 0
                self._trump_tucked       = True
                self._shuffling          = False
                self._animating          = True   # keep input locked during role reveal
                self._begin_role_reveal()

    # ── role reveal animation ─────────────────────────────────────────────────

    _ROLE_CYCLE_TICKS = 160   # ~2.7s cycling through roles
    _ROLE_HOLD_TICKS  = 80    # ~1.3s hold on final role
    _ROLE_FADE_TICKS  = 60    # ~1s grow + fade out
    _ROLE_CYCLE_SPEED = 14    # ticks per role flip — slower so it's readable

    def _begin_role_reveal(self):
        g = self.game
        self._role_final         = "attacking" if g.attacker_idx == 0 else "defending"
        self._role_tick          = 0
        self._role_reveal_active = True

    def _update_role_reveal(self):
        if not self._role_reveal_active:
            return
        self._role_tick += 1
        total = self._ROLE_CYCLE_TICKS + self._ROLE_HOLD_TICKS + self._ROLE_FADE_TICKS
        if self._role_tick >= total:
            self._role_reveal_active = False
            self._animating          = False
            self._start_round()

    def _draw_role_reveal(self, t):
        if not self._role_reveal_active:
            return

        W, H   = t.get_width(), t.get_height()
        cx, cy = W // 2, H // 2
        tick   = self._role_tick

        roles     = ["attacking", "defending"]
        cycle_end = self._ROLE_CYCLE_TICKS
        hold_end  = cycle_end + self._ROLE_HOLD_TICKS
        fade_end  = hold_end  + self._ROLE_FADE_TICKS

        # Determine which role word to show
        if tick < cycle_end:
            # Pre-compute flip points: intervals grow from 8 → 30 ticks (slot machine slowdown)
            # Build the list of cumulative flip times
            flip_times = []
            t_acc      = 0
            interval   = 8
            while t_acc < cycle_end - 20:
                t_acc    += interval
                flip_times.append(t_acc)
                interval  = min(30, int(interval * 1.18))

            # Count how many flips have happened so far
            flips_done = sum(1 for ft in flip_times if tick >= ft)
            idx        = flips_done % 2
            word       = roles[idx]

            # Snap to final role in the last 20 ticks
            if tick >= cycle_end - 20:
                word = self._role_final
        else:
            word = self._role_final

        # Scale: normal during cycle/hold, grows during fade
        if tick < hold_end:
            scale  = 1.0
            alpha  = 255
        else:
            fade_t = (tick - hold_end) / self._ROLE_FADE_TICKS
            scale  = 1.0 + fade_t * 0.6       # grows to 1.6×
            alpha  = int(255 * (1.0 - fade_t))  # fades out

        if alpha <= 0:
            return

        is_attack  = (word == "attacking")
        word_col   = (100, 220, 255) if is_attack else (255, 160, 80)
        label_col  = TEXT_DIM

        title_f = get_fonts()["title"]
        role_f  = get_fonts()["title"]

        you_surf = title_f.render(_t("game.you_are"), False, label_col)
        you_surf.set_alpha(alpha)

        role_word = _t(f"game.{word}")
        role_surf_base = role_f.render(role_word, False, word_col)
        if scale != 1.0:
            new_w = max(1, int(role_surf_base.get_width()  * scale))
            new_h = max(1, int(role_surf_base.get_height() * scale))
            role_surf = pygame.transform.scale(role_surf_base, (new_w, new_h))
        else:
            role_surf = role_surf_base
        role_surf.set_alpha(alpha)

        # Neon glow behind role word
        glow_surf_base = role_f.render(role_word, False, NEON_GLOW)
        if scale != 1.0:
            gw = max(1, int(glow_surf_base.get_width()  * scale))
            gh = max(1, int(glow_surf_base.get_height() * scale))
            glow_surf = pygame.transform.scale(glow_surf_base, (gw, gh))
        else:
            glow_surf = glow_surf_base
        glow_surf.set_alpha(min(alpha, int(120 * (1 - max(0, tick - hold_end) / self._ROLE_FADE_TICKS))))

        gap    = 12
        total_h = you_surf.get_height() + gap + role_surf.get_height()
        you_y   = cy - total_h // 2
        role_y  = you_y + you_surf.get_height() + gap

        # Dim overlay so text pops
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, min(alpha // 2, 120)))
        t.blit(overlay, (0, 0))

        # Glow passes
        for off, a_mult in [(6, 0.15), (3, 0.35)]:
            g2 = glow_surf.copy()
            g2.set_alpha(int(glow_surf.get_alpha() * a_mult))
            t.blit(g2, (cx - glow_surf.get_width() // 2 - off, role_y))
            t.blit(g2, (cx - glow_surf.get_width() // 2 + off, role_y))

        t.blit(glow_surf, (cx - glow_surf.get_width() // 2, role_y))
        t.blit(you_surf,  (cx - you_surf.get_width()  // 2, you_y))
        t.blit(role_surf, (cx - role_surf.get_width() // 2, role_y))


        """Phase 3 only — draws card travelling back under the deck stack."""
        if self._trump_reveal_phase != 3:
            return
        tuck_pos   = self._trump_tucked_pos()
        centre_pos = (WIDTH // 2, HEIGHT // 2)
        progress   = min(self._reveal_tick / self._REVEAL_FLY_OUT, 1.0)
        ease_p     = _ease_out(progress)
        x = centre_pos[0] + (tuck_pos[0] - centre_pos[0]) * ease_p
        y = centre_pos[1] + (tuck_pos[1] - centre_pos[1]) * ease_p
        angle = progress * 90   # linear rotation so final angle matches tucked state exactly
        self._blit_reveal_card(t, self._reveal_surf_front, x, y, angle, 1.0)

    def _draw_trump_reveal(self, t, under_deck=False):
        """Draw the trump reveal card animation.
        under_deck=True: only draws phase 3 (card returns under deck).
        under_deck=False: only draws phases 1+2 (card above deck)."""
        phase = self._trump_reveal_phase

        if under_deck:
            if phase != 3:
                return
            tuck_pos   = self._trump_tucked_pos()
            centre_pos = (WIDTH // 2, HEIGHT // 2)
            progress   = min(self._reveal_tick / self._REVEAL_FLY_OUT, 1.0)
            ease_p     = _ease_out(progress)
            x = centre_pos[0] + (tuck_pos[0] - centre_pos[0]) * ease_p
            y = centre_pos[1] + (tuck_pos[1] - centre_pos[1]) * ease_p
            angle = progress * 90
            self._blit_reveal_card(t, self._reveal_surf_front, x, y, angle, 1.0)
            return

        if phase not in (1, 2):
            return

        deck_pos   = self._deck_centre()
        centre_pos = (WIDTH // 2, HEIGHT // 2)
        tick       = self._reveal_tick

        if phase == 1:
            progress = _ease_out(min(tick / self._REVEAL_FLY_IN, 1.0))
            x = deck_pos[0] + (centre_pos[0] - deck_pos[0]) * progress
            y = deck_pos[1] + (centre_pos[1] - deck_pos[1]) * progress
            angle = (1 - progress) * 15
            self._blit_reveal_card(t, self._reveal_surf_back, x, y, angle, 1.0)

        elif phase == 2:
            x, y   = centre_pos
            spin_t = min(tick / self._REVEAL_SPIN, 1.0)
            angle  = math.sin(spin_t * math.pi * 2.5) * 25 * (1 - spin_t)
            flip_t = min(tick / (self._REVEAL_SPIN * 0.7), 1.0)
            if flip_t < 0.5:
                x_scale = 1.0 - _ease_out(flip_t / 0.5)
                surf    = self._reveal_surf_back
            else:
                x_scale = _ease_out((flip_t - 0.5) / 0.5)
                surf    = self._reveal_surf_front
            self._blit_reveal_card(t, surf, x, y, angle, x_scale)

    def _blit_reveal_card(self, t, surf, x, y, angle, x_scale):
        """Blit a card surface at (x,y) with rotation and optional x squash."""
        if x_scale < 0.02:
            return
        s = surf
        if angle != 0:
            s = pygame.transform.rotate(s, angle)
        if x_scale < 0.99:
            new_w = max(1, int(s.get_width() * x_scale))
            s = pygame.transform.scale(s, (new_w, s.get_height()))
        t.blit(s, (int(x) - s.get_width() // 2, int(y) - s.get_height() // 2))

    # ── animation helpers ─────────────────────────────────────────────────────

    def _scaled(self, surf):
        return pygame.transform.scale(surf, (CARD_W, CARD_H))

    def _fly_card(self, card_str, src, dst, duration=22,
                  src_angle=0.0, dst_angle=0.0, on_done=None, sound="card_place"):
        """Launch a flying card. sound= is played when it lands (None to silence)."""
        original_on_done = on_done
        def wrapped_on_done():
            if sound:
                audio.play(sound)
            if original_on_done:
                original_on_done()
        surf = self._scaled(self._card_surf_by_str(card_str))
        self._flying.append(FlyingCard(surf, src, dst, duration,
                                        src_angle, dst_angle, wrapped_on_done))
        self._animating = True

    def _scatter_table(self, pairs, on_all_done):
        """Fly every card in pairs to a random discard position."""
        count   = len(pairs)
        total   = sum(1 + (1 if dfn else 0) for _, dfn in pairs)
        if total == 0:
            on_all_done()
            return
        pending = [total]

        def landed(surf, pos, angle):
            self._discards.append({'surf': surf, 'pos': pos, 'angle': angle})
            if len(self._discards) > 50:
                self._discards.pop(0)
            pending[0] -= 1
            if pending[0] <= 0:
                audio.play("card_discard")
                on_all_done()

        for i, (atk, dfn) in enumerate(pairs):
            for card_str, is_dfn in [(atk, False)] + ([(dfn, True)] if dfn else []):
                src   = self._table_pos(i, count, is_dfn)
                dst   = self._discard_pos()
                angle = random.uniform(-35, 35)
                surf  = self._scaled(self._get_back_surf((CARD_W, CARD_H)))
                def make_cb(s=surf, d=dst, a=angle):
                    def cb(): landed(s, d, a)
                    return cb
                self._flying.append(FlyingCard(surf, src, dst,
                                               duration=28, dst_angle=angle,
                                               on_done=make_cb()))
        self._animating = True

    def _sweep_table(self, pairs, to_player, on_all_done):
        """Fly every card in pairs to player or bot hand."""
        count = len(pairs)
        total = sum(1 + (1 if dfn else 0) for _, dfn in pairs)
        if total == 0:
            on_all_done()
            return
        pending = [total]

        def dec():
            pending[0] -= 1
            if pending[0] <= 0:
                audio.play("card_take")
                on_all_done()

        dst = (WIDTH // 2, HEIGHT - CARD_H // 2) if to_player else self._bot_hand_centre()
        for i, (atk, dfn) in enumerate(pairs):
            for card_str, is_dfn in [(atk, False)] + ([(dfn, True)] if dfn else []):
                src  = self._table_pos(i, count, is_dfn)
                surf = self._scaled(self._card_surf_by_str(card_str))
                self._flying.append(FlyingCard(surf, src, dst, duration=22, on_done=dec))
        self._animating = True

    # ── round management ─────────────────────────────────────────────────────

    def _start_round(self):
        g = self.game
        g.table.clear()
        self._vis_table = []
        self._animating = False
        self._flying.clear()
        self._stat_rounds += 1
        trump = g.deck.trump
        player_trump_count = sum(1 for c in g.players[0].hand if c.is_trump(trump))
        bot_hand_size      = len(g.players[1].hand)
        self._ach_tracker.on_round_start(
            self._stat_rounds, bot_hand_size, player_trump_count)
        if g.attacker_idx == 0:
            self._set(S_HUMAN_ATTACK, "")
        else:
            self._set(S_BOT_THINKING, "")
            self._queue_bot_attack(first=True)

    def _set(self, state, msg=""):
        self._state   = state
        self._message = msg
        key   = _STATUS_KEYS.get(state, "")
        label = _t(key) if key else ("..." if state == S_ROUND_OVER else "")
        if label and label != self._status_label:
            self._status_label = label
            self._status_alpha = 255
            self._status_fade  = 180
        if state == S_ROUND_OVER:
            self._round_timer = _ROUND_DELAY

    def _queue_bot_attack(self, first=False):
        g = self.game
        trump    = g.deck.trump
        attacker = g.players[g.attacker_idx]
        defender = g.players[g.defender_idx]

        def act():
            if first:
                card = _ai_choose_attack(attacker, g.table, trump)
            else:
                card = None if _ai_should_stop_attacking(attacker, g.table, defender, trump) \
                           else _ai_choose_attack(attacker, g.table, trump)

            if card is None:
                # bot passes — scatter what's on table
                pairs = list(self._vis_table)
                self._vis_table = []
                if pairs:
                    self._scatter_table(pairs, on_all_done=lambda: self._do_finish_round(False))
                else:
                    self._do_finish_round(False)
            else:
                pair_idx = len(g.table.pairs)
                attacker.remove_card(card)
                g.table.add_attack(card)
                if g.attacker_idx != 0:
                    self._ach_tracker.on_bot_attack()
                src = self._bot_hand_centre()
                # total pairs after add
                total = len(g.table.pairs)
                dst   = self._table_pos(pair_idx, total, False)
                card_str = str(card)
                def on_land(cs=card_str, pi=pair_idx):
                    # add to vis_table as attack with no defence yet
                    while len(self._vis_table) <= pi:
                        self._vis_table.append((None, None))
                    atk_cur, dfn_cur = self._vis_table[pi]
                    self._vis_table[pi] = (cs, dfn_cur)
                    self._animating = False
                    self._after_attack()
                self._fly_card(card_str, src, dst, on_done=on_land)

        self._bot_timer  = _BOT_DELAY
        self._bot_action = act

    def _queue_bot_defence(self):
        g     = self.game
        trump = g.deck.trump
        idx   = g.table.first_undefended_index()

        def act():
            attack_card = g.table.pairs[idx].attack
            defender    = g.players[g.defender_idx]
            defence     = _ai_choose_defence(defender, attack_card, trump)

            if defence is None:
                # bot takes cards — sweep to bot hand, then do animated draw-up
                pairs = list(self._vis_table)
                self._vis_table = []
                taken = g.table.all_cards()
                defender.hand.extend(taken)
                defender.sort_hand(trump)
                g._advance_roles(defender_took=True)
                def after():
                    self._animating = False
                    self._do_finish_round(defender_took=True)
                self._sweep_table(pairs, to_player=False, on_all_done=after)
            else:
                pair_idx = idx
                defender.remove_card(defence)
                g.table.add_defence(idx, defence)
                self._ach_tracker.on_bot_defend_success()
                src = self._bot_hand_centre()
                total = len(g.table.pairs)
                dst   = self._table_pos(pair_idx, total, True)
                card_str = str(defence)
                def on_land(cs=card_str, pi=pair_idx):
                    if pi < len(self._vis_table):
                        atk_cur, _ = self._vis_table[pi]
                        self._vis_table[pi] = (atk_cur, cs)
                    self._animating = False
                    self._after_attack()
                self._fly_card(card_str, src, dst, on_done=on_land)

        self._bot_timer  = _BOT_DELAY
        self._bot_action = act

    def _after_attack(self):
        g         = self.game
        trump     = g.deck.trump
        validator = MoveValidator(trump)

        if g.table.first_undefended_index() is not None:
            if g.defender_idx == 0:
                idx = g.table.first_undefended_index()
                self._set(S_HUMAN_DEFEND, "")
            else:
                self._set(S_BOT_THINKING, "")
                self._queue_bot_defence()
        else:
            if g.attacker_idx == 0:
                self._set(S_PILE_ON, "")
            else:
                self._set(S_BOT_THINKING, "")
                self._queue_bot_attack(first=False)

    def _finish_round(self, defender_took):
        """Called from human actions."""
        self._attack_commit_timer = 0   # cancel any pending commit window
        pairs = list(self._vis_table)
        self._vis_table = []

        if defender_took:
            def after():
                self._animating = False
                self._do_finish_round(True)
            self._sweep_table(pairs, to_player=True, on_all_done=after)
        else:
            if pairs:
                def after():
                    self._animating = False
                    self._do_finish_round(False)
                self._scatter_table(pairs, on_all_done=after)
            else:
                self._do_finish_round(False)

    def _do_finish_round(self, defender_took):
        g     = self.game
        trump = g.deck.trump
        if not defender_took:
            # Successful defence — pile discarded
            self._ach_tracker.on_round_defended_successfully()
            g._advance_roles(defender_took=False)

        # ── tie detection: both hands empty simultaneously ─────────────────
        both_empty = all(len(p.hand) == 0 for p in g.players)
        if both_empty:
            self._trigger_game_over(R_TIE)
            return

        loser = g._check_game_over()
        if loser is not None:
            result = R_WIN if loser != 0 else R_LOSS
            # You Had One Job: how many attacks were on table when player lost
            if result == R_LOSS:
                atk_count = len([pr for pr in g.table.pairs])
                self._ach_tracker.on_final_round_attack_count(atk_count)
            self._trigger_game_over(result)
            return

        # Deck-empty check
        if g.deck.remaining() == 0 and not self._ach_tracker._deck_empty_fired:
            all_trumps = ([c for c in g.players[0].hand if c.is_trump(trump)] +
                          [c for c in g.players[1].hand if c.is_trump(trump)])
            self._ach_tracker.on_deck_empty(
                g.players[0].hand, all_trumps, trump)

        # Draw-up queue
        order = ([g.attacker_idx]
                 + [i for i in range(len(g.players))
                    if i not in (g.attacker_idx, g.defender_idx)]
                 + [g.defender_idx])
        needs = {idx: max(0, 6 - len(g.players[idx].hand)) for idx in order}
        draw_queue = []
        given      = {idx: 0 for idx in order}
        any_dealt  = True
        while any_dealt and g.deck.remaining() > 0:
            any_dealt = False
            for idx in order:
                if given[idx] < needs[idx] and g.deck.remaining() > 0:
                    draw_queue.append((idx, g.deck.draw()))
                    given[idx] += 1
                    any_dealt   = True

        if draw_queue:
            self._state     = S_DRAWING
            self._animating = True
            self._draw_fly_next(draw_queue, 0)
        else:
            self._start_round()

    def _trigger_game_over(self, result: str) -> None:
        g     = self.game
        trump = g.deck.trump

        self._result      = result
        self._result_tick = 0

        # Snapshot stats
        self._result_stats = {
            "rounds":       self._stat_rounds,
            "piles_taken":  self._stat_piles_taken,
            "biggest_pile": self._stat_biggest_pile,
            "trumps_played":self._stat_trumps_played,
            "passes":       self._stat_passes,
        }

        # Fire achievement tracker
        self._ach_tracker.on_game_over(
            result, g.players[0].hand, g.players[1].hand, trump)

        # Set game-over state
        if result == R_WIN:
            msg = "VICTORY"
            audio.play("win")
        elif result == R_LOSS:
            msg = "DEFEAT"
            audio.play("loss")
            self._spawn_falling_cards()
        else:
            msg = "DRAW"
            audio.play("win")  # neutral

        self._set(S_GAME_OVER, msg)
        audio.stop_music()

    def _draw_fly_next(self, queue, i):
        """Fly one draw-up card, add to hand on landing, then recurse until done."""
        if i >= len(queue):
            for p in self.game.players:
                p.sort_hand(self.game.deck.trump)
            self._animating = False
            self._start_round()
            return

        p_idx, card = queue[i]
        player      = self.game.players[p_idx]
        src         = self._deck_centre()

        if p_idx == 0:
            slot     = len(player.hand)
            rect     = self._hand_rect(slot, slot + 1)
            dst      = (rect.x + CARD_W // 2, rect.y + CARD_H // 2)
            card_key = str(card)          # face-up for player
        else:
            slot     = len(player.hand)
            dst      = self._bot_card_centre(slot, slot + 1)
            card_key = "back"             # face-down for bot

        def on_land(p=player, c=card, qi=i):
            p.hand.append(c)
            self._draw_fly_next(queue, qi + 1)

        self._fly_card(
            card_key, src, dst,
            duration=14,
            src_angle=random.uniform(-8, 8),
            dst_angle=0.0,
            on_done=on_land,
            sound="card_take",
        )

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._state == S_GAME_OVER:
                    return "back"
                return "pause"
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self._state == S_GAME_OVER:
                    return "back"
                if not self._animating:
                    self._on_confirm()
            # ── cheat code (silent) ───────────────────────────────────────
            if event.key == _CHEAT_SEQUENCE[self._cheat_pos]:
                self._cheat_pos += 1
                if self._cheat_pos == len(_CHEAT_SEQUENCE):
                    self._cheat_pos = 0
                    self._activate_cheat()
            else:
                self._cheat_pos = 0
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pause_rect = pygame.Rect(WIDTH - 76, 76, 40, 40)
            if pause_rect.collidepoint(event.pos):
                audio.play("menu_click")
                return "pause"
            if self._state == S_GAME_OVER:
                return "back"
            if not self._animating and self._state not in (S_DEALING, S_DRAWING):
                self._on_click(event.pos)
        return None

    def _activate_cheat(self):
        """Queue all non-unlocked achievements to drip in one by one."""
        s = self._ach_tracker._stats
        queue = [a for a in ACHIEVEMENTS if a.key not in s.unlocked]
        self._cheat_queue = queue
        self._cheat_timer = 0

    def _on_confirm(self):
        if self._state in (S_HUMAN_ATTACK, S_PILE_ON):
            self._stat_passes += 1
            self._finish_round(defender_took=False)

    def _on_click(self, pos):
        g         = self.game
        trump     = g.deck.trump
        validator = MoveValidator(trump)

        if self._state == S_ROUND_OVER:
            return

        if self._state in (S_HUMAN_ATTACK, S_PILE_ON):
            if not g.table.is_empty() and self._pass_rect().collidepoint(pos):
                self._stat_passes += 1
                self._finish_round(defender_took=False)
                return
            card = self._card_at_pos(pos)
            if card is None:
                return
            if not g.table.is_empty() and not validator.can_attack(card, g.table):
                self._invalid_card = card
                self._invalid_tick = 40
                self._message = f"{card} — {_t('game.rank_not_on_table')}"
                audio.play("card_reject")
                return
            hand_before = list(g.players[0].hand)
            hand_idx    = g.players[0].hand.index(card)
            src_rect    = self._hand_rect(hand_idx, len(g.players[0].hand))
            pair_idx    = len(g.table.pairs)
            g.players[0].remove_card(card)
            g.table.add_attack(card)
            g.players[0].sort_hand(trump)
            total    = len(g.table.pairs)
            dst      = self._table_pos(pair_idx, total, False)
            src      = (src_rect.centerx, src_rect.centery)
            card_str = str(card)
            if card.is_trump(trump):
                self._stat_trumps_played += 1
            self._ach_tracker.on_player_attack(card, trump, hand_before)
            if len(g.players[0].hand) == 0:
                self._ach_tracker.on_final_card_played(card, trump, was_attack=True)
            def on_land(cs=card_str, pi=pair_idx):
                while len(self._vis_table) <= pi:
                    self._vis_table.append((None, None))
                _, dfn = self._vis_table[pi]
                self._vis_table[pi] = (cs, dfn)
                self._animating = False
                self._attack_commit_timer = _ATTACK_COMMIT_DELAY
            self._fly_card(card_str, src, dst, on_done=on_land)

        elif self._state == S_HUMAN_DEFEND:
            if self._pickup_rect().collidepoint(pos):
                taken = g.table.all_cards()
                # Check if had valid defence (The Fumble)
                idx_def = g.table.first_undefended_index()
                had_valid = False
                if idx_def is not None:
                    atk_card = g.table.pairs[idx_def].attack
                    had_valid = bool(validator.valid_defences(g.players[0].hand, atk_card))
                self._stat_piles_taken  += 1
                self._stat_biggest_pile  = max(self._stat_biggest_pile, len(taken))
                self._ach_tracker.on_player_takes_pile(taken, trump, had_valid)
                g.players[0].hand.extend(taken)
                g.players[0].sort_hand(trump)
                g._advance_roles(defender_took=True)
                self._finish_round(defender_took=True)
                return
            card = self._card_at_pos(pos)
            if card is None:
                return
            idx = g.table.first_undefended_index()
            atk = g.table.pairs[idx].attack
            if not validator.can_defend(card, atk):
                self._invalid_card = card
                self._invalid_tick = 40
                self._message = f"{card} {_t('game.cant_beat')} {atk}"
                audio.play("card_reject")
                return
            hand_before = list(g.players[0].hand)
            hand_idx    = g.players[0].hand.index(card)
            src_rect    = self._hand_rect(hand_idx, len(g.players[0].hand))
            g.players[0].remove_card(card)
            g.table.add_defence(idx, card)
            g.players[0].sort_hand(trump)
            total    = len(g.table.pairs)
            dst      = self._table_pos(idx, total, True)
            src      = (src_rect.centerx, src_rect.centery)
            card_str = str(card)
            if card.is_trump(trump):
                self._stat_trumps_played += 1
            self._ach_tracker.on_player_defend(card, atk, trump)
            if len(g.players[0].hand) == 0:
                self._ach_tracker.on_final_card_played(card, trump, was_attack=False)
            def on_land(cs=card_str, pi=idx):
                if pi < len(self._vis_table):
                    atk_s, _ = self._vis_table[pi]
                    self._vis_table[pi] = (atk_s, cs)
                self._animating = False
                self._after_attack()
            self._fly_card(card_str, src, dst, on_done=on_land)

    # ── update ────────────────────────────────────────────────────────────────

    def update(self):
        self.tick += 1
        if getattr(self, "_shuffling", False) or self._trump_reveal_phase != 0:
            self._shuffle_tick += 1
        if self._invalid_tick > 0:
            self._invalid_tick -= 1

        # Trump reveal animation
        self._update_trump_reveal()

        # Role reveal animation
        self._update_role_reveal()

        for fc in self._flying:
            fc.update()
        self._flying = [fc for fc in self._flying if not fc.done]
        if not self._flying:
            self._animating = False

        if self._state == S_BOT_THINKING and self._bot_action and not self._animating:
            self._bot_timer -= 1
            if self._bot_timer <= 0:
                fn = self._bot_action
                self._bot_action = None
                fn()

        if self._state == S_ROUND_OVER and not self._animating:
            self._round_timer -= 1
            if self._round_timer <= 0:
                self._start_round()

        # Attack commit window — count down after last attack card lands
        if self._attack_commit_timer > 0 and not self._animating:
            self._attack_commit_timer -= 1
            if self._attack_commit_timer <= 0:
                self._after_attack()

        if self._status_fade > 0:
            self._status_fade -= 1
        elif self._status_alpha > 0:
            self._status_alpha = max(0, self._status_alpha - 4)

        mouse = pygame.mouse.get_pos()
        hand  = self.game.players[0].hand
        for i, card in enumerate(hand):
            rect   = self._hand_rect(i, len(hand))
            target = 20.0 if rect.collidepoint(mouse) else 0.0
            cur    = self._hover.get(id(card), 0.0)
            self._hover[id(card)] = cur + (target - cur) * 0.2

        # Cheat drip: unlock one achievement every 90 ticks
        if self._cheat_queue:
            self._cheat_timer -= 1
            if self._cheat_timer <= 0:
                ach = self._cheat_queue.pop(0)
                self._ach_tracker._stats.unlocked.add(ach.key)
                self._ach_toast.push(ach)
                # Check platinum
                from .achievements import _NON_PLATINUM
                if all(k in self._ach_tracker._stats.unlocked for k in _NON_PLATINUM):
                    plat = ACH["fools_overtime"]
                    if plat.key not in self._ach_tracker._stats.unlocked:
                        self._ach_tracker._stats.unlocked.add(plat.key)
                        self._ach_toast.push(plat)
                self._cheat_timer = 90

        # Falling cards (loss screen)
        if self._result == R_LOSS:
            self._result_tick += 1
            for fc in self._falling_cards:
                fc["y"]   += fc["vy"]
                fc["x"]   += fc["vx"]
                fc["vy"]  += 0.4  # gravity
                fc["rot"] += fc["rot_v"]

        elif self._result in (R_WIN, R_TIE):
            self._result_tick += 1

        self._ach_toast.update()

    # ── falling cards (loss animation) ────────────────────────────────────────

    def _spawn_falling_cards(self):
        self._falling_cards = []
        suits = ["♠", "♥", "♦", "♣"]
        ranks = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        for _ in range(18):
            self._falling_cards.append({
                "x":     random.randint(0, WIDTH),
                "y":     random.randint(-HEIGHT, 0),
                "vx":    random.uniform(-1.5, 1.5),
                "vy":    random.uniform(1, 4),
                "rot":   random.uniform(0, 360),
                "rot_v": random.uniform(-3, 3),
                "card":  f"{random.choice(ranks)}{random.choice(suits)}",
            })

    # ── draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface=None):
        t     = surface or self.screen
        W, H  = t.get_width(), t.get_height()
        mouse = pygame.mouse.get_pos()

        t.fill(BG)
        self._draw_bg_grid(t, W, H)
        self._draw_discards(t)
        self._draw_bot_hand(t, W, H)
        self._draw_trump_reveal(t, under_deck=True)
        self._draw_deck_and_trump(t, W, H)
        self._draw_trump_reveal(t, under_deck=False)
        self._draw_table_cards(t, W, H)
        self._draw_status_bar(t, W, H)
        self._draw_player_hand(t, W, H, mouse)
        self._draw_action_buttons(t, W, H, mouse)
        self._draw_trump_box(t, W, H)
        self._draw_pause_btn(t, W, H, mouse)

        for fc in self._flying:
            fc.draw(t)

        self._draw_role_reveal(t)

        if self._state == S_GAME_OVER:
            self._draw_result_screen(t, W, H)

        self._ach_toast.draw(t)

    def _draw_bg_grid(self, t, W, H):
        for x in range(0, W, 40):
            pygame.draw.line(t, (30, 15, 50), (x, 0), (x, H))
        for y in range(0, H, 40):
            pygame.draw.line(t, (30, 15, 50), (0, y), (W, y))

    def _draw_discards(self, t):
        for d in self._discards:
            rot = pygame.transform.rotate(d['surf'], d['angle'])
            x, y = d['pos']
            t.blit(rot, (x - rot.get_width() // 2, y - rot.get_height() // 2))

    def _draw_bot_hand(self, t, W, H):
        bot     = self.game.players[1]
        count   = len(bot.hand)
        max_w   = W - 40
        gap     = 6
        total_w = count * CARD_W + max(0, count - 1) * gap
        if total_w > max_w and count > 1:
            gap     = max(-(CARD_W - 8), (max_w - count * CARD_W) // (count - 1))
            total_w = count * CARD_W + (count - 1) * gap
        sx = W // 2 - total_w // 2
        y  = 20
        for i in range(count):
            t.blit(self._get_back_surf((CARD_W, CARD_H)), (sx + i * (CARD_W + gap), y))

        av_cx, av_cy = W // 2, y + CARD_H + 36
        av_r         = 28
        pygame.draw.circle(t, PURPLE_DIM, (av_cx, av_cy), av_r)
        pygame.draw.circle(t, PURPLE,     (av_cx, av_cy), av_r, width=2)
        pygame.draw.circle(t, TEXT_DIM,   (av_cx, av_cy - 8), 10)
        pygame.draw.ellipse(t, TEXT_DIM,
            pygame.Rect(av_cx - 14, av_cy + 4, 28, 16))
        f   = get_fonts()["small"]
        cnt = f.render(str(count), False, TEXT_DIM)
        t.blit(cnt, (av_cx - cnt.get_width() // 2, av_cy + av_r + 6))

    def _draw_deck_and_trump(self, t, W, H):
        remaining = self.game.deck.remaining()
        x, y      = 110, H // 2 - CARD_H // 2

        # Draw tucked trump face-up rotated 90° under the deck — only once reveal is done
        if getattr(self, "_trump_tucked", False) and remaining > 0 \
                and self._trump_reveal_phase == 0:
            trump_card = self.game.deck.peek_bottom()
            trump_surf = self._scaled(self._card_surf_by_str(str(trump_card)))
            rotated    = pygame.transform.rotate(trump_surf, 90)
            tx, ty     = self._trump_tucked_pos()
            t.blit(rotated, (tx - rotated.get_width() // 2,
                              ty - rotated.get_height() // 2))

        for i in range(min(4, remaining)):
            t.blit(self._get_back_surf((CARD_W, CARD_H)), (x + i * 2, y - i * 2))

        # shuffle flourish during intro deal and trump reveal
        if getattr(self, "_shuffling", False) or self._trump_reveal_phase != 0:
            cx = x + CARD_W // 2
            cy = y + CARD_H // 2
            for k in range(5):
                ang = (self._shuffle_tick * 9 + k * 72) % 360
                rad = 10 + (k % 2) * 6
                ox  = int(math.cos(math.radians(ang)) * rad)
                oy  = int(math.sin(math.radians(ang)) * rad)
                surf = pygame.transform.rotate(
                    self._get_back_surf((CARD_W, CARD_H)),
                    int(math.sin(math.radians(ang)) * 12)
                )
                t.blit(
                    surf,
                    (cx - surf.get_width() // 2 + ox, cy - surf.get_height() // 2 + oy)
                )

        f   = get_fonts()["small"]
        cnt = f.render(str(remaining), False, TEXT_DIM)
        t.blit(cnt, (x + CARD_W // 2 - cnt.get_width() // 2, y + CARD_H + 6))

    def _draw_table_cards(self, t, W, H):
        # Always draw _vis_table — it's the source of truth for settled cards
        pairs = self._vis_table
        if not pairs:
            return
        count  = len(pairs)
        gap    = CARD_W + 20
        offset = 16
        sx     = W // 2 - count * gap // 2

        for i, (atk, dfn) in enumerate(pairs):
            x = sx + i * gap
            y = H // 2 - CARD_H // 2
            if atk:
                self._draw_card_face(t, atk, x, y)
            if dfn:
                self._draw_card_face(t, dfn, x + offset, y - offset)

    def _draw_status_bar(self, t, W, H):
        cx = W // 2
        f  = get_fonts()["small"]

        if self._status_alpha > 0 and self._status_label:
            label = self._status_label
            if self._state == S_BOT_THINKING:
                label = "THINKING" + "." * (int(self.tick / 15) % 4)
            lbl  = f.render(label, False, NEON_GLOW)
            surf = pygame.Surface((lbl.get_width(), lbl.get_height()), pygame.SRCALPHA)
            surf.blit(lbl, (0, 0))
            surf.set_alpha(self._status_alpha)
            av_y = 20 + CARD_H + 36
            t.blit(surf, (cx - surf.get_width() // 2, av_y + 40))

        # Attack commit countdown arc — shows remaining window to add cards
        if self._attack_commit_timer > 0 and not self._animating:
            ratio   = self._attack_commit_timer / _ATTACK_COMMIT_DELAY
            r       = 18
            arc_y   = H // 2 - CARD_H // 2 - 48
            rect    = pygame.Rect(cx - r, arc_y - r, r * 2, r * 2)
            # background ring
            pygame.draw.circle(t, PURPLE_DIM, (cx, arc_y), r, width=3)
            # coloured arc — green to red as time runs out
            g_val   = int(200 * ratio)
            r_val   = int(200 * (1 - ratio))
            col     = (r_val, g_val, 60)
            end_ang = -90 + (1 - ratio) * 360
            start   = math.radians(-90)
            end     = math.radians(end_ang)
            # draw arc as polyline
            steps   = max(2, int(ratio * 32))
            pts     = []
            for s in range(steps + 1):
                a = math.radians(-90 + ratio * 360 * s / steps)
                pts.append((cx + int(r * math.cos(a)), arc_y + int(r * math.sin(a))))
            if len(pts) >= 2:
                pygame.draw.lines(t, col, False, pts, 3)
            # label inside
            secs = math.ceil(self._attack_commit_timer / 60)
            lbl  = f.render(str(secs), False, col)
            t.blit(lbl, (cx - lbl.get_width() // 2, arc_y - lbl.get_height() // 2))

        if self._message:
            msg = f.render(self._message, False, TEXT_DIM)
            t.blit(msg, (cx - msg.get_width() // 2, H // 2 + 20))

    def _draw_player_hand(self, t, W, H, mouse):
        hand       = self.game.players[0].hand
        actionable = self._state in (S_HUMAN_ATTACK, S_HUMAN_DEFEND, S_PILE_ON)
        for i, card in enumerate(hand):
            rect    = self._hand_rect(i, len(hand))
            lift    = int(self._hover.get(id(card), 0.0)) if actionable else 0
            invalid = card == self._invalid_card and self._invalid_tick > 0
            hover   = lift > 2 and actionable
            surf    = self._get_card_surf(card, (CARD_W, CARD_H))
            if hover or invalid:
                surf    = surf.copy()
                overlay = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
                overlay.fill((255, 80, 80, 60) if invalid else (*NEON_GLOW, 40))
                surf.blit(overlay, (0, 0))
                pygame.draw.rect(surf,
                    (220, 60, 60) if invalid else NEON_GLOW,
                    (0, 0, CARD_W, CARD_H), width=2)
            t.blit(surf, (rect.x, rect.y - lift))

    def _draw_action_buttons(self, t, W, H, mouse):
        f = get_fonts()["small"]

        if self._state == S_HUMAN_DEFEND:
            r   = self._pickup_rect()
            col = NEON_DARK if r.collidepoint(mouse) else (80, 20, 40)
            pygame.draw.rect(t, col, r, border_radius=6)
            pygame.draw.rect(t, NEON, r, width=1, border_radius=6)
            lbl = f.render(_t("game.take_cards"), False, TEXT_MAIN)
            t.blit(lbl, (r.centerx - lbl.get_width() // 2,
                          r.centery - lbl.get_height() // 2))

        if self._state in (S_HUMAN_ATTACK, S_PILE_ON) and not self.game.table.is_empty():
            r   = self._pass_rect()
            col = (50, 50, 120) if r.collidepoint(mouse) else (20, 20, 55)
            pygame.draw.rect(t, col, r, border_radius=6)
            pygame.draw.rect(t, PURPLE, r, width=1, border_radius=6)
            lbl = f.render(_t("game.pass"), False, TEXT_MAIN)
            t.blit(lbl, (r.centerx - lbl.get_width() // 2,
                          r.centery - lbl.get_height() // 2))

    def _draw_trump_box(self, t, W, H):
        r = pygame.Rect(20, 20, 150, 70)
        pygame.draw.rect(t, PURPLE_DIM, r, border_radius=8)
        pygame.draw.rect(t, PURPLE,     r, width=1, border_radius=8)

        _all_suits   = ['♥', '♦', '♠', '♣']
        name_map     = {
            '♥': _t("suits.hearts")   if False else 'HEARTS',
            '♦': _t("suits.diamonds") if False else 'DIAMONDS',
            '♠': _t("suits.spades")   if False else 'SPADES',
            '♣': _t("suits.clubs")    if False else 'CLUBS',
        }
        # Suit names in all three languages
        from .locale import get_lang as _gl
        _suit_names = {
            "en": {'♥': 'HEARTS', '♦': 'DIAMONDS', '♠': 'SPADES', '♣': 'CLUBS'},
            "ru": {'♥': 'ЧЕРВЫ',  '♦': 'БУБНЫ',    '♠': 'ПИКИ',   '♣': 'ТРЕФЫ'},
            "ro": {'♥': 'INIMI',  '♦': 'ROMBURI',  '♠': 'PICĂ',   '♣': 'TREFLĂ'},
        }
        name_map = _suit_names.get(_gl(), _suit_names["en"])
        real_sym     = str(self.game.deck.trump)   # the actual trump suit symbol
        f            = get_fonts()["small"]
        f_big        = get_fonts().get("body", f)

        # During deal: cycle fast using shuffle_tick
        # During reveal phases 1+2: cycle fast using reveal_tick
        # During reveal phase 3: slow down and snap to real suit
        # Otherwise: show real suit
        phase = self._trump_reveal_phase
        if getattr(self, "_shuffling", False) and phase == 0:
            idx      = (self._shuffle_tick // 4) % 4
            suit_sym = _all_suits[idx]
        elif phase in (1, 2):
            idx      = (self._reveal_tick // 4) % 4
            suit_sym = _all_suits[idx]
        elif phase == 3:
            progress = self._reveal_tick / self._REVEAL_FLY_OUT
            if progress < 0.6:
                idx      = (self._reveal_tick // 6) % 4
                suit_sym = _all_suits[idx]
            else:
                suit_sym = real_sym
        else:
            suit_sym = real_sym

        is_red   = suit_sym in ('♥', '♦')
        suit_col = (220, 60, 80) if is_red else TEXT_MAIN

        label = f.render(_t("game.trump"), False, TEXT_DIM)
        t.blit(label, (r.x + 10, r.y + 8))

        sym      = f_big.render(suit_sym, False, suit_col)
        target_h = 36
        scale    = target_h / max(sym.get_height(), 1)
        sym_big  = pygame.transform.scale(sym,
            (max(1, int(sym.get_width() * scale)), target_h))
        t.blit(sym_big, (r.x + 10, r.y + 26))

        name = f.render(name_map.get(suit_sym, suit_sym), False, suit_col)
        t.blit(name, (r.x + 10 + sym_big.get_width() + 8,
                      r.y + 26 + (target_h - name.get_height()) // 2))

    def _draw_pause_btn(self, t, W, H, mouse):
        r   = pygame.Rect(W - 76, 76, 40, 40)
        col = PURPLE if r.collidepoint(mouse) else PURPLE_DIM
        pygame.draw.rect(t, col, r, border_radius=6)
        pygame.draw.rect(t, PURPLE, r, width=1, border_radius=6)
        for dy in (-8, 0, 8):
            pygame.draw.rect(t, TEXT_DIM, (r.x + 8, r.centery + dy - 1, 24, 2))

    def _draw_result_screen(self, t, W, H):
        result = self._result
        tick   = self._result_tick
        stats  = self._result_stats
        f_title = get_fonts()["title"]
        f_btn   = get_fonts()["btn"]
        f_sm    = get_fonts()["small"]

        # ── shared overlay ────────────────────────────────────────────────────
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        if result == R_WIN:
            ov.fill((0, 0, 0, 200))
        elif result == R_LOSS:
            ov.fill((0, 0, 0, 210))
        else:
            ov.fill((0, 0, 0, 195))
        t.blit(ov, (0, 0))

        # ── loss: falling cards ───────────────────────────────────────────────
        if result == R_LOSS:
            for fc in self._falling_cards:
                if fc["y"] > H + CARD_H:
                    continue
                cs = self._card_surf_by_str(fc["card"])
                rot = pygame.transform.rotate(cs, fc["rot"])
                rot.set_alpha(140)
                t.blit(rot, (int(fc["x"]) - rot.get_width() // 2,
                              int(fc["y"]) - rot.get_height() // 2))

        cx = W // 2
        cy = H // 2

        # ── title ─────────────────────────────────────────────────────────────
        fade_in  = min(1.0, tick / 40)
        if result == R_WIN:
            title_str = _t("result.victory")
            title_col = GOLD
            sub_col   = NEON_GLOW
            sub_str   = _t("result.sub_win")
        elif result == R_LOSS:
            title_str = _t("result.defeat")
            title_col = (220, 60, 80)
            sub_col   = TEXT_DIM
            sub_str   = _t("result.sub_loss")
        else:
            title_str = _t("result.draw")
            title_col = PURPLE
            sub_col   = TEXT_DIM
            sub_str   = _t("result.sub_draw")

        title_s = f_title.render(title_str, False, title_col)
        glow_s  = f_title.render(title_str, False, title_col)
        glow_s.set_alpha(int(60 * fade_in))

        # Pulse glow
        pulse = abs(math.sin(tick * 0.04)) * 20
        gs = pygame.Surface((title_s.get_width() + 40,
                              title_s.get_height() + 20), pygame.SRCALPHA)
        pygame.draw.rect(gs, (*title_col, int(20 + pulse)), gs.get_rect(),
                         border_radius=6)
        t.blit(gs, (cx - gs.get_width() // 2, cy - 120 - 10))

        title_s.set_alpha(int(255 * fade_in))
        t.blit(title_s, (cx - title_s.get_width() // 2, cy - 120))

        sub_s = f_sm.render(sub_str, False, sub_col)
        sub_s.set_alpha(int(220 * fade_in))
        t.blit(sub_s, (cx - sub_s.get_width() // 2, cy - 120 + title_s.get_height() + 8))

        # ── divider ───────────────────────────────────────────────────────────
        div_alpha = int(180 * fade_in)
        div_surf  = pygame.Surface((320, 1), pygame.SRCALPHA)
        div_surf.fill((*PURPLE, div_alpha))
        t.blit(div_surf, (cx - 160, cy - 50))

        # ── stats panel ───────────────────────────────────────────────────────
        stat_fade = min(1.0, max(0.0, (tick - 20) / 40))
        stat_lines = [
            (_t("result.rounds"),        str(stats.get("rounds", 0))),
            (_t("result.piles_taken"),   str(stats.get("piles_taken", 0))),
            (_t("result.biggest_pile"),  str(stats.get("biggest_pile", 0))),
            (_t("result.trumps_played"), str(stats.get("trumps_played", 0))),
            (_t("result.times_passed"),  str(stats.get("passes", 0))),
        ]

        panel_w, panel_h = 320, len(stat_lines) * 22 + 16
        px = cx - panel_w // 2
        py = cy - 38

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 40, int(200 * stat_fade)))
        pygame.draw.rect(panel_surf, (*PURPLE_DIM, int(150 * stat_fade)),
                         panel_surf.get_rect(), width=1, border_radius=4)
        t.blit(panel_surf, (px, py))

        for i, (label, val) in enumerate(stat_lines):
            sy    = py + 8 + i * 22
            lbl_s = f_sm.render(label, False, TEXT_DIM)
            val_s = f_sm.render(val,   False, TEXT_MAIN)
            lbl_s.set_alpha(int(220 * stat_fade))
            val_s.set_alpha(int(220 * stat_fade))
            t.blit(lbl_s, (px + 12, sy))
            t.blit(val_s, (px + panel_w - val_s.get_width() - 12, sy))

        # ── prompt ────────────────────────────────────────────────────────────
        prompt_fade = min(1.0, max(0.0, (tick - 50) / 30))
        if prompt_fade > 0:
            blink = abs(math.sin(tick * 0.05))
            prompt_s = f_sm.render(_t("result.press_any_key"), False, TEXT_DIM)
            prompt_s.set_alpha(int(200 * prompt_fade * blink))
            t.blit(prompt_s, (cx - prompt_s.get_width() // 2, cy + panel_h + 20))

    # ── card image loading ────────────────────────────────────────────────────

    def _load_card_images(self):
        import os
        card_dir = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
        images   = {}
        suit_map = {'♥': 'hearts', '♦': 'diamonds', '♠': 'spades', '♣': 'clubs'}
        rank_map = {
            'A': 'ace', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
            '7': '7', '8': '8', '9': '9', '10': '10',
            'J': 'jack', 'Q': 'queen', 'K': 'king',
        }
        try:
            for suit_sym, suit_name in suit_map.items():
                for rank_sym, rank_name in rank_map.items():
                    key  = f'{rank_sym}{suit_sym}'
                    path = os.path.join(card_dir, f'{rank_name}_of_{suit_name}.png')
                    if os.path.exists(path):
                        images[key] = pygame.image.load(path).convert_alpha()
            back_path = os.path.join(card_dir, 'back.png')
            if os.path.exists(back_path):
                images['back'] = pygame.image.load(back_path).convert_alpha()
        except Exception as e:
            print(f'[warn] card image load failed: {e}')
        return images

    def _card_surf_by_str(self, card_str):
        card_str = card_str.strip()
        # Try direct lookup first (e.g. "6♥")
        base = self._cards.get(card_str)
        if base:
            return pygame.transform.scale(base, (CARD_W, CARD_H))
        # Fall back to parsing and drawing programmatically
        from ..core.card import Card, Suit
        suit_map = {'♥': Suit.HEARTS, '♦': Suit.DIAMONDS, '♠': Suit.SPADES, '♣': Suit.CLUBS}
        for sym, suit in suit_map.items():
            if card_str.endswith(sym):
                rank = card_str[:-1]
                try:
                    return self._get_card_surf(Card(suit=suit, rank=rank), (CARD_W, CARD_H))
                except Exception:
                    pass
        # Last resort fallback
        surf = pygame.Surface((CARD_W, CARD_H))
        surf.fill((220, 220, 220))
        return surf

    def _get_card_surf(self, card, size):
        key  = f'{card.rank}{card.suit.value}'
        base = self._cards.get(key, None)
        if base is None:
            base = self._make_card_face_surf(card)
        return pygame.transform.scale(base, size)

    def _get_back_surf(self, size):
        base = self._cards.get('back')
        if base is None:
            return self._make_card_back_surf(*size)
        return pygame.transform.scale(base, size)

    def _make_card_back_surf(self, w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, CARD_BACK, (0, 0, w, h), border_radius=5)
        pygame.draw.rect(surf, PURPLE,    (0, 0, w, h), width=1, border_radius=5)
        return surf

    def _make_card_face_surf(self, card):
        surf   = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        is_red = card.suit.value in ('♥', '♦')
        col    = CARD_RED if is_red else CARD_BLACK
        pygame.draw.rect(surf, CARD_BG,    (0, 0, CARD_W, CARD_H), border_radius=5)
        pygame.draw.rect(surf, CARD_BORDER,(0, 0, CARD_W, CARD_H), width=1, border_radius=5)
        lbl = get_fonts()["small"].render(str(card), False, col)
        surf.blit(lbl, (4, 4))
        return surf

    def _draw_card_face(self, target, card_str, x, y):
        base = self._cards.get(card_str.strip())
        surf = pygame.transform.scale(base, (CARD_W, CARD_H)) if base else \
               (lambda s: (s.fill((220,220,220)), s)[1])(pygame.Surface((CARD_W, CARD_H)))
        target.blit(surf, (x, y))

    # ── hit testing ───────────────────────────────────────────────────────────

    def _card_at_pos(self, pos):
        hand = self.game.players[0].hand
        for i, card in reversed(list(enumerate(hand))):
            if self._hand_rect(i, len(hand)).collidepoint(pos):
                return card
        return None

    def _pickup_rect(self):
        return pygame.Rect(WIDTH - 200, HEIGHT // 2 + 80, 140, 40)

    def _pass_rect(self):
        return pygame.Rect(WIDTH - 200, HEIGHT // 2 + 80, 140, 40)
    
