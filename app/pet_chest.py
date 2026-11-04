"""Compagnon — coffres et inventaire. Lot 1 (« revenir tous les jours ») puis lot A « Collection » (4.11.2026).

· Inventaire de la boucle du jour (owner["loop"]["inv"]) : {identifiant: quantité}. « famille:nom » : snack:cupcake,
  sticker:disco ; les anciens morceaux (piece:…) et tenues (outfit:…) d'avant la collection sont convertis une fois par
  app/pet_collection.py (tenue → objet de la collection, morceau → poussière).
· Tirage DATA-DRIVEN : une table pondérée (catégories → poids → réserve). Le tirage est fait par le serveur avec un
  hasard HMAC par compte, jour et coffre (app/pet_store.py) : imprévisible, rejouable et vérifiable ; le résultat garde
  son jet (`roll`) et la version de la table. Les accessoires viennent du catalogue (app/pet_catalog.json), par rareté.
· Garantie anti-malchance : au plus 30 coffres d'affilée sans Épique (ou mieux) ; le 30e en donne un.
· Doublon (objet déjà à toi) → poussière d'étoile ; Légendaire : d'abord ceux qui te manquent ; Mythique (« Objet
  mystère ») : seulement s'il reste des exemplaires (tirage limité, numérotés), sinon la part passe au Légendaire.
Économie sans argent réel : rien ne s'achète avec de l'argent, rien ne s'échange contre de l'argent, aucun lot réel.
"""
from . import pet_catalog

TABLE_VERSION = 2
PITY = 30                                  # un Épique (ou mieux) au plus tard au 30e coffre
EPIC_PLUS = ("epic", "legendary", "mythic")
PIECE_DUST = 5                             # ancien morceau de tenue (lot 1) → poussière

SNACKS = {   # goûters rares (sac) : donnés hors limite de repas
    "cupcake": ("Cupcake arc-en-ciel", "🧁", {"food": 35.0, "joy": 12.0}),
    "glace": ("Glace à la fraise", "🍨", {"food": 25.0, "joy": 18.0}),
    "crepe": ("Crêpe au chocolat", "🥞", {"food": 40.0, "joy": 8.0}),
}
STICKERS = (
    ("disco", "Boule à facettes", "🪩"), ("vinyle", "Vinyle", "💿"), ("micro", "Micro", "🎤"),
    ("guitare", "Guitare", "🎸"), ("pizza", "Pizza", "🍕"), ("fusee", "Fusée", "🚀"), ("arcenciel", "Arc-en-ciel", "🌈"),
    ("etoile", "Étoile", "⭐"), ("lune", "Lune", "🌙"), ("cactus", "Cactus", "🌵"), ("donut", "Donut", "🍩"),
    ("ballon", "Ballon", "🎈"), ("casque", "Casque", "🎧"), ("cerise", "Cerises", "🍒"), ("champi", "Champignon", "🍄"),
    ("licorne", "Licorne", "🦄"), ("pingouin", "Pingouin", "🐧"), ("ananas", "Ananas", "🍍"), ("de", "Dé", "🎲"),
    ("trefle", "Trèfle", "🍀"), ("glacon", "Glaçon", "🧊"), ("tournesol", "Tournesol", "🌻"), ("hibou", "Hibou", "🦉"),
    ("couronne", "Couronne", "👑"),
)
GOLD_STICKER = "sticker:or"   # palier de 50 jours (jamais dans les coffres)


def _catalog() -> dict[str, dict]:
    items = {f"snack:{k}": {"family": "snack", "label": v[0], "emoji": v[1], "gains": v[2], "max": None}
             for k, v in SNACKS.items()}
    items |= {f"sticker:{k}": {"family": "sticker", "label": f"Sticker {label}", "emoji": emo, "max": 1}
              for k, label, emo in STICKERS}
    items[GOLD_STICKER] = {"family": "sticker", "label": "Sticker Médaille d'or", "emoji": "🏅", "max": 1}
    return items


ITEMS = _catalog()
SNACK_WEIGHT, STICKER_WEIGHT = 8, 1   # objet : moitié goûters (3), moitié stickers (24)

