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

S_HUMAN_ATTACK  = "human_attack"
S_HUMAN_DEFEND  = "human_defend"
S_PILE_ON       = "pile_on"
S_PILE_ON_TAKING = "pile_on_taking"   # defender chose to take; attacker may still add cards
S_BOT_THINKING  = "bot_thinking"
S_ROUND_OVER    = "round_over"
S_GAME_OVER     = "game_over"
S_DEALING       = "dealing"
S_DRAWING       = "drawing"

# game-over result
R_WIN  = "win"
R_LOSS = "loss"
R_TIE  = "tie"

_STATUS_KEYS = {
    S_DEALING:       "game.status_deal",
    S_DRAWING:       "game.status_deal",
    S_HUMAN_ATTACK:  "game.status_attack",
    S_HUMAN_DEFEND:  "game.status_defend",
    S_PILE_ON:       "game.status_pile_on",
    S_PILE_ON_TAKING:"game.status_taking",
    S_BOT_THINKING:  "game.status_bot",
    S_ROUND_OVER:    "",
    S_GAME_OVER:     "game.status_game_over",
}

# Cheat code: first 12 digits of pi = 3 1 4 1 5 9 2 6 5 3 5 8
_CHEAT_SEQUENCE = [pygame.K_3, pygame.K_1, pygame.K_4, pygame.K_1, pygame.K_5,
                   pygame.K_9, pygame.K_2, pygame.K_6, pygame.K_5, pygame.K_3,
                   pygame.K_5, pygame.K_8]


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3

def _ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)

