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
                
        for p in self.players:
            p.sort_hand(self.deck.trump)


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
        print()

        # First attack
        attack_card = sorted(a.hand, key=lambda c: (c.suit == self.deck.trump, c.rank_value))[0]
        a.remove_card(attack_card)
        self.table.add_attack(attack_card)

        print(f"{a.name} attacks with {attack_card}")

        while True:
            # Defender must respond to each undefended attack
            idx = self.table.first_undefended_index()
            if idx is None:
                break  # all defended

            attack = self.table.pairs[idx].attack

            beating_options = [c for c in d.hand if self.validator.can_defend(attack, c)]
            if not beating_options:
                print(f"{d.name} cannot defend {attack} and picks up.")
                d.hand.extend(self.table.all_cards())
                self.table.clear()

                a.draw_to_six(self.deck)
                d.draw_to_six(self.deck)
                return

            defence = sorted(beating_options, key=lambda c: (c.suit == self.deck.trump, c.rank_value))[0]
            d.remove_card(defence)
            self.table.add_defence(idx, defence)

            print(f"{d.name} defends {attack} with {defence}")

            # Attacker may add another attack if possible
            addable = [c for c in a.hand if self.validator.can_attack_additional(self.table, c)]
            if not addable:
                continue

            # --- simple "stop attacking" heuristic (v0.2.2) ---
            if len(d.hand) <= 2:
                print(f"{a.name} stops adding attacks (defender low on cards).")
                break

            non_trump_addable = [c for c in addable if c.suit != self.deck.trump]
            candidate_pool = non_trump_addable if non_trump_addable else addable

            import random
            if random.random() < 0.4:
                print(f"{a.name} chooses to stop attacking.")
                break

            next_attack = sorted(candidate_pool, key=lambda c: c.rank_value)[0]
            a.remove_card(next_attack)
            self.table.add_attack(next_attack)
            print(f"{a.name} adds attack {next_attack}")


        print("All attacks defended successfully.")
        self.table.clear()

        a.draw_to_six(self.deck)
        d.draw_to_six(self.deck)

        self._rotate_roles_after_successful_defence()

        print("Roles rotated.")
        print(f"Deck remaining: {self.deck.remaining()}")
    def play_interactive_round_demo(self) -> None:
        a = self.attacker()   # human
        d = self.defender()   # AI

        print("\n=== Interactive Round Demo ===")
        print(f"Trump suit: {self.deck.trump.value}")
        print(f"Deck remaining: {self.deck.remaining()}")
        print()

        # --- Human chooses first attack ---
        while True:
            print(f"{a.name} (YOU) hand: {a.hand_with_indexes()}")
            raw = input("Choose attack card index (or 'q' to quit): ").strip().lower()
            if raw == "q":
                raise SystemExit(0)

            if not raw.isdigit():
                print("Please type a number.\n")
                continue

            idx = int(raw)
            if idx < 0 or idx >= len(a.hand):
                print("Index out of range.\n")
                continue

            attack_card = a.hand[idx]
            if not self.validator.can_attack_first(attack_card):
                print("Illegal first attack (unexpected). Try again.\n")
                continue

            a.remove_card(attack_card)
            self.table.add_attack(attack_card)
            print(f"\n{a.name} attacks with {attack_card}\n")
            break

        # --- Loop until pickup or all defended + you stop ---
        while True:
            # Defender responds to first undefended attack
            undef_idx = self.table.first_undefended_index()
            if undef_idx is None:
                # all defended -> discard
                print("All attacks defended successfully. Discarding table.")
                self.table.clear()
                a.draw_to_six(self.deck)
                d.draw_to_six(self.deck)
                self._rotate_roles_after_successful_defence()
                return

            attack = self.table.pairs[undef_idx].attack

            # AI chooses cheapest beating card
            beating_options = [c for c in d.hand if self.validator.can_defend(attack, c)]
            if not beating_options:
                print(f"{d.name} cannot defend {attack} and picks up!")
                d.hand.extend(self.table.all_cards())
                self.table.clear()

                # Draw up to 6 (attacker then defender) – simple standard
                a.draw_to_six(self.deck)
                d.draw_to_six(self.deck)
                return

            defence = sorted(beating_options, key=lambda c: (c.suit == self.deck.trump, c.rank_value))[0]
            d.remove_card(defence)
            self.table.add_defence(undef_idx, defence)
            print(f"{d.name} defends {attack} with {defence}")
            print(f"Table: {self.table}\n")

            # --- Human decides whether to add another attack ---
            addable = [c for c in a.hand if self.validator.can_attack_additional(self.table, c)]
            if not addable:
                print("You have no legal additional attacks. Continuing...\n")
                continue

            print(f"Your hand: {a.hand_with_indexes()}")
            print("Legal additional attacks:", " ".join(str(c) for c in addable))
            raw2 = input("Add another attack? Enter index, or press Enter to stop: ").strip().lower()

            if raw2 == "":
                print("You stop attacking.\n")
                # next loop iteration will detect all_defended (if true) and discard/rotate
                continue

            if raw2 == "q":
                raise SystemExit(0)

            if not raw2.isdigit():
                print("Not a number. Stopping attack.\n")
                continue

            idx2 = int(raw2)
            if idx2 < 0 or idx2 >= len(a.hand):
                print("Index out of range. Stopping attack.\n")
                continue

            next_attack = a.hand[idx2]
            if not self.validator.can_attack_additional(self.table, next_attack):
                print(f"Illegal additional attack: {next_attack} (rank must match table). Stopping.\n")
                continue

            a.remove_card(next_attack)
            self.table.add_attack(next_attack)
            print(f"You add attack {next_attack}\n")

