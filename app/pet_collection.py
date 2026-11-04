"""Compagnon — la collection (lot A, 4 novembre 2026) : calcul pur, testable, sans base ni horloge cachée.

État au compte, dans owner["coll"] (jamais montré aux amis) :
  inv     : {objet: 1} — accessoires Communs, Rares, Épiques et décor (les Légendaires et Mythiques sont des
            EXEMPLAIRES numérotés en base, public.pet_items, avec certificat signé : voir app/pet_cert.py) ;
  dust    : poussière d'étoile ✨ (doublons) ; pity : coffres d'affilée sans Épique (garantie à 30) ;
  series  : séries complétées (bonus une fois) ; awards : cadeaux d'événement déjà rangés ; shop : achats du jour.
Ce que voient les amis vit dans life : acc {emplacement: objet} (ce qu'il porte), shiny, showcase (vitrine).
Économie FERMÉE : les pièces se gagnent en jouant et ne s'achètent jamais ; rien ne se convertit en argent.
"""
import copy

from . import pet_catalog, pet_chest

SHOP_COMMONS, SHOP_RARES = 3, 1           # boutique du jour : 4 articles (3 Communs, 1 Rare), renouvelée à minuit
SNACK_PRICES = {"cupcake": 40, "glace": 40, "crepe": 50}
SNACKS_PER_DAY = 3
SHINY_ONE_IN = 64                          # Zicou shiny : 1 éclosion sur 64 (chance affichée)
SHOWCASE_MAX = 3
SHOWCASE_TITLE_MAX = 40


class CollectionError(ValueError):
    """Refus (pas assez de pièces, objet déjà à toi…) : message montré tel quel, sans reproche."""


def new_coll() -> dict:
    return {"v": 1, "inv": {}, "dust": 0, "pity": 0, "series": [], "awards": [], "shop": {"day": "", "bought": []},
            "snacks": {"day": "", "n": 0}, "upgraded": False}


def coll_of(owner: dict) -> dict:
    """owner["coll"] complété ; la première fois, les tenues et morceaux d'avant la collection sont convertis :
    tenue gagnée (lot 1) → objet de la collection, morceau de tenue → 5 poussières."""
    coll = owner.get("coll")
    if not isinstance(coll, dict):
        coll = owner["coll"] = {}
    for key, value in new_coll().items():
        coll.setdefault(key, copy.deepcopy(value))
    if not coll["upgraded"]:
        _upgrade(owner, coll)
    return coll


def _upgrade(owner: dict, coll: dict) -> None:
    loop = owner.get("loop") if isinstance(owner.get("loop"), dict) else {}
    inv = dict(loop.get("inv") or {})
    for key, n in list(inv.items()):
        family, _, name = key.partition(":")
        if family == "outfit" and n > 0 and pet_catalog.item(name):
            coll["inv"][name] = 1
        elif family == "piece" and n > 0:
            coll["dust"] += pet_chest.PIECE_DUST * int(n)
        if family in ("outfit", "piece"):
            del inv[key]
    if loop:
        loop["inv"] = inv
    for oid in owner.get("unlocked", []):
        if pet_catalog.item(oid):
            coll["inv"][oid] = 1
    coll["upgraded"] = True


def owned(owner: dict, instances: list[dict] | None = None) -> set[str]:
    """Tout ce que possède le compte : collection, tenues gagnées (anciennes règles) et exemplaires numérotés."""
    coll = owner.get("coll") or {}
    have = {i for i, n in (coll.get("inv") or {}).items() if n > 0}
    have |= {i for i in owner.get("unlocked", []) if pet_catalog.item(i)}
    have |= {x["item"] for x in instances or [] if x.get("item")}
    return have


def add_item(owner: dict, iid: str) -> None:
    coll = coll_of(owner)
    coll["inv"] = {**coll["inv"], iid: 1}


# ── Séries ──

def series_bonus(owner: dict, have: set[str]) -> list[dict]:
    """Séries complètes (hors Mythique) pas encore payées : bonus une fois (pièces et poussière)."""
    coll, loop, out = coll_of(owner), owner.setdefault("loop", {}), []
    for sid, s in pet_catalog.series().items():
        if sid in coll["series"] or not set(pet_catalog.series_items(sid)) <= have:
            continue
        coll["series"] = sorted(set(coll["series"]) | {sid})
        loop["coins"] = int(loop.get("coins", 0)) + s["bonus"]["coins"]
        coll["dust"] += s["bonus"]["dust"]
        out.append({"kind": "series_done", "series": sid, "label": s["label"], "emoji": s["emoji"], **s["bonus"]})
    return out


