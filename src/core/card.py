from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Suit(str, Enum):
    CLUBS = "♣"
    DIAMONDS = "♦"
    HEARTS = "♥"
    SPADES = "♠"


# 32-card Durak deck (6..A)
RANKS_32: tuple[str, ...] = ("6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANK_VALUE = {r: i for i, r in enumerate(RANKS_32)}


@dataclass(frozen=True, slots=True)
class Card:
    suit: Suit
    rank: str

    def __post_init__(self) -> None:
        if self.rank not in RANK_VALUE:
            raise ValueError(f"Invalid rank for 32-card deck: {self.rank}")

    def __str__(self) -> str:
        return f"{self.rank}{self.suit.value}"

    @property
    def rank_value(self) -> int:
        return RANK_VALUE[self.rank]

    def can_beat(self, other: Card, trump: Suit) -> bool:
        """
        Durak beating logic:
        - Same suit: higher rank beats lower rank
        - Trump beats any non-trump
        - Non-trump cannot beat trump
        """
        if self.suit == other.suit:
            return self.rank_value > other.rank_value

        # different suits
        if self.suit == trump and other.suit != trump:
            return True
        return False


def ranks_on_cards(cards: Iterable[Card]) -> set[str]:
    return {c.rank for c in cards}
