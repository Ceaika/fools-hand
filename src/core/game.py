from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .card import Card, Suit
from .deck import Deck
from .move_validator import MoveValidator
from .player import Player
from .table import Table


# ── simple AI helpers ────────────────────────────────────────────────────────

def _ai_choose_attack(player: Player, table: Table, trump: Suit) -> Optional[Card]:
    """Pick the weakest valid attack card. Prefer non-trumps."""
    validator = MoveValidator(trump)
    valid = validator.valid_attacks(player.hand, table)

    if not valid:
        return None

    non_trump = [c for c in valid if not c.is_trump(trump)]
    pool = non_trump if non_trump else valid
    return min(pool, key=lambda c: c.rank_value())


def _ai_should_stop_attacking(attacker: Player, table: Table, defender: Player, trump: Suit) -> bool:
    """
    Stop attacking when:
    - No more valid pile-on cards exist, OR
    - Defender has few cards left (don't over-commit), OR
    - We've already attacked with 6 cards.
    """
    on_table = table.ranks_on_table()
    can_add = [c for c in attacker.hand if c.rank in on_table]

    if not can_add:
        return True
    if table.all_defended() and len(can_add) > 0 and len(defender.hand) == 0:
        return True
    if len(table.attacks()) >= 6:
        return True
    # Hard stop heuristic: don't pile on if defender is nearly empty
    if len(defender.hand) <= len(table.attacks()):
        return True
    return False


def _ai_choose_defence(defender: Player, attack_card: Card, trump: Suit) -> Optional[Card]:
    """
    Pick the cheapest card that beats the attack.
    Prefer same-suit over trump.
    """
    validator = MoveValidator(trump)
    valid = validator.valid_defences(defender.hand, attack_card)

    if not valid:
        return None

    same_suit = [c for c in valid if c.suit == attack_card.suit]
    pool = same_suit if same_suit else valid
    return min(pool, key=lambda c: c.rank_value())


# ── Game ─────────────────────────────────────────────────────────────────────