# ── Boutique (pièces gagnées seulement) ──

def shop_today(rng) -> list[str]:
    """Les 4 articles du jour (même boutique pour tout le monde ce jour-là : hasard du serveur, graine du jour)."""
    commons = sorted(pet_catalog.chest_pool("common"))
    rares = sorted(pet_catalog.chest_pool("rare"))
    pick = []
    for pool, n in ((commons, SHOP_COMMONS), (rares, SHOP_RARES)):
        left = list(pool)
        for _ in range(min(n, len(left))):
            pick.append(left.pop(int(rng.random() * len(left)) % len(left)))
    return pick


def _spend(owner: dict, price: int) -> None:
    loop = owner.setdefault("loop", {})
    coins = int(loop.get("coins", 0))
    if coins < price:
        raise CollectionError(f"Il te manque {price - coins} pièces 🪙 Elles se gagnent en jouant avec lui.")
    loop["coins"] = coins - price


def buy(owner: dict, have: set[str], what: str, today: str, shop: list[str]) -> dict:
    """Acheter avec des pièces : un article de la boutique du jour, un décor de la chambre ou un goûter rare."""
    coll = coll_of(owner)
    if what.startswith("snack:"):
        return _buy_snack(owner, coll, what.split(":", 1)[1], today)
    it = pet_catalog.item(what)
    if not it or (what not in shop and what not in pet_catalog.decor_items()):
        raise CollectionError("Cet article n'est pas en boutique aujourd'hui.")
    if what in have:
        raise CollectionError("Il est déjà à toi ✨")
    if coll["shop"].get("day") != today:
        coll["shop"] = {"day": today, "bought": []}
    if what in coll["shop"]["bought"]:
        raise CollectionError("Déjà acheté aujourd'hui.")
    price = pet_catalog.shop_price(what)
    _spend(owner, price)
    coll["shop"]["bought"] = coll["shop"]["bought"] + [what]
    coll["inv"] = {**coll["inv"], what: 1}
    return {"kind": "bought", "item": what, "price": price}


def _buy_snack(owner: dict, coll: dict, snack: str, today: str) -> dict:
    if snack not in SNACK_PRICES:
        raise CollectionError("Ce goûter n'est pas en boutique.")
    if coll["snacks"].get("day") != today:
        coll["snacks"] = {"day": today, "n": 0}
    if coll["snacks"]["n"] >= SNACKS_PER_DAY:
        raise CollectionError(f"{SNACKS_PER_DAY} goûters par jour au plus : il en a assez pour aujourd'hui 🧁")
    _spend(owner, SNACK_PRICES[snack])
    coll["snacks"] = {"day": today, "n": coll["snacks"]["n"] + 1}
    loop = owner["loop"]
    loop["inv"] = pet_chest.add(loop.get("inv") or {}, f"snack:{snack}")
    return {"kind": "bought", "item": f"snack:{snack}", "price": SNACK_PRICES[snack]}


# ── Atelier (poussière d'étoile) ──

def craft(owner: dict, have: set[str], iid: str) -> dict:
    """Fabriquer un objet précis avec la poussière (40 / 100 / 400 / 1 600 ✨). Jamais un Mythique ni un souvenir de
    soirée. Un Légendaire fabriqué est frappé en base (mint), avec son numéro et son certificat."""
    cost = pet_catalog.craft_cost(iid)
    if cost is None:
        raise CollectionError("Cet objet ne se fabrique pas à l'atelier.")
    if iid in have:
        raise CollectionError("Il est déjà à toi ✨")
    coll = coll_of(owner)
    if coll["dust"] < cost:
        raise CollectionError(f"Il te manque {cost - coll['dust']} poussières d'étoile ✨ Les doublons en donnent.")
    coll["dust"] -= cost
    mint = pet_catalog.is_instance(iid)
    if not mint:
        coll["inv"] = {**coll["inv"], iid: 1}
    return {"kind": "crafted", "item": iid, "cost": cost, "mint": mint}


# ── Ce qu'il porte, vitrine, shiny ──

