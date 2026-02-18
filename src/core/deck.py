from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from .card import Card, Suit, RANKS_32


@dataclass(slots=True)
class Deck:
    cards: List[Card]
    trump: Suit

    @classmethod
    def new_shuffled(cls, *, seed: Optional[int] = None) -> Deck:
        rng = random.Random(seed)
        all_cards: List[Card] = [Card(suit=s, rank=r) for s in Suit for r in RANKS_32]
        rng.shuffle(all_cards)

        # In Durak, trump is usually revealed from the bottom card.
        # We'll set it based on the last card in our list.
        trump_suit = all_cards[-1].suit
        return cls(cards=all_cards, trump=trump_suit)

    def draw(self) -> Card:
        if not self.cards:
            raise IndexError("Cannot draw: deck is empty")
        return self.cards.pop(0)

    def remaining(self) -> int:
        return len(self.cards)

    def peek_bottom(self) -> Card:
        if not self.cards:
            raise IndexError("Deck empty")
        return self.cards[-1]