@dataclass
class Game:
    seed: Optional[int] = None
    players: List[Player] = field(default_factory=list)
    deck: Optional[Deck] = None
    table: Table = field(default_factory=Table)
    attacker_idx: int = 0
    defender_idx: int = 1

    def setup(self, num_players: int = 2) -> None:
        assert 2 <= num_players <= 6
        self.deck = Deck.new_shuffled(seed=self.seed)
        self.players = [Player(name=f"Bot {i}" if i > 0 else "You")
                        for i in range(num_players)]
        # deal 6 cards each, 2 at a time
        for _ in range(3):
            for p in self.players:
                for _ in range(2):
                    if self.deck.remaining() > 0:
                        p.hand.append(self.deck.draw())
        # sort hands trump-last
        for p in self.players:
            p.sort_hand(self.deck.trump)

        self.attacker_idx = 0
        self.defender_idx = 1
        print(f"\nTrump suit: {self.deck.trump}")
        print(f"Trump card: {self.deck.peek_bottom()}")

    # ── round helpers ────────────────────────────────────────────────────────

    def _draw_up(self) -> None:
        """All players draw back up to 6, attacker first then others."""
        order = (
            [self.attacker_idx]
            + [i for i in range(len(self.players))
               if i not in (self.attacker_idx, self.defender_idx)]
            + [self.defender_idx]
        )
        for idx in order:
            self.players[idx].draw_to_six(self.deck)
            self.players[idx].sort_hand(self.deck.trump)

    def _advance_roles(self, defender_took: bool) -> None:
        n = len(self.players)
        if defender_took:
            # Defender picks up; skip them — attacker stays, next attacker is after defender
            self.attacker_idx = (self.defender_idx + 1) % n
        else:
            # Successful defence: defender becomes next attacker
            self.attacker_idx = self.defender_idx
        self.defender_idx = (self.attacker_idx + 1) % n

    def _active_players(self) -> List[int]:
        """Indices of players still holding cards."""
        return [i for i, p in enumerate(self.players) if len(p.hand) > 0]

    def _check_game_over(self) -> Optional[int]:
        """Return index of the loser if only one player has cards, else None."""
        active = self._active_players()
        if len(active) == 1:
            return active[0]
        return None

    # ── display helpers ──────────────────────────────────────────────────────

    def _show_state(self) -> None:
        """Print the current hand and table cleanly."""
        player = self.players[0]
        trump = self.deck.trump
        print(f"\n  Trump: {trump}  |  Deck: {self.deck.remaining()} cards")
        print(f"  Bot cards: {self.players[1].card_count()}")
        if not self.table.is_empty():
            print(f"  Table: {self.table}")
        print(f"\n  Your hand: ", end="")
        for i, card in enumerate(player.hand, start=1):
            print(f"[{i}] {card}", end="  ")
        print()

    def _pick_card_by_index(self, player: Player, prompt: str) -> Optional[Card]:
        """Let the player pick a card by index, or 0 to pass."""
        while True:
            raw = input(f"\n  {prompt} (0 to pass): ").strip()
            if not raw.isdigit():
                print("  Please enter a number.")
                continue
            choice = int(raw)
            if choice == 0:
                return None
            if 1 <= choice <= len(player.hand):
                return player.hand[choice - 1]
            print(f"  Pick a number between 0 and {len(player.hand)}.")

    def _thinking(self, name: str) -> None:
        """Animate thinking dots then leave cursor on same line."""
        import time
        print(f"\n  {name} is thinking ", end="", flush=True)
        for _ in range(3):
            time.sleep(0.4)
            print(".", end="", flush=True)
        time.sleep(0.3)
        print()

    def _wait(self) -> None:
        input("\n  Press Enter for next round...")

    # ── round ────────────────────────────────────────────────────────────────

    def _play_round(self) -> None:
        attacker = self.players[self.attacker_idx]
        defender = self.players[self.defender_idx]
        human_is_attacker = (self.attacker_idx == 0)
        human_is_defender = (self.defender_idx == 0)
        trump = self.deck.trump
        validator = MoveValidator(trump)

        self.table.clear()

        print(f"\n{'─'*50}")
        print(f"  {'Your turn to attack' if human_is_attacker else f'{attacker.name} is attacking'}"
              f"  |  {'You defend' if human_is_defender else f'{defender.name} defends'}")

        # ── attack phase ─────────────────────────────────────────────────────
        first_attack = True
        while True:
            if human_is_attacker:
                self._show_state()
                prompt = "Choose attack card" if first_attack else "Add another card (pile on)"
                card = self._pick_card_by_index(attacker, prompt)
                if card is None:
                    if first_attack:
                        print("  You passed — no attack this round.")
                    else:
                        print("  You stop attacking.")
                    break
                if not first_attack and not validator.can_attack(card, self.table):
                    print(f"  ✗ {card} — rank not on table, pick a matching rank or pass.")
                    continue
            else:
                self._thinking(attacker.name)
                if first_attack:
                    card = _ai_choose_attack(attacker, self.table, trump)
                else:
                    if _ai_should_stop_attacking(attacker, self.table, defender, trump):
                        card = None
                    else:
                        card = _ai_choose_attack(attacker, self.table, trump)
                if card is None:
                    print(f"  {attacker.name} stops attacking.")
                    break

            attacker.remove_card(card)
            self.table.add_attack(card)
            if not human_is_attacker:
                pass  # bot action printed after defence below
            else:
                print(f"  You play  →  {card}")
            first_attack = False

            # ── defender responds ─────────────────────────────────────────────
            while self.table.first_undefended_index() is not None:
                idx = self.table.first_undefended_index()
                attack_card = self.table.pairs[idx].attack

                if human_is_defender:
                    self._show_state()
                    print(f"  Defend against: {attack_card}")
                    defence = self._pick_card_by_index(defender, "Choose defence card")
                    if defence is not None and not validator.can_defend(defence, attack_card):
                        print(f"  ✗ {defence} cannot beat {attack_card}. Try again.")
                        continue
                else:
                    self._thinking(defender.name)
                    defence = _ai_choose_defence(defender, attack_card, trump)

                if defence is None:
                    taken = self.table.all_cards()
                    if not human_is_attacker:
                        print(f"  {attacker.name} plays  →  {attack_card}")
                    print(f"  {defender.name} picks up {len(taken)} cards.")
                    defender.hand.extend(taken)
                    defender.sort_hand(trump)
                    self._draw_up()
                    self._advance_roles(defender_took=True)
                    self._wait()
                    return

                defender.remove_card(defence)
                self.table.add_defence(idx, defence)
                if not human_is_attacker:
                    print(f"  {attacker.name} plays  →  {attack_card}  /  {defence}  ←  {defender.name}")
                else:
                    print(f"  {defender.name} responds  →  {defence}")

        # ── end of round ─────────────────────────────────────────────────────
        print(f"\n  {defender.name} defended successfully.")
        self._draw_up()
        self._advance_roles(defender_took=False)
        self._wait()

    # ── full game ────────────────────────────────────────────────────────────

    def play(self) -> None:
        """Run a full interactive game to completion."""
        print(f"\n  Trump suit: {self.deck.trump}  ({self.deck.peek_bottom()})")

        while True:
            active = self._active_players()
            if len(active) <= 1:
                break

            while self.attacker_idx not in active:
                self.attacker_idx = (self.attacker_idx + 1) % len(self.players)
            while self.defender_idx not in active or self.defender_idx == self.attacker_idx:
                self.defender_idx = (self.defender_idx + 1) % len(self.players)

            self._play_round()

            if self._check_game_over() is not None:
                break

        loser_idx = self._check_game_over()
        print(f"\n{'═'*50}")
        if loser_idx is not None:
            print(f"  🃏 {self.players[loser_idx].name} is the DURAK (fool)!")
        else:
            print("  Game ended.")

    # ── legacy demo methods (kept for compatibility) ─────────────────────────

    def play_single_attack_demo(self) -> None:
        """One-shot attack demo (early prototype behaviour)."""
        self._play_round()

    def play_interactive_round_demo(self) -> None:
        """Interactive single-round demo."""
        self._play_round()