def _ease_out_back(t: float) -> float:
    """Slight overshoot then settle — gives cards a satisfying landing."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


# ── Flying card sprite ────────────────────────────────────────────────────────

class FlyingCard:
    def __init__(self, surf, src, dst, duration=0.40,
                 src_angle=0.0, dst_angle=0.0, on_done=None,
                 arc=0.10, easing="out", delay=0.0):
        """
        duration: seconds for the flight
        delay:    seconds to wait before starting
        arc:      fraction of travel distance to lift at mid-flight
        easing:   "out" | "in_out" | "out_back"
        """
        self.surf      = surf
        self.src       = src
        self.dst       = dst
        self.duration  = max(0.01, duration)
        self.elapsed   = -delay          # negative = delay remaining
        self.src_angle = src_angle
        self.dst_angle = dst_angle
        self.on_done   = on_done
        self.done      = False
        self.arc       = arc
        self.easing    = easing

    def update(self, dt: float):
        self.elapsed += dt
        if self.elapsed <= 0:
            return  # still in delay
        if self.elapsed >= self.duration:
            self.elapsed = self.duration
            if not self.done:
                self.done = True
                if self.on_done:
                    self.on_done()

    @property
    def t(self):
        if self.elapsed <= 0:
            return 0.0
        raw = min(1.0, self.elapsed / self.duration)
        if self.easing == "in_out":
            return _ease_in_out(raw)
        elif self.easing == "out_back":
            return _ease_out_back(raw)
        return _ease_out(raw)

    @property
    def pos(self):
        if self.elapsed <= 0:
            return self.src
        t   = self.t
        raw = min(1.0, self.elapsed / self.duration)
        x   = self.src[0] + (self.dst[0] - self.src[0]) * t
        y   = self.src[1] + (self.dst[1] - self.src[1]) * t
        if self.arc != 0:
            dist = math.hypot(self.dst[0] - self.src[0],
                              self.dst[1] - self.src[1])
            y -= 4 * raw * (1 - raw) * self.arc * dist
        return (x, y)

    @property
    def angle(self):
        if self.elapsed <= 0:
            return self.src_angle
        return self.src_angle + (self.dst_angle - self.src_angle) * self.t

    def draw(self, target):
        if self.elapsed <= 0:
            return
        rotated = pygame.transform.rotate(self.surf, self.angle)
        x, y    = self.pos
        target.blit(rotated, (int(x) - rotated.get_width()  // 2,
                               int(y) - rotated.get_height() // 2))


# ── GameScreen ────────────────────────────────────────────────────────────────

class GameScreen:
    def __init__(self, screen, fonts, game, transfer_mode: bool = False):
        self.screen        = screen
        self.fonts         = fonts
        self.game          = game
        self.tick          = 0
        self.transfer_mode = transfer_mode

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
        self._vis_table: list[tuple]  = []
        self._sliding_slots: set      = set()   # (pair_idx, is_defence) currently sliding
        self._vis_table_total: int    = 0        # layout total to use during slide animations
        self._sorting_hand: bool      = False    # suppress hand draw during sort animation
        self._transfer_badge_rects: dict = {}    # card id → badge Rect above card
        self._pending_defender_took: bool = False  # set when defender chose to take; attacker may still pile on

        # ── pre-built cached surfaces (expensive to recreate every frame) ────
        self._time            = 0.0
        self._cached_bg       = None
        self._cached_dividers = None
        self._cached_glow     = {}
        self._flying   : list[FlyingCard] = []
        self._discards : list[dict]       = []
        self._hover    : dict             = {}
        self._animating = False
        # hand spread animation: card_id → [progress 0→1, old_total]
        # when a card lands in hand, existing cards animate from old positions to new
        self._hand_spread: dict = {}
        self._round_had_transfer: bool = False   # skip bot pile-on window if transfer occurred

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
        max_w   = WIDTH - 40
        gap     = 10
        total_w = total * CARD_W + (total - 1) * gap
        if total_w > max_w and total > 1:
            gap     = max(-(CARD_W - 8), (max_w - total * CARD_W) // (total - 1))
            total_w = total * CARD_W + (total - 1) * gap
        sx = WIDTH // 2 - total_w // 2
        return pygame.Rect(sx + idx * (CARD_W + gap), HEIGHT - CARD_H - 20, CARD_W, CARD_H)

    def _hand_rect_spread(self, idx, total, card=None):
        """Like _hand_rect but interpolates from old position when spread animation is active."""
        new_rect = self._hand_rect(idx, total)
        if card is None or id(card) not in self._hand_spread:
            return new_rect
        progress, old_total = self._hand_spread[id(card)]
        # Ease out: fast start, settle at end
        t = 1 - (1 - progress) ** 3
        old_rect = self._hand_rect(idx, old_total)
        x = int(old_rect.x + (new_rect.x - old_rect.x) * t)
        return pygame.Rect(x, new_rect.y, CARD_W, CARD_H)

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

    def _animate_sort_player_hand(self, g, callback):
        """Slide player hand cards to their sorted positions, then call callback."""
        player = g.players[0]
        trump  = g.deck.trump
        old_hand = list(player.hand)
        sorted_hand = sorted(old_hand, key=lambda c: c.sort_key(trump))

        # Check if sort actually changes anything
        if old_hand == sorted_hand:
            player.sort_hand(trump)
            for p in g.players[1:]:
                p.sort_hand(trump)
            self._animating = False
            callback()
            return

        total = len(old_hand)
        pending = [0]

        # Suppress the hand from drawing — we'll draw via flying cards
        self._sorting_hand = True

        for old_idx, card in enumerate(old_hand):
            new_idx = sorted_hand.index(card)
            old_rect = self._hand_rect(old_idx, total)
            new_rect = self._hand_rect(new_idx, total)
            old_pos  = (old_rect.centerx, old_rect.centery)
            new_pos  = (new_rect.centerx, new_rect.centery)

            if old_pos == new_pos:
                continue

            pending[0] += 1
            surf = self._get_card_surf(card, (CARD_W, CARD_H))

            def on_done(pending=pending, g=g, sorted_hand=sorted_hand,
                        trump=trump, callback=callback):
                pending[0] -= 1
                if pending[0] <= 0:
                    player.hand[:] = sorted_hand
                    for p in g.players[1:]:
                        p.sort_hand(trump)
                    self._sorting_hand = False
                    self._animating    = False
                    callback()

            self._flying.append(FlyingCard(surf, old_pos, new_pos,
                                           duration=0.38, on_done=on_done,
                                           arc=0.0, easing="in_out"))

        if pending[0] == 0:
            # All cards were already in place
            player.hand[:] = sorted_hand
            for p in g.players[1:]:
                p.sort_hand(trump)
            self._sorting_hand = False
            self._animating    = False
            callback()

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
        """Launch all remaining deal cards with staggered overlapping starts."""
        g     = self.game
        trump = g.deck.trump

        if self._deal_i >= len(self._deal_queue):
            g._assign_first_attacker()
            self._animating = True
            self._animate_sort_player_hand(g, callback=lambda: (
                self._ach_tracker.on_game_start(g.players[0].hand, g.deck.trump),
                self._begin_trump_reveal()
            ))
            return

        # Launch all remaining cards with a stagger delay so they overlap in flight.
        # Each card "pre-draws" from deck and targets its final sorted slot.
        # on_land callbacks insert them in-order so hand state is always consistent.
        STAGGER   = 0.16   # seconds between card launches
        DURATION  = 0.45   # seconds per card flight

        remaining_queue = self._deal_queue[self._deal_i:]
        # Pre-draw all cards now (before any land) so targets can be computed
        pre_drawn: list[tuple] = []   # (p_idx, card, slot_at_launch)
        hand_sizes = {i: len(g.players[i].hand) for i in range(len(g.players))}
        for p_idx in remaining_queue:
            slot = hand_sizes[p_idx]
            hand_sizes[p_idx] += 1
            card = g.deck.draw()
            pre_drawn.append((p_idx, card, slot))

        total_by_player = {}
        for p_idx, _, _ in pre_drawn:
            total_by_player[p_idx] = total_by_player.get(p_idx, 0) + 1

        # Track how many have been sent to each player so far for slot targeting
        sent_counts: dict[int, int] = {i: len(g.players[i].hand) for i in range(len(g.players))}

        completed = [0]
        total_cards = len(pre_drawn)

        for launch_idx, (p_idx, card, _) in enumerate(pre_drawn):
            player     = g.players[p_idx]
            slot       = sent_counts[p_idx]
            final_size = len(player.hand) + total_by_player[p_idx]
            sent_counts[p_idx] += 1

            if p_idx == 0:
                rect = self._hand_rect(slot, final_size)
                dst  = (rect.x + CARD_W // 2, rect.y + CARD_H // 2)
            else:
                dst  = self._bot_card_centre(slot, final_size)

            delay = launch_idx * STAGGER   # seconds to wait before launching

            def make_on_land(p=player, c=card):
                def on_land():
                    p.hand.append(c)
                    completed[0] += 1
                    if completed[0] >= total_cards:
                        # All dealt — sort and reveal trump
                        self._deal_i = len(self._deal_queue)
                        g._assign_first_attacker()
                        self._animating = True
                        self._animate_sort_player_hand(g, callback=lambda: (
                            self._ach_tracker.on_game_start(g.players[0].hand, g.deck.trump),
                            self._begin_trump_reveal()
                        ))
                return on_land

            # Use a delayed FlyingCard so cards launch with stagger
            surf = self._scaled(self._card_surf_by_str("back"))
            src  = self._deck_centre()
            angle_s = random.uniform(-10, 10)
            angle_d = random.uniform(-3, 3)

            def make_wrapped(original_done=make_on_land()):
                def wrapped():
                    audio.play("card_take")
                    original_done()
                return wrapped

            fc = FlyingCard(surf, src, dst, duration=DURATION,
                            src_angle=angle_s, dst_angle=angle_d,
                            on_done=make_wrapped(), arc=0.12, delay=delay)
            self._flying.append(fc)

        self._deal_i = len(self._deal_queue)  # mark all as launched
        self._animating = True

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

    _ROLE_CYCLE_TICKS = 80    # ~1.3s cycling through roles
    _ROLE_HOLD_TICKS  = 45    # ~0.75s hold on final role
    _ROLE_FADE_TICKS  = 40    # ~0.67s grow + fade out
    _ROLE_CYCLE_SPEED = 8     # ticks per role flip — faster flicker

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

    def _fly_card(self, card_str, src, dst, duration=0.40,
                  src_angle=0.0, dst_angle=0.0, on_done=None, sound="card_place",
                  arc=0.10, easing="out"):
        """Launch a flying card. sound= is played when it lands (None to silence)."""
        original_on_done = on_done
        def wrapped_on_done():
            if sound:
                audio.play(sound)
            if original_on_done:
                original_on_done()
        surf = self._scaled(self._card_surf_by_str(card_str))
        self._flying.append(FlyingCard(surf, src, dst, duration,
                                        src_angle, dst_angle, wrapped_on_done,
                                        arc=arc, easing=easing))
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
                                               duration=0.45, dst_angle=angle,
                                               on_done=make_cb(), arc=0.12))
        self._animating = True

    def _slide_table_to(self, new_total):
        """Smoothly slide all existing vis_table cards to positions for new_total pairs."""
        if new_total <= 1:
            self._vis_table_total = new_total
            return
        self._vis_table_total = new_total
        for i, (atk, dfn) in enumerate(self._vis_table):
            for card_str, is_dfn in [(atk, False), (dfn, True)]:
                if not card_str:
                    continue
                old_pos = self._table_pos(i, new_total - 1, is_dfn)
                new_pos = self._table_pos(i, new_total, is_dfn)
                if old_pos == new_pos:
                    continue
                surf = self._scaled(self._card_surf_by_str(card_str))
                slot_key = (i, is_dfn)
                self._sliding_slots.add(slot_key)
                def on_done(sk=slot_key):
                    self._sliding_slots.discard(sk)
                self._flying.append(FlyingCard(surf, old_pos, new_pos,
                                               duration=0.28, on_done=on_done,
                                               arc=0.0, easing="in_out"))

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
                self._flying.append(FlyingCard(surf, src, dst, duration=0.40,
                                               on_done=dec, arc=0.08))
        self._animating = True

    # ── round management ─────────────────────────────────────────────────────

    def _start_round(self):
        g = self.game
        g.table.clear()
        self._vis_table             = []
        self._sliding_slots         = set()
        self._vis_table_total       = 0
        self._pending_defender_took = False
        self._round_had_transfer    = False
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
            # Hard cap: 6 cards total. Also cap at defender hand size on the
            # very first attack so they always have a card to beat with.
            max_attacks = min(6, len(defender.hand)) if first else 6
            if len(g.table.pairs) >= max_attacks:
                card = None
            elif first:
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
                total = len(g.table.pairs)
                dst   = self._table_pos(pair_idx, total, False)
                card_str = str(card)

                # Slide existing table cards to their new positions
                self._slide_table_to(total)

                def on_land(cs=card_str, pi=pair_idx):
                    while len(self._vis_table) <= pi:
                        self._vis_table.append((None, None))
                    atk_cur, dfn_cur = self._vis_table[pi]
                    self._vis_table[pi] = (cs, dfn_cur)
                    self._vis_table_total = len(self._vis_table)
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
            validator   = MoveValidator(trump)

            # In transfer mode, bot will transfer if it can and has no good defence
            new_def_hand = g.players[g.attacker_idx].hand  # attacker becomes new defender
            if self.transfer_mode and validator.can_transfer(attack_card, g.table,
                                                             new_defender_hand=new_def_hand):
                transfers = validator.valid_transfers(defender.hand, g.table,
                                                      new_defender_hand=new_def_hand)
                defence   = _ai_choose_defence(defender, attack_card, trump)
                # Prefer transferring if defence would cost a trump or there's no defence
                should_transfer = transfers and (
                    defence is None or
                    (defence.is_trump(trump) and not attack_card.is_trump(trump))
                )
                if should_transfer:
                    card     = transfers[0]
                    pair_idx = len(g.table.pairs)
                    defender.remove_card(card)
                    g.table.add_attack(card)
                    # Swap roles
                    g.attacker_idx, g.defender_idx = g.defender_idx, g.attacker_idx
                    self._round_had_transfer = True
                    total    = len(g.table.pairs)
                    dst      = self._table_pos(pair_idx, total, False)
                    card_str = str(card)
                    self._slide_table_to(total)
                    def on_land(cs=card_str, pi=pair_idx):
                        while len(self._vis_table) <= pi:
                            self._vis_table.append((None, None))
                        _, dfn = self._vis_table[pi]
                        self._vis_table[pi] = (cs, dfn)
                        self._vis_table_total = len(self._vis_table)
                        self._animating = False
                        # Player now defends the transferred attack
                        self._set(S_HUMAN_DEFEND, _t("game.transfer"))
                    self._fly_card(card_str, self._bot_hand_centre(), dst, on_done=on_land)
                    return

            defence = _ai_choose_defence(defender, attack_card, trump)

            if defence is None:
                pairs = list(self._vis_table)
                self._vis_table = []
                taken = g.table.all_cards()
                defender.hand.extend(taken)
                defender.sort_hand(trump)
                # Check if human attacker can pile on
                attacker = g.players[g.attacker_idx]
                can_pile = bool(validator.valid_attacks(attacker.hand, g.table))
                if g.attacker_idx == 0 and can_pile:
                    # Human can pile on — sweep cards to bot, then wait for human
                    def after_sweep():
                        self._animating = False
                        self._pending_defender_took = True
                        self._set(S_PILE_ON_TAKING, "")
                    self._sweep_table(pairs, to_player=False, on_all_done=after_sweep)
                else:
                    def_is_player = (g.defender_idx == 0)
                    g._advance_roles(defender_took=True)
                    def after():
                        self._animating = False
                        self._do_finish_round(defender_took=True)
                    self._sweep_table(pairs, to_player=def_is_player, on_all_done=after)
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

    def _queue_bot_pile_on_taking(self):
        """Bot (attacker) decides whether to add more cards while defender is taking."""
        g     = self.game
        trump = g.deck.trump
        attacker = g.players[g.attacker_idx]
        defender = g.players[g.defender_idx]

        def act():
            validator = MoveValidator(trump)
            card = _ai_choose_attack(attacker, g.table, trump) \
                   if validator.valid_attacks(attacker.hand, g.table) else None

            if card is None:
                self._end_pile_on_taking()
            else:
                pair_idx = len(g.table.pairs)
                attacker.remove_card(card)
                g.table.add_attack(card)
                src      = self._bot_hand_centre()
                total    = len(g.table.pairs)
                dst      = self._table_pos(pair_idx, total, False)
                card_str = str(card)
                self._slide_table_to(total)
                def on_land(cs=card_str, pi=pair_idx):
                    while len(self._vis_table) <= pi:
                        self._vis_table.append((None, None))
                    atk_cur, dfn_cur = self._vis_table[pi]
                    self._vis_table[pi] = (cs, dfn_cur)
                    self._vis_table_total = len(self._vis_table)
                    self._animating = False
                    # Bot done piling on — end taking
                    self._end_pile_on_taking()
                self._fly_card(card_str, src, dst, on_done=on_land)

        self._bot_timer  = _BOT_DELAY
        self._bot_action = act

    def _end_pile_on_taking(self):
        """Finalise the round where defender chose to take."""
        g = self.game
        self._pending_defender_took = False
        # Any NEW cards piled on after the defender clicked take must also go to them
        # (original pile was already added to hand at pickup time)
        defender = g.players[g.defender_idx]
        extra = g.table.all_cards()
        # Only add cards that aren't already in the defender's hand
        # (original pile was added at click time; extras are subsequent pile-ons)
        for c in extra:
            if c not in defender.hand:
                defender.hand.append(c)
        defender.sort_hand(g.deck.trump)
        pairs = list(self._vis_table)
        self._vis_table = []
        # Capture defender_idx BEFORE advancing roles
        def_is_player = (g.defender_idx == 0)
        g._advance_roles(defender_took=True)
        if pairs:
            def after():
                self._animating = False
                self._do_finish_round(defender_took=True)
            self._sweep_table(pairs, to_player=def_is_player, on_all_done=after)
        else:
            self._do_finish_round(defender_took=True)

    def _after_attack(self):
        g         = self.game
        trump     = g.deck.trump
        validator = MoveValidator(trump)
        taking    = self._pending_defender_took

        if g.table.first_undefended_index() is not None:
            if g.defender_idx == 0:
                self._set(S_HUMAN_DEFEND, "")
            else:
                self._set(S_BOT_THINKING, "")
                self._queue_bot_defence()
        else:
            if g.attacker_idx == 0:
                # Stay in taking state if defender already chose to take
                self._set(S_PILE_ON_TAKING if taking else S_PILE_ON, "")
            else:
                self._set(S_BOT_THINKING, "")
                if taking:
                    self._queue_bot_pile_on_taking()
                else:
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
        """Fly one draw-up card to its final sorted position, recurse until done."""
        if i >= len(queue):
            # All cards landed and already in sorted order — no sort jump needed
            self._animating = False
            self._start_round()
            return

        p_idx, card = queue[i]
        player      = self.game.players[p_idx]
        src         = self._deck_centre()
        trump       = self.game.deck.trump

        # Simulate the full final hand for this player after all queue cards land
        future_cards_for_player = [c for (pi, c) in queue[i:] if pi == p_idx]
        final_hand_sim = sorted(
            list(player.hand) + future_cards_for_player,
            key=lambda c: c.sort_key(trump)
        )
        total_final = len(final_hand_sim)
        sorted_idx  = final_hand_sim.index(card)

        if p_idx == 0:
            rect     = self._hand_rect(sorted_idx, total_final)
            dst      = (rect.x + CARD_W // 2, rect.y + CARD_H // 2)
            card_key = str(card)
        else:
            dst      = self._bot_card_centre(sorted_idx, total_final)
            card_key = "back"

        def on_land(p=player, c=card, t=trump, qi=i):
            # Record old total before inserting so spread animation knows where cards were
            old_total = len(p.hand)
            future = [cc for (pi, cc) in queue[qi:] if pi == p_idx]
            sim    = sorted(list(p.hand) + future, key=lambda x: x.sort_key(t))
            idx    = sim.index(c)
            p.hand.insert(idx, c)
            # Start spread: each existing card animates from old_total layout → new layout
            if p_idx == 0:
                new_total = len(p.hand)
                for existing_card in p.hand:
                    if existing_card is not c:
                        self._hand_spread[id(existing_card)] = [0.0, old_total]
            self._draw_fly_next(queue, qi + 1)

        self._fly_card(
            card_key, src, dst,
            duration=0.40,
            src_angle=random.uniform(-6, 6),
            dst_angle=0.0,
            on_done=on_land,
            sound="card_take",
            arc=0.14,
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
        g = self.game
        if self._state in (S_HUMAN_ATTACK, S_PILE_ON):
            if g.table.is_empty():
                return
            self._stat_passes += 1
            self._finish_round(defender_took=False)
        elif self._state == S_PILE_ON_TAKING:
            # Human attacker lets defender take without adding more
            self._end_pile_on_taking()

    def _on_click(self, pos):
        g         = self.game
        trump     = g.deck.trump
        validator = MoveValidator(trump)

        if self._state == S_ROUND_OVER:
            return

        if self._state in (S_HUMAN_ATTACK, S_PILE_ON, S_PILE_ON_TAKING):
            if not g.table.is_empty() and self._pass_rect().collidepoint(pos):
                if self._state == S_PILE_ON_TAKING:
                    self._end_pile_on_taking()
                else:
                    self._stat_passes += 1
                    self._finish_round(defender_took=False)
                return
            card = self._card_at_pos(pos)
            if card is None:
                return

            # Card limit: max 6 cards total on table.
            # During initial attack only, also cap at defender's hand size
            # (so they always have cards to beat with). During pile-on the
            # defender has already committed, so only the 6-card hard cap applies.
            defender    = g.players[g.defender_idx]
            if self._state == S_HUMAN_ATTACK and g.table.is_empty():
                max_attacks = min(6, len(defender.hand))
            else:
                max_attacks = 6
            if len(g.table.pairs) >= max_attacks:
                self._invalid_card = card
                self._invalid_tick = 40
                self._message = _t("game.too_many_cards")
                audio.play("card_reject")
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
            self._slide_table_to(total)
            def on_land(cs=card_str, pi=pair_idx):
                while len(self._vis_table) <= pi:
                    self._vis_table.append((None, None))
                _, dfn = self._vis_table[pi]
                self._vis_table[pi] = (cs, dfn)
                self._vis_table_total = len(self._vis_table)
                self._animating = False
                self._attack_commit_timer = _ATTACK_COMMIT_DELAY
            self._fly_card(card_str, src, dst, on_done=on_land)

        elif self._state == S_HUMAN_DEFEND:
            if self._pickup_rect().collidepoint(pos):
                taken = g.table.all_cards()
                idx_def  = g.table.first_undefended_index()
                had_valid = False
                if idx_def is not None:
                    atk_card = g.table.pairs[idx_def].attack
                    had_valid = bool(validator.valid_defences(g.players[0].hand, atk_card))
                self._stat_piles_taken  += 1
                self._stat_biggest_pile  = max(self._stat_biggest_pile, len(taken))
                self._ach_tracker.on_player_takes_pile(taken, trump, had_valid)
                # Give cards to defender but don't advance roles yet — check if attacker can pile on
                g.players[0].hand.extend(taken)
                g.players[0].sort_hand(trump)
                # Check if attacker (bot) has any pile-on cards.
                # Skip pile-on window if a transfer already happened this round —
                # the attacker already played their transfer card, no second bite.
                attacker = g.players[g.attacker_idx]
                can_pile = (not self._round_had_transfer and
                            bool(validator.valid_attacks(attacker.hand, g.table)))
                if g.attacker_idx != 0 and can_pile:
                    # Bot can pile on — enter taking state so bot gets a chance
                    self._set(S_PILE_ON_TAKING, "")
                    self._pending_defender_took = True
                    self._queue_bot_pile_on_taking()
                else:
                    g._advance_roles(defender_took=True)
                    self._finish_round(defender_took=True)
                return
            card = self._card_at_pos(pos)

            # Check if player clicked a transfer badge
            if self.transfer_mode:
                for crd, badge_r in self._transfer_badge_rects.items():
                    if badge_r.collidepoint(pos):
                        self._do_transfer(crd, validator, trump)
                        return

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

    def update(self, dt: float = 1/60):
        self.tick   += 1
        self._time  += dt

        # Hand spread animation — slide existing cards to make room for incoming card
        SPREAD_SPEED = 8.0   # progress units per second (0→1 in ~0.12s)
        done_keys = []
        for cid, state in self._hand_spread.items():
            state[0] = min(1.0, state[0] + dt * SPREAD_SPEED)
            if state[0] >= 1.0:
                done_keys.append(cid)
        for k in done_keys:
            del self._hand_spread[k]

        if getattr(self, "_shuffling", False) or self._trump_reveal_phase != 0:
            self._shuffle_tick += 1
        if self._invalid_tick > 0:
            self._invalid_tick -= dt * 60   # convert to seconds

        # Trump / role reveal animations
        self._update_trump_reveal()
        self._update_role_reveal()

        # Flying cards — pass real dt
        for fc in self._flying:
            fc.update(dt)
        self._flying = [fc for fc in self._flying if not fc.done]
        if not self._flying:
            self._animating = False

        if self._state == S_BOT_THINKING and self._bot_action and not self._animating:
            self._bot_timer -= dt * 60
            if self._bot_timer <= 0:
                fn = self._bot_action
                self._bot_action = None
                fn()

        if self._state == S_ROUND_OVER and not self._animating:
            self._round_timer -= dt * 60
            if self._round_timer <= 0:
                self._start_round()

        # Attack commit window
        if self._attack_commit_timer > 0 and not self._animating:
            self._attack_commit_timer -= dt * 60
            if self._attack_commit_timer <= 0:
                self._after_attack()

        if self._status_fade > 0:
            self._status_fade -= dt * 60
        elif self._status_alpha > 0:
            self._status_alpha = max(0, self._status_alpha - dt * 240)

        # Card hover — smooth lerp
        mouse = pygame.mouse.get_pos()
        hand  = self.game.players[0].hand
        speed = 1 - (0.85 ** (dt * 60))   # frame-rate independent lerp
        for i, card in enumerate(hand):
            rect   = self._hand_rect(i, len(hand))
            target = 20.0 if rect.collidepoint(mouse) else 0.0
            cur    = self._hover.get(id(card), 0.0)
            self._hover[id(card)] = cur + (target - cur) * speed

        # Cheat drip
        if self._cheat_queue:
            self._cheat_timer -= dt * 60
            if self._cheat_timer <= 0:
                ach = self._cheat_queue.pop(0)
                self._ach_tracker._stats.unlocked.add(ach.key)
                self._ach_toast.push(ach)
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
                fc["y"]   += fc["vy"] * dt * 60
                fc["x"]   += fc["vx"] * dt * 60
                fc["vy"]  += 0.4 * dt * 60
                fc["rot"] += fc["rot_v"] * dt * 60

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
        self._draw_table_zone(t, W, H)
        self._draw_zone_dividers(t, W, H)
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
        # Static base (fill + vignette) cached once
        if self._cached_bg is None:
            bg = pygame.Surface((W, H))
            bg.fill(BG)
            vig = pygame.Surface((W, H), pygame.SRCALPHA)
            for i in range(12):
                a = int(140 * (i / 12) ** 2)
                r = int(520 - i * 28)
                for corner in [(0, 0), (W, 0), (0, H), (W, H)]:
                    pygame.draw.circle(vig, (0, 0, 10, a), corner, r)
            bg.blit(vig, (0, 0))
            self._cached_bg = bg
        t.blit(self._cached_bg, (0, 0))

        # Animated diamond trellis — drifts slowly upward, colour breathes
        gx, gy  = 52, 36
        drift   = (self._time * 10) % gy
        phase   = self._time * 0.35
        col_line = (
            34 + int(10 * math.sin(phase)),
            12 + int(5  * math.sin(phase + 1.0)),
            58 + int(14 * math.sin(phase + 2.0)),
        )
        col_node = (
            48 + int(12 * math.sin(phase + 0.8)),
            16 + int(6  * math.sin(phase + 1.8)),
            75 + int(16 * math.sin(phase + 0.3)),
        )

        hx, hy = gx // 2, gy // 2
        cols = W // gx + 2
        rows = H // gy + 3

        for row in range(-1, rows + 1):
            ox = hx if (row % 2) else 0
            for col in range(cols):
                cx_ = col * gx + ox - hx
                cy_ = row * gy - int(drift)
                pts = [
                    (cx_,       cy_ - hy),
                    (cx_ + hx,  cy_),
                    (cx_,       cy_ + hy),
                    (cx_ - hx,  cy_),
                ]
                pygame.draw.polygon(t, col_line, pts, 1)
                pygame.draw.circle(t, col_node, (cx_, cy_), 1)

        # Faint centre play-zone brightening
        play_cy = H // 2
        play_h  = CARD_H + 60
        s = pygame.Surface((W, play_h), pygame.SRCALPHA)
        s.fill((255, 255, 255, 8))
        t.blit(s, (0, play_cy - play_h // 2))

    def _draw_table_zone(self, t, W, H):
        pass

    def _draw_zone_dividers(self, t, W, H):
        """Glowing separator lines + role ambient glow."""
        # Build static divider lines once
        if self._cached_dividers is None:
            bot_line_y    = 20 + CARD_H + 8
            player_line_y = H - CARD_H - 28
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            for line_y, col in [(bot_line_y, PURPLE), (player_line_y, NEON)]:
                # Fast gradient: draw a bright centre rect, fade with two dark wedges
                pygame.draw.rect(surf, (*col, 40), (0, line_y, W, 1))
                # Fade edges via alpha-blended rects on each side
                for side in [0, 1]:
                    fade = pygame.Surface((160, 1), pygame.SRCALPHA)
                    for px in range(160):
                        a = int(40 * (px / 160))
                        fade.set_at((px if side else 159 - px, 0), (*col, a))
                    surf.blit(fade, (0 if side else W - 160, line_y))
                # Centre node
                node_x = W // 2
                for r, a in [(16, 6), (9, 14), (4, 28)]:
                    gs = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(gs, (*col, a), (r, r), r)
                    surf.blit(gs, (node_x - r, line_y - r + 1))
            self._cached_dividers = surf
        t.blit(self._cached_dividers, (0, 0))

        # Subtle role indicator — tint the player zone divider line instead of a big glow
        if self._state in (S_HUMAN_ATTACK, S_PILE_ON, S_PILE_ON_TAKING):
            role_col = (255, 140, 40)
        elif self._state == S_HUMAN_DEFEND:
            role_col = (60, 170, 255)
        else:
            return
        pulse    = 0.6 + 0.4 * math.sin(self._time * 2.2)
        line_y   = H - CARD_H - 28
        line_a   = int(55 * pulse)
        # Draw a slim tinted rect over the player divider line
        pygame.draw.rect(t, role_col, (W // 2 - 120, line_y, 240, 1))
        # Two small accent dots flanking centre
        for dx in (-60, 60):
            pygame.draw.circle(t, role_col, (W // 2 + dx, line_y), 2)



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

        # Card shadows — use simple offset rect, no SRCALPHA
        for i in range(count):
            pygame.draw.rect(t, (0, 0, 0),
                             (sx + i * (CARD_W + gap) + 2, y + 3, CARD_W, CARD_H),
                             border_radius=6)

        for i in range(count):
            t.blit(self._get_back_surf((CARD_W, CARD_H)), (sx + i * (CARD_W + gap), y))

        # Bot badge — draw directly onto screen (opaque, fast)
        av_cx, av_cy = W // 2, y + CARD_H + 44
        f   = get_fonts()["small"]
        label_str = _t("game.status_bot")
        cnt_str   = str(count)
        lbl_s = f.render(label_str, False, TEXT_DIM)
        cnt_s = f.render(cnt_str,   False, TEXT_MAIN)
        pad   = 14
        pill_w = lbl_s.get_width() + cnt_s.get_width() + pad * 3 + 6
        pill_h = 26
        pill_r = pygame.Rect(av_cx - pill_w // 2, av_cy - pill_h // 2, pill_w, pill_h)
        pygame.draw.rect(t, (30, 15, 55), pill_r, border_radius=pill_h // 2)
        pygame.draw.rect(t, PURPLE,       pill_r, width=1, border_radius=pill_h // 2)
        bx = pill_r.x
        t.blit(lbl_s, (bx + pad, pill_r.y + pill_h // 2 - lbl_s.get_height() // 2))
        sep_x = bx + pad + lbl_s.get_width() + 4
        pygame.draw.line(t, PURPLE_DIM, (sep_x, pill_r.y + 6), (sep_x, pill_r.bottom - 6), 1)
        t.blit(cnt_s, (sep_x + 6, pill_r.y + pill_h // 2 - cnt_s.get_height() // 2))

    def _draw_deck_and_trump(self, t, W, H):
        remaining = self.game.deck.remaining()
        x, y      = 110, H // 2 - CARD_H // 2

        if getattr(self, "_trump_tucked", False) and remaining > 0 \
                and self._trump_reveal_phase == 0:
            trump_card = self.game.deck.peek_bottom()
            trump_surf = self._scaled(self._card_surf_by_str(str(trump_card)))
            rotated    = pygame.transform.rotate(trump_surf, 90)
            tx, ty     = self._trump_tucked_pos()
            t.blit(rotated, (tx - rotated.get_width() // 2,
                              ty - rotated.get_height() // 2))

        # Shadow under deck — simple dark rect, no SRCALPHA
        if remaining > 0:
            pygame.draw.rect(t, (0, 0, 0), (x + 2, y + 4, CARD_W, CARD_H), border_radius=6)

        for i in range(min(4, remaining)):
            t.blit(self._get_back_surf((CARD_W, CARD_H)), (x + i * 2, y - i * 2))

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
                t.blit(surf,
                    (cx - surf.get_width() // 2 + ox, cy - surf.get_height() // 2 + oy))

        # Card count badge — opaque
        f       = get_fonts()["small"]
        cnt_str = str(remaining)
        cnt_s   = f.render(cnt_str, False, TEXT_DIM if remaining > 0 else (80, 50, 100))
        pad     = 8
        badge_w = cnt_s.get_width() + pad * 2
        badge_h = cnt_s.get_height() + 6
        bx = x + CARD_W // 2 - badge_w // 2
        by = y + CARD_H + 6
        pygame.draw.rect(t, (20, 10, 38), (bx, by, badge_w, badge_h), border_radius=badge_h // 2)
        pygame.draw.rect(t, PURPLE_DIM,   (bx, by, badge_w, badge_h), width=1, border_radius=badge_h // 2)
        t.blit(cnt_s, (bx + pad, by + badge_h // 2 - cnt_s.get_height() // 2))

    def _draw_table_cards(self, t, W, H):
        pairs = self._vis_table
        if not pairs:
            return
        # Use the target total during slide animations so layout is already at final positions
        count  = self._vis_table_total if self._vis_table_total > len(pairs) else len(pairs)
        gap    = CARD_W + 20
        offset = 16
        sx     = W // 2 - count * gap // 2

        # Draw all shadows first — simple offset rects, no SRCALPHA
        for i, (atk, dfn) in enumerate(pairs):
            x = sx + i * gap
            y = H // 2 - CARD_H // 2
            if atk and (i, False) not in self._sliding_slots:
                pygame.draw.rect(t, (0, 0, 0), (x + 2, y + 4, CARD_W, CARD_H), border_radius=6)
            if dfn and (i, True) not in self._sliding_slots:
                pygame.draw.rect(t, (0, 0, 0), (x + offset + 2, y - offset + 4, CARD_W, CARD_H), border_radius=6)

        for i, (atk, dfn) in enumerate(pairs):
            x = sx + i * gap
            y = H // 2 - CARD_H // 2
            if atk and (i, False) not in self._sliding_slots:
                self._draw_card_face(t, atk, x, y)
            if dfn and (i, True) not in self._sliding_slots:
                self._draw_card_face(t, dfn, x + offset, y - offset)

    def _draw_status_bar(self, t, W, H):
        cx = W // 2
        f  = get_fonts()["small"]

        if self._status_alpha > 0 and self._status_label:
            label = self._status_label
            if self._state == S_BOT_THINKING:
                label = "THINKING" + "." * (int(self._time * 4) % 4)

            lbl_s  = f.render(label, False, NEON_GLOW)
            pad    = 14
            pill_w = lbl_s.get_width() + pad * 2
            pill_h = lbl_s.get_height() + 10
            av_y   = 20 + CARD_H + 36
            pill_y = av_y + 52
            pill_x = cx - pill_w // 2
            alpha  = int(self._status_alpha)

            # Draw pill directly onto screen — opaque bg, then set_alpha via subsurface trick
            # Use a per-frame surface only the size of the pill (much cheaper than full-screen)
            pill = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
            pygame.draw.rect(pill, (30, 10, 50, alpha), pill.get_rect(),
                             border_radius=pill_h // 2)
            pygame.draw.rect(pill, (*NEON, min(120, alpha)), pill.get_rect(),
                             width=1, border_radius=pill_h // 2)
            pill.blit(lbl_s, (pad, pill_h // 2 - lbl_s.get_height() // 2))
            t.blit(pill, (pill_x, pill_y))

        # Attack commit countdown arc
        if self._attack_commit_timer > 0 and not self._animating:
            ratio   = self._attack_commit_timer / _ATTACK_COMMIT_DELAY
            r       = 18
            arc_y   = H // 2 - CARD_H // 2 - 48
            rect    = pygame.Rect(cx - r, arc_y - r, r * 2, r * 2)
            pygame.draw.circle(t, PURPLE_DIM, (cx, arc_y), r, width=3)
            g_val   = int(200 * ratio)
            r_val   = int(200 * (1 - ratio))
            col     = (r_val, g_val, 60)
            end_ang = -90 + (1 - ratio) * 360
            steps   = max(2, int(ratio * 32))
            pts     = []
            for s in range(steps + 1):
                a = math.radians(-90 + ratio * 360 * s / steps)
                pts.append((cx + int(r * math.cos(a)), arc_y + int(r * math.sin(a))))
            if len(pts) >= 2:
                pygame.draw.lines(t, col, False, pts, 3)
            secs = math.ceil(self._attack_commit_timer / 60)
            lbl  = f.render(str(secs), False, col)
            t.blit(lbl, (cx - lbl.get_width() // 2, arc_y - lbl.get_height() // 2))

        if self._message:
            msg_s  = f.render(self._message, False, TEXT_DIM)
            pad    = 10
            pill_w = msg_s.get_width() + pad * 2
            pill_h = msg_s.get_height() + 8
            pill   = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
            pygame.draw.rect(pill, (20, 10, 35, 180), pill.get_rect(),
                             border_radius=4)
            pygame.draw.rect(pill, (*PURPLE, 100), pill.get_rect(),
                             width=1, border_radius=4)
            pill.blit(msg_s, (pad, pill_h // 2 - msg_s.get_height() // 2))
            t.blit(pill, (cx - pill_w // 2, H // 2 + CARD_H // 2 + 12))

    def _draw_player_hand(self, t, W, H, mouse):
        if self._sorting_hand:
            return
        hand       = self.game.players[0].hand
        actionable = self._state in (S_HUMAN_ATTACK, S_HUMAN_DEFEND, S_PILE_ON, S_PILE_ON_TAKING)

        # Compute transfer-eligible cards when defending in transfer mode
        transfer_cards = set()
        if self.transfer_mode and self._state == S_HUMAN_DEFEND:
            validator = MoveValidator(self.game.deck.trump)
            new_def_hand = self.game.players[self.game.attacker_idx].hand
            transfer_cards = {c for c in hand
                              if validator.can_transfer(c, self.game.table,
                                                        new_defender_hand=new_def_hand)}

        self._transfer_badge_rects = {}

        # Draw shadows first — simple offset rects, no SRCALPHA
        for i, card in enumerate(hand):
            rect = self._hand_rect_spread(i, len(hand), card)
            lift = int(self._hover.get(id(card), 0.0)) if actionable else 0
            pygame.draw.rect(t, (0, 0, 0),
                             (rect.x + 2, rect.y - lift + 4, CARD_W, CARD_H), border_radius=6)

        f_small   = get_fonts()["small"]
        badge_lbl = f_small.render(_t("game.transfer"), False, (255, 200, 60))
        badge_pad = 8
        badge_w   = badge_lbl.get_width() + badge_pad * 2
        badge_h   = badge_lbl.get_height() + 6

        # Pre-build shared surfaces once (cached on self)
        if not hasattr(self, '_hover_glow_surf'):
            gs = pygame.Surface((CARD_W + 16, CARD_H + 16), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*NEON_GLOW, 45), gs.get_rect(), border_radius=10)
            self._hover_glow_surf = gs
        if not hasattr(self, '_invalid_overlay'):
            ov = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            ov.fill((255, 80, 80, 60))
            self._invalid_overlay = ov
        if not hasattr(self, '_hover_overlay'):
            ov = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            ov.fill((*NEON_GLOW, 40))
            self._hover_overlay = ov

        pulse = 0.5 + 0.5 * math.sin(self._time * 5.0)   # smooth, time-based

        for i, card in enumerate(hand):
            rect    = self._hand_rect_spread(i, len(hand), card)
            lift    = int(self._hover.get(id(card), 0.0)) if actionable else 0
            invalid = card == self._invalid_card and self._invalid_tick > 0
            hover   = lift > 2 and actionable
            surf    = self._get_card_surf(card, (CARD_W, CARD_H))
            if hover or invalid:
                surf = surf.copy()
                surf.blit(self._invalid_overlay if invalid else self._hover_overlay, (0, 0))
                pygame.draw.rect(surf, (220, 60, 60) if invalid else NEON_GLOW,
                                 (0, 0, CARD_W, CARD_H), width=2)
            t.blit(surf, (rect.x, rect.y - lift))

            # Transfer badge
            if card in transfer_cards:
                base_bx = rect.centerx - badge_w // 2
                base_by = rect.y - lift - badge_h - 6
                base_r  = pygame.Rect(base_bx, base_by, badge_w, badge_h)
                hovered = base_r.inflate(16, 12).collidepoint(mouse)

                scale = 1.15 if hovered else 1.0
                sw    = int(badge_w * scale)
                sh_h  = int(badge_h * scale)
                bx    = rect.centerx - sw // 2
                by    = base_by - (sh_h - badge_h) // 2
                self._transfer_badge_rects[card] = pygame.Rect(bx, by, sw, sh_h)

                bc  = (255, 220, 60) if hovered else (
                    int(180 + 60 * pulse), int(140 + 40 * pulse), 40)

                # Glow (small surface, cheap)
                gs = pygame.Surface((sw + 12, sh_h + 12), pygame.SRCALPHA)
                pygame.draw.rect(gs, (*bc, 90 if hovered else int(50 + 30 * pulse)),
                                 gs.get_rect(), border_radius=sh_h // 2 + 4)
                t.blit(gs, (bx - 6, by - 6))

                # Badge pill
                bs = pygame.Surface((sw, sh_h), pygame.SRCALPHA)
                pygame.draw.rect(bs, (80, 55, 5, 240) if hovered else (60, 38, 5, 220),
                                 bs.get_rect(), border_radius=sh_h // 2)
                pygame.draw.rect(bs, (*bc, 255 if hovered else 220),
                                 bs.get_rect(), width=3 if hovered else 2,
                                 border_radius=sh_h // 2)
                lbl = f_small.render(_t("game.transfer"), False, bc)
                bs.blit(lbl, (sw // 2 - lbl.get_width() // 2,
                              sh_h // 2 - lbl.get_height() // 2))
                t.blit(bs, (bx, by))

                ax, ay = rect.centerx, by + sh_h
                pygame.draw.line(t, bc, (ax, ay + 1), (ax, ay + 5), 2)
                pygame.draw.polygon(t, bc, [(ax - 4, ay + 5), (ax + 4, ay + 5), (ax, ay + 9)])

    def _draw_action_buttons(self, t, W, H, mouse):
        f = get_fonts()["small"]

        def _draw_btn(r, label, base_col, border_col, hov_col):
            hov  = r.collidepoint(mouse)
            fill = hov_col if hov else base_col
            # Shadow — draw as semi-transparent rect offset (no SRCALPHA surface needed)
            sr = r.move(2, 3)
            pygame.draw.rect(t, (0, 0, 0), sr, border_radius=8)
            # Button body
            pygame.draw.rect(t, fill, r, border_radius=8)
            pygame.draw.rect(t, border_col, r, width=2 if hov else 1, border_radius=8)
            # Hover glow — thin border rings (no surface needed)
            if hov:
                pulse_a = int(30 + 20 * math.sin(self._time * 6.0))
                er = r.inflate(6, 6)
                pygame.draw.rect(t, (*border_col[:3], pulse_a) if len(border_col) == 3
                                 else (*border_col, pulse_a),
                                 er, width=2, border_radius=10)
            lbl = f.render(label, False, TEXT_MAIN)
            t.blit(lbl, (r.centerx - lbl.get_width() // 2,
                          r.centery - lbl.get_height() // 2))

        if self._state == S_HUMAN_DEFEND:
            r = self._pickup_rect()
            _draw_btn(r, _t("game.take_cards"),
                      base_col=(90, 18, 42),
                      border_col=NEON,
                      hov_col=NEON_DARK)

        if self._state in (S_HUMAN_ATTACK, S_PILE_ON) and not self.game.table.is_empty():
            r = self._pass_rect()
            _draw_btn(r, _t("game.pass"),
                      base_col=(22, 18, 60),
                      border_col=PURPLE,
                      hov_col=(50, 40, 110))

        if self._state == S_PILE_ON_TAKING:
            r = self._pass_rect()
            # If human is the defender who chose to take → "LET TAKE"
            # If bot is the defender who took → "PASS" (human is just piling on)
            lbl = _t("game.let_take") if self.game.defender_idx == 0 else _t("game.pass")
            _draw_btn(r, lbl,
                      base_col=(22, 18, 60),
                      border_col=PURPLE,
                      hov_col=(50, 40, 110))

    def _draw_trump_box(self, t, W, H):
        r = pygame.Rect(20, 20, 150, 80)

        pygame.draw.rect(t, (0, 0, 0), r.move(3, 4), border_radius=10)
        pygame.draw.rect(t, (18, 10, 35), r, border_radius=10)
        pygame.draw.rect(t, PURPLE_DIM, r, border_radius=10)
        pygame.draw.rect(t, PURPLE, r, width=1, border_radius=10)

        _all_suits = ['♥', '♦', '♠', '♣']
        from .locale import get_lang as _gl
        _suit_names = {
            "en": {'♥': 'HEARTS', '♦': 'DIAMONDS', '♠': 'SPADES', '♣': 'CLUBS'},
            "ru": {'♥': 'ЧЕРВЫ',  '♦': 'БУБНЫ',    '♠': 'ПИКИ',   '♣': 'ТРЕФЫ'},
            "ro": {'♥': 'INIMI',  '♦': 'ROMBURI',  '♠': 'PICĂ',   '♣': 'TREFLĂ'},
        }
        name_map = _suit_names.get(_gl(), _suit_names["en"])
        real_sym = str(self.game.deck.trump)

        phase = self._trump_reveal_phase
        if getattr(self, "_shuffling", False) and phase == 0:
            suit_sym = _all_suits[(self._shuffle_tick // 4) % 4]
        elif phase in (1, 2):
            suit_sym = _all_suits[(self._reveal_tick // 4) % 4]
        elif phase == 3:
            progress = self._reveal_tick / self._REVEAL_FLY_OUT
            suit_sym = _all_suits[(self._reveal_tick // 6) % 4] if progress < 0.6 else real_sym
        else:
            suit_sym = real_sym

        is_red   = suit_sym in ('♥', '♦')
        suit_col = (220, 60, 80) if is_red else (220, 225, 235)

        # "TRUMP" label
        f = get_fonts()["small"]
        label = f.render(_t("game.trump"), False, TEXT_DIM)
        t.blit(label, (r.x + 12, r.y + 10))

        # Draw suit glyph as vector polygon — reliable across all fonts
        gx = r.x + 20
        gy = r.y + 44
        sz = 18   # half-size of glyph

        def _draw_heart(cx, cy, s, col):
            # Two circles + triangle
            pygame.draw.circle(t, col, (cx - s//2, cy - s//4), s//2)
            pygame.draw.circle(t, col, (cx + s//2, cy - s//4), s//2)
            pygame.draw.polygon(t, col, [
                (cx - s, cy - s//4),
                (cx + s, cy - s//4),
                (cx, cy + s),
            ])

        def _draw_diamond(cx, cy, s, col):
            pygame.draw.polygon(t, col, [
                (cx,     cy - s),
                (cx + s, cy),
                (cx,     cy + s),
                (cx - s, cy),
            ])

        def _draw_spade(cx, cy, s, col):
            # Inverted heart + stalk
            pygame.draw.circle(t, col, (cx - s//2, cy + s//4), s//2)
            pygame.draw.circle(t, col, (cx + s//2, cy + s//4), s//2)
            pygame.draw.polygon(t, col, [
                (cx - s, cy + s//4),
                (cx + s, cy + s//4),
                (cx,     cy - s),
            ])
            # stalk
            pygame.draw.rect(t, col, (cx - s//3, cy + s//2, s*2//3, s//2))
            pygame.draw.rect(t, col, (cx - s//2, cy + s, s, s//4))

        def _draw_club(cx, cy, s, col):
            # Three circles + stalk
            pygame.draw.circle(t, col, (cx,        cy), int(s * 0.55))
            pygame.draw.circle(t, col, (cx - s//2, cy + s//4), int(s * 0.45))
            pygame.draw.circle(t, col, (cx + s//2, cy + s//4), int(s * 0.45))
            pygame.draw.rect(t, col, (cx - s//3, cy + s//2, s*2//3, s//2))
            pygame.draw.rect(t, col, (cx - s//2, cy + s, s, s//4))

        draw_fn = {'♥': _draw_heart, '♦': _draw_diamond,
                   '♠': _draw_spade, '♣': _draw_club}
        draw_fn[suit_sym](gx, gy, sz, suit_col)

        # Suit name text
        name = f.render(name_map.get(suit_sym, suit_sym), False, suit_col)
        t.blit(name, (gx + sz + 14, gy - name.get_height() // 2))

        # Thin accent line at bottom
        pygame.draw.line(t, suit_col,
                         (r.x + 10, r.bottom - 8),
                         (r.right - 10, r.bottom - 8), 1)

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
        # Try direct lookup first 
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
        return pygame.Rect(WIDTH - 200, HEIGHT // 2 + 130, 140, 40)

    def _do_transfer(self, card, validator, trump):
        """Player transfers the attack to the bot by playing a same-rank card."""
        g = self.game
        hand_idx = g.players[0].hand.index(card)
        src_rect = self._hand_rect(hand_idx, len(g.players[0].hand))
        pair_idx = len(g.table.pairs)
        g.players[0].remove_card(card)
        g.table.add_attack(card)
        g.players[0].sort_hand(trump)
        # Swap roles: original attacker becomes defender
        g.attacker_idx, g.defender_idx = g.defender_idx, g.attacker_idx
        self._round_had_transfer = True
        total    = len(g.table.pairs)
        dst      = self._table_pos(pair_idx, total, False)
        src      = (src_rect.centerx, src_rect.centery)
        card_str = str(card)
        if card.is_trump(trump):
            self._stat_trumps_played += 1
        self._slide_table_to(total)
        def on_land(cs=card_str, pi=pair_idx):
            while len(self._vis_table) <= pi:
                self._vis_table.append((None, None))
            _, dfn = self._vis_table[pi]
            self._vis_table[pi] = (cs, dfn)
            self._vis_table_total = len(self._vis_table)
            self._animating = False
            # Now bot must defend the transferred attack
            self._set(S_BOT_THINKING, _t("game.transfer"))
            self._queue_bot_defence()
        self._fly_card(card_str, src, dst, on_done=on_land)