from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .card import Card, ranks_on_cards


@dataclass(slots=True)
class BattlePair:
    attack: Card
    defence: Optional[Card] = None

    def is_defended(self) -> bool:
        return self.defence is not None


@dataclass(slots=True)
class Table:
    pairs: List[BattlePair] = field(default_factory=list)

    def clear(self) -> None:
        self.pairs.clear()

    def attacks(self) -> List[Card]:
        return [p.attack for p in self.pairs]

    def defences(self) -> List[Card]:
        return [p.defence for p in self.pairs if p.defence is not None]

    def all_cards(self) -> List[Card]:
        out = []
        for p in self.pairs:
            out.append(p.attack)
            if p.defence:
                out.append(p.defence)
        return out

    def ranks_on_table(self) -> set[str]:
        return ranks_on_cards(self.all_cards())

    def add_attack(self, card: Card) -> None:
        self.pairs.append(BattlePair(attack=card))

    def add_defence(self, attack_index: int, card: Card) -> None:
        if attack_index < 0 or attack_index >= len(self.pairs):
            raise IndexError("Invalid attack index")
        if self.pairs[attack_index].is_defended():
            raise ValueError("That attack is already defended")
        self.pairs[attack_index].defence = card

    def first_undefended_index(self) -> Optional[int]:
        for i, p in enumerate(self.pairs):
            if not p.is_defended():
                return i
        return None

    def all_defended(self) -> bool:
        return self.first_undefended_index() is None

    def __str__(self) -> str:
        if not self.pairs:
            return "(empty)"
        parts = []
        for i, p in enumerate(self.pairs):
            if p.defence:
                parts.append(f"{p.attack} / {p.defence}")
            else:
                parts.append(f"{p.attack} / _")
        return " | ".join(parts)