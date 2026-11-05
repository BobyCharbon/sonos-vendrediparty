"""Compagnon — catalogue de la collection (lot A « Collection », 4 novembre 2026).

Les données vivent dans UN fichier, app/pet_catalog.json (raretés, emplacements, séries, objets) ; ce module le lit,
le valide au démarrage et en tire les réserves : coffres, atelier, boutique, décor. La base en garde une copie
(public.pet_catalog, migration 20261104210000) pour les cadeaux d'événement et la frappe des numérotés ; sql_values()
produit cette copie et tests/test_pet_catalog.py vérifie qu'elle est identique.
Les dessins sont côté navigateur (app/static/pet/acc-*.js), un par identifiant.
Économie sans argent réel : rien ne s'achète avec de l'argent, rien ne se convertit en argent."""
import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("pet_catalog.json")
RARITY_ORDER = ("common", "rare", "epic", "legendary", "mythic")
INSTANCE_RARITIES = ("legendary", "mythic")   # exemplaires numérotés en base, avec certificat signé
SLOT_IDS = ("head", "eyes", "neck", "hand", "back", "feet", "facets", "effect", "decor", "pet")
SPECIAL_HINTS = {   # tenues d'avant la collection : elles gardent leur façon d'être gagnées (app/pet.py _unlock_rules)
    "noeud": "Offert dès le premier jour",
    "lunettes": "Série de 3 jours 🔥",
    "casquette": "Série de 7 jours 🔥",
    "casque": "5 parties de Méninges",
    "boa": "Venir à une soirée Party",
    "chapeau": "Recevoir 5 cadeaux d'amis",
    "couronne": "Faire grandir un adulte « étoile »",
}


class CatalogError(ValueError):
    pass


@lru_cache(maxsize=1)
def data() -> dict:
    raw = json.loads(PATH.read_text(encoding="utf-8"))
    validate(raw)
    return raw


def validate(raw: dict) -> None:
    """Le catalogue est cohérent : identifiants uniques, emplacement, série et rareté connus, Mythiques limités."""
    rarities = {r["id"] for r in raw["rarities"]}
    series = {s["id"] for s in raw["series"]}
    if tuple(r["id"] for r in raw["rarities"]) != RARITY_ORDER or tuple(s["id"] for s in raw["slots"]) != SLOT_IDS:
        raise CatalogError("raretés ou emplacements dans le désordre")
    seen = set()
    for it in raw["items"]:
        iid = it["id"]
        if iid in seen or not iid.replace("-", "").isalnum() or len(iid) > 30 or iid != iid.lower():
            raise CatalogError(f"identifiant invalide ou en double : {iid}")
        seen.add(iid)
        if it["slot"] not in SLOT_IDS or it["series"] not in series or it["rarity"] not in rarities:
            raise CatalogError(f"{iid} : emplacement, série ou rareté inconnus")
        if (it["rarity"] == "mythic") != bool(it.get("edition")):
            raise CatalogError(f"{iid} : un Mythique (et lui seul) a un tirage limité")
        if it["rarity"] == "mythic" and not iid.startswith("m-"):
            raise CatalogError(f"{iid} : identifiant neutre attendu (m-…) pour un Mythique")
        if it.get("price") and it["slot"] != "decor":
            raise CatalogError(f"{iid} : seul le décor a un prix fixe")
    for s in raw["series"]:
        rel = s.get("release")
        if rel is not None and (not isinstance(rel, str) or len(rel) != 10 or rel[4] != "-" or rel[7] != "-"):
            raise CatalogError(f"{s['id']} : date de sortie AAAA-MM-JJ attendue")


def rarities() -> dict[str, dict]:
    return {r["id"]: r for r in data()["rarities"]}


def series() -> dict[str, dict]:
    return {s["id"]: s for s in data()["series"]}


def items() -> dict[str, dict]:
    return {it["id"]: it for it in data()["items"]}


def item(iid: str) -> dict | None:
    return items().get(iid)


def slot_label(slot: str) -> str:
    return next((s["label"] for s in data()["slots"] if s["id"] == slot), slot)


def is_instance(iid: str) -> bool:
    it = item(iid)
    return bool(it) and it["rarity"] in INSTANCE_RARITIES


def is_event_only(it: dict) -> bool:
    return series()[it["series"]]["source"] == "event"


