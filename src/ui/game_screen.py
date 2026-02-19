from __future__ import annotations

import math
import pygame
from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, PURPLE, PURPLE_DIM,
    TEXT_MAIN, TEXT_DIM, GOLD,
    CARD_W, CARD_H, CARD_BG, CARD_BACK, CARD_BORDER, CARD_RED, CARD_BLACK,
)

# prototype colours
_GREEN  = (30,  160, 60)   # felt-ish table colour
_GREEN2 = (20,  120, 45)


class GameScreen:
    """
    Prototype game screen — wires up Game core to a visual display.
    No interaction yet, just renders state so we can see the game logic.
    """

    def __init__(self, screen: pygame.Surface, fonts: dict,
                 game) -> None:
        self.screen = screen
        self.fonts  = fonts
        self.game   = game
        self.tick   = 0

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "back"
        return None

    def update(self) -> None:
        self.tick += 1

    def draw(self, surface: pygame.Surface | None = None) -> None:
        target = surface if surface is not None else self.screen
        target.fill((15, 60, 30))   # dark green felt

        self._draw_table_area(target)
        self._draw_bot_hand(target)
        self._draw_player_hand(target)
        self._draw_deck(target)
        self._draw_hud(target)

    # ── drawing ──────────────────────────────────────────────────────────────

    def _draw_table_area(self, target: pygame.Surface) -> None:
        # centre play area
        area = pygame.Rect(WIDTH // 2 - 300, HEIGHT // 2 - 80, 600, 160)
        pygame.draw.rect(target, (20, 80, 40), area, border_radius=12)
        pygame.draw.rect(target, (40, 120, 60), area, width=2, border_radius=12)

        if self.game.table.is_empty():
            label = self.fonts["small"].render("- no cards on table -", False, (60, 120, 70))
            target.blit(label, (area.centerx - label.get_width() // 2,
                                area.centery - label.get_height() // 2))
        else:
            self._draw_table_cards(target, area)

    def _draw_table_cards(self, target: pygame.Surface, area: pygame.Rect) -> None:
        pairs   = self.game.table.pairs
        total_w = len(pairs) * (CARD_W + 10) + 20  # attack + defence overlap
        start_x = area.centerx - total_w // 2

        for i, pair in enumerate(pairs):
            x = start_x + i * (CARD_W + 10)
            y = area.centery - CARD_H // 2

            # attack card
            self._draw_card_face(target, pair.attack, x, y)

            # defence card slightly offset on top
            if pair.defence is not None:
                self._draw_card_face(target, pair.defence, x + 12, y - 12)

    def _draw_bot_hand(self, target: pygame.Surface) -> None:
        bot   = self.game.players[1]
        count = len(bot.hand)
        if count == 0:
            return

        label = self.fonts["small"].render(
            f"Bot 1  [{count} cards]", False, TEXT_DIM)
        target.blit(label, (WIDTH // 2 - label.get_width() // 2, 14))

        # show card backs
        total_w = count * (CARD_W // 2) + CARD_W // 2
        start_x = WIDTH // 2 - total_w // 2
        for i in range(count):
            x = start_x + i * (CARD_W // 2)
            self._draw_card_back(target, x, 36)

    def _draw_player_hand(self, target: pygame.Surface) -> None:
        player = self.game.players[0]
        hand   = player.hand
        if not hand:
            return

        total_w = len(hand) * (CARD_W + 8)
        start_x = WIDTH // 2 - total_w // 2
        base_y  = HEIGHT - CARD_H - 24

        label = self.fonts["small"].render("Your hand", False, TEXT_DIM)
        target.blit(label, (WIDTH // 2 - label.get_width() // 2, base_y - 20))

        for i, card in enumerate(hand):
            x = start_x + i * (CARD_W + 8)
            self._draw_card_face(target, card, x, base_y)

    def _draw_deck(self, target: pygame.Surface) -> None:
        remaining = self.game.deck.remaining()
        trump     = self.game.deck.trump

        x = 40
        y = HEIGHT // 2 - CARD_H // 2

        if remaining > 0:
            # stack effect
            for i in range(min(3, remaining)):
                self._draw_card_back(target, x + i * 2, y - i * 2)

        label = self.fonts["small"].render(f"{remaining}", False, TEXT_DIM)
        target.blit(label, (x + CARD_W // 2 - label.get_width() // 2,
                             y + CARD_H + 6))

        # trump indicator
        trump_label = self.fonts["small"].render(f"trump: {trump}", False, GOLD)
        target.blit(trump_label, (x, y - 22))

    def _draw_hud(self, target: pygame.Surface) -> None:
        attacker = self.game.players[self.game.attacker_idx].name
        defender = self.game.players[self.game.defender_idx].name

        info = self.fonts["small"].render(
            f"{'Attacking' if attacker == 'You' else attacker + ' attacks'}  "
            f"|  {'Defending' if defender == 'You' else defender + ' defends'}",
            False, TEXT_DIM)
        target.blit(info, (WIDTH // 2 - info.get_width() // 2, HEIGHT // 2 - 110))

        esc = self.fonts["small"].render("ESC to go back", False, (50, 90, 60))
        target.blit(esc, (WIDTH - esc.get_width() - 12, HEIGHT - esc.get_height() - 10))

    # ── card rendering ────────────────────────────────────────────────────────

    def _draw_card_back(self, target: pygame.Surface, x: int, y: int) -> None:
        rect = pygame.Rect(x, y, CARD_W, CARD_H)
        pygame.draw.rect(target, CARD_BACK, rect, border_radius=4)
        pygame.draw.rect(target, PURPLE, rect, width=1, border_radius=4)
        # simple pattern
        inner = rect.inflate(-8, -8)
        pygame.draw.rect(target, (40, 30, 90), inner, width=1, border_radius=2)

    def _draw_card_face(self, target: pygame.Surface, card, x: int, y: int) -> None:
        rect    = pygame.Rect(x, y, CARD_W, CARD_H)
        is_red  = card.suit.value in ('♥', '♦')
        colour  = CARD_RED if is_red else CARD_BLACK

        pygame.draw.rect(target, CARD_BG, rect, border_radius=4)
        pygame.draw.rect(target, CARD_BORDER, rect, width=1, border_radius=4)

        # rank top-left
        rank = self.fonts["small"].render(card.rank, False, colour)
        target.blit(rank, (x + 4, y + 3))

        # suit centre
        suit = self.fonts["btn"].render(card.suit.value, False, colour)
        target.blit(suit, (x + CARD_W // 2 - suit.get_width() // 2,
                           y + CARD_H // 2 - suit.get_height() // 2))

        # trump highlight
        if card.is_trump(self.game.deck.trump):
            pygame.draw.rect(target, (*GOLD[:3], 60),
                             rect.inflate(-4, -4), width=2, border_radius=3)