# Table du coffre du jour (et du coffre bonus) : poids sur 1000, affichés pour CHAQUE tirage (« i »).
CHEST_TABLE = (
    {"cat": "coins", "weight": 500, "coins": (10, 30)},
    {"cat": "object", "weight": 150, "pool": tuple((f"snack:{k}", SNACK_WEIGHT) for k in SNACKS)
                                             + tuple((f"sticker:{k}", STICKER_WEIGHT) for k, _, _ in STICKERS)},
    {"cat": "common", "weight": 220},
    {"cat": "rare", "weight": 90},
    {"cat": "epic", "weight": 32},
    {"cat": "legendary", "weight": 7},
    {"cat": "mythic", "weight": 1},
)
BONUS_COINS_FACTOR = 2     # coffre bonus des missions : pièces doublées
FALLBACK_COINS = 25        # réserve vide : des pièces à la place
ODDS_LABELS = {"coins": "Pièces (10 à 30)", "object": "Goûter rare ou sticker", "common": "Accessoire Commun",
               "rare": "Accessoire Rare", "epic": "Accessoire Épique", "legendary": "Accessoire Légendaire (numéroté)",
               "mythic": "Objet mystère"}


def _table(mythic_open: bool, guaranteed: bool) -> list[dict]:
    """Table effective : sans Mythique disponible, sa part va au Légendaire ; garantie : Épique ou mieux seulement."""
    rows = [dict(r) for r in CHEST_TABLE]
    if not mythic_open:
        myth = next(r for r in rows if r["cat"] == "mythic")
        next(r for r in rows if r["cat"] == "legendary")["weight"] += myth["weight"]
        myth["weight"] = 0
    if guaranteed:
        rows = [r for r in rows if r["cat"] in EPIC_PLUS]
    return [r for r in rows if r["weight"] > 0]


def mythic_pool(mythic_left: dict | None) -> list[str]:
    return [m for m in pet_catalog.mythics("chest") if int((mythic_left or {}).get(m, 0)) > 0]


def odds(pity: int = 0, mythic_left: dict | None = None) -> list[dict]:
    """Chances du prochain coffre, en %, à une décimale (« Objet mystère : 0,1 % » compris)."""
    guaranteed = pity >= PITY - 1
    rows = _table(bool(mythic_pool(mythic_left)), guaranteed)
    total = sum(r["weight"] for r in rows)
    shown = [{"kind": r["cat"], "label": ODDS_LABELS[r["cat"]], "pct": round(100 * r["weight"] / total, 1)} for r in rows]
    if not guaranteed and not any(r["kind"] == "mythic" for r in shown):
        shown.append({"kind": "mythic", "label": ODDS_LABELS["mythic"] + " (tous les exemplaires sont partis)", "pct": 0.0})
    return shown


def pity_left(pity: int) -> int:
    """Coffres avant l'Épique garanti (1 = le prochain)."""
    return max(1, PITY - int(pity or 0))


def _complete(item: str, inv: dict) -> bool:
    info = ITEMS.get(item) or {}
    return info.get("max") is not None and inv.get(item, 0) >= info["max"]


def _weighted(rng, rows: list[tuple]) -> tuple:
    roll = rng.random() * sum(w for *_, w in rows)
    acc = 0.0
    for row in rows:
        acc += row[-1]
        if roll < acc:
            return row
    return rows[-1]


class _Fixed:
    """Un jet déjà tiré, rejoué par _weighted (la catégorie dépend de `roll`, gardé dans le résultat)."""

    def __init__(self, value: float):
        self.value = value

    def random(self) -> float:
        return self.value


def draw(rng, inv: dict, owned: set[str], pity: int = 0, mythic_left: dict | None = None, bonus: bool = False) -> dict:
    """Un tirage : la catégorie d'abord (poids de la table, garantie comprise), puis l'objet dans sa réserve."""
    roll = rng.random()
    guaranteed = pity >= PITY - 1
    table = _table(bool(mythic_pool(mythic_left)), guaranteed)
    row = _weighted(_Fixed(roll), [(r, r["weight"]) for r in table])[0]
    factor = BONUS_COINS_FACTOR if bonus else 1
    base = {"cat": row["cat"], "roll": round(roll, 6), "table": TABLE_VERSION, "guaranteed": guaranteed}
    if row["cat"] == "coins":
        lo, hi = row["coins"]
        return base | {"kind": "coins", "amount": rng.randint(lo, hi) * factor}
    if row["cat"] == "object":
        pool = [(item, w) for item, w in row["pool"] if not _complete(item, inv)]
        if not pool:
            return base | {"kind": "coins", "amount": FALLBACK_COINS * factor}
        item = _weighted(rng, pool)[0]
        return base | {"kind": ITEMS[item]["family"], "item": item}
    return base | _accessory(rng, row["cat"], owned, mythic_left)