def released(sid: str, today: str | None = None) -> bool:
    """Saisons (économie du 4.11.2026) : une série n'entre dans les coffres, la boutique et l'atelier qu'à partir de sa
    date de sortie (« release », jour de Zurich AAAA-MM-JJ). today=None : pas de filtre (calcul hors date)."""
    rel = (series().get(sid) or {}).get("release")
    return today is None or not rel or rel <= today


def upcoming(today: str | None) -> list[str]:
    """Séries pas encore sorties (Zicoudex : « Bientôt : ??? », sans le nom des objets)."""
    return [sid for sid in series() if not released(sid, today)]


def chest_pool(rarity: str, today: str | None = None) -> list[str]:
    """Objets qu'un coffre peut donner : séries « coffre » déjà sorties, hors décor (boutique) et hors Soirées Party."""
    return [it["id"] for it in data()["items"] if it["rarity"] == rarity and not is_event_only(it) and not it.get("price")
            and released(it["series"], today)]


def craft_cost(iid: str, today: str | None = None) -> int | None:
    """Prix à l'atelier en poussière (barème façon Hearthstone) ; None : ne se fabrique pas (Mythique, souvenir de
    soirée, décor de la boutique, série pas encore sortie)."""
    it = item(iid)
    if not it or it["rarity"] == "mythic" or is_event_only(it) or it.get("price") or not released(it["series"], today):
        return None
    return rarities()[it["rarity"]]["craft"]


def dust_value(iid: str) -> int:
    """Poussière d'un doublon (5 / 20 / 100 / 400) ; un Mythique ne fait jamais de doublon."""
    it = item(iid)
    return int(rarities()[it["rarity"]]["dust"] or 0) if it else 0


def shop_pool(today: str | None = None) -> list[str]:
    """Boutique du jour : Communs et Rares des séries « coffre » sorties (jamais un souvenir de soirée)."""
    return chest_pool("common", today) + chest_pool("rare", today)


def shop_price(iid: str) -> int | None:
    it = item(iid)
    if not it:
        return None
    return it.get("price") or rarities()[it["rarity"]]["shop"]


def decor_items(today: str | None = None) -> list[str]:
    return [it["id"] for it in data()["items"] if it.get("price") and released(it["series"], today)]


def series_items(sid: str, with_mythic: bool = False) -> list[str]:
    return [it["id"] for it in data()["items"] if it["series"] == sid and (with_mythic or it["rarity"] != "mythic")]


def mythics(source: str | None = None) -> list[str]:
    """Mythiques ; source « chest » : ceux qu'un coffre peut donner (« Objet mystère »)."""
    return [it["id"] for it in data()["items"] if it["rarity"] == "mythic"
            and (source is None or series()[it["series"]]["source"] == source)]


def where(iid: str) -> str:
    """« Où le trouver » (Zicoudex)."""
    it = item(iid)
    if not it:
        return ""
    if it.get("price"):
        return f"Boutique › Décor de la chambre ({it['price']} 🪙)"
    if it["rarity"] == "mythic":
        return "Objet mystère : coffres du jour et cadeaux d'événement Party"
    parts = [SPECIAL_HINTS[iid]] if iid in SPECIAL_HINTS else []
    if is_event_only(it):
        parts.append("Cadeau d'un événement Party où tu es présent")
        return " · ".join(parts)
    parts.append("Coffres du jour")
    if it["rarity"] == "common":
        parts.append("Boutique du jour")
    elif it["rarity"] == "rare":
        parts.append("Boutique (un jour sur deux)")
    parts.append(f"Atelier ({craft_cost(iid)} ✨)")
    return " · ".join(parts)


def public_item(iid: str) -> dict:
    """Ce qu'on montre d'un objet (nom, emplacement, série, rareté) : seulement pour un objet visible."""
    it = item(iid)
    r = rarities()[it["rarity"]]
    return {"id": iid, "label": it["label"], "emoji": it["emoji"], "slot": it["slot"], "series": it["series"],
            "rarity": it["rarity"], "rarity_label": r["label"], "color": r["color"], "edition": it.get("edition")}


def sql_values() -> str:
    """Lignes de public.pet_catalog (migration) : identifiant, emplacement, série, rareté, tirage, source, coût."""
    def q(v) -> str:
        return "null" if v is None else str(v) if isinstance(v, int) else "'" + str(v).replace("'", "''") + "'"
    rows = []
    for it in data()["items"]:
        rows.append(f"({q(it['id'])}, {q(it['slot'])}, {q(it['series'])}, {q(it['rarity'])}, {q(it.get('edition'))}, "
                    f"{q(series()[it['series']]['source'])}, {q(it['label'])})")
    return ",\n".join(rows)
