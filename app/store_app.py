"""App VendrediParty de l'App Store (« PartyStore » dans l'User-Agent, ios/Party/AppConfig.swift).

Refus Apple 1.4.3 du 25.11.2026 (build 216) : dans l'app App Store, AUCUN jeu à boire, aucune gorgée, aucune
boisson alcoolisée ni drogue, aucun vote sexuel sur les présents (modes Hot / Mix). C'est le SERVEUR qui le garantit :
- jeux cachés : refusés à la création, au lancement depuis une salle, à la lecture et aux actions (code, QR) ;
- partie créée par l'app (ou lancée dans une salle où l'app est entrée) : marquée `store`, gorgées forcées à 0,
  questions et mots tirés sans boisson ni drogue (`drinky`) ;
- partie créée ailleurs : refusée à l'app si elle a des gorgées, un mode Hot / Mix, ou des questions déjà tirées
  sans ce filtre. Le site, l'app BETA et Android gardent tout. Voir CLAUDE.md « Refus Apple 1.4.3 (25.11) ».
"""
import re
from functools import lru_cache

from .features import is_test_site

MARK = "PartyStore"
# Casino et Blackjack (jeux d'argent simulés) depuis le 05.11 ; les autres vivent par l'alcool (Beer pong, Biskit,
# Pyramide) ou parlent de drogue et de sexe explicite (Purify Test).
HIDDEN_GAMES = ("casino", "blackjack", "beerpong", "biskit", "pyramid", "purity")
# Modes de questions refusés (votes sexuels sur les personnes présentes, Apple 1.1.4 / 1.2).
HIDDEN_MODES = ("hot", "mix")
# Jeux dont le texte vient d'une banque (questions, mots, cartes) : filtrée seulement dans une partie `store`.
BANK_GAMES = ("never", "whoof", "likely", "undercover", "quiz", "tmc", "divan", "debate")
MESSAGE = "Ce jeu n'est pas disponible dans l'app."

# Mots et emojis de boisson, d'ivresse ou de drogue (larges exprès : une question de trop retirée ne coûte rien).
DRINK_RE = re.compile(
    r"gorg[ée]es?|\bboire\b|\bboi[st]\b|\bboivent\b|\bbuvez\b|\bbu\b|\bshots?\b|alcool|bi[èe]res?\b|\bvins?\b|vodka|tequila"
    r"|whisky|\brhums?\b|\bgin\b|tourn[ée]e|\bcuites?\b|\bivres?\b|ivresse|bourr[ée]e?s?\b|gueule de bois|ap[ée]ro"
    r"|cocktail|champagne|mojito|ca[iï]pirinha|sangria|spritz|pastis|j[äa]germeister|liqueur|\bbars?\b|\bverres?\b"
    r"|drogue|cannabis|coca[iï]ne|\bjoint\b|ecstasy|mdma|\blsd\b|cigarette|nicotine|🍻|🍺|🥃|🍸|🍹|🍷|🍾|🥂",
    re.IGNORECASE)


def is_store(request) -> bool:
    """L'app App Store : « PartyStore » dans l'User-Agent (vue web). En production, tout client iOS natif aussi : les
    écrans natifs n'envoient que « X-Party-Native: ios » (PartyAPI.swift), et la BETA parle au site de test, jamais à
    la prod (ios/project.yml, workflow TestFlight) ; le site de test garde la BETA telle quelle."""
    if request is None:
        return False
    ua = request.headers.get("user-agent", "")
    if MARK in ua:
        return True
    return request.headers.get("x-party-native") == "ios" and not is_test_site()


def drinky(text) -> bool:
    return _drinky(str(text or ""))


@lru_cache(maxsize=None)  # banques fixes : chaque texte n'est examiné qu'une fois
def _drinky(text: str) -> bool:
    return bool(DRINK_RE.search(text))


def clean(pool: list, text=lambda x: x) -> list:
    """La banque sans boisson ni drogue (jamais vide : les banques en ont des centaines)."""
    return [x for x in pool if not drinky(text(x))] or pool


def flag(g: dict):
    """Partie de l'app App Store : sans gorgées, questions filtrées (les modules qui ne voient que leur état le lisent)."""
    g["store"] = True
    g["options"]["sips"] = 0
    if g["options"].get("mode") in HIDDEN_MODES:
        g["options"]["mode"] = "soft"
    for key in ("likely", "debate", "quiz"):
        if isinstance(g.get(key), dict):
            g[key]["store"] = True


def refused(g: dict) -> bool:
    """L'app App Store ne voit pas cette partie (jeu caché, gorgées, mode Hot, texte tiré sans filtre)."""
    if g["type"] in HIDDEN_GAMES or (g.get("options") or {}).get("sips"):
        return True
    if g["type"] in ("whoof", "never") and g["options"].get("mode") in HIDDEN_MODES:
        return True
    return g["type"] in BANK_GAMES and not g.get("store") and g.get("phase") != "lobby"


DRINK_EMOJIS = ("🍻", "🍷")  # emojis de groupe de la liste fermée (member_groups.emoji) : 🎉 dans l'app App Store


def neutral_emojis(data):
    """Réponse des discussions pour l'app App Store : l'emoji 🍻 / 🍷 d'un groupe (clé « emoji ») devient 🎉."""
    if isinstance(data, dict):
        return {k: ("🎉" if k == "emoji" and v in DRINK_EMOJIS else neutral_emojis(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [neutral_emojis(x) for x in data]
    return data
