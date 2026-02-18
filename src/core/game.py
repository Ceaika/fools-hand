from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .deck import Deck
from .move_validator import MoveValidator
from .player import Player
from .table import Table


@dataclass(slots=True)
class Game:
    seed: Optional[int] = None

    deck: Deck = field(init=False)
    validator: MoveValidator = field(init=False)
    table: Table = field(init=False)
    players: List[Player] = field(init=False)

    attacker_idx: int = field(init=False)
    defender_idx: int = field(init=False)

    def __post_init__(self) -> None:
        self.deck = Deck.new_shuffled(seed=self.seed)
        self.validator = MoveValidator(trump=self.deck.trump)
        self.table = Table()
        self.players = []
        self.attacker_idx = 0
        self.defender_idx = 1

    def setup(self, num_players: int = 2) -> None:
        if num_players < 2:
            raise ValueError("Durak needs at least 2 players")

        self.players = [Player(name=f"P{i+1}") for i in range(num_players)]

        # initial deal: 6 each
        for _ in range(6):
            for p in self.players:
                p.hand.append(self.deck.draw())

        self.attacker_idx = 0
        self.defender_idx = 1

    def attacker(self) -> Player:
        return self.players[self.attacker_idx]

    def defender(self) -> Player:
        return self.players[self.defender_idx]

    def _rotate_roles_after_successful_defence(self) -> None:
        # In basic 2-player: swap
        self.attacker_idx, self.defender_idx = self.defender_idx, self.attacker_idx

    def play_single_attack_demo(self) -> None:
        a = self.attacker()
        d = self.defender()

        print("=== Fool's Hand Prototype ===")
        print(f"Trump suit: {self.deck.trump.value}")
        print(f"Deck bottom (trump reveal card): {self.deck.peek_bottom()}")
        print()
        print("Initial hands:")
        print(a)
        print(d)
        print()

        # attacker chooses "lowest" card
        attack_card = sorted(a.hand, key=lambda c: (c.suit == self.deck.trump, c.rank_value))[0]
        a.remove_card(attack_card)

        self.table.add_attack(attack_card)
        print(f"{a.name} attacks with {attack_card}")
        print(f"Table: {self.table}")
        print()

        # defender chooses cheapest beating card (naive)
        beating_options = [c for c in d.hand if self.validator.can_defend(attack_card, c)]
        if beating_options:
            defence_card = sorted(beating_options, key=lambda c: (c.suit == self.deck.trump, c.rank_value))[0]
            d.remove_card(defence_card)
            self.table.add_defence(0, defence_card)
            print(f"{d.name} defends with {defence_card}")
            print(f"Table: {self.table}")
            print()

            self.table.clear()

            # draw to six (attacker first)
            a.draw_to_six(self.deck)
            d.draw_to_six(self.deck)

            print("Defence successful. Roles rotate.")
            self._rotate_roles_after_successful_defence()

        else:
            print(f"{d.name} cannot defend and picks up.")
            d.hand.extend(self.table.all_cards())
            self.table.clear()

            a.draw_to_six(self.deck)
            d.draw_to_six(self.deck)

            print("Pickup complete. Attacker remains attacker (2-player simple rule).")

        print()
        print("After round:")
        print(self.players[self.attacker_idx])
        print(self.players[self.defender_idx])
        print(f"Deck remaining: {self.deck.remaining()}")
