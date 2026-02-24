"""
achievements.py — Fool's Hand achievement system (34 achievements)

No persistent saves for now — all state is in-memory per session.
Saves will be wired in after final checks.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable


# ── tiers ─────────────────────────────────────────────────────────────────────
COMMON   = "common"
RARE     = "rare"
EPIC     = "epic"
PLATINUM = "platinum"


# ── achievement definition ─────────────────────────────────────────────────────
@dataclass
class Achievement:
    key:         str
    name:        str
    description: str
    tier:        str


# ── master list ───────────────────────────────────────────────────────────────
ACHIEVEMENTS: list[Achievement] = [

    # ── Common ────────────────────────────────────────────────────────────────
    Achievement("accidental_genius",
                "Accidental Genius",
                "Won your first game. Don't read too much into it.",
                COMMON),

    Achievement("tutorial_dropout",
                "Tutorial Dropout",
                "Lost your first game. The tutorial was right there.",
                COMMON),

    Achievement("the_grind",
                "The Grind",
                "Played 10 total games.",
                COMMON),

    Achievement("participation_trophy",
                "Participation Trophy",
                "Lost in under 4 rounds. At least you showed up.",
                COMMON),

    Achievement("deja_vu",
                "Deja Vu",
                "Lost 3 games in a row. It's not bad luck at this point.",
                COMMON),

    Achievement("thanks_i_hate_it",
                "Thanks, I Hate It",
                "Started with 5 cards of the same non-trump suit. Rough.",
                COMMON),

    Achievement("the_fumble",
                "The Fumble",
                "Took the pile when you had a valid defence card in hand.",
                COMMON),

    Achievement("oh_the_gluttony",
                "Oh.. the Gluttony..",
                "Took the pile 4 or more times in a single game.",
                COMMON),

    Achievement("bold_strategy",
                "Bold Strategy",
                "Attacked with your only trump on the very first round.",
                COMMON),

    Achievement("mutually_assured_stupidity",
                "Mutually Assured Stupidity",
                "Both hands emptied simultaneously. The game couldn't pick a fool. You both volunteered.",
                COMMON),

    # ── Rare ──────────────────────────────────────────────────────────────────
    Achievement("house_of_cards",
                "House of Cards",
                "Defended 6 attacks in a single round. Built different.",
                RARE),

    Achievement("dealt_a_bad_hand",
                "Dealt a Bad Hand",
                "Started with zero trumps and still won. Respect.",
                RARE),

    Achievement("uno_reverse",
                "Uno Reverse",
                "Took a pile of 4 or more cards, then won the very next round.",
                RARE),

    Achievement("sweet_revenge",
                "Sweet Revenge",
                "Won a game after losing the previous two.",
                RARE),

    Achievement("wrong_place_wrong_time",
                "Wrong Place Wrong Time",
                "Took a pile that contained 3 or more trumps.",
                RARE),

    Achievement("richest_loser",
                "Richest Loser in the Room",
                "Lost while holding more trumps than the bot. Tragic.",
                RARE),

    Achievement("now_what",
                "Now what?",
                "Had 6 cards in hand when the deck ran out. Fully loaded for endgame.",
                RARE),

    Achievement("choked",
                "Choked",
                "Lost a game when the bot had only 1 card left.",
                RARE),

    Achievement("you_had_one_job",
                "You Had One Job",
                "Lost a game where you only needed to defend one more card.",
                RARE),

    Achievement("did_you_mean_to_do_that",
                "Did You Mean To Do That",
                "Played your only trump while attacking, then took the pile that same round.",
                RARE),

    Achievement("one_of_those_days",
                "One of Those Days",
                "Lost 3 games in a row where you started with at least 2 trumps each time.",
                RARE),

    Achievement("the_hoarder",
                "The Hoarder",
                "Ended a game with 10 or more cards in your hand.",
                RARE),

    Achievement("now_where_was_i",
                "Now... where was I?",
                "Won the game by playing your very last card as an attack.",
                RARE),

    Achievement("the_student",
                "The Student...",
                "Won 10 games total.",
                RARE),

    Achievement("controlled_demolition",
                "Controlled Demolition",
                "Discarded 5 fully defended piles in a single game.",
                RARE),

    # ── Epic ──────────────────────────────────────────────────────────────────
    Achievement("absolute_unit",
                "Absolute Unit",
                "The deck ran dry and every remaining trump was in your hands.",
                EPIC),

    Achievement("couldnt_get_a_word_in",
                "Couldn't Get a Word In",
                "Won a game where the bot never got a single attack off.",
                EPIC),

    Achievement("purist",
                "Purist",
                "Won without ever using a trump to attack. Who even needs them?",
                EPIC),

    Achievement("royal_flush",
                "Royal Flush",
                "Started with a full trump run, 6 through Ace. Wrong game, right instinct.",
                EPIC),

    Achievement("suited_up",
                "Suited Up",
                "Your opening hand was 6 cards all of the same suit.",
                EPIC),

    Achievement("nuclear_option",
                "Nuclear Option",
                "Used the Ace of trumps to defend against a 6.",
                EPIC),

    Achievement("becomes_the_master",
                "...Becomes the Master",
                "Won 5 games in a row.",
                EPIC),

    Achievement("what_where_and_when",
                "What, Where and When? Also How?",
                "Started with no trumps, took the pile at least once, yet the bot never defended a single one of your attacks. And you won.",
                EPIC),

    # ── Platinum ──────────────────────────────────────────────────────────────
    Achievement("fools_overtime",
                "Fool's Overtime",
                "Unlocked every achievement. You didn't have to. But here we are.",
                PLATINUM),
]

ACH: dict[str, Achievement] = {a.key: a for a in ACHIEVEMENTS}
_NON_PLATINUM = [a.key for a in ACHIEVEMENTS if a.tier != PLATINUM]


# ── global stats (no file persistence yet) ───────────────────────────────────
class GlobalStats:
    def __init__(self):
        self.games_played:          int  = 0
        self.games_won:             int  = 0
        self.current_streak:        int  = 0
        self.loss_streak:           int  = 0
        self.trump_loss_streak_data: list = []
        self.unlocked:              set  = set()

_global_stats = GlobalStats()

def get_global_stats() -> GlobalStats:
    return _global_stats


# ── tracker ───────────────────────────────────────────────────────────────────
class AchievementTracker:
    def __init__(self) -> None:
        self._callbacks: list[Callable[[Achievement], None]] = []
        self._stats = get_global_stats()

        # per-game
        self._rounds                   = 0
        self._piles_taken              = 0
        self._biggest_pile             = 0
        self._piles_defended           = 0
        self._player_took_this_game    = False
        self._starting_trumps          = 0
        self._starting_zero_trumps     = False
        self._player_attacks_total     = 0
        self._player_trump_attacks     = 0
        self._bot_defended_any         = False
        self._bot_card_count_at_round  = {}
        self._bot_attacks_total        = 0
        self._player_defences_total    = 0
        self._round_defences           = 0
        self._round_player_trump_only  = False
        self._round_took_pile          = False
        self._deck_empty_fired         = False
        self._uno_reverse_pending      = False
        self._uno_reverse_round        = 0
        self._only_trump_left_attacked = False
        self._final_card_was_attack    = False
        self._final_round_attack_count = 0
        self._wwwh_no_start_trumps     = False
        self._wwwh_took_pile           = False
        self._prev_loss_streak         = 0

    def add_listener(self, fn: Callable[[Achievement], None]) -> None:
        self._callbacks.append(fn)

    def _unlock(self, key: str) -> None:
        s = self._stats
        if key in s.unlocked:
            return
        s.unlocked.add(key)
        ach = ACH[key]
        for fn in self._callbacks:
            fn(ach)
        # auto-platinum
        if key != "fools_overtime" and all(k in s.unlocked for k in _NON_PLATINUM):
            self._unlock("fools_overtime")

    # ── setup ─────────────────────────────────────────────────────────────────
    def on_game_start(self, player_hand: list, trump) -> None:
        trump_cards = [c for c in player_hand if c.is_trump(trump)]
        self._starting_trumps      = len(trump_cards)
        self._starting_zero_trumps = (self._starting_trumps == 0)
        self._wwwh_no_start_trumps = (self._starting_trumps == 0)

        suits = [c.suit for c in player_hand]
        if len(set(suits)) == 1:
            self._unlock("suited_up")

        suit_counts = Counter(suits)
        for suit, count in suit_counts.items():
            if count >= 5 and suit != trump:
                self._unlock("thanks_i_hate_it")
                break

        # Royal Flush: all 6 cards are trump AND consecutive ranks
        if self._starting_trumps == 6:
            ranks = sorted(c.rank_value() for c in trump_cards)
            if ranks[-1] - ranks[0] == 5 and len(set(ranks)) == 6:
                self._unlock("royal_flush")

    def on_round_start(self, round_num: int, bot_hand_size: int,
                       player_trump_count: int) -> None:
        self._rounds = round_num
        self._round_defences           = 0
        self._round_took_pile          = False
        self._only_trump_left_attacked = False
        self._bot_card_count_at_round[round_num] = bot_hand_size
        if round_num == 1:
            self._round_player_trump_only = (player_trump_count == 1)

    # ── attacks ───────────────────────────────────────────────────────────────
    def on_player_attack(self, card, trump, hand_before: list) -> None:
        self._player_attacks_total += 1
        self._final_card_was_attack = (len(hand_before) == 1)
        if card.is_trump(trump):
            self._player_trump_attacks += 1
            if self._rounds == 1 and self._round_player_trump_only:
                trump_before = [c for c in hand_before if c.is_trump(trump)]
                if len(trump_before) == 1:
                    self._unlock("bold_strategy")
            trump_before = [c for c in hand_before if c.is_trump(trump)]
            if len(trump_before) == 1:
                self._only_trump_left_attacked = True

    def on_bot_attack(self) -> None:
        self._bot_attacks_total += 1

    def on_bot_defend_success(self) -> None:
        self._bot_defended_any = True

    # ── defences ──────────────────────────────────────────────────────────────
    def on_player_defend(self, defence_card, attack_card, trump) -> None:
        self._player_defences_total += 1
        self._round_defences += 1
        if (defence_card.rank == "A" and defence_card.is_trump(trump)
                and attack_card.rank == "6"):
            self._unlock("nuclear_option")
        if self._round_defences >= 6:
            self._unlock("house_of_cards")

    # ── pile ──────────────────────────────────────────────────────────────────
    def on_player_takes_pile(self, cards: list, trump,
                             had_valid_defence: bool) -> None:
        count = len(cards)
        self._piles_taken         += 1
        self._round_took_pile      = True
        self._player_took_this_game = True
        self._biggest_pile         = max(self._biggest_pile, count)
        self._wwwh_took_pile       = True

        if sum(1 for c in cards if c.is_trump(trump)) >= 3:
            self._unlock("wrong_place_wrong_time")
        if self._piles_taken >= 4:
            self._unlock("oh_the_gluttony")
        if had_valid_defence:
            self._unlock("the_fumble")
        if self._only_trump_left_attacked:
            self._unlock("did_you_mean_to_do_that")
        if count >= 4:
            self._uno_reverse_pending = True
            self._uno_reverse_round   = self._rounds

    def on_round_defended_successfully(self) -> None:
        self._piles_defended += 1
        if self._piles_defended >= 5:
            self._unlock("controlled_demolition")

    # ── deck ──────────────────────────────────────────────────────────────────
    def on_deck_empty(self, player_hand: list, all_game_trumps: list, trump) -> None:
        if self._deck_empty_fired:
            return
        self._deck_empty_fired = True
        if len(player_hand) == 6:
            self._unlock("now_what")
        player_trumps = [c for c in player_hand if c.is_trump(trump)]
        if all_game_trumps and len(player_trumps) == len(all_game_trumps):
            self._unlock("absolute_unit")

    # ── game over ─────────────────────────────────────────────────────────────
    def on_game_over(self, result: str, player_hand: list,
                     bot_hand: list, trump) -> None:
        s = self._stats
        s.games_played += 1

        if result == "tie":
            self._unlock("mutually_assured_stupidity")
            s.current_streak = 0
            s.loss_streak    = 0
            s.trump_loss_streak_data = []
            if s.games_played >= 10:
                self._unlock("the_grind")
            return

        player_won = (result == "win")

        if player_won:
            self._prev_loss_streak = s.loss_streak
            s.games_won      += 1
            s.current_streak += 1
            s.loss_streak     = 0
            s.trump_loss_streak_data = []

            if s.games_won == 1:
                self._unlock("accidental_genius")
            if s.games_won >= 10:
                self._unlock("the_student")
            if s.current_streak >= 5:
                self._unlock("becomes_the_master")
            if self._prev_loss_streak == 2:
                self._unlock("sweet_revenge")
            if self._starting_zero_trumps:
                self._unlock("dealt_a_bad_hand")
            if self._player_trump_attacks == 0 and self._player_attacks_total > 0:
                self._unlock("purist")
            if self._bot_attacks_total == 0:
                self._unlock("couldnt_get_a_word_in")
            if self._final_card_was_attack:
                self._unlock("now_where_was_i")
            if (self._uno_reverse_pending
                    and self._rounds == self._uno_reverse_round + 1):
                self._unlock("uno_reverse")
            if (self._wwwh_no_start_trumps
                    and self._wwwh_took_pile
                    and not self._bot_defended_any):
                self._unlock("what_where_and_when")
            if len(player_hand) >= 10:
                self._unlock("the_hoarder")

        else:
            s.current_streak = 0
            s.loss_streak   += 1
            total_losses = s.games_played - s.games_won
            if total_losses == 1:
                self._unlock("tutorial_dropout")
            if s.loss_streak >= 3:
                self._unlock("deja_vu")
            if self._rounds < 4:
                self._unlock("participation_trophy")
            player_t = len([c for c in player_hand if c.is_trump(trump)])
            bot_t    = len([c for c in bot_hand    if c.is_trump(trump)])
            if player_t > bot_t:
                self._unlock("richest_loser")
            if self._bot_card_count_at_round.get(self._rounds, 99) == 1:
                self._unlock("choked")
            if self._final_round_attack_count == 1:
                self._unlock("you_had_one_job")
            s.trump_loss_streak_data.append(self._starting_trumps)
            if len(s.trump_loss_streak_data) >= 3:
                if all(t >= 2 for t in s.trump_loss_streak_data[-3:]):
                    self._unlock("one_of_those_days")
            if len(player_hand) >= 10:
                self._unlock("the_hoarder")

        if s.games_played >= 10:
            self._unlock("the_grind")

    def on_final_round_attack_count(self, count: int) -> None:
        self._final_round_attack_count = count

    def on_final_card_played(self, card, trump, was_attack: bool) -> None:
        """Player just played their very last card."""
        self._final_card_was_attack = was_attack