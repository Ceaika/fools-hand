from __future__ import annotations

from typing import List

from .card import Card, Suit
from .table import Table


class MoveValidator:


    def __init__(self, trump: Suit) -> None:
        self.trump = trump

    def valid_attacks(self, hand: List[Card], table: Table) -> List[Card]:
        """Cards in hand that are legal opening or pile-on attacks."""
        if not table.attacks():
            return list(hand)
        on_table = table.ranks_on_table()
        return [c for c in hand if c.rank in on_table]

    def can_attack(self, card: Card, table: Table) -> bool:
        if not table.attacks():
            return True
        return card.rank in table.ranks_on_table()

    def valid_defences(self, hand: List[Card], attack_card: Card) -> List[Card]:
        """Cards in hand that can legally beat the given attack card."""
        return [c for c in hand if c.can_beat(attack_card, self.trump)]

    def can_defend(self, card: Card, attack_card: Card) -> bool:
        return card.can_beat(attack_card, self.trump)