"""
locale.py — All UI strings for English, Russian, and Romanian.

Usage:
    from .locale import t, set_lang, get_lang

    t("menu.play")          -> "PLAY" / "ИГРАТЬ" / "JOC"
    t("game.take_cards")    -> "TAKE CARDS" / "ВЗЯТЬ КАРТЫ" / "IAU CĂRȚILE"
"""
from __future__ import annotations

_lang: str = "en"   # "en" | "ru" | "ro"

def get_lang() -> str:
    return _lang

def set_lang(code: str) -> None:
    global _lang
    if code in ("en", "ru", "ro"):
        _lang = code

def t(key: str) -> str:
    """Translate a dot-notation key for the current language."""
    node = _STRINGS
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return key   # fallback: return the key itself
    if isinstance(node, dict):
        return node.get(_lang, node.get("en", key))
    return str(node)


# ── String table ──────────────────────────────────────────────────────────────
# Each leaf is either a plain string (English only) or {"en":..., "ru":..., "ro":...}

_STRINGS: dict = {

    # ── Menu ──────────────────────────────────────────────────────────────────
    "menu": {
        "play":         {"en": "PLAY",         "ru": "ИГРАТЬ",     "ro": "JOC"},
        "tutorial":     {"en": "TUTORIAL",      "ru": "ОБУЧЕНИЕ",   "ro": "TUTORIAL"},
        "settings":     {"en": "SETTINGS",      "ru": "НАСТРОЙКИ",  "ro": "SETĂRI"},
        "quit":         {"en": "QUIT",           "ru": "ВЫХОД",      "ro": "IEȘIRE"},
        "achievements": {"en": "ACHIEVEMENTS",   "ru": "ДОСТИЖЕНИЯ", "ro": "REALIZĂRI"},
        "credits":      {"en": "CREDITS",        "ru": "АВТОРЫ",     "ro": "CREDITE"},
        "pre_release":  {"en": "pre-release",    "ru": "пре-релиз",  "ro": "pre-lansare"},
    },

    # ── Pause ─────────────────────────────────────────────────────────────────
    "pause": {
        "title":        {"en": "PAUSED",         "ru": "ПАУЗА",      "ro": "PAUZĂ"},
        "resume":       {"en": "RESUME",         "ru": "ПРОДОЛЖИТЬ", "ro": "CONTINUĂ"},
        "achievements": {"en": "ACHIEVEMENTS",   "ru": "ДОСТИЖЕНИЯ", "ro": "REALIZĂRI"},
        "settings":     {"en": "SETTINGS",       "ru": "НАСТРОЙКИ",  "ro": "SETĂRI"},
        "main_menu":    {"en": "MAIN MENU",      "ru": "ГЛАВНОЕ МЕНЮ","ro": "MENIU PRINCIPAL"},
    },

    # ── Settings ──────────────────────────────────────────────────────────────
    "settings": {
        "title":        {"en": "SETTINGS",       "ru": "НАСТРОЙКИ",  "ro": "SETĂRI"},
        "master":       {"en": "MASTER AUDIO",   "ru": "ОБЩИЙ ЗВУК", "ro": "VOLUM GENERAL"},
        "sfx":          {"en": "SFX",            "ru": "ЭФФЕКТЫ",    "ro": "EFECTE"},
        "bgm":          {"en": "BGM",            "ru": "МУЗЫКА",     "ro": "MUZICĂ"},
        "language":     {"en": "LANGUAGE",       "ru": "ЯЗЫК",       "ro": "LIMBĂ"},
        "back":         {"en": "< BACK",         "ru": "< НАЗАД",    "ro": "< ÎNAPOI"},
        "lang_en":      {"en": "ENGLISH",        "ru": "АНГЛИЙСКИЙ", "ro": "ENGLEZĂ"},
        "lang_ru":      {"en": "RUSSIAN",        "ru": "РУССКИЙ",    "ro": "RUSĂ"},
        "lang_ro":      {"en": "ROMANIAN",       "ru": "РУМЫНСКИЙ",  "ro": "ROMÂNĂ"},
    },

    # ── Play select ───────────────────────────────────────────────────────────
    "play_select": {
        "title":        {"en": "SELECT MODE",    "ru": "ВЫБОР РЕЖИМА","ro": "SELECTEAZĂ MODUL"},
        "duel":         {"en": "FOOL'S DUEL",    "ru": "ДУЭЛЬ ДУРАКА","ro": "DUELUL PROSTULUI"},
        "duel_sub":     {"en": "1 BOT  |  SINGLEPLAYER","ru": "1 БОТ  |  ОДИНОЧНАЯ","ro": "1 BOT  |  JOC SOLO"},
        "multi_bot":    {"en": "MULTI BOT",      "ru": "МУЛЬТИ БОТ", "ro": "MULTI BOT"},
        "multi_sub":    {"en": "2+ BOTS  |  COMING SOON","ru": "2+ БОТОВ  |  СКОРО","ro": "2+ BOȚI  |  ÎN CURÂND"},
        "wip":          {"en": "WIP",            "ru": "В РАЗР.",    "ro": "WIP"},
        "back":         {"en": "< BACK",         "ru": "< НАЗАД",    "ro": "< ÎNAPOI"},
    },

    # ── Game UI ───────────────────────────────────────────────────────────────
    "game": {
        "status_attack":    {"en": "ATTACK",     "ru": "АТАКА",      "ro": "ATAC"},
        "status_defend":    {"en": "DEFEND",     "ru": "ЗАЩИТА",     "ro": "APĂRARE"},
        "status_pile_on":   {"en": "PILE ON",    "ru": "ДОБАВИТЬ",   "ro": "ADAUGĂ"},
        "status_bot":       {"en": "BOT",        "ru": "БОТ",        "ro": "BOT"},
        "status_deal":      {"en": "DEAL",       "ru": "РАЗДАЧА",    "ro": "ÎMPĂRȚIRE"},
        "status_game_over": {"en": "GAME OVER",  "ru": "ИГРА ОКОНЧЕНА","ro": "JOC TERMINAT"},
        "take_cards":       {"en": "TAKE CARDS", "ru": "ВЗЯТЬ КАРТЫ","ro": "IAU CĂRȚILE"},
        "pass":             {"en": "PASS",       "ru": "ПАС",        "ro": "PAS"},
        "trump":            {"en": "TRUMP",      "ru": "КОЗЫРЬ",     "ro": "ATU"},
        "you_are":          {"en": "YOU ARE",    "ru": "ВЫ",         "ro": "EȘTI"},
        "attacking":        {"en": "ATTACKING",  "ru": "АТАКУЕТЕ",   "ro": "ATACATORUL"},
        "defending":        {"en": "DEFENDING",  "ru": "ЗАЩИЩАЕТЕСЬ","ro": "APĂRĂTORUL"},
        "rank_not_on_table":{"en": "rank not on table","ru": "ранг не на столе","ro": "rang inexistent pe masă"},
        "cant_beat":        {"en": "can't beat", "ru": "не бьёт",    "ro": "nu bate"},
    },

    # ── Result screen ─────────────────────────────────────────────────────────
    "result": {
        "victory":      {"en": "VICTORY",        "ru": "ПОБЕДА",     "ro": "VICTORIE"},
        "defeat":       {"en": "DEFEAT",         "ru": "ПОРАЖЕНИЕ",  "ro": "ÎNFRÂNGERE"},
        "draw":         {"en": "DRAW",           "ru": "НИЧЬЯ",      "ro": "EGAL"},
        "sub_win":      {"en": "You are not the fool. This time.",
                         "ru": "Вы не дурак. На этот раз.",
                         "ro": "Nu ești prostul. De data asta."},
        "sub_loss":     {"en": "You are the Durak.",
                         "ru": "Вы — дурак.",
                         "ro": "Ești Prostul."},
        "sub_draw":     {"en": "Mutually assured foolishness.",
                         "ru": "Взаимная гарантированная глупость.",
                         "ro": "Prostie reciprocă garantată."},
        "press_any_key":{"en": "PRESS ANY KEY TO CONTINUE",
                         "ru": "НАЖМИТЕ ЛЮБУЮ КЛАВИШУ",
                         "ro": "APASĂ ORICE TASTĂ"},
        "rounds":       {"en": "ROUNDS PLAYED",  "ru": "РАУНДОВ",    "ro": "RUNDE JUCATE"},
        "piles_taken":  {"en": "PILES TAKEN",    "ru": "ВЗЯТО КУЧ",  "ro": "GRĂMEZI LUATE"},
        "biggest_pile": {"en": "BIGGEST PILE",   "ru": "МАКС. КУЧА", "ro": "CEA MAI MARE GRĂMADĂ"},
        "trumps_played":{"en": "TRUMPS PLAYED",  "ru": "КОЗ. СЫГРАНО","ro": "ATOURI JUCATE"},
        "times_passed": {"en": "TIMES PASSED",   "ru": "ПАСОВ",      "ro": "PASURI"},
    },

    # ── Achievements screen ───────────────────────────────────────────────────
    "ach_screen": {
        "title":        {"en": "ACHIEVEMENTS",   "ru": "ДОСТИЖЕНИЯ", "ro": "REALIZĂRI"},
        "unlocked":     {"en": "UNLOCKED",       "ru": "ОТКРЫТО",    "ro": "DEBLOCAT"},
        "back":         {"en": "< BACK",         "ru": "< НАЗАД",    "ro": "< ÎNAPOI"},
        "click_close":  {"en": "CLICK ANYWHERE TO CLOSE",
                         "ru": "НАЖМИТЕ ДЛЯ ЗАКРЫТИЯ",
                         "ro": "CLICK ORIUNDE PENTRU ÎNCHIDERE"},
        "locked_desc":  {"en": "???",            "ru": "???",        "ro": "???"},
    },

    # ── Achievement tier labels ───────────────────────────────────────────────
    "tier": {
        "common":   {"en": "COMMON",     "ru": "ОБЫЧНОЕ",    "ro": "COMUN"},
        "rare":     {"en": "RARE",       "ru": "РЕДКОЕ",     "ro": "RAR"},
        "epic":     {"en": "EPIC",       "ru": "ЭПИЧЕСКОЕ",  "ro": "EPIC"},
        "platinum": {"en": "PLATINUM",   "ru": "ПЛАТИНА",    "ro": "PLATINĂ"},
    },

    # ── Achievement toast headers ─────────────────────────────────────────────
    "toast": {
        "common":   {"en": "ACHIEVEMENT UNLOCKED",    "ru": "ДОСТИЖЕНИЕ ОТКРЫТО",   "ro": "REALIZARE DEBLOCATĂ"},
        "rare":     {"en": "RARE ACHIEVEMENT",        "ru": "РЕДКОЕ ДОСТИЖЕНИЕ",    "ro": "REALIZARE RARĂ"},
        "epic":     {"en": "EPIC ACHIEVEMENT",        "ru": "ЭПИЧЕСКОЕ ДОСТИЖЕНИЕ", "ro": "REALIZARE EPICĂ"},
        "platinum": {"en": "PLATINUM  •  ALL ACHIEVEMENTS",
                     "ru": "ПЛАТИНА  •  ВСЕ ДОСТИЖЕНИЯ",
                     "ro": "PLATINĂ  •  TOATE REALIZĂRILE"},
    },

    # ── Tutorial ──────────────────────────────────────────────────────────────
    "tut": {
        "next":         {"en": "NEXT",           "ru": "ДАЛЕЕ",      "ro": "URMĂTORUL"},
        "play_now":     {"en": "PLAY NOW",       "ru": "ИГРАТЬ",     "ro": "JOACĂ ACUM"},
        "skip":         {"en": "SKIP TUTORIAL",  "ru": "ПРОПУСТИТЬ", "ro": "SARI TUTORIALUL"},
        "yes":          {"en": "YES",            "ru": "ДА",         "ro": "DA"},
        "no":           {"en": "NO",             "ru": "НЕТ",        "ro": "NU"},
        "take_pile":    {"en": "TAKE PILE",      "ru": "ВЗЯТЬ КУЧУ", "ro": "IA GRĂMADA"},
        "score":        {"en": "SCORE",          "ru": "СЧЁТ",       "ro": "SCOR"},
        "beats":        {"en": "BEATS!",         "ru": "БЬЁТ!",      "ro": "BATE!"},
        "vs":           {"en": "VS",             "ru": "VS",         "ro": "VS"},
        "attack":       {"en": "ATTACK",         "ru": "АТАКА",      "ro": "ATAC"},
        "defence":      {"en": "DEFENCE",        "ru": "ЗАЩИТА",     "ro": "APĂRARE"},
        "trump_suit":   {"en": "TRUMP  SUIT:",   "ru": "КОЗЫРЬ:",    "ro": "ATU:"},
        "bots_hand":    {"en": "BOT'S HAND",     "ru": "РУКА БОТА",  "ro": "MÂNA BOTULUI"},
        "your_hand":    {"en": "YOUR HAND — CLICK TO ATTACK",
                         "ru": "ВАША РУКА — НАЖМИТЕ ДЛЯ АТАКИ",
                         "ro": "MÂNA TA — CLICK PENTRU ATAC"},
        "rank_of":      {"en": "RANK",           "ru": "РАНГ",       "ro": "RANG"},
        "strongest":    {"en": "A = STRONGEST",  "ru": "Т = СИЛЬНЕЙШИЙ","ro": "A = CEL MAI PUTERNIC"},

        # Step 0 — Intro
        "s0_title":     {"en": "FOOL'S  HAND",   "ru": "РУКА  ДУРАКА","ro": "MÂNA  PROSTULUI"},
        "s0_subtitle":  {"en": "a tutorial",     "ru": "обучение",   "ro": "un tutorial"},
        "s0_body":      {"en": ("Durak is a Russian card game.\n"
                                "The goal is simple:\n\n"
                                "Empty your hand before\n"
                                "your opponent does.\n\n"
                                "The last one holding\ncards is the Durak — the Fool."),
                         "ru": ("Дурак — русская карточная игра.\n"
                                "Цель проста:\n\n"
                                "Избавьтесь от карт раньше\n"
                                "соперника.\n\n"
                                "Тот, у кого остались карты —\nДурак."),
                         "ro": ("Durak este un joc de cărți rusesc.\n"
                                "Scopul este simplu:\n\n"
                                "Scapă de cărți înaintea\nadversarului.\n\n"
                                "Ultimul cu cărți în mână\neste Prostul.")},
        "s0_hint":      {"en": "Press NEXT or SPACE to continue",
                         "ru": "Нажмите ДАЛЕЕ или ПРОБЕЛ",
                         "ro": "Apasă URMĂTOR sau SPAȚIU"},

        # Step 1 — Card ranks
        "s1_title":     {"en": "CARD  RANKS",    "ru": "РАНГИ  КАРТ", "ro": "RANGURILE  CĂRȚILOR"},
        "s1_body":      {"en": ("The deck has cards ranked\n"
                                "from 6 (weakest) to Ace (strongest).\n\n"
                                "A higher-ranked card always\nbeats a lower one —\n"
                                "unless trumps are involved."),
                         "ru": ("В колоде карты от\n"
                                "6 (слабейшей) до Туза (сильнейшего).\n\n"
                                "Старшая карта бьёт младшую —\n"
                                "если нет козырей."),
                         "ro": ("Pachetul are cărți de la\n"
                                "6 (cea mai slabă) la As (cea mai puternică).\n\n"
                                "O carte mai mare bate una mai mică —\n"
                                "fără atouri.")},
        "s1_hint":      {"en": "Hover cards to inspect them",
                         "ru": "Наведите курсор на карты",
                         "ro": "Plasează cursorul pe cărți"},

        # Step 2 — Trump suit
        "s2_title":     {"en": "THE  TRUMP  SUIT",  "ru": "КОЗЫРНАЯ  МАСТЬ","ro": "ATUUL"},
        "s2_body":      {"en": ("One suit is chosen as TRUMP\nat the start of every game.\n\n"
                                "Any trump card beats any\nnon-trump card, regardless of rank.\n\n"
                                "Even a trump 6 beats an Ace\nof another suit."),
                         "ru": ("В начале каждой игры\nвыбирается козырная масть.\n\n"
                                "Любой козырь бьёт любую\nнекозырную карту.\n\n"
                                "Даже козырная 6 бьёт Туза\nдругой масти."),
                         "ro": ("La fiecare joc se alege\nun atu.\n\n"
                                "Orice carte de atu bate orice\ncarte non-atu, indiferent de rang.\n\n"
                                "Chiar și un 6 de atu bate un As\nde altă culoare.")},
        "s2_hint":      {"en": "Watch the animation",
                         "ru": "Смотрите анимацию",
                         "ro": "Urmărește animația"},

        # Step 3 — Quiz
        "s3_title":     {"en": "CAN  IT  BEAT?",    "ru": "БЬЁТ  ЛИ  КАРТА?","ro": "POATE  BATE?"},
        "s3_body":      {"en": ("Test your understanding.\n\n"
                                "Can the card on the right\nbeat the card on the left?\n\n"
                                "Remember: trump beats\nnon-trump always."),
                         "ru": ("Проверьте понимание.\n\n"
                                "Бьёт ли карта справа\nкарту слева?\n\n"
                                "Помните: козырь всегда\nбьёт некозырную."),
                         "ro": ("Testează-ți înțelegerea.\n\n"
                                "Poate carta din dreapta\nsă bată carta din stânga?\n\n"
                                "Reține: atuul bate\nîntotdeauna non-atoul.")},
        "s3_hint":      {"en": "Click YES or NO",
                         "ru": "Нажмите ДА или НЕТ",
                         "ro": "Apasă DA sau NU"},

        # Step 4 — Attack
        "s4_title":     {"en": "YOUR  TURN:  ATTACK","ru": "ВАШ  ХОД:  АТАКА","ro": "RÂNDUL  TĂU:  ATAC"},
        "s4_body":      {"en": ("You are the attacker.\n\n"
                                "Play a card from your hand\nonto the table.\n\n"
                                "The bot must defend or\ntake the whole pile."),
                         "ru": ("Вы — атакующий.\n\n"
                                "Сыграйте карту из руки\nна стол.\n\n"
                                "Бот должен отбиться\nили взять всю кучу."),
                         "ro": ("Ești atacatorul.\n\n"
                                "Joacă o carte din mână\npe masă.\n\n"
                                "Botul trebuie să se apere\nsau să ia grămada.")},
        "s4_hint":      {"en": "Click any card in your hand to attack",
                         "ru": "Нажмите на карту в руке для атаки",
                         "ro": "Click pe o carte din mână pentru a ataca"},

        # Step 5 — Defend
        "s5_title":     {"en": "YOUR  TURN:  DEFEND","ru": "ВАШ  ХОД:  ЗАЩИТА","ro": "RÂNDUL  TĂU:  APĂRARE"},
        "s5_body":      {"en": ("The bot attacked.\n\n"
                                "Play a higher card of the same suit,\nor any trump card.\n\n"
                                "Can't defend? Take the pile\nand your turn is over."),
                         "ru": ("Бот атаковал.\n\n"
                                "Сыграйте старшую карту\nтой же масти или любой козырь.\n\n"
                                "Не можете отбиться?\nВозьмите кучу."),
                         "ro": ("Botul a atacat.\n\n"
                                "Joacă o carte mai mare din\naceeași culoare, sau orice atu.\n\n"
                                "Nu poți apăra? Ia grămada\nși rândul tău s-a terminat.")},
        "s5_hint":      {"en": "Click a card to defend. Green = valid, Red = invalid",
                         "ru": "Нажмите на карту. Зелёный = можно, Красный = нельзя",
                         "ro": "Click pe o carte. Verde = valid, Roșu = invalid"},

        # Step 6 — Pile on
        "s6_title":     {"en": "PILE-ON:  MORE  ATTACKS","ru": "ДОБАВИТЬ  АТАКИ","ro": "ATAC  MULTIPLU"},
        "s6_body":      {"en": ("After the first attack,\nyou can pile on more cards\n"
                                "of the same rank.\n\n"
                                "More cards on the table\nmeans more the defender\nmust beat — or take."),
                         "ru": ("После первой атаки\nможно добавить карты\nтого же ранга.\n\n"
                                "Больше карт на столе —\nбольше нужно отбить."),
                         "ro": ("După primul atac,\npoți adăuga mai multe cărți\nde același rang.\n\n"
                                "Mai multe cărți pe masă —\nmai multe de apărat sau luat.")},
        "s6_hint":      {"en": "Watch the animation — it loops automatically",
                         "ru": "Смотрите анимацию",
                         "ro": "Urmărește animația — se repetă automat"},

        # Step 7 — Taking the pile
        "s7_title":     {"en": "TAKING  THE  PILE","ru": "ВЗЯТИЕ  КУЧИ","ro": "LUAREA  GRĂMEZII"},
        "s7_body":      {"en": ("If you can't beat every\nattack card on the table,\nyou take the whole pile.\n\n"
                                "This ends your turn and\nyou become the defender\nagain next round."),
                         "ru": ("Если не можете отбить\nвсе атакующие карты —\nберёте всю кучу.\n\n"
                                "Ваш ход заканчивается,\nи снова становитесь\nзащищающимся."),
                         "ro": ("Dacă nu poți bate toate\ncărțile de pe masă,\niei toată grămada.\n\n"
                                "Rândul tău se termină\nși devii din nou\napărătorul.")},
        "s7_hint":      {"en": "Click TAKE PILE to see what happens",
                         "ru": "Нажмите ВЗЯТЬ КУЧУ",
                         "ro": "Apasă IA GRĂMADA"},

        # Step 8 — Drawing up
        "s8_title":     {"en": "DRAWING  UP","ru": "ДОБОР  КАРТ","ro": "COMPLETAREA  MÂINII"},
        "s8_body":      {"en": ("After every round both\nplayers draw from the deck\nuntil they hold 6 cards.\n\n"
                                "The attacker draws first.\nOnce the deck runs out,\nno more drawing."),
                         "ru": ("После каждого раунда\nоба игрока добирают\nкарты до 6.\n\n"
                                "Атакующий берёт первым.\nКогда колода закончится —\nдобора нет."),
                         "ro": ("După fiecare rundă ambii\njucători trag din pachet\npână la 6 cărți.\n\n"
                                "Atacatorul trage primul.\nCând pachetul se termină,\nnu mai există tragere.")},
        "s8_hint":      {"en": "Watch the animation — shows full deck then empty",
                         "ru": "Смотрите анимацию",
                         "ro": "Urmărește animația"},

        # Step 9 — How to win
        "s9_title":     {"en": "HOW  TO  WIN","ru": "КАК  ПОБЕДИТЬ","ro": "CUM  SĂ  CÂȘTIG"},
        "s9_body":      {"en": ("The first player to empty\ntheir hand after the\ndeck runs out — WINS.\n\n"
                                "The player left holding\ncards is the DURAK.\n\nGood luck!"),
                         "ru": ("Первый, кто избавится\nот карт после опустошения\nколоды — ПОБЕДИЛ.\n\n"
                                "Тот, у кого остались\nкарты — ДУРАК.\n\nУдачи!"),
                         "ro": ("Primul care rămâne\nfără cărți după ce\npachetul s-a terminat — CÂȘTIGĂ.\n\n"
                                "Cel cu cărți rămase\neste PROSTUL.\n\nSucces!")},
        "s9_hint":      {"en": "Click PLAY NOW when ready!",
                         "ru": "Нажмите ИГРАТЬ, когда готовы!",
                         "ro": "Apasă JOACĂ ACUM când ești gata!"},
    },
}