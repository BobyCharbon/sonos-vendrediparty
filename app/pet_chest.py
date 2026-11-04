"""Compagnon — coffres et inventaire (lot 1 « revenir tous les jours »), pensés pour grandir (système de collection à venir).

· Inventaire : {identifiant: quantité}, jamais un booléen par objet. Identifiants « famille:nom » : snack:cupcake,
  sticker:disco, piece:casque (morceau de tenue), outfit:casque (tenue gagnée). Un objet inconnu est gardé tel quel.
· Tirage DATA-DRIVEN : une table pondérée (catégories → poids → réserve d'objets pondérés). Le tirage est fait par le
  serveur avec un hasard déterministe par compte, jour et coffre (app/pet_store.py) : rejouable et vérifiable, et le
  résultat garde son jet (`roll`) et la version de la table. Un objet déjà complet (sticker déjà collé, tenue déjà à
  toi) sort de la réserve ; réserve vide → des pièces à la place (jamais un tirage vide).
Économie sans argent réel : rien ne s'achète, rien ne s'échange contre de l'argent, aucun lot réel.
"""
TABLE_VERSION = 1
PIECES_NEEDED = 3
CHEST_OUTFITS = ("lunettes", "casquette", "casque", "boa", "chapeau")   # tenues actuelles qu'un coffre peut donner

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
    from .pet import OUTFITS  # import tardif : pet n'importe pas ce module
    items = {f"snack:{k}": {"family": "snack", "label": v[0], "emoji": v[1], "gains": v[2], "max": None}
             for k, v in SNACKS.items()}
    items |= {f"sticker:{k}": {"family": "sticker", "label": f"Sticker {label}", "emoji": emo, "max": 1}
              for k, label, emo in STICKERS}
    items[GOLD_STICKER] = {"family": "sticker", "label": "Sticker Médaille d'or", "emoji": "🏅", "max": 1}
    for oid, label, emo, _ in OUTFITS:
        items[f"outfit:{oid}"] = {"family": "outfit", "label": label, "emoji": emo, "max": 1, "outfit": oid}
        items[f"piece:{oid}"] = {"family": "piece", "label": f"Morceau de {label}", "emoji": emo, "max": PIECES_NEEDED,
                                 "outfit": oid}
    return items


ITEMS = _catalog()
SNACK_WEIGHT, STICKER_WEIGHT = 8, 1   # objet : moitié goûters (3), moitié stickers (24)

# Table du coffre du jour : poids en % (affichés sous « i »). « coins » : bornes ; sinon une réserve pondérée.
CHEST_TABLE = (
    {"cat": "coins", "weight": 70, "coins": (10, 30)},
    {"cat": "object", "weight": 20, "pool": tuple((f"snack:{k}", SNACK_WEIGHT) for k in SNACKS)
                                            + tuple((f"sticker:{k}", STICKER_WEIGHT) for k, _, _ in STICKERS)},
    {"cat": "piece", "weight": 8, "pool": tuple((f"piece:{o}", 1) for o in CHEST_OUTFITS)},
    {"cat": "rare", "weight": 2, "pool": tuple((f"outfit:{o}", 1) for o in CHEST_OUTFITS)},
)
BONUS_COINS_FACTOR = 2     # coffre bonus des missions : pièces doublées
FALLBACK_COINS = 25        # réserve vide : des pièces à la place (×2 pour une tenue rare)


def odds(table=CHEST_TABLE) -> list[dict]:
    total = sum(row["weight"] for row in table)
    return [{"kind": row["cat"], "pct": round(100 * row["weight"] / total)} for row in table]


def _complete(item: str, inv: dict, unlocked: set[str]) -> bool:
    """Objet qu'il ne sert plus à rien de tirer : sticker déjà collé, tenue (ou ses morceaux) déjà à toi."""
    info = ITEMS.get(item) or {}
    if info.get("outfit") and info["outfit"] in unlocked:
        return True
    return info.get("max") is not None and inv.get(item, 0) >= info["max"]