def _accessory(rng, rarity: str, owned: set[str], mythic_left: dict | None) -> dict:
    if rarity == "mythic":
        pool = mythic_pool(mythic_left)
        iid = pool[int(rng.random() * len(pool)) % len(pool)]
        return {"kind": "item", "item": iid, "rarity": "mythic", "dup": False, "mint": True}
    pool = pet_catalog.chest_pool(rarity)
    if rarity == "legendary":
        missing = [i for i in pool if i not in owned]
        pool = missing or pool   # pas de doublon de Légendaire tant qu'il en manque un
    iid = pool[int(rng.random() * len(pool)) % len(pool)]
    dup = iid in owned
    return {"kind": "item", "item": iid, "rarity": rarity, "dup": dup,
            "mint": rarity in pet_catalog.INSTANCE_RARITIES and not dup}


def add(inv: dict, item: str, n: int = 1) -> dict:
    """Inventaire neuf avec `n` objets de plus (jamais au-delà du maximum de l'objet)."""
    cap = (ITEMS.get(item) or {}).get("max")
    have = inv.get(item, 0) + n
    return {**inv, item: min(have, cap) if cap is not None else have}


def apply(loop: dict, found: dict, coll: dict | None = None) -> dict:
    """Range ce qu'on a trouvé (pièces, sac, collection, poussière) ; renvoie le résultat montré (libellé, emoji).
    Un Légendaire ou un Mythique neuf (mint) est frappé en base par app/pet_store.py, qui complète le résultat."""
    if found["kind"] == "coins":
        loop["coins"] = loop.get("coins", 0) + found["amount"]
        return found | {"label": f"{found['amount']} pièces", "emoji": "🪙"}
    if found["kind"] == "item":
        return _apply_item(found, coll if coll is not None else {})
    item, info = found["item"], ITEMS[found["item"]]
    loop["inv"] = add(loop.get("inv") or {}, item)
    return found | {"label": info["label"], "emoji": info["emoji"]}


def _apply_item(found: dict, coll: dict) -> dict:
    it = pet_catalog.item(found["item"])
    rarity_label = pet_catalog.rarities()[it["rarity"]]["label"]
    coll["pity"] = 0 if found["rarity"] in EPIC_PLUS else int(coll.get("pity", 0)) + 1
    if found["dup"]:
        dust = pet_catalog.dust_value(found["item"])
        coll["dust"] = int(coll.get("dust", 0)) + dust
        return found | {"label": f"Doublon : {it['label']} (+{dust} poussière ✨)", "emoji": it["emoji"], "dust": dust,
                        "rarity_label": rarity_label, "item_info": pet_catalog.public_item(found["item"])}
    if not found["mint"]:
        coll["inv"] = {**coll.get("inv", {}), found["item"]: 1}
    label = "Objet mystère : Mythique !" if found["rarity"] == "mythic" else f"{rarity_label} : {it['label']}"
    return found | {"label": label, "emoji": it["emoji"], "rarity_label": rarity_label,
                    "item_info": pet_catalog.public_item(found["item"])}


def note_chest(coll: dict, found: dict) -> None:
    """Pièces ou objet du sac : la garantie avance aussi (l'accessoire, lui, est compté par _apply_item)."""
    if found["kind"] != "item":
        coll["pity"] = int(coll.get("pity", 0)) + 1


def bag(inv: dict) -> list[dict]:
    return [{"id": k.split(":", 1)[1], "label": ITEMS[k]["label"], "emoji": ITEMS[k]["emoji"], "n": n}
            for k, n in inv.items() if k.startswith("snack:") and k in ITEMS and n > 0]


def stickers(inv: dict) -> dict:
    have = [ITEMS[k]["emoji"] for k, n in inv.items() if k.startswith("sticker:") and k in ITEMS and n > 0]
    return {"have": have, "total": len(STICKERS) + 1}
