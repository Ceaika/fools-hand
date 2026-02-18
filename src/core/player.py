from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .card import Card, Suit


@dataclass(slots=True)
class Player:
    name: str
    hand: List[Card] = field(default_factory=list)

    def draw_to_six(self, deck) -> None:
        while len(self.hand) < 6 and deck.remaining() > 0:
            self.hand.append(deck.draw())

    def remove_card(self, card: Card) -> None:
        self.hand.remove(card)

    def card_count(self) -> int:
        return len(self.hand)

    def sort_hand(self, trump: Suit) -> None:
        self.hand.sort(key=lambda c: c.sort_key(trump))

    def __str__(self) -> str:
        return f"{self.name}({len(self.hand)}): " + " ".join(str(c) for c in self.hand)