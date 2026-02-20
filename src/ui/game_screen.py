from __future__ import annotations

import math
import random
import pygame
from ..core.game import _ai_choose_attack, _ai_choose_defence, _ai_should_stop_attacking
from ..core.move_validator import MoveValidator
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM, GOLD,
    CARD_BG, CARD_BACK, CARD_BORDER, CARD_RED, CARD_BLACK,
    CARD_W, CARD_H,
)

_BOT_DELAY    = 90
_ROUND_DELAY  = 90
_ATTACK_COMMIT_DELAY = 180   # ~3 seconds at 60fps — window to add more attack cards

S_HUMAN_ATTACK = "human_attack"
S_HUMAN_DEFEND = "human_defend"
S_PILE_ON      = "pile_on"
S_BOT_THINKING = "bot_thinking"
S_ROUND_OVER   = "round_over"
S_GAME_OVER    = "game_over"

S_DEALING      = "dealing"
S_DRAWING      = "drawing"   # draw-up animation in progress

_STATUS = {
    S_DEALING:      "DEAL",
    S_DRAWING:      "DEAL",
    S_HUMAN_ATTACK: "ATTACK",
    S_HUMAN_DEFEND: "DEFEND",
    S_PILE_ON:      "PILE ON",
    S_BOT_THINKING: "BOT",
    S_ROUND_OVER:   "...",
    S_GAME_OVER:    "GAME OVER",
}


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

        # --- intro shuffle+deal animation state ---
        self._shuffling    = False
        self._shuffle_tick = 0
        self._deal_queue   = []
        self._deal_i       = 0

        # If the game was started with setup_no_deal(), hands are empty and we animate dealing.
        if all(len(p.hand) == 0 for p in self.game.players):
            self._begin_initial_deal()
        else:
            self._start_round()

    # ── position helpers ─────────────────────────────────────────────────────

    def _hand_rect(self, idx, total):
        gap     = 10
        total_w = total * CARD_W + (total - 1) * gap
        sx      = WIDTH // 2 - total_w // 2
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

        # lock input via _animating and show status
        self._set(S_DEALING, "")
        self._animating    = True
        self._shuffling    = True
        self._shuffle_tick = 0

        # Deal 6 cards each, in 3 rounds of 2 (same pattern as typical setup)
        self._deal_queue = []
        players = list(range(len(g.players)))
        for _ in range(3):
            for p_idx in players:
                for _ in range(2):
                    if g.deck.remaining() > 0:
                        self._deal_queue.append((p_idx, g.deck.draw()))

        self._deal_i = 0
        self._deal_fly_next()

    def _deal_fly_next(self):
        g = self.game

        if self._deal_i >= len(self._deal_queue):
            # finish up and begin the actual round
            for p in g.players:
                p.sort_hand(g.deck.trump)
            self._animating = False
            self._shuffling = False
            self._start_round()
            return

        p_idx, card = self._deal_queue[self._deal_i]
        player      = g.players[p_idx]

        src = self._deck_centre()

        if p_idx == 0:
            # human hand landing slot (based on where it will be after append)
            slot = len(player.hand)
            total_after = slot + 1
            rect = self._hand_rect(slot, total_after)
            dst  = (rect.x + CARD_W // 2, rect.y + CARD_H // 2)
        else:
            # bot hand landing slot (based on your draw layout)
            slot = len(player.hand)
            total_after = slot + 1
            dst  = self._bot_card_centre(slot, total_after)

        def on_land(p=player, c=card):
            p.hand.append(c)
            self._deal_i += 1
            self._deal_fly_next()

        # fly card BACK during the deal (looks like dealing)
        self._fly_card(
            "back",
            src,
            dst,
            duration=16,
            src_angle=random.uniform(-12, 12),
            dst_angle=random.uniform(-6, 6),
            on_done=on_land
        )

    # ── animation helpers ─────────────────────────────────────────────────────

    def _scaled(self, surf):
        return pygame.transform.scale(surf, (CARD_W, CARD_H))

    def _fly_card(self, card_str, src, dst, duration=22,
                  src_angle=0.0, dst_angle=0.0, on_done=None):
        surf = self._scaled(self._card_surf_by_str(card_str))
        self._flying.append(FlyingCard(surf, src, dst, duration,
                                        src_angle, dst_angle, on_done))
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
                on_all_done()

        for i, (atk, dfn) in enumerate(pairs):
            for card_str, is_dfn in [(atk, False)] + ([(dfn, True)] if dfn else []):
                src   = self._table_pos(i, count, is_dfn)
                dst   = self._discard_pos()
                angle = random.uniform(-35, 35)
                surf  = self._scaled(self._card_surf_by_str(card_str))
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
        if g.attacker_idx == 0:
            self._set(S_HUMAN_ATTACK, "")
        else:
            self._set(S_BOT_THINKING, "")
            self._queue_bot_attack(first=True)

    def _set(self, state, msg=""):
        self._state   = state
        self._message = msg
        label = _STATUS.get(state, "")
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
        g = self.game
        if not defender_took:
            g._advance_roles(defender_took=False)
        loser = g._check_game_over()
        if loser is not None:
            name = "You are" if loser == 0 else f"{g.players[loser].name} is"
            self._set(S_GAME_OVER, f"{name} the DURAK!")
            return
        # Build draw-up queue: attacker first, then others, then defender
        order = (
            [g.attacker_idx]
            + [i for i in range(len(g.players))
               if i not in (g.attacker_idx, g.defender_idx)]
            + [g.defender_idx]
        )
        draw_queue = []
        for idx in order:
            p = g.players[idx]
            already_queued = sum(1 for qi, _ in draw_queue if qi == idx)
            while (len(p.hand) + already_queued) < 6 and g.deck.remaining() > 0:
                draw_queue.append((idx, g.deck.draw()))
                already_queued += 1
        if draw_queue:
            self._state     = S_DRAWING
            self._animating = True
            self._draw_fly_next(draw_queue, 0)
        else:
            self._start_round()

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
        )

    # ── events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "back"
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if not self._animating:
                    self._on_confirm()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._animating and self._state not in (S_DEALING, S_DRAWING):
                self._on_click(event.pos)
        return None

    def _on_confirm(self):
        if self._state in (S_HUMAN_ATTACK, S_PILE_ON):
            self._finish_round(defender_took=False)

    def _on_click(self, pos):
        g         = self.game
        trump     = g.deck.trump
        validator = MoveValidator(trump)

        if self._state == S_ROUND_OVER:
            return

        if self._state in (S_HUMAN_ATTACK, S_PILE_ON):
            if not g.table.is_empty() and self._pass_rect().collidepoint(pos):
                self._finish_round(defender_took=False)
                return
            card = self._card_at_pos(pos)
            if card is None:
                return
            if not g.table.is_empty() and not validator.can_attack(card, g.table):
                self._invalid_card = card
                self._invalid_tick = 40
                self._message      = f"{card} — rank not on table"
                return
            hand_idx = g.players[0].hand.index(card)
            src_rect = self._hand_rect(hand_idx, len(g.players[0].hand))
            pair_idx = len(g.table.pairs)
            g.players[0].remove_card(card)
            g.table.add_attack(card)
            g.players[0].sort_hand(trump)
            total    = len(g.table.pairs)
            dst      = self._table_pos(pair_idx, total, False)
            src      = (src_rect.centerx, src_rect.centery)
            card_str = str(card)
            def on_land(cs=card_str, pi=pair_idx):
                while len(self._vis_table) <= pi:
                    self._vis_table.append((None, None))
                _, dfn = self._vis_table[pi]
                self._vis_table[pi] = (cs, dfn)
                self._animating = False
                # Start/reset the commit window — player can still add more cards
                self._attack_commit_timer = _ATTACK_COMMIT_DELAY
            self._fly_card(card_str, src, dst, on_done=on_land)

        elif self._state == S_HUMAN_DEFEND:
            if self._pickup_rect().collidepoint(pos):
                taken = g.table.all_cards()
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
                self._message      = f"{card} can't beat {atk}"
                return
            hand_idx = g.players[0].hand.index(card)
            src_rect = self._hand_rect(hand_idx, len(g.players[0].hand))
            g.players[0].remove_card(card)
            g.table.add_defence(idx, card)
            g.players[0].sort_hand(trump)
            total    = len(g.table.pairs)
            dst      = self._table_pos(idx, total, True)
            src      = (src_rect.centerx, src_rect.centery)
            card_str = str(card)
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
        if getattr(self, "_shuffling", False):
            self._shuffle_tick += 1
        if self._invalid_tick > 0:
            self._invalid_tick -= 1

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

    # ── draw ──────────────────────────────────────────────────────────────────

    def draw(self, surface=None):
        t     = surface or self.screen
        W, H  = t.get_width(), t.get_height()
        mouse = pygame.mouse.get_pos()

        t.fill(BG)
        self._draw_bg_grid(t, W, H)
        self._draw_discards(t)
        self._draw_bot_hand(t, W, H)
        self._draw_deck_and_trump(t, W, H)
        self._draw_table_cards(t, W, H)
        self._draw_status_bar(t, W, H)
        self._draw_player_hand(t, W, H, mouse)
        self._draw_action_buttons(t, W, H, mouse)
        self._draw_trump_box(t, W, H)
        self._draw_pause_btn(t, W, H, mouse)

        for fc in self._flying:
            fc.draw(t)

        if self._state == S_GAME_OVER:
            self._draw_game_over(t, W, H)

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
        gap     = 6
        total_w = count * CARD_W + (count - 1) * gap
        sx      = W // 2 - total_w // 2
        y       = 20
        for i in range(count):
            t.blit(self._get_back_surf((CARD_W, CARD_H)), (sx + i * (CARD_W + gap), y))

        av_cx, av_cy = W // 2, y + CARD_H + 36
        av_r         = 28
        pygame.draw.circle(t, PURPLE_DIM, (av_cx, av_cy), av_r)
        pygame.draw.circle(t, PURPLE,     (av_cx, av_cy), av_r, width=2)
        pygame.draw.circle(t, TEXT_DIM,   (av_cx, av_cy - 8), 10)
        pygame.draw.ellipse(t, TEXT_DIM,
            pygame.Rect(av_cx - 14, av_cy + 4, 28, 16))
        f   = self.fonts["small"]
        cnt = f.render(str(count), False, TEXT_DIM)
        t.blit(cnt, (av_cx - cnt.get_width() // 2, av_cy + av_r + 6))

    def _draw_deck_and_trump(self, t, W, H):
        remaining = self.game.deck.remaining()
        x, y      = 110, H // 2 - CARD_H // 2
        for i in range(min(4, remaining)):
            t.blit(self._get_back_surf((CARD_W, CARD_H)), (x + i * 2, y - i * 2))

        # shuffle flourish (only during intro deal)
        if getattr(self, "_shuffling", False) and remaining > 0:
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

        f   = self.fonts["small"]
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
        f  = self.fonts["small"]

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
        f = self.fonts["small"]

        if self._state == S_HUMAN_DEFEND:
            r   = self._pickup_rect()
            col = NEON_DARK if r.collidepoint(mouse) else (80, 20, 40)
            pygame.draw.rect(t, col, r, border_radius=6)
            pygame.draw.rect(t, NEON, r, width=1, border_radius=6)
            lbl = f.render("TAKE CARDS", False, TEXT_MAIN)
            t.blit(lbl, (r.centerx - lbl.get_width() // 2,
                          r.centery - lbl.get_height() // 2))

        if self._state in (S_HUMAN_ATTACK, S_PILE_ON) and not self.game.table.is_empty():
            r   = self._pass_rect()
            col = (50, 50, 120) if r.collidepoint(mouse) else (20, 20, 55)
            pygame.draw.rect(t, col, r, border_radius=6)
            pygame.draw.rect(t, PURPLE, r, width=1, border_radius=6)
            lbl = f.render("PASS", False, TEXT_MAIN)
            t.blit(lbl, (r.centerx - lbl.get_width() // 2,
                          r.centery - lbl.get_height() // 2))

    def _draw_trump_box(self, t, W, H):
        r = pygame.Rect(20, 20, 150, 70)
        pygame.draw.rect(t, PURPLE_DIM, r, border_radius=8)
        pygame.draw.rect(t, PURPLE,     r, width=1, border_radius=8)
        trump    = self.game.deck.trump
        suit_sym = str(trump)
        is_red   = suit_sym in ('♥', '♦')
        suit_col = (220, 60, 80) if is_red else TEXT_MAIN
        f        = self.fonts["small"]
        f_big    = self.fonts.get("body", f)
        label    = f.render("TRUMP", False, TEXT_DIM)
        t.blit(label, (r.x + 10, r.y + 8))
        sym     = f_big.render(suit_sym, False, suit_col)
        target_h = 36
        scale    = target_h / max(sym.get_height(), 1)
        sym_big  = pygame.transform.scale(sym,
            (max(1, int(sym.get_width() * scale)), target_h))
        t.blit(sym_big, (r.x + 10, r.y + 26))
        name_map = {'♥': 'HEARTS', '♦': 'DIAMONDS', '♠': 'SPADES', '♣': 'CLUBS'}
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

    def _draw_game_over(self, t, W, H):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        t.blit(ov, (0, 0))
        lbl = self.fonts["title"].render(self._message, False, NEON_GLOW)
        t.blit(lbl, (W // 2 - lbl.get_width() // 2, H // 2 - 30))
        sub = self.fonts["small"].render("ESC to return", False, TEXT_DIM)
        t.blit(sub, (W // 2 - sub.get_width() // 2, H // 2 + 20))

    # ── card image loading ────────────────────────────────────────────────────

    def _load_card_images(self):
        import os
        card_dir = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
        images   = {}
        rank_map = {'A':'ace','2':'2','3':'3','4':'4','5':'5','6':'6',
                    '7':'7','8':'8','9':'9','10':'10','J':'jack','Q':'queen','K':'king'}
        suit_map = {'♥':'hearts','♦':'diamonds','♠':'spades','♣':'clubs'}
        try:
            for suit_sym, suit_name in suit_map.items():
                for rank_sym, rank_name in rank_map.items():
                    key  = f'{rank_sym}{suit_sym}'
                    path = os.path.join(card_dir, f'{rank_name}_of_{suit_name}.png')
                    images[key] = pygame.image.load(path).convert_alpha()
            images['back'] = pygame.image.load(
                os.path.join(card_dir, 'back.png')).convert_alpha()
        except Exception as e:
            print(f'[warn] card image load failed: {e}')
        return images

    def _card_surf_by_str(self, card_str):
        base = self._cards.get(card_str.strip())
        if base:
            return base
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
        lbl = self.fonts["small"].render(str(card), False, col)
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