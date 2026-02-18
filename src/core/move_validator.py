from __future__ import annotations

from dataclasses import dataclass

from .card import Card, Suit
from .table import Table


@dataclass(frozen=True, slots=True)
class MoveValidator:
    trump: Suit

    def can_attack_first(self, card: Card) -> bool:
        # First attack: any card is allowed
        return True

    def can_attack_additional(self, table: Table, card: Card) -> bool:
        """
        Standard Durak rule: additional attack cards must match
        a rank already on the table (attack or defence cards).
        """
        if not table.pairs:
            return True
        return card.rank in table.ranks_on_table()

    def can_defend(self, attack_card: Card, defence_card: Card) -> bool:
        return defence_card.can_beat(attack_card, trump=self.trump)
