"""Zicou sur la fiche profil d'un membre (avis de l'admin, 4.11) : son APPARENCE publique, rien de privé.

Montré à tout membre connecté qui peut ouvrir la fiche (jamais à quelqu'un de bloqué, dans un sens ou l'autre : la base
le refuse, fonction public.pet_profile) : stade, humeur, variante, ce qu'il porte, shiny, génération, âge en jours et la
rareté de sa plus belle pièce montrée. Le nom seulement s'il passe le filtre (app/moderation.py) en plus de celui de la
base ; sinon aucun nom. Jamais : jauges, pièces, poussière, inventaire, série, souvenirs, titre de vitrine.
Un Zicou envolé (mort) compte comme « pas encore de Zicou » : la fiche montre l'œuf terne qui donne envie d'en avoir un."""
from datetime import datetime

from . import moderation, pet, pet_catalog, pet_collection

HOURS_PER_DAY = 24
RARITY_RANK = {r: i for i, r in enumerate(pet_catalog.RARITY_ORDER)}


def clean_name(life: dict) -> str | None:
    """Nom du Zicou s'il passe le filtre commun ; None sinon (jamais un nom refusé, même masqué)."""
    raw = " ".join(str(life.get("name") or "").split())[:pet.NAME_MAX]
    if not raw:
        return None
    verdict = moderation.check(raw, "name")
    return verdict.text if verdict.ok else None


def best_piece(life: dict, worn: dict) -> dict | None:
    """La pièce la plus rare qu'il montre (portée ou en vitrine) : rareté et libellé du catalogue, jamais de texte saisi."""
    shown = [x["id"] for x in (pet_collection.showcase_view(life) or {}).get("items", [])] + list(worn.values())
    known = [i for i in dict.fromkeys(shown) if pet_catalog.item(i)]
    if not known:
        return None
    return _piece(max(known, key=lambda i: RARITY_RANK.get(pet_catalog.item(i)["rarity"], -1)))


def appearance(life: dict, now: datetime) -> dict | None:
    """Apparence publique d'un Zicou vécu jusqu'à maintenant (rien d'enregistré) ; None s'il n'y en a pas (ou envolé)."""
    seen = pet.friend_view(life, now)
    if seen["stage"] == "dead":
        return None
    worn = pet_collection.worn(life)
    return {"name": clean_name(seen), "stage": seen["stage"], "variant": seen["variant"], "emotion": seen["emotion"],
            "outfit": None if worn else seen.get("outfit"), "acc": worn, "shiny": bool(life.get("shiny")),
            "gen": int(seen.get("gen") or 1), "age_days": int(max(0.0, float(seen["age_hours"])) // HOURS_PER_DAY),
            "best": best_piece(life, worn), "acc_items": [_piece(i) for i in worn.values()]}


def _piece(iid: str) -> dict:
    it = pet_catalog.public_item(iid)
    return {k: it[k] for k in ("id", "slot", "label", "emoji", "rarity", "rarity_label", "color")}


def card(row: dict, member: str, now: datetime) -> dict:
    """Réponse de /api/pet/profile à partir de public.pet_profile : {member, me, friend, mine, zicou}."""
    life = row.get("life")
    zicou = None
    if isinstance(life, dict):
        try:
            zicou = appearance(life, now)
        except (KeyError, TypeError, ValueError):
            zicou = None   # état illisible : la fiche montre l'œuf plutôt que de casser
    me = bool(row.get("me"))
    return {"member": member, "me": me, "friend": bool(row.get("friend")) and not me and zicou is not None,
            "mine": bool(row.get("mine")), "zicou": zicou}
