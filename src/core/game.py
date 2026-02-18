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

    # ── interactive helpers ──────────────────────────────────────────────────

    def _pick_card_by_index(self, player: Player, prompt: str) -> Optional[Card]:
        """Show player's hand and let them pick a card by index, or 0 to pass."""
        print(f"\n  {player}")
        numbered = list(enumerate(player.hand, start=1))
        for idx, card in numbered:
            print(f"    [{idx}] {card}")
        print(f"    [0] Pass / stop")
        while True:
            raw = input(f"  {prompt} (0 to pass): ").strip()
            if not raw.isdigit():
                print("  Please enter a number.")
                continue
            choice = int(raw)
            if choice == 0:
                return None
            if 1 <= choice <= len(player.hand):
                return player.hand[choice - 1]
            print(f"  Pick a number between 0 and {len(player.hand)}.")

    # ── round ────────────────────────────────────────────────────────────────

    def _play_round(self) -> None:
        attacker = self.players[self.attacker_idx]
        defender = self.players[self.defender_idx]
        human_is_attacker = (self.attacker_idx == 0)
        human_is_defender = (self.defender_idx == 0)
        trump = self.deck.trump

        self.table.clear()

        print(f"\n{'─'*50}")
        print(f"  Attacker: {attacker.name}  │  Defender: {defender.name}")
        print(f"  Deck: {self.deck.remaining()} cards remaining")
        print(f"  Trump: {trump}")

        # ── attack phase ─────────────────────────────────────────────────────
        first_attack = True
        while True:
            # --- attacker picks a card ---
            if human_is_attacker:
                if first_attack:
                    card = self._pick_card_by_index(attacker, "Choose attack card")
                    if card is None:
                        # passing on first attack means nothing to defend; skip round
                        print("  No attack played.")
                        return
                else:
                    # show table state
                    print(f"\n  Table: {self.table}")
                    card = self._pick_card_by_index(attacker, "Add another attack card")
            else:
                if first_attack:
                    card = _ai_choose_attack(attacker, self.table, trump)
                else:
                    if _ai_should_stop_attacking(attacker, self.table, defender, trump):
                        card = None
                    else:
                        card = _ai_choose_attack(attacker, self.table, trump)

            if card is None:
                break  # attacker is done

            # validate rank-matching rule (after first attack)
            if not first_attack:
                validator = MoveValidator(trump)
                if not validator.can_attack(card, self.table):
                    if human_is_attacker:
                        print(f"  ✗ {card} rank not on table — pick a card matching a rank already played.")
                        continue
                    else:
                        break  # AI picked bad card somehow, stop

            attacker.remove_card(card)
            self.table.add_attack(card)
            print(f"\n  {attacker.name} attacks with {card}")
            print(f"  Table: {self.table}")
            first_attack = False

            # ── defender responds to every undefended attack ──────────────────
            while self.table.first_undefended_index() is not None:
                idx = self.table.first_undefended_index()
                attack_card = self.table.pairs[idx].attack

                if human_is_defender:
                    print(f"\n  You must defend against: {attack_card}")
                    defence = self._pick_card_by_index(defender, "Choose defence card")
                else:
                    defence = _ai_choose_defence(defender, attack_card, trump)

                if defence is None:
                    # defender gives up — picks up everything
                    taken = self.table.all_cards()
                    defender.pick_up = taken  # flag for later
                    print(f"\n  {defender.name} cannot defend — picks up {len(taken)} cards.")
                    defender.hand.extend(taken)
                    defender.sort_hand(trump)
                    self._draw_up()
                    self._advance_roles(defender_took=True)
                    return

                # validate the defence card
                validator = MoveValidator(trump)
                if not validator.can_defend(defence, attack_card):
                    if human_is_defender:
                        print(f"  ✗ {defence} cannot beat {attack_card}. Try again.")
                        continue
                    else:
                        # AI logic error — give up
                        taken = self.table.all_cards()
                        print(f"\n  {defender.name} cannot defend — picks up {len(taken)} cards.")
                        defender.hand.extend(taken)
                        defender.sort_hand(trump)
                        self._draw_up()
                        self._advance_roles(defender_took=True)
                        return

                defender.remove_card(defence)
                self.table.add_defence(idx, defence)
                print(f"  {defender.name} defends with {defence}")
                print(f"  Table: {self.table}")

        # ── end of round: all attacks defended ───────────────────────────────
        print(f"\n  {defender.name} successfully defended!")
        self._draw_up()
        self._advance_roles(defender_took=False)

    # ── full game ────────────────────────────────────────────────────────────

    def play(self) -> None:
        """Run a full interactive game to completion."""
        trump = self.deck.trump
        round_num = 0

        while True:
            # Skip players with no cards when assigning roles
            active = self._active_players()
            if len(active) <= 1:
                break

            # Make sure attacker and defender are still active
            while self.attacker_idx not in active:
                self.attacker_idx = (self.attacker_idx + 1) % len(self.players)
            while self.defender_idx not in active or self.defender_idx == self.attacker_idx:
                self.defender_idx = (self.defender_idx + 1) % len(self.players)

            round_num += 1
            print(f"\n{'═'*50}")
            print(f"  ROUND {round_num}")
            self._play_round()

            loser_idx = self._check_game_over()
            if loser_idx is not None:
                break

        loser_idx = self._check_game_over()
        if loser_idx is not None:
            print(f"\n{'═'*50}")
            print(f"  🃏 {self.players[loser_idx].name} is the DURAK (fool)!")
        else:
            print("\n  Game ended — no loser determined.")

    # ── legacy demo methods (kept for compatibility) ─────────────────────────

    def play_single_attack_demo(self) -> None:
        """One-shot attack demo (early prototype behaviour)."""
        self._play_round()

    def play_interactive_round_demo(self) -> None:
        """Interactive single-round demo."""
        self._play_round()