def worn(life: dict) -> dict:
    """Accessoires portés {emplacement: objet} ; l'ancienne tenue unique (life["outfit"]) y est rangée."""
    acc = {k: v for k, v in (life.get("acc") or {}).items() if pet_catalog.item(v)}
    old = life.get("outfit")
    if old and pet_catalog.item(old):
        acc.setdefault(pet_catalog.item(old)["slot"], old)
    return acc


def equip(life: dict, have: set[str], slot: str, iid: str) -> None:
    """Porter (ou retirer, iid vide) un accessoire sur son emplacement."""
    if slot not in pet_catalog.SLOT_IDS:
        raise CollectionError("Emplacement inconnu.")
    acc = worn(life)
    if not iid:
        acc.pop(slot, None)
    else:
        it = pet_catalog.item(iid)
        if not it or it["slot"] != slot:
            raise CollectionError("Cet objet ne va pas à cet endroit.")
        if iid not in have:
            raise CollectionError("Pas encore débloquée : cet objet n'est pas encore à toi.")
        acc[slot] = iid
    life["acc"] = acc
    life["outfit"] = None


def strip_lost(life: dict, have: set[str]) -> None:
    """N'affiche jamais un objet qui n'est plus à lui (retiré par la modération, compte réparé…)."""
    life["acc"] = {s: i for s, i in worn(life).items() if i in have}
    if life.get("outfit") and life["outfit"] not in have:
        life["outfit"] = None


def set_showcase(life: dict, have: set[str], items: list[str], title: str, instances: list[dict]) -> None:
    """Vitrine : 3 objets au plus (à soi) et un titre court, déjà passé par la modération (app/moderation.py)."""
    picked = list(dict.fromkeys(i for i in items if i))
    if len(picked) > SHOWCASE_MAX:
        raise CollectionError(f"{SHOWCASE_MAX} objets au plus dans la vitrine.")
    if any(i not in have for i in picked):
        raise CollectionError("Seuls tes objets vont dans ta vitrine.")
    serials = {x["item"]: x for x in instances or []}
    life["showcase"] = {"title": title[:SHOWCASE_TITLE_MAX],
                        "items": [{"id": i, **({"serial": serials[i]["serial"], "edition": serials[i].get("edition")}
                                               if i in serials else {})} for i in picked]}


def showcase_view(life: dict) -> dict | None:
    sc = life.get("showcase")
    if not isinstance(sc, dict):
        return None
    out = []
    for x in sc.get("items") or []:
        if isinstance(x, dict) and pet_catalog.item(x.get("id")):
            out.append(pet_catalog.public_item(x["id"]) | {"serial": x.get("serial"), "of": x.get("edition")})
    if not out and not sc.get("title"):
        return None
    return {"title": str(sc.get("title") or ""), "items": out}


def roll_shiny(rng) -> bool:
    return rng.random() < 1 / SHINY_ONE_IN


# ── Zicoudex ──

def dex(have: set[str], instances: list[dict] | None = None) -> list[dict]:
    """Tous les objets obtenables, par série et rareté. Pas encore à toi : grisé, avec rareté et « où le trouver ».
    MYTHIQUE pas à toi : TOUJOURS masqué (ni nom, ni identifiant, ni image) — une silhouette « ??? »."""
    serials = {}
    for x in instances or []:
        serials.setdefault(x["item"], x)
    order = {r: i for i, r in enumerate(pet_catalog.RARITY_ORDER)}
    out = []
    for sid, s in pet_catalog.series().items():
        rows = []
        for iid in sorted(pet_catalog.series_items(sid, with_mythic=True), key=lambda i: order[pet_catalog.item(i)["rarity"]]):
            it = pet_catalog.item(iid)
            if it["rarity"] == "mythic" and iid not in have:
                rows.append({"masked": True, "rarity": "mythic", "rarity_label": "Mythique", "label": "???",
                             "where": pet_catalog.where(iid)})
                continue
            row = pet_catalog.public_item(iid) | {"owned": iid in have, "where": pet_catalog.where(iid),
                                                  "craft": pet_catalog.craft_cost(iid)}
            if iid in serials:
                row |= {"serial": serials[iid]["serial"], "code": serials[iid].get("code"), "instance": serials[iid]["id"]}
            rows.append(row)
        regular = pet_catalog.series_items(sid)
        out.append({"id": sid, "label": s["label"], "emoji": s["emoji"], "bonus": s["bonus"],
                    "have": sum(1 for i in regular if i in have), "total": len(regular), "items": rows})
    return out