def _weighted(rng, rows: list[tuple]) -> tuple:
    roll = rng.random() * sum(w for *_, w in rows)
    acc = 0.0
    for row in rows:
        acc += row[-1]
        if roll < acc:
            return row
    return rows[-1]


def draw(rng, inv: dict, unlocked: set[str], bonus: bool = False, table=CHEST_TABLE) -> dict:
    """Un tirage : la catégorie d'abord (poids de la table), puis l'objet dans sa réserve (sans les objets complets)."""
    roll = rng.random()
    row = _weighted(_Fixed(roll), [(r, r["weight"]) for r in table])[0]
    factor = BONUS_COINS_FACTOR if bonus else 1
    base = {"cat": row["cat"], "roll": round(roll, 6), "table": TABLE_VERSION}
    if "coins" in row:
        lo, hi = row["coins"]
        return base | {"kind": "coins", "amount": rng.randint(lo, hi) * factor}
    pool = [(item, w) for item, w in row["pool"] if not _complete(item, inv, unlocked)]
    if not pool:
        fixed = FALLBACK_COINS * (2 if row["cat"] == "rare" else 1)
        return base | {"kind": "coins", "amount": fixed * factor}
    item = _weighted(rng, pool)[0]
    return base | {"kind": ITEMS[item]["family"], "item": item}


class _Fixed:
    """Un jet déjà tiré, rejoué par _weighted (la catégorie dépend de `roll`, gardé dans le résultat)."""

    def __init__(self, value: float):
        self.value = value

    def random(self) -> float:
        return self.value


def add(inv: dict, item: str, n: int = 1) -> dict:
    """Inventaire neuf avec `n` objets de plus (jamais au-delà du maximum de l'objet)."""
    cap = (ITEMS.get(item) or {}).get("max")
    have = inv.get(item, 0) + n
    return {**inv, item: min(have, cap) if cap is not None else have}


def apply(loop: dict, found: dict) -> dict:
    """Range ce qu'on a trouvé dans `loop` (pièces, inventaire) ; renvoie le résultat montré (libellé, emoji)."""
    if found["kind"] == "coins":
        loop["coins"] = loop.get("coins", 0) + found["amount"]
        return found | {"label": f"{found['amount']} pièces", "emoji": "🪙"}
    item, info = found["item"], ITEMS[found["item"]]
    loop["inv"] = add(loop.get("inv") or {}, item)
    label = info["label"]
    if info["family"] == "piece":
        have = loop["inv"][item]
        label = f"{label} ({have}/{PIECES_NEEDED})"
        if have >= PIECES_NEEDED:
            loop["inv"] = add(loop["inv"], f"outfit:{info['outfit']}")
    elif info["family"] == "outfit":
        label = f"Tenue rare : {label}"
    return found | {"label": label, "emoji": info["emoji"]}


def bag(inv: dict) -> list[dict]:
    return [{"id": k.split(":", 1)[1], "label": ITEMS[k]["label"], "emoji": ITEMS[k]["emoji"], "n": n}
            for k, n in inv.items() if k.startswith("snack:") and k in ITEMS and n > 0]


def stickers(inv: dict) -> dict:
    have = [ITEMS[k]["emoji"] for k, n in inv.items() if k.startswith("sticker:") and k in ITEMS and n > 0]
    return {"have": have, "total": len(STICKERS) + 1}


def pieces(inv: dict, unlocked: set[str]) -> list[dict]:
    out = []
    for oid in CHEST_OUTFITS:
        if oid in unlocked:
            continue
        info = ITEMS[f"outfit:{oid}"]
        out.append({"id": oid, "label": info["label"], "emoji": info["emoji"],
                    "have": min(PIECES_NEEDED, inv.get(f"piece:{oid}", 0)), "need": PIECES_NEEDED})
    return out
