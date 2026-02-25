import unittest
from src.core.card import Card, Suit


class TestCardRules(unittest.TestCase):
    def test_same_suit_beats_higher_rank(self):
        trump = Suit.SPADES
        a = Card(Suit.HEARTS, "9")
        b = Card(Suit.HEARTS, "J")
        self.assertTrue(b.can_beat(a, trump))
        self.assertFalse(a.can_beat(b, trump))

    def test_trump_beats_non_trump(self):
        trump = Suit.CLUBS
        a = Card(Suit.HEARTS, "A")
        b = Card(Suit.CLUBS, "6")
        self.assertTrue(b.can_beat(a, trump))
        self.assertFalse(a.can_beat(b, trump))


if __name__ == "__main__":
    unittest.main()
