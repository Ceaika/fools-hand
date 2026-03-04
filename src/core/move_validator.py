from __future__ import annotations

from typing import List

from .card import Card, Suit
from .table import Table


class MoveValidator:
    """Centralised Durak rule checking, extracted from game loop logic."""

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

    def can_transfer(self, card: Card, table: Table,
                     new_defender_hand: list | None = None) -> bool:
        """In transfer mode: defender can play a card of the same rank as the attack
        to redirect it — only if all attacks share one rank, no defences have been
        played yet, and the new defender (current attacker) has enough cards to
        actually defend the resulting pile."""
        if table.defences():
            return False
        attack_ranks = {p.attack.rank for p in table.pairs}
        if len(attack_ranks) != 1 or card.rank not in attack_ranks:
            return False
        # New defender would face len(pairs)+1 attacks — they need at least that many cards
        if new_defender_hand is not None:
            attacks_after = len(table.pairs) + 1
            if len(new_defender_hand) < attacks_after:
                return False
        return True

    def valid_transfers(self, hand: list, table: Table,
                        new_defender_hand: list | None = None) -> list:
        """Cards that can legally transfer the attack."""
        return [c for c in hand
                if self.can_transfer(c, table, new_defender_hand=new_defender_hand)]