from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Suit(Enum):
    CLUBS    = "♣"
    DIAMONDS = "♦"
    HEARTS   = "♥"
    SPADES   = "♠"

    def __str__(self) -> str:
        return self.value


# 32-card Durak deck: 6 through Ace
RANKS_32 = ["6", "7", "8", "9", "10", "J", "Q", "K", "A"]
_RANK_VALUE = {r: i for i, r in enumerate(RANKS_32)}


def ranks_on_cards(cards: Iterable[Card]) -> set[str]:
    """Return the set of rank strings present in a collection of cards."""
    return {c.rank for c in cards}


@dataclass(frozen=True, slots=True)
class Card:
    suit: Suit
    rank: str  # one of RANKS_32

    def rank_value(self) -> int:
        return _RANK_VALUE[self.rank]

    def is_trump(self, trump: Suit) -> bool:
        return self.suit == trump

    def can_beat(self, other: Card, trump: Suit) -> bool:
        """Return True if self beats other under Durak rules."""
        if self.suit == other.suit:
            return self.rank_value() > other.rank_value()
        if self.is_trump(trump) and not other.is_trump(trump):
            return True
        return False

    def sort_key(self, trump: Suit) -> tuple:
        """Non-trumps first (by rank, then suit as tiebreaker), trumps last."""
        is_trump = 1 if self.suit == trump else 0
        return (is_trump, self.rank_value(), list(Suit).index(self.suit))

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return self.__str__()