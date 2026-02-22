from __future__ import annotations

import math
import os
import random
import pygame

from .constants import (
    WIDTH, HEIGHT,
    BG, NEON, NEON_GLOW, NEON_DARK, PURPLE, PURPLE_DIM,
    CARD_BG, CARD_BACK, CARD_BORDER, CARD_RED, CARD_BLACK,
    TEXT_MAIN, TEXT_DIM, BTN_RADIUS, GOLD,
)
from ..core.card import Card, Suit, RANKS_32

# ── extra colours ─────────────────────────────────────────────────────────────
_GREEN   = (60,  220, 120)
_GREEN_D = (20,  100,  55)
_RED     = (220,  50,  50)
_RED_D   = (120,  20,  20)
_AMBER   = (255, 180,  40)
_CYAN    = ( 80, 220, 255)

# ── layout zones ──────────────────────────────────────────────────────────────
# Screen is split: left panel = text/narration, right panel = interactive scene
_SPLIT   = 420          # x where left panel ends
_SCENE_X = _SPLIT + 20  # scene starts here
_SCENE_W = WIDTH - _SCENE_X
_SCENE_CX = _SCENE_X + _SCENE_W // 2

# Card dimensions for the scene
CW, CH = 76, 110

# ── card rendering ────────────────────────────────────────────────────────────

def _load_images() -> dict:
    d    = os.path.join(os.path.dirname(__file__), 'assets', 'cards')
    imgs = {}
    sm   = {'♥': 'hearts', '♦': 'diamonds', '♠': 'spades', '♣': 'clubs'}
    rm   = {'A': 'ace', 'J': 'jack', 'Q': 'queen', 'K': 'king',
            **{str(i): str(i) for i in range(2, 11)}}
    try:
        for ss, sn in sm.items():
            for rs, rn in rm.items():
                k = f'{rs}{ss}'
                p = os.path.join(d, f'{rn}_of_{sn}.png')
                if os.path.exists(p):
                    imgs[k] = pygame.image.load(p).convert_alpha()
        bp = os.path.join(d, 'back.png')
        if os.path.exists(bp):
            imgs['back'] = pygame.image.load(bp).convert_alpha()
    except Exception as e:
        print(f'[tutorial] {e}')
    return imgs


def _csurf(card: Card, imgs: dict, font, w=CW, h=CH) -> pygame.Surface:
    k = f'{card.rank}{card.suit.value}'
    b = imgs.get(k)
    if b:
        return pygame.transform.smoothscale(b, (w, h))
    s  = pygame.Surface((w, h), pygame.SRCALPHA)
    rc = CARD_RED if card.suit.value in ('♥', '♦') else CARD_BLACK
    pygame.draw.rect(s, CARD_BG,     (0, 0, w, h), border_radius=5)
    pygame.draw.rect(s, CARD_BORDER, (0, 0, w, h), width=1, border_radius=5)
    lbl = font.render(str(card), False, rc)
    s.blit(lbl, (4, 4))
    return s


def _bsurf(imgs: dict, w=CW, h=CH) -> pygame.Surface:
    b = imgs.get('back')
    if b:
        return pygame.transform.smoothscale(b, (w, h))
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, CARD_BACK, (0, 0, w, h), border_radius=5)
    pygame.draw.rect(s, PURPLE,    (0, 0, w, h), width=1, border_radius=5)
    return s


# ── animated card ─────────────────────────────────────────────────────────────

