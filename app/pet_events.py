"""Compagnon — cadeaux d'événement (lot A, 4.11.2026) : vérification et règlement.

Le tirage est fait par la BASE (migration 20261104210000, private.pet_event_draw), à la fin de l'événement, pour TOUS
les présents, jamais selon un paiement. Avant : chances et exemplaires publiés et figés, avec l'empreinte sha256 de la
graine. Après : la graine est révélée ; chacun refait son propre jet avec roll() et vérifie qu'il correspond.
"""
import hashlib
import hmac

RULES = (
    "Qui participe : toutes les personnes présentes à l'événement (billet scanné ou arrivée notée, ou notées "
    "« Présent » par l'organisateur). Jamais selon un paiement : payer ou non sa part ne change rien.",
    "Quoi : des accessoires de Zicou uniquement, sans aucune valeur en argent. Aucun lot réel (boisson, "
    "bon, place, objet physique), rien à acheter, rien à miser.",
    "Chances et nombre d'exemplaires : publiés avant le début de l'événement, puis figés (personne ne peut plus les "
    "changer, pas même l'admin).",
    "Tirage : fait par le serveur de Party à la fin de l'événement, un jet par personne et par objet. L'empreinte de la "
    "graine est publiée avant ; la graine est révélée après, pour que chacun puisse vérifier son jet.",
    "Apple et Google ne sont ni organisateurs ni sponsors de ces cadeaux, et n'y participent d'aucune manière.",
)


def roll(seed: str, event_id: str, user_id: str, prize: int) -> float:
    """Jet d'un présent pour un lot, 0 ≤ jet < 100 (même calcul que private.pet_drop_roll)."""
    digest = hmac.new(seed.encode(), f"{event_id}|{user_id}|{prize}".encode(), hashlib.sha256).hexdigest()
    return round(int(digest[:13], 16) / 2 ** 52 * 100, 6)


def seed_matches(seed: str, seed_hash: str) -> bool:
    """La graine révélée est bien celle dont l'empreinte avait été publiée avant l'événement."""
    return hashlib.sha256(seed.encode()).hexdigest() == (seed_hash or "").lower()


def won(seed: str, event_id: str, user_id: str, prize: int, pct: float) -> bool:
    """Le jet est-il gagnant (avant la limite d'exemplaires, servie dans l'ordre tiré de la graine) ?"""
    return roll(seed, event_id, user_id, prize) < pct