class ACard:
    def __init__(self, card: Card, x: float, y: float,
                 facedown=False, alpha=255):
        self.card     = card
        self.x        = float(x)
        self.y        = float(y)
        self._tx      = float(x)
        self._ty      = float(y)
        self._lerp    = 0.14
        self.alpha    = alpha
        self.facedown = facedown
        self.glow     = False
        self.glow_col = NEON
        self.shake    = 0
        self.angle    = 0.0

    def go(self, tx, ty, lerp=0.14):
        self._tx, self._ty, self._lerp = tx, ty, lerp

    def update(self):
        self.x += (self._tx - self.x) * self._lerp
        self.y += (self._ty - self.y) * self._lerp
        if self.shake > 0:
            self.shake -= 1

    def draw(self, surf, imgs, font, tick=0):
        dx  = math.sin(self.shake * 1.6) * 4 if self.shake else 0
        cs  = _bsurf(imgs) if self.facedown else _csurf(self.card, imgs, font)
        if self.angle:
            cs = pygame.transform.rotate(cs, self.angle)
        if self.alpha < 255:
            cs = cs.copy(); cs.set_alpha(int(self.alpha))
        px = int(self.x - cs.get_width()  // 2 + dx)
        py = int(self.y - cs.get_height() // 2)
        if self.glow:
            p  = abs(math.sin(tick * 0.005)) * 0.45 + 0.55
            ga = int(p * 150)
            gs = pygame.Surface((cs.get_width() + 14, cs.get_height() + 14), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*self.glow_col, ga), gs.get_rect(), border_radius=9)
            surf.blit(gs, (px - 7, py - 7))
        surf.blit(cs, (px, py))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step base
# ═══════════════════════════════════════════════════════════════════════════════

class Step:
    title    : str = ""
    subtitle : str = ""   # smaller line under title
    body     : str = ""   # narrative text, supports \n
    hint     : str = ""   # bottom-left hint bar (what to do)
    done     : bool = False

    def enter(self, tut: "TutorialScreen"): pass
    def handle_event(self, ev, tut): pass
    def update(self, tut): pass
    def draw_scene(self, surf, tut): pass   # draws into the right panel


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Welcome
# ═══════════════════════════════════════════════════════════════════════════════

class StepWelcome(Step):
    title    = "FOOL'S  HAND"
    subtitle = "a tutorial"
    body     = ("'Fool's Hand' is a Durak card game.\n"
                "The loser is the fool left holding cards.\n\n"
                "This tutorial teaches you everything\n"
                "you need to not be the fool.\n\n"
                "Press NEXT when ready.")
    hint     = "Press NEXT or SPACE to continue"

    def enter(self, tut):
        self.done  = True
        self._tick = 0
        # Scatter some face-down cards as decoration
        self._cards = []
        cx, cy = _SCENE_CX, HEIGHT // 2
        for i in range(7):
            angle = random.uniform(-30, 30)
            ox    = random.randint(-110, 110)
            oy    = random.randint(-80, 80)
            ac    = ACard(Card(Suit.HEARTS, "A"), cx + ox, cy + oy, facedown=True)
            ac.angle = angle
            ac.alpha = 160
            self._cards.append(ac)

    def update(self, tut):
        self._tick += 1

    def draw_scene(self, surf, tut):
        for ac in self._cards:
            ac.draw(surf, tut.imgs, tut.fonts["small"], tut.tick)
        # Floating "?" in the middle
        f  = tut.fonts["title"]
        q  = f.render("?", False, NEON_GLOW)
        qa = int(abs(math.sin(self._tick * 0.04)) * 80 + 140)
        q.set_alpha(qa)
        surf.blit(q, (_SCENE_CX - q.get_width() // 2,
                      HEIGHT // 2 - q.get_height() // 2))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Card ranks chart
# ═══════════════════════════════════════════════════════════════════════════════

class StepRanks(Step):
    title = "CARD  RANKS"
    body  = ("The deck has cards ranked\n"
             "6 through Ace.\n\n"
             "Higher rank beats lower rank,\n"
             "but only within the same suit.\n\n"
             "Hover a card to see its rank value.")
    hint  = "Hover cards to inspect them"

    def enter(self, tut):
        self.done    = True
        self._tick   = 0
        self._hover  = -1
        self._cards  = []
        self._target_pos = []   # final resting positions
        sw, sh = 56, 80
        gap    = 10
        n      = len(RANKS_32)
        cols   = 5
        rows   = math.ceil(n / cols)
        total_w = cols * sw + (cols - 1) * gap
        total_h = rows * (sh + gap) - gap
        # Centre grid in scene, vertically centred with room for bottom labels
        x0 = _SCENE_CX - total_w // 2
        y0 = (HEIGHT - 120) // 2 - total_h // 2 + 20
        for i, rank in enumerate(RANKS_32):
            col  = i % cols
            row  = i // cols
            tx   = x0 + col * (sw + gap) + sw // 2
            ty   = y0 + row * (sh + gap) + sh // 2
            card = Card(Suit.HEARTS, rank)
            # Start from right off-screen, fly into position
            ac   = ACard(card, tx + 300, ty, alpha=0)
            self._cards.append(ac)
            self._target_pos.append((tx, ty))
        self._reveal_tick = 0

    def update(self, tut):
        self._tick += 1
        self._reveal_tick += 1
        mouse = pygame.mouse.get_pos()
        self._hover = -1
        for i, ac in enumerate(self._cards):
            # Use current animated position for hover detection
            r = pygame.Rect(int(ac.x - 28), int(ac.y - 40), 56, 80)
            if r.collidepoint(mouse):
                self._hover = i
        # Fly cards in one by one to their target positions
        for i, ac in enumerate(self._cards):
            if self._reveal_tick > i * 4:
                tx, ty = self._target_pos[i]
                ac.go(tx, ty, lerp=0.18)
                ac.alpha = min(255, ac.alpha + 18)
            ac.update()

    def draw_scene(self, surf, tut):
        sw, sh = 56, 80
        f = tut.fonts["small"]
        for i, ac in enumerate(self._cards):
            w = sw + 10 if i == self._hover else sw
            h = sh + 14 if i == self._hover else sh
            cs = _csurf(ac.card, tut.imgs, f, w, h)
            if ac.alpha < 255:
                cs = cs.copy(); cs.set_alpha(int(ac.alpha))
            px = int(ac.x - w // 2)
            py = int(ac.y - h // 2)
            if i == self._hover:
                gs = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
                pygame.draw.rect(gs, (*NEON, 80), gs.get_rect(), border_radius=7)
                surf.blit(gs, (px - 6, py - 6))
            surf.blit(cs, (px, py))
            if i == self._hover:
                lbl = f.render(f"RANK  {i + 1}  OF  9", False, NEON_GLOW)
                in_top_row = (i < 5)   # cols=5, top row is indices 0-4
                if in_top_row:
                    surf.blit(lbl, (int(ac.x) - lbl.get_width() // 2, py - lbl.get_height() - 5))
                else:
                    surf.blit(lbl, (int(ac.x) - lbl.get_width() // 2, py + h + 4))

        # Weakest / Strongest labels  well above nav bar
        label_y = HEIGHT - 105
        wk = f.render("6 = WEAKEST", False, TEXT_DIM)
        st = f.render("A = STRONGEST", False, GOLD)
        surf.blit(wk, (_SCENE_X + 10, label_y))
        surf.blit(st, (WIDTH - st.get_width() - 14, label_y))
        lx1 = _SCENE_X + wk.get_width() + 14
        lx2 = WIDTH - st.get_width() - 20
        ly  = label_y + 8
        pygame.draw.line(surf, PURPLE, (lx1, ly), (lx2, ly), 1)
        pygame.draw.polygon(surf, GOLD,
            [(lx2, ly), (lx2 - 8, ly - 5), (lx2 - 8, ly + 5)])


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Trump suit
# ═══════════════════════════════════════════════════════════════════════════════

class StepTrump(Step):
    title = "THE  TRUMP  SUIT"
    body  = ("One suit is chosen as TRUMP\nat the start of every game.\n\n"
             "Trump cards have a superpower:\nthey beat ANY non-trump card,\n"
             "no matter the rank.\n\n"
             "Watch the 7♥ beat the K♠.")
    hint  = "Watch the animation"

    def enter(self, tut):
        self.done   = True
        self._tick  = 0
        self._phase = 0   # 0=show both, 1=beat anim, 2=hold
        cx, cy = _SCENE_CX, HEIGHT // 2
        self._king   = ACard(Card(Suit.SPADES, "K"),  cx - 60, cy, alpha=0)
        self._trump7 = ACard(Card(Suit.HEARTS, "7"),  cx + 60, cy, alpha=0)
        self._trump7.glow     = True
        self._trump7.glow_col = NEON_GLOW

    def update(self, tut):
        self._tick += 1
        self._king.alpha   = min(255, self._king.alpha + 8)
        self._trump7.alpha = min(255, self._trump7.alpha + 8)
        self._king.update()
        self._trump7.update()
        if self._tick == 90 and self._phase == 0:
            self._phase = 1
        if self._phase == 1 and self._tick > 90:
            # Trump card lunges toward king
            self._trump7.go(_SCENE_CX - 20, HEIGHT // 2 - 10, lerp=0.1)
            if self._tick > 130:
                self._phase = 2

    def draw_scene(self, surf, tut):
        cx, cy = _SCENE_CX, HEIGHT // 2
        f = tut.fonts["small"]

        self._king.draw(surf, tut.imgs, f, tut.tick)
        self._trump7.draw(surf, tut.imgs, f, tut.tick)

        # Labels
        kl = f.render("K♠  (King, not trump)", False, TEXT_DIM)
        surf.blit(kl, (cx - 60 - kl.get_width() // 2, cy + CH // 2 + 10))
        tl = f.render("7♥  (trump)", False, NEON_GLOW)
        surf.blit(tl, (cx + 60 - tl.get_width() // 2, cy + CH // 2 + 10))

        # Trump label top
        trump_lbl = f.render("TRUMP  SUIT:  ♥ HEARTS", False, NEON_GLOW)
        surf.blit(trump_lbl, (_SCENE_CX - trump_lbl.get_width() // 2, 36))

        if self._phase >= 2:
            beat = tut.fonts["btn"].render("BEATS!", False, _GREEN)
            pulse = abs(math.sin(self._tick * 0.08)) * 5
            bx = _SCENE_CX - beat.get_width() // 2
            surf.blit(beat, (bx, int(cy - CH // 2 - 40 - pulse)))

        if self._phase == 0 and self._tick < 80:
            # VS badge
            vs = tut.fonts["btn"].render("VS", False, PURPLE)
            surf.blit(vs, (cx - vs.get_width() // 2, cy - vs.get_height() // 2))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Beating rules quiz
# ═══════════════════════════════════════════════════════════════════════════════

class StepBeatQuiz(Step):
    title = "CAN  IT  BEAT?"
    body  = ("Test your understanding.\n\n"
             "The attack card is shown.\n"
             "Click YES or NO, does the\n"
             "defending card beat it?\n\n"
             "Trump suit is ♦ Diamonds.")
    hint  = "Click YES or NO"

    _QUIZ = [
        # (attack, defence, answer, explanation)
        (Card(Suit.CLUBS,  "8"), Card(Suit.CLUBS,  "K"), True,
         "K♣ beats 8♣, same suit, higher rank ✓"),
        (Card(Suit.CLUBS,  "K"), Card(Suit.CLUBS,  "8"), False,
         "8♣ can't beat K♣,  same suit but lower ✗"),
        (Card(Suit.SPADES, "A"), Card(Suit.DIAMONDS,"6"), True,
         "6♦ beats A♠, any trump beats any non-trump ✓"),
        (Card(Suit.HEARTS, "9"), Card(Suit.SPADES,  "J"), False,
         "J♠ can't beat 9♥  different suits, no trump ✗"),
        (Card(Suit.DIAMONDS,"7"), Card(Suit.DIAMONDS,"K"), True,
         "K♦ beats 7♦, both trump, higher rank wins ✓"),
    ]

    def enter(self, tut):
        self._tut    = tut          # store reference so _reveal can schedule
        self._trump  = Suit.DIAMONDS
        self._qi     = 0
        self._answered = False
        self._correct  = False
        self._msg      = ""
        self._msg_col  = TEXT_MAIN
        self._msg_tick = 0
        self._score    = 0
        self.done      = False
        self._tick     = 0
        self._set_question()

    def _set_question(self):
        self._answered = False
        self._msg      = ""
        q = self._QUIZ[self._qi]
        cx, cy = _SCENE_CX, HEIGHT // 2 - 20
        self._atk_card  = ACard(q[0], cx - 55, cy, alpha=0)
        self._def_card  = ACard(q[1], cx + 55, cy, alpha=0)
        # buttons
        bw, bh = 90, 38
        self._yes_rect = pygame.Rect(_SCENE_CX - bw - 10, cy + CH // 2 + 30, bw, bh)
        self._no_rect  = pygame.Rect(_SCENE_CX + 10,      cy + CH // 2 + 30, bw, bh)

    def handle_event(self, ev, tut):
        if self._answered:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            answer = self._QUIZ[self._qi][2]
            exp    = self._QUIZ[self._qi][3]
            if self._yes_rect.collidepoint(ev.pos):
                self._reveal(True,  answer, exp)
            elif self._no_rect.collidepoint(ev.pos):
                self._reveal(False, answer, exp)

    def _reveal(self, chose_yes, answer, exp):
        self._answered = True
        self._correct  = (chose_yes == answer)
        self._msg      = exp
        self._msg_col  = _GREEN if self._correct else _RED
        self._msg_tick = 120
        if self._correct:
            self._score += 1
            self._atk_card.glow     = True
            self._def_card.glow     = True
            self._def_card.glow_col = _GREEN
        else:
            self._atk_card.shake = 20
            self._def_card.shake = 20
        self._tut._schedule(80, self._next_q, self._tut)

    def _next_q(self, tut):
        self._qi += 1
        if self._qi >= len(self._QUIZ):
            self.done = True
        else:
            self._set_question()

    def update(self, tut):
        self._tick += 1
        self._atk_card.alpha = min(255, self._atk_card.alpha + 12)
        self._def_card.alpha = min(255, self._def_card.alpha + 12)
        self._atk_card.update()
        self._def_card.update()
        if self._msg_tick > 0:
            self._msg_tick -= 1

    def draw_scene(self, surf, tut):
        cx, cy = _SCENE_CX, HEIGHT // 2 - 20
        f = tut.fonts["small"]

        # Trump label
        tl = f.render("TRUMP: DIAMONDS", False, NEON_GLOW)
        surf.blit(tl, (_SCENE_CX - tl.get_width() // 2, 36))

        # Progress dots
        for i in range(len(self._QUIZ)):
            col = _GREEN if i < self._qi else (NEON_GLOW if i == self._qi else PURPLE_DIM)
            pygame.draw.circle(surf, col,
                               (_SCENE_CX - (len(self._QUIZ) - 1) * 12 + i * 24, 60), 5)

        # Cards
        self._atk_card.draw(surf, tut.imgs, f, tut.tick)
        self._def_card.draw(surf, tut.imgs, f, tut.tick)

        # Labels
        al = f.render("ATTACK", False, _RED)
        surf.blit(al, (cx - 55 - al.get_width() // 2, cy - CH // 2 - 20))
        dl = f.render("DEFENCE?", False, _CYAN)
        surf.blit(dl, (cx + 55 - dl.get_width() // 2, cy - CH // 2 - 20))

        # YES / NO buttons
        mouse = pygame.mouse.get_pos()
        for rect, label, col in [
            (self._yes_rect, "YES ✓", _GREEN),
            (self._no_rect,  "NO  ✗", _RED),
        ]:
            hov  = rect.collidepoint(mouse) and not self._answered
            fill = (*col[:3],) if hov else PURPLE_DIM
            border = col if hov else PURPLE
            pygame.draw.rect(surf, fill,   rect, border_radius=BTN_RADIUS)
            pygame.draw.rect(surf, border, rect, width=2, border_radius=BTN_RADIUS)
            lbl = f.render(label, False, col if hov else TEXT_DIM)
            surf.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                             rect.centery - lbl.get_height() // 2))

        # Feedback message
        if self._msg and self._msg_tick > 0:
            alpha = min(255, self._msg_tick * 6)
            msg = f.render(self._msg, False, self._msg_col)
            msg.set_alpha(alpha)
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2,
                             cy + CH // 2 + 80))

        # Score
        sc = f.render(f"SCORE:  {self._score}/{len(self._QUIZ)}", False, GOLD)
        surf.blit(sc, (WIDTH - sc.get_width() - 10, HEIGHT - 30))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Interactive attack
# ═══════════════════════════════════════════════════════════════════════════════

class StepAttack(Step):
    title = "YOUR  TURN:  ATTACK"
    body  = ("You are the attacker.\n\n"
             "Play any card from your hand\nto start the round.\n\n"
             "The bot must then beat it\nor take the pile.\n\n"
             "Click a card to attack!")
    hint  = "Click any card in your hand to attack"

    def enter(self, tut):
        self.done     = False
        self._phase   = 0   # 0=waiting for click, 1=card flying, 2=bot defends, 3=done
        self._tick    = 0
        trump = Suit.DIAMONDS
        tut._trump_suit = trump

        # Player hand  spaced to fit in scene, lifted clear of nav bar
        hand_cards = [
            Card(Suit.CLUBS,    "9"),
            Card(Suit.HEARTS,   "J"),
            Card(Suit.DIAMONDS, "6"),
            Card(Suit.SPADES,   "K"),
        ]
        n      = len(hand_cards)
        gap    = 14
        hand_w = n * CW + (n - 1) * gap
        hx0    = _SCENE_CX - hand_w // 2 + CW // 2
        hand_y = HEIGHT - CH // 2 - 60   # fully above nav bar

        self._hand = []
        for i, c in enumerate(hand_cards):
            ac          = ACard(c, hx0 + i * (CW + gap), hand_y, alpha=0)
            ac.glow     = True
            ac.glow_col = NEON
            self._hand.append(ac)

        # Bot hand (top, facedown)  centred, clear of top edge
        bot_y = CH // 2 + 50
        self._bot = [
            ACard(Card(Suit.CLUBS, "A"),
                  _SCENE_CX + (i - 1) * (CW + 10), bot_y,
                  facedown=True, alpha=180)
            for i in range(3)
        ]

        self._table      = []
        self._bot_def    = None   # bot's defence card
        self._attacked_card = None
        self._phase2_wait = 0
        self._wait       = 0

    def handle_event(self, ev, tut):
        if self._phase != 0:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for ac in self._hand:
                r = pygame.Rect(int(ac.x - CW//2), int(ac.y - CH//2), CW, CH)
                if r.collidepoint(ev.pos):
                    self._play(ac, tut)
                    return

    def _play(self, ac, tut):
        self._phase = 1
        self._attacked_card = ac
        ac.glow_col = _GREEN
        ac.go(_SCENE_CX - CW // 2 - 8, HEIGHT // 2, lerp=0.14)
        self._table = [ac]
        self._hand  = [c for c in self._hand if c is not ac]
        tut._flash("Good! Watch the bot defend...", _GREEN)
        self._wait = 70

    def update(self, tut):
        self._tick += 1
        for ac in self._hand + self._bot + self._table:
            ac.alpha = min(255, ac.alpha + 8)
            ac.update()
        if self._bot_def:
            self._bot_def.update()

        if self._phase == 1:
            self._wait -= 1
            if self._wait <= 0:
                self._phase = 2
                # Bot defends: pick a card that beats the attack
                # Attack suit is Clubs (9♣/J♥/6♦/K♠ → bot plays K♣ for clubs, or A♦ for diamonds trump)
                atk = self._attacked_card.card
                if atk.suit == Suit.CLUBS:
                    def_card = Card(Suit.CLUBS, "K")
                    reason   = "K of Clubs beats it, same suit, higher rank"
                elif atk.suit == Suit.HEARTS:
                    def_card = Card(Suit.DIAMONDS, "6")
                    reason   = "6 of Diamonds beats it, trump beats any non-trump!"
                elif atk.suit == Suit.DIAMONDS:
                    def_card = Card(Suit.DIAMONDS, "K")
                    reason   = "K of Diamonds beats it, higher trump rank"
                else:
                    def_card = Card(Suit.DIAMONDS, "6")
                    reason   = "6 of Diamonds beats it, trump beats any non-trump!"
                self._bot_def = ACard(def_card, self._bot[0].x, self._bot[0].y)
                self._bot_def.glow     = True
                self._bot_def.glow_col = _AMBER
                self._bot_def.go(_SCENE_CX + CW // 2 + 8, HEIGHT // 2, lerp=0.12)
                tut._flash(reason, _AMBER)
                self._phase2_wait = 130

        if self._phase == 2:
            self._phase2_wait -= 1
            if self._phase2_wait <= 0:
                self.done = True

    def draw_scene(self, surf, tut):
        f = tut.fonts["small"]

        tl = f.render("TRUMP: DIAMONDS", False, NEON_GLOW)
        surf.blit(tl, (WIDTH - tl.get_width() - 14, 14))

        bl = f.render("BOT'S HAND", False, TEXT_DIM)
        surf.blit(bl, (_SCENE_CX - bl.get_width() // 2, 14))

        # Hand label above cards
        hand_top = int(self._hand[0].y if self._hand else HEIGHT - 120) - CH // 2
        yl = f.render("YOUR HAND  CLICK TO ATTACK", False, NEON)
        surf.blit(yl, (_SCENE_CX - yl.get_width() // 2, hand_top - 22))

        # Table slot outlines when empty
        if self._phase >= 1:
            atk_slot = pygame.Rect(_SCENE_CX - CW - 8, HEIGHT // 2 - CH // 2, CW, CH)
            def_slot = pygame.Rect(_SCENE_CX + 8,       HEIGHT // 2 - CH // 2, CW, CH)
            if self._phase < 2:
                pygame.draw.rect(surf, PURPLE_DIM, def_slot, border_radius=5)
                pygame.draw.rect(surf, PURPLE, def_slot, width=1, border_radius=5)
                q = f.render("?", False, PURPLE)
                surf.blit(q, (def_slot.centerx - q.get_width() // 2,
                               def_slot.centery - q.get_height() // 2))

            # Table labels
            al = f.render("ATTACK", False, _RED)
            surf.blit(al, (atk_slot.centerx - al.get_width() // 2,
                            atk_slot.top - 22))
            dl = f.render("DEFENCE", False, _GREEN if self._phase >= 2 else TEXT_DIM)
            surf.blit(dl, (def_slot.centerx - dl.get_width() // 2,
                            def_slot.top - 22))

        for ac in self._bot + self._table + self._hand:
            ac.draw(surf, tut.imgs, f, tut.tick)
        if self._bot_def:
            self._bot_def.draw(surf, tut.imgs, f, tut.tick)


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Interactive defence
# ═══════════════════════════════════════════════════════════════════════════════

class StepDefend(Step):
    title = "YOUR  TURN:  DEFEND"
    body  = ("The bot attacked.\n\n"
             "To defend, play a card that\nbeats the attack card:\n\n"
             "  • Higher rank, same suit\n"
             "  • OR any trump card (♦)\n\n"
             "Invalid cards will be rejected.\nTry both to see what happens!")
    hint  = "Click a card to defend. Green = valid, Red = invalid"

    def enter(self, tut):
        self.done   = False
        self._phase = 0
        self._tick  = 0
        trump = Suit.DIAMONDS
        tut._trump_suit = trump

        # Table zone: upper-centre of scene, attack card on left slot
        table_y = HEIGHT // 2 - CH // 2 - 20   # top of card area
        self._atk_x = _SCENE_CX - CW - 16       # left slot
        self._def_x = _SCENE_CX + 16            # right slot (empty until defended)
        self._table_y = table_y + CH // 2

        self._atk = ACard(Card(Suit.CLUBS, "8"),
                          self._atk_x + CW // 2, self._table_y, alpha=0)

        # Player hand  4 cards, spaced to fit within scene width with margin
        self._hand_cards = [
            Card(Suit.CLUBS,    "K"),     # valid: higher same suit
            Card(Suit.DIAMONDS, "6"),     # valid: trump
            Card(Suit.HEARTS,   "J"),     # invalid: wrong suit
            Card(Suit.CLUBS,    "6"),     # invalid: lower same suit
        ]
        self._valid = {0: True, 1: True, 2: False, 3: False}

        n      = len(self._hand_cards)
        gap    = 14
        hand_w = n * CW + (n - 1) * gap
        # Centre in scene, with margin from edges
        hx0    = max(_SCENE_X + 20, _SCENE_CX - hand_w // 2)
        hand_y = HEIGHT - CH // 2 - 58   # above nav bar (nav at HEIGHT-54)

        self._hand = []
        for i, c in enumerate(self._hand_cards):
            ac          = ACard(c, hx0 + i * (CW + gap) + CW // 2, hand_y, alpha=0)
            ac.glow     = True
            ac.glow_col = _GREEN if self._valid[i] else _RED
            self._hand.append(ac)

        self._def_card  = None
        self._msg       = ""
        self._msg_col   = TEXT_MAIN
        self._msg_tick  = 0
        self._wait      = 0

    def handle_event(self, ev, tut):
        if self._phase != 0:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, ac in enumerate(self._hand):
                r = pygame.Rect(int(ac.x - CW//2), int(ac.y - CH//2), CW, CH)
                if r.collidepoint(ev.pos):
                    self._try(i, ac, tut)
                    return

    def _try(self, i, ac, tut):
        if self._valid[i]:
            self._phase = 1
            ac.glow_col = _GREEN
            # Fly to the RIGHT table slot  clearly separate from attack card
            ac.go(self._def_x + CW // 2, self._table_y, lerp=0.16)
            self._def_card = ac
            self._hand = [c for c in self._hand if c is not ac]
            self._msg  = "Correct! That card beats the attack."
            self._msg_col = _GREEN
            self._msg_tick = 120
            tut._flash("Defended! The pile gets discarded.", _GREEN)
            self._wait = 100
        else:
            ac.shake = 22
            if ac.card.suit == self._atk.card.suit:
                self._msg = f"{ac.card}  same suit but lower rank."
            else:
                self._msg = f"{ac.card}  wrong suit, not trump."
            self._msg_col  = _RED
            self._msg_tick = 100
            tut._flash("That card can't beat 8 of Clubs. Try a valid one.", _RED)

    def update(self, tut):
        self._tick += 1
        self._atk.alpha = min(255, self._atk.alpha + 8)
        self._atk.update()
        if self._def_card:
            self._def_card.update()
        for ac in self._hand:
            ac.alpha = min(255, ac.alpha + 8)
            ac.update()
        if self._msg_tick > 0:
            self._msg_tick -= 1
        if self._phase == 1:
            self._wait -= 1
            if self._wait <= 0:
                self.done = True

    def draw_scene(self, surf, tut):
        f = tut.fonts["small"]

        # Trump indicator  inside right panel, top right
        tl = f.render("TRUMP: DIAMONDS", False, NEON_GLOW)
        surf.blit(tl, (WIDTH - tl.get_width() - 14, 14))

        # Attack label above the table area
        table_top = self._table_y - CH // 2
        al = f.render("BOT ATTACKS WITH:", False, _RED)
        surf.blit(al, (_SCENE_CX - al.get_width() // 2, table_top - 24))

        # Attack card (left slot)
        self._atk.draw(surf, tut.imgs, f, tut.tick)

        # Empty right slot outline (shows where defence goes)
        if self._def_card is None:
            slot = pygame.Rect(self._def_x, self._table_y - CH // 2, CW, CH)
            pygame.draw.rect(surf, PURPLE_DIM, slot, border_radius=5)
            pygame.draw.rect(surf, PURPLE,     slot, width=1, border_radius=5)
            q = f.render("?", False, PURPLE)
            surf.blit(q, (slot.centerx - q.get_width() // 2,
                          slot.centery - q.get_height() // 2))
        else:
            self._def_card.draw(surf, tut.imgs, f, tut.tick)

        # Hand label above the hand, below feedback zone
        hand_top = int(self._hand[0].y if self._hand else HEIGHT - CH - 58) - CH // 2
        yl = f.render("YOUR HAND: CLICK TO DEFEND", False, NEON)
        surf.blit(yl, (_SCENE_CX - yl.get_width() // 2, hand_top - 22))

        for ac in self._hand:
            ac.draw(surf, tut.imgs, f, tut.tick)

        # Card validity labels beneath each card
        labels = ["K CLUBS\nvalid", "6 DIAMONDS\ntrump", "J HEARTS\nwrong", "6 CLUBS\nlow"]
        cols   = [_GREEN, _GREEN, _RED, _RED]
        for i, ac in enumerate(self._hand):
            if i < len(labels):
                for li, line in enumerate(labels[i].split("\n")):
                    lbl = f.render(line, False, cols[i])
                    surf.blit(lbl, (int(ac.x) - lbl.get_width() // 2,
                                     int(ac.y) + CH // 2 + 4 + li * 14))

        # Inline feedback message
        if self._msg and self._msg_tick > 0:
            alpha = min(255, self._msg_tick * 6)
            msg = f.render(self._msg, False, self._msg_col)
            msg.set_alpha(alpha)
            my = self._table_y + CH // 2 + 14
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2, my))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Pile-on mechanic
# ═══════════════════════════════════════════════════════════════════════════════

class StepPileOn(Step):
    title = "PILE-ON:  MORE  ATTACKS"
    body  = ("After the first attack,\nyou can pile on more cards\n"
             "but only cards that match\na rank already on the table.\n\n"
             "The defender must beat\nevery card piled on.\n\n"
             "Watch the example. It loops.")
    hint  = "Watch the animation, it loops automatically"

    # Timing constants (ticks)  slow enough to follow
    _T_ATK1_IN   = 40
    _T_ATK1_LBL  = 90
    _T_ATK2_IN   = 130
    _T_ATK2_LBL  = 180
    _T_DEF1_IN   = 260
    _T_DEF2_IN   = 340
    _T_GLOW      = 420
    _T_PAUSE     = 520   # hold final state before looping
    _T_LOOP      = 580   # restart

    def enter(self, tut):
        self.done   = True
        self._tick  = 0
        self._reset_cards()

    def _reset_cards(self):
        cx, cy = _SCENE_CX, HEIGHT // 2 - 20
        self._atk1   = ACard(Card(Suit.SPADES, "9"), cx - CW - 18, cy, alpha=0)
        self._atk2   = ACard(Card(Suit.CLUBS,  "9"), cx + CW + 18, cy, alpha=0)
        self._def1   = ACard(Card(Suit.SPADES, "J"), cx - CW - 18, cy, alpha=0)
        self._def2   = ACard(Card(Suit.CLUBS,  "K"), cx + CW + 18, cy, alpha=0)
        self._show_atk1  = False
        self._show_atk2  = False
        self._show_def1  = False
        self._show_def2  = False
        self._show_lbl1  = False
        self._show_lbl2  = False
        self._glow_on    = False

    def update(self, tut):
        self._tick += 1
        t = self._tick

        # Loop
        if t >= self._T_LOOP:
            self._tick = 0
            self._reset_cards()
            return

        # Phase triggers
        if t == self._T_ATK1_IN:
            self._show_atk1 = True
        if t == self._T_ATK1_LBL:
            self._show_lbl1 = True
        if t == self._T_ATK2_IN:
            self._show_atk2 = True
        if t == self._T_ATK2_LBL:
            self._show_lbl2 = True
        if t == self._T_DEF1_IN:
            self._show_def1 = True
        if t == self._T_DEF2_IN:
            self._show_def2 = True
        if t == self._T_GLOW:
            self._glow_on = True
            self._def1.glow     = True
            self._def1.glow_col = _GREEN
            self._def2.glow     = True
            self._def2.glow_col = _GREEN
            self._atk2.glow     = True
            self._atk2.glow_col = _AMBER

        if self._show_atk1: self._atk1.alpha = min(255, self._atk1.alpha + 6)
        if self._show_atk2: self._atk2.alpha = min(255, self._atk2.alpha + 6)
        if self._show_def1: self._def1.alpha = min(255, self._def1.alpha + 6)
        if self._show_def2: self._def2.alpha = min(255, self._def2.alpha + 6)

        for ac in [self._atk1, self._atk2, self._def1, self._def2]:
            ac.update()

    def draw_scene(self, surf, tut):
        f  = tut.fonts["small"]
        cx, cy = _SCENE_CX, HEIGHT // 2 - 20
        t = self._tick

        # ── Attack cards row (centre of scene) ──────────────────────────────
        if self._show_atk1:
            self._atk1.draw(surf, tut.imgs, f, tut.tick)
        if self._show_atk2:
            self._atk2.draw(surf, tut.imgs, f, tut.tick)

        # ── Defence cards (offset above attack slots) ────────────────────────
        def_offset = CH + 20
        if self._show_def1:
            # Temporarily move def card to its "on top of attack" position
            self._def1.x = cx - CW - 18
            self._def1.y = cy - def_offset // 2
            self._def1.draw(surf, tut.imgs, f, tut.tick)
        if self._show_def2:
            self._def2.x = cx + CW + 18
            self._def2.y = cy - def_offset // 2
            self._def2.draw(surf, tut.imgs, f, tut.tick)

        # ── Labels ──────────────────────────────────────────────────────────
        if self._show_lbl1:
            l = f.render("9 of SPADES: ATTACK", False, _RED)
            surf.blit(l, (cx - CW - 18 - l.get_width() // 2, cy + CH // 2 + 8))

        if self._show_lbl2:
            for li, line in enumerate(["9 of CLUBS: PILE ON", "(same rank = allowed!)"]):
                col = _AMBER if li == 1 else _RED
                l   = f.render(line, False, col)
                surf.blit(l, (cx + CW + 18 - l.get_width() // 2,
                               cy + CH // 2 + 8 + li * 16))

        if self._show_def1:
            l = f.render("J beats 9", False, _GREEN)
            surf.blit(l, (cx - CW - 18 - l.get_width() // 2,
                           cy - def_offset // 2 - CH // 2 - 18))
        if self._show_def2:
            l = f.render("K beats 9", False, _GREEN)
            surf.blit(l, (cx + CW + 18 - l.get_width() // 2,
                           cy - def_offset // 2 - CH // 2 - 18))

        # ── Progress annotation ──────────────────────────────────────────────
        if t > self._T_GLOW:
            msg = f.render("Both defended! Pile discarded.", False, _GREEN)
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2,
                             cy + CH // 2 + 55))
        elif t > self._T_DEF1_IN:
            msg = f.render("Defender must beat BOTH attacks.", False, _AMBER)
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2,
                             cy + CH // 2 + 55))
        elif t > self._T_ATK2_LBL:
            msg = f.render("Attacker piles on a second 9.", False, _AMBER)
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2,
                             cy + CH // 2 + 55))
        elif t > self._T_ATK1_LBL:
            msg = f.render("Attacker plays 9 of Spades.", False, TEXT_DIM)
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2,
                             cy + CH // 2 + 55))

        # Loop counter in corner
        loop_n = self._tick // self._T_LOOP if self._T_LOOP > 0 else 0
        prog = f.render(f"looping...", False, PURPLE_DIM)
        surf.blit(prog, (WIDTH - prog.get_width() - 14, HEIGHT - 110))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Taking the pile
# ═══════════════════════════════════════════════════════════════════════════════

class StepTake(Step):
    title = "TAKING  THE  PILE"
    body  = ("If you can't beat every\nattack card on the table,\nyou take the whole pile.\n\n"
             "Note: attackers can never\npile on MORE cards than the\ndefender holds, so the\ndefender can always fight back.\n\n"
             "Click TAKE PILE below.")
    hint  = "Click TAKE PILE to see what happens"

    def enter(self, tut):
        self.done   = False
        self._phase = 0
        self._tick  = 0
        hand_y = HEIGHT - CH // 2 - 65   # safely above nav bar

        # Table: 3 attack cards, centred
        cx, cy = _SCENE_CX, HEIGHT // 2 - 60
        self._atk_cards = [
            ACard(Card(Suit.SPADES, "A"), cx - CW - 14, cy),
            ACard(Card(Suit.CLUBS,  "K"), cx,           cy),
            ACard(Card(Suit.HEARTS, "Q"), cx + CW + 14, cy),
        ]

        # Player's 3-card hand (matches 3 attack cards), above nav bar
        self._hand = [
            ACard(Card(Suit.CLUBS,  "6"), cx - CW - 14, hand_y),
            ACard(Card(Suit.SPADES, "7"), cx,           hand_y),
            ACard(Card(Suit.HEARTS, "8"), cx + CW + 14, hand_y),
        ]

        bw, bh = 140, 42
        self._take_btn = pygame.Rect(_SCENE_CX - bw // 2, cy + CH // 2 + 28, bw, bh)
        self._wait = 0

        # After taking: spread all 6 cards (3 pile + 3 hand) evenly
        total  = len(self._atk_cards) + len(self._hand)   # 6
        gap    = 10
        full_w = total * CW + (total - 1) * gap
        hx0    = _SCENE_CX - full_w // 2 + CW // 2
        self._take_targets = [(hx0 + i * (CW + gap), hand_y) for i in range(total)]

    def handle_event(self, ev, tut):
        if self._phase != 0:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._take_btn.collidepoint(ev.pos):
                self._phase = 1
                # Existing hand cards slide to slots 3,4,5
                for i, ac in enumerate(self._hand):
                    tx, ty = self._take_targets[3 + i]
                    ac.go(tx, ty, lerp=0.1)
                # Pile cards fly to slots 0,1,2
                for i, ac in enumerate(self._atk_cards):
                    ac.glow     = True
                    ac.glow_col = _RED
                    tx, ty = self._take_targets[i]
                    ac.go(tx, ty, lerp=0.07)
                tut._flash("6 cards now in your hand, ouch!", _RED)
                self._wait = 150

    def update(self, tut):
        self._tick += 1
        for ac in self._atk_cards + self._hand:
            ac.update()
        if self._phase == 1:
            self._wait -= 1
            if self._wait <= 0:
                self.done = True

    def draw_scene(self, surf, tut):
        f     = tut.fonts["small"]
        mouse = pygame.mouse.get_pos()
        cx, cy = _SCENE_CX, HEIGHT // 2 - 60

        al = f.render("BOT ATTACKS WITH ALL THREE:", False, _RED)
        surf.blit(al, (_SCENE_CX - al.get_width() // 2, cy - CH // 2 - 24))

        for ac in self._atk_cards + self._hand:
            ac.draw(surf, tut.imgs, f, tut.tick)

        hand_y = HEIGHT - CH // 2 - 65
        yl = f.render("YOUR HAND", False, TEXT_DIM)
        surf.blit(yl, (_SCENE_CX - yl.get_width() // 2, hand_y - CH // 2 - 22))

        if self._phase == 0:
            hov = self._take_btn.collidepoint(mouse)
            pygame.draw.rect(surf, _RED_D if hov else PURPLE_DIM,
                              self._take_btn, border_radius=BTN_RADIUS)
            pygame.draw.rect(surf, _RED if hov else PURPLE,
                              self._take_btn, width=2, border_radius=BTN_RADIUS)
            lbl = f.render("TAKE PILE", False, _RED if hov else TEXT_DIM)
            surf.blit(lbl, (self._take_btn.centerx - lbl.get_width() // 2,
                             self._take_btn.centery - lbl.get_height() // 2))

        if self._phase == 1 and self._tick > 80:
            msg = f.render("All 6 cards are now in your hand!", False, _RED)
            surf.blit(msg, (_SCENE_CX - msg.get_width() // 2, cy + CH // 2 + 80))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Drawing up
# ═══════════════════════════════════════════════════════════════════════════════

class StepDraw(Step):
    title = "DRAWING  UP"
    body  = ("After every round both\nplayers draw from the deck\nuntil they hold 6 cards.\n\n"
             "The attacker draws first.\n\n"
             "Once the deck is empty,\nno more drawing. Every card\nin your hand is precious.")
    hint  = "Watch the animation: shows full deck then empty"

    # All timing in ticks (60 fps)
    _DEAL_START  = 50     # first card fires
    _DEAL_GAP    = 55     # gap between each card leaving deck
    _CARDS_DEALT = 3
    # Last card fires at DEAL_START + 2*DEAL_GAP = 160
    # Give ~120 ticks for cards to land + read labels before switching
    _EMPTY_START = 50 + 2 * 55 + 150   # = 310
    _EMPTY_HOLD  = 220                   # time to show empty state
    _LOOP        = 310 + 220             # = 530

    def enter(self, tut):
        self.done         = True
        self._tick        = 0
        self._phase       = 0
        self._flying      = []   # list of (ACard, slot_index)
        self._hand_y      = HEIGHT - CH // 2 - 65

        # Unified 6-slot grid existing cards at 0,1,2; new cards at 3,4,5
        full_gap = 12
        full_w   = 6 * CW + 5 * full_gap
        hx0      = _SCENE_CX - full_w // 2 + CW // 2
        self._slots = [(hx0 + i * (CW + full_gap), self._hand_y) for i in range(6)]

        # Deck position left of centre so hand fits on the right
        self._deck_x = _SCENE_CX - 220
        self._deck_y = HEIGHT // 2 - CH // 2 - 20
        self._deck_count = 8

        # Existing hand: 3 face-up cards at slots 0,1,2
        self._hand_cards = []
        for i, c in enumerate([Card(Suit.SPADES, "9"),
                                Card(Suit.HEARTS, "J"),
                                Card(Suit.CLUBS,  "7")]):
            sx, sy = self._slots[i]
            self._hand_cards.append(ACard(c, sx, sy))

    def _reset(self):
        self._tick       = 0
        self._phase      = 0
        self._flying     = []
        self._deck_count = 8
        # Reset hand cards back to slots 0,1,2
        for i, ac in enumerate(self._hand_cards):
            sx, sy = self._slots[i]
            ac.x, ac.y = sx, sy
            ac._tx, ac._ty = sx, sy

    def update(self, tut):
        self._tick += 1
        t = self._tick

        if t >= self._LOOP:
            self._reset()
            return

        if self._phase == 0:
            # Fire one card per _DEAL_GAP
            for i in range(self._CARDS_DEALT):
                if t == self._DEAL_START + i * self._DEAL_GAP:
                    sx, sy = self._slots[3 + i]
                    ac = ACard(Card(Suit.HEARTS, "A"),
                               self._deck_x + CW // 2,
                               self._deck_y + CH // 2,
                               facedown=True)
                    ac.go(sx, sy, lerp=0.09)
                    self._flying.append((ac, i))
                    self._deck_count -= 1

            # Flip face-up once within ~25px of target
            reveal_cards = [Card(Suit.DIAMONDS, "8"),
                            Card(Suit.CLUBS,    "Q"),
                            Card(Suit.SPADES,   "K")]
            for ac, idx in self._flying:
                ac.update()
                sx, sy = self._slots[3 + idx]
                if abs(ac.x - sx) + abs(ac.y - sy) < 25 and ac.facedown:
                    ac.facedown = False
                    ac.card     = reveal_cards[idx]

            if t == self._EMPTY_START:
                self._phase = 1

        for ac in self._hand_cards:
            ac.update()

    def draw_scene(self, surf, tut):
        f  = tut.fonts["small"]
        cx = _SCENE_CX
        dx, dy = self._deck_x, self._deck_y

        # ── Hand label ─────────────────────────────────────────────────────
        yl = f.render("YOUR HAND", False, NEON)
        surf.blit(yl, (cx - yl.get_width() // 2,
                       self._hand_y - CH // 2 - 22))

        # ── Existing hand cards (always visible) ───────────────────────────
        for ac in self._hand_cards:
            ac.draw(surf, tut.imgs, f, tut.tick)

        # ── Flying draw cards ──────────────────────────────────────────────
        for ac, _ in self._flying:
            ac.draw(surf, tut.imgs, f, tut.tick)

        # ── Deck (phase 0) ─────────────────────────────────────────────────
        if self._phase == 0:
            rem = self._deck_count
            if rem > 0:
                for i in range(min(rem, 5)):
                    bs = _bsurf(tut.imgs, CW, CH)
                    surf.blit(bs, (dx + i * 2, dy - i * 2))
            else:
                # deck visually empty draw outline
                s = pygame.Rect(dx, dy, CW, CH)
                pygame.draw.rect(surf, PURPLE_DIM, s, border_radius=5)
                pygame.draw.rect(surf, PURPLE, s, width=1, border_radius=5)

            cnt = f.render(f"{rem} left in deck", False,
                           NEON_GLOW if rem > 0 else _RED)
            surf.blit(cnt, (dx + CW // 2 - cnt.get_width() // 2, dy + CH + 8))
            dl = f.render("DECK", False, TEXT_DIM)
            surf.blit(dl, (dx + CW // 2 - dl.get_width() // 2, dy - 20))

            # Arrow while cards are flying
            if self._flying:
                sx, sy = self._slots[5]
                pygame.draw.line(surf, PURPLE_DIM,
                                 (dx + CW, dy + CH // 2),
                                 (sx - CW // 2 - 10, sy), 1)

            msg = f.render("Drawing up to 6...", False, TEXT_DIM)
            surf.blit(msg, (cx - msg.get_width() // 2,
                            self._hand_y - CH // 2 - 42))

        # ── Empty deck (phase 1) ───────────────────────────────────────────
        else:
            s = pygame.Rect(dx, dy, CW, CH)
            pygame.draw.rect(surf, PURPLE_DIM, s, border_radius=5)
            pygame.draw.rect(surf, PURPLE,     s, width=1, border_radius=5)
            xl = f.render("EMPTY", False, _RED)
            surf.blit(xl, (dx + CW // 2 - xl.get_width() // 2,
                            dy + CH // 2 - xl.get_height() // 2))
            dl = f.render("DECK", False, TEXT_DIM)
            surf.blit(dl, (dx + CW // 2 - dl.get_width() // 2, dy - 20))

            pulse = abs(math.sin(self._tick * 0.08))
            warn = tut.fonts["btn"].render("DECK EMPTY!", False, _RED)
            surf.blit(warn, (cx - warn.get_width() // 2, dy + 10))
            sub = f.render("No more drawing, every card counts.", False, _AMBER)
            surf.blit(sub, (cx - sub.get_width() // 2, dy + 46))


# ═══════════════════════════════════════════════════════════════════════════════
#  Step: Win condition
# ═══════════════════════════════════════════════════════════════════════════════

class StepWin(Step):
    title = "HOW  TO  WIN"
    body  = ("The first player to empty\ntheir hand after the\ndeck runs out, WINS.\n\n"
             "The last player still holding\ncards is the DURAK.\n\nThe fool.\n\n"
             "Don't. Be. The. Fool.")
    hint  = "Click PLAY NOW when ready!"

    def enter(self, tut):
        self.done   = True
        self._tick  = 0
        self._cards = []
        cx, cy = _SCENE_CX, HEIGHT // 2
        # Start with a full hand of 6, then discard one by one
        ranks = ["6", "7", "8", "9", "J", "K"]
        suits = [Suit.CLUBS, Suit.HEARTS, Suit.SPADES,
                 Suit.DIAMONDS, Suit.CLUBS, Suit.HEARTS]
        for i in range(6):
            ac = ACard(Card(suits[i], ranks[i]),
                       cx - (5 - i) * (CW // 2), cy)
            ac.alpha = 200
            self._cards.append(ac)
        self._discarded = 0

    def update(self, tut):
        self._tick += 1
        if self._tick % 50 == 0 and self._discarded < len(self._cards):
            ac           = self._cards[self._discarded]
            ac.glow      = True
            ac.glow_col  = _GREEN
            # fly off screen upward
            ac.go(_SCENE_CX, -CH, lerp=0.1)
            self._discarded += 1
        for ac in self._cards:
            ac.update()

    def draw_scene(self, surf, tut):
        f  = tut.fonts["small"]
        remaining = len(self._cards) - self._discarded
        for ac in self._cards:
            if ac.y > 0:
                ac.draw(surf, tut.imgs, f, tut.tick)

        if remaining == 0:
            win = tut.fonts["btn"].render("YOU  WIN!", False, _GREEN)
            pulse = abs(math.sin(self._tick * 0.07)) * 8
            surf.blit(win, (_SCENE_CX - win.get_width() // 2,
                             HEIGHT // 2 - win.get_height() // 2 - int(pulse)))
        else:
            lbl = tut.fonts["small"].render(f"{remaining} cards remaining", False, TEXT_DIM)
            surf.blit(lbl, (_SCENE_CX - lbl.get_width() // 2, HEIGHT // 2 + 60))


# ═══════════════════════════════════════════════════════════════════════════════
#  TutorialScreen
# ═══════════════════════════════════════════════════════════════════════════════

class TutorialScreen:
    """Full interactive tutorial. Returns 'menu' or 'play' from handle_event."""

    _STEPS = [
        StepWelcome,
        StepRanks,
        StepTrump,
        StepBeatQuiz,
        StepAttack,
        StepDefend,
        StepPileOn,
        StepTake,
        StepDraw,
        StepWin,
    ]

    def __init__(self, screen: pygame.Surface, fonts: dict,
                 vignette: pygame.Surface) -> None:
        self.screen    = screen
        self.fonts     = fonts
        self._vignette = vignette
        self.tick      = 0
        self.imgs      = _load_images()

        self._steps      = [cls() for cls in self._STEPS]
        self._idx        = 0
        self._trump_suit = Suit.HEARTS

        # Typewriter state
        self._tw_chars = 0
        self._tw_tick  = 0
        self._TW_SPEED = 1   # chars per tick

        # Flash message (feedback overlay)
        self._flash_msg  = ""
        self._flash_col  = TEXT_MAIN
        self._flash_tick = 0

        # Scheduled callbacks: [(tick_to_fire, fn, tut), ...]
        self._scheduled: list = []

        # Buttons  all along the bottom bar, never overlapping the scene
        bh     = 42
        bw     = 150
        bar_y  = HEIGHT - bh - 12   # bottom nav bar y
        # MENU: bottom-left of LEFT panel only
        self._menu_rect = pygame.Rect(12, bar_y, 120, bh)
        # BACK / NEXT: bottom-right of entire screen (right panel)
        self._next_rect = pygame.Rect(WIDTH - bw - 12,      bar_y, bw, bh)
        self._back_rect = pygame.Rect(WIDTH - bw * 2 - 28,  bar_y, bw, bh)
        # PLAY NOW: centred in right panel bottom
        self._play_rect = pygame.Rect(_SCENE_CX - 110, bar_y, 220, bh)

        self._enter(0)

    # ── public ───────────────────────────────────────────────────────────────

    def handle_event(self, ev) -> str | None:
        if ev.type == pygame.QUIT:
            return "menu"
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return "menu"
            if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                self._try_next()

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._menu_rect.collidepoint(ev.pos):
                return "menu"
            last = (self._idx == len(self._steps) - 1)
            if last and self._play_rect.collidepoint(ev.pos):
                return "play"
            if not last and self._next_rect.collidepoint(ev.pos):
                self._try_next()
            if self._idx > 0 and self._back_rect.collidepoint(ev.pos):
                self._enter(self._idx - 1)

        step = self._steps[self._idx]
        step.handle_event(ev, self)
        return None

    def update(self) -> None:
        self.tick += 1

        # Typewriter
        step     = self._steps[self._idx]
        full_len = len(step.body)
        self._tw_tick += self._TW_SPEED
        if self._tw_tick >= 1:
            self._tw_tick = 0
            if self._tw_chars < full_len:
                self._tw_chars = min(self._tw_chars + 2, full_len)

        step.update(self)

        if self._flash_tick > 0:
            self._flash_tick -= 1

        # Scheduled callbacks
        remaining = []
        for (fire_at, fn, tut) in self._scheduled:
            if self.tick >= fire_at:
                fn(tut)
            else:
                remaining.append((fire_at, fn, tut))
        self._scheduled = remaining

    def draw(self, surface=None) -> None:
        t = surface or self.screen
        t.fill(BG)
        self._draw_grid(t)
        t.blit(self._vignette, (0, 0))
        self._draw_divider(t)
        self._draw_left(t)
        self._draw_right(t)
        self._draw_progress(t)
        self._draw_nav(t)
        self._draw_flash(t)

    # ── internal ──────────────────────────────────────────────────────────────

    def _enter(self, idx: int) -> None:
        self._idx      = idx
        self._tw_chars = 0
        self._tw_tick  = 0
        self._flash_msg = ""
        self._flash_tick = 0
        self._scheduled  = []
        step = self._steps[idx]
        step.done = False
        step.enter(self)

    def _try_next(self) -> None:
        step = self._steps[self._idx]
        # Finish typewriter instantly first
        if self._tw_chars < len(step.body):
            self._tw_chars = len(step.body)
            return
        if step.done and self._idx < len(self._steps) - 1:
            self._enter(self._idx + 1)

    def _flash(self, msg: str, col=TEXT_MAIN) -> None:
        self._flash_msg  = msg
        self._flash_col  = col
        self._flash_tick = 160

    def _schedule(self, delay: int, fn, tut) -> None:
        self._scheduled.append((self.tick + delay, fn, tut))

    # ── drawing ───────────────────────────────────────────────────────────────

    def _draw_grid(self, t) -> None:
        for x in range(0, WIDTH, 40):
            pygame.draw.line(t, (30, 15, 50), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 40):
            pygame.draw.line(t, (30, 15, 50), (0, y), (WIDTH, y))

    def _draw_divider(self, t) -> None:
        # Vertical neon line splitting left/right
        pygame.draw.line(t, PURPLE,    (_SPLIT, 0), (_SPLIT, HEIGHT), 1)
        pygame.draw.line(t, NEON_DARK, (_SPLIT - 1, 0), (_SPLIT - 1, HEIGHT), 1)

    def _draw_left(self, t) -> None:
        # Hard-clip everything to the left panel so nothing bleeds past the divider
        t.set_clip(pygame.Rect(0, 0, _SPLIT - 2, HEIGHT))

        step   = self._steps[self._idx]
        f_big  = self.fonts["btn"]
        f_body = self.fonts["btn"]    # use btn font (16px) for body instead of 8px small
        f_sm   = self.fonts["small"]
        pad    = 20
        x      = pad
        y      = 56   # start below the progress bar row

        # ── Step title ──────────────────────────────────────────────────────
        max_w = _SPLIT - pad * 2

        # Word-wrap title to fit panel
        words    = step.title.split()
        lines_t  = []
        cur_line = ""
        for w in words:
            test = (cur_line + "  " + w).strip() if cur_line else w
            if f_big.render(test, False, TEXT_MAIN).get_width() > max_w:
                if cur_line:
                    lines_t.append(cur_line)
                cur_line = w
            else:
                cur_line = test
        if cur_line:
            lines_t.append(cur_line)

        for line in lines_t:
            for off, alpha in [(5, 20), (2, 50)]:
                g = f_big.render(line, False, NEON_GLOW)
                g.set_alpha(alpha)
                t.blit(g, (x - off // 2, y)); t.blit(g, (x + off // 2, y))
            ts = f_big.render(line, False, TEXT_MAIN)
            t.blit(ts, (x, y))
            y += ts.get_height() + 2

        # underline
        y += 6
        pygame.draw.rect(t, NEON, (x, y, max_w, 2))
        y += 14

        # ── Body text typewriter with word-wrap ──────────────────────────────
        # Leave room for hint bar (≈40px) + nav buttons (54px) + breathing room
        body_max_y = HEIGHT - 130
        show  = step.body[:self._tw_chars]

        # Word-wrap every paragraph line to max_w
        wrapped_lines = []
        for raw_line in show.split("\n"):
            if raw_line.strip() == "":
                wrapped_lines.append("")
                continue
            words_b = raw_line.split(" ")
            cur = ""
            for w in words_b:
                test = (cur + " " + w).strip() if cur else w
                if f_body.render(test, False, TEXT_DIM).get_width() > max_w:
                    if cur:
                        wrapped_lines.append(cur)
                    cur = w
                else:
                    cur = test
            if cur:
                wrapped_lines.append(cur)

        lh = f_body.get_height() + 8
        for line in wrapped_lines:
            if y + lh > body_max_y:
                break
            ls = f_body.render(line, False, TEXT_DIM)
            t.blit(ls, (x, y))
            y += lh

        # blinking cursor
        if self._tw_chars < len(step.body) and y < body_max_y:
            if (self.tick // 18) % 2 == 0:
                pygame.draw.rect(t, NEON, (x, y, 2, f_body.get_height()))

        # ── Hint bar well above nav buttons (bar_y = HEIGHT-54) ────────────
        if step.hint:
            hy = HEIGHT - 140
            pygame.draw.line(t, PURPLE, (pad, hy), (_SPLIT - pad, hy), 1)
            # Word-wrap hint text
            hint_words = step.hint.split(" ")
            hint_lines = []
            cur_h = ""
            for w in hint_words:
                test = (cur_h + " " + w).strip() if cur_h else w
                if f_sm.render(test, False, TEXT_DIM).get_width() > max_w:
                    if cur_h: hint_lines.append(cur_h)
                    cur_h = w
                else:
                    cur_h = test
            if cur_h: hint_lines.append(cur_h)
            for li, hl_line in enumerate(hint_lines):
                hl = f_sm.render(hl_line, False, TEXT_DIM)
                t.blit(hl, (pad, hy + 6 + li * (f_sm.get_height() + 3)))

        t.set_clip(None)   # restore after left-panel clip

    def _draw_right(self, t) -> None:
        step = self._steps[self._idx]
        # Clip to right panel
        clip = pygame.Rect(_SPLIT, 0, WIDTH - _SPLIT, HEIGHT)
        t.set_clip(clip)
        step.draw_scene(t, self)
        t.set_clip(None)

    def _draw_progress(self, t) -> None:
        n     = len(self._steps)
        dot_r = 5
        gap   = 14
        total = n * dot_r * 2 + (n - 1) * gap
        x0    = _SPLIT // 2 - total // 2
        y     = 16
        for i in range(n):
            cx = x0 + i * (dot_r * 2 + gap) + dot_r
            if i < self._idx:
                pygame.draw.circle(t, NEON, (cx, y), dot_r)
            elif i == self._idx:
                pulse = abs(math.sin(self.tick * 0.07)) * 2
                pygame.draw.circle(t, NEON_GLOW, (cx, y), int(dot_r + pulse))
                pygame.draw.circle(t, NEON, (cx, y), dot_r, 1)
            else:
                pygame.draw.circle(t, PURPLE_DIM, (cx, y), dot_r)
                pygame.draw.circle(t, PURPLE,     (cx, y), dot_r, 1)
        # Step counter just below dots
        f  = self.fonts["small"]
        sc = f.render(f"{self._idx + 1} / {n}", False, TEXT_DIM)
        t.blit(sc, (_SPLIT // 2 - sc.get_width() // 2, y + dot_r + 8))

    def _draw_nav(self, t) -> None:
        mouse = pygame.mouse.get_pos()
        f     = self.fonts["small"]
        last  = (self._idx == len(self._steps) - 1)
        step  = self._steps[self._idx]

        # Menu button (always)
        hov = self._menu_rect.collidepoint(mouse)
        pygame.draw.rect(t, NEON_DARK if hov else PURPLE_DIM,
                          self._menu_rect, border_radius=BTN_RADIUS)
        pygame.draw.rect(t, NEON if hov else PURPLE,
                          self._menu_rect, width=1, border_radius=BTN_RADIUS)
        ml = f.render("< MENU", False, TEXT_MAIN)
        t.blit(ml, (self._menu_rect.centerx - ml.get_width() // 2,
                     self._menu_rect.centery - ml.get_height() // 2))

        if last:
            # Play Now button  green, pulsing
            hov = self._play_rect.collidepoint(mouse)
            pulse = abs(math.sin(self.tick * 0.07))
            col_b = (int(60 + pulse * 40), int(220 + pulse * 35), int(120 + pulse * 30))
            pygame.draw.rect(t, _GREEN_D if hov else (20, 80, 45),
                              self._play_rect, border_radius=BTN_RADIUS)
            pygame.draw.rect(t, col_b, self._play_rect, width=2, border_radius=BTN_RADIUS)
            if hov:
                gs = pygame.Surface((self._play_rect.w + 12, self._play_rect.h + 12), pygame.SRCALPHA)
                pygame.draw.rect(gs, (*_GREEN, 45), gs.get_rect(), border_radius=BTN_RADIUS + 4)
                t.blit(gs, (self._play_rect.x - 6, self._play_rect.y - 6))
            pl = f.render("PLAY  NOW  ▶", False, col_b)
            t.blit(pl, (self._play_rect.centerx - pl.get_width() // 2,
                         self._play_rect.centery - pl.get_height() // 2))
        else:
            # Back button
            if self._idx > 0:
                hov = self._back_rect.collidepoint(mouse)
                pygame.draw.rect(t, NEON_DARK if hov else PURPLE_DIM,
                                  self._back_rect, border_radius=BTN_RADIUS)
                pygame.draw.rect(t, NEON if hov else PURPLE,
                                  self._back_rect, width=1, border_radius=BTN_RADIUS)
                bl = f.render("< BACK", False, TEXT_MAIN)
                t.blit(bl, (self._back_rect.centerx - bl.get_width() // 2,
                              self._back_rect.centery - bl.get_height() // 2))

            # Next button
            ready = step.done
            hov   = self._next_rect.collidepoint(mouse) and ready
            fill  = (180, 30, 80) if hov else (NEON_DARK if ready else PURPLE_DIM)
            border= NEON_GLOW if hov else (NEON if ready else PURPLE)
            pygame.draw.rect(t, fill,   self._next_rect, border_radius=BTN_RADIUS)
            pygame.draw.rect(t, border, self._next_rect, width=2, border_radius=BTN_RADIUS)
            if ready and hov:
                gs = pygame.Surface((self._next_rect.w + 12, self._next_rect.h + 12), pygame.SRCALPHA)
                pygame.draw.rect(gs, (*NEON, 45), gs.get_rect(), border_radius=BTN_RADIUS + 4)
                t.blit(gs, (self._next_rect.x - 6, self._next_rect.y - 6))
            nl = f.render("NEXT  >" if ready else "...", False,
                           NEON_GLOW if ready else TEXT_DIM)
            t.blit(nl, (self._next_rect.centerx - nl.get_width() // 2,
                         self._next_rect.centery - nl.get_height() // 2))

    def _draw_flash(self, t) -> None:
        if not self._flash_msg or self._flash_tick <= 0:
            return
        f     = self.fonts["small"]
        alpha = min(255, self._flash_tick * 7)
        msg   = f.render(self._flash_msg, False, self._flash_col)
        mw, mh = msg.get_width() + 24, msg.get_height() + 14
        bx = _SCENE_CX - mw // 2
        by = HEIGHT // 2 - mh // 2 - 60
        bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
        bg.fill((8, 4, 20, min(210, alpha)))
        pygame.draw.rect(bg, (*self._flash_col, min(200, alpha)),
                          bg.get_rect(), width=2, border_radius=6)
        t.blit(bg, (bx, by))
        msg.set_alpha(alpha)
        t.blit(msg, (bx + 12, by + 7))