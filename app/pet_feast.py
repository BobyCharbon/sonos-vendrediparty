"""Zicou — les festins (économie du 4.11.2026, scratchpad economie/usages-pieces.md, usage n° 1).

Des plats spéciaux, payés en pièces GAGNÉES (jamais achetées), à effet borné dans le temps :
  · 🍕 Pizza dorée (120) : XP ×2 pendant 24 h (gains et plafonds du jour, app/pet_xp.py) — jamais « pièces ×2 » ;
  · 🫕 Fondue (60)       : humeur au maximum et air de fête pendant 6 h ;
  · 🧀 Raclette (100)    : aucune jauge ne baisse pendant 24 h (le sommeil répare toujours l'énergie).
Un seul festin actif à la fois, un ACHAT par jour. Un festin ne change aucune chance de coffre et ne donne aucun
avantage contre les amis. Offrir un festin au Zicou d'un ami (Pizza dorée ou Fondue seulement : une Raclette offerte
en boucle figerait un Zicou sans soin) passe par le système de cadeaux existant (pet_gift) : on offre un EFFET, jamais
des pièces. Reçu pendant un autre festin, il attend son tour (file de QUEUE_MAX au plus).
Calcul pur, horloge en paramètre ; l'état vit dans life["feast"] (et life["feast_next"]).
"""
from datetime import datetime, timedelta, timezone

FEASTS = {
    "pizza": {"label": "Pizza dorée", "emoji": "🍕", "price": 120, "hours": 24, "effect": "XP ×2 pendant 24 h",
              "giftable": True},
    "fondue": {"label": "Fondue", "emoji": "🫕", "price": 60, "hours": 6,
               "effect": "Humeur au maximum et air de fête pendant 6 h", "giftable": True},
    "raclette": {"label": "Raclette", "emoji": "🧀", "price": 100, "hours": 24,
                 "effect": "Aucune jauge ne baisse pendant 24 h", "giftable": False},
}
FROZEN = {"raclette": ("food", "joy", "care", "energy"), "fondue": ("joy",)}
GIFT_KINDS = {f"feast_{k}": k for k, v in FEASTS.items() if v["giftable"]}   # kind de pet_gift → festin
QUEUE_MAX = 5
XP_FACTOR = 2


class FeastError(ValueError):
    """Refus (déjà un festin, déjà acheté aujourd'hui…) : message montré tel quel, sans reproche."""


def _parse(value) -> datetime | None:
    if not value:
        return None
    t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def current(life: dict, at: datetime) -> dict | None:
    """Le festin en cours à l'instant `at` (None sinon)."""
    f = life.get("feast")
    if not isinstance(f, dict) or f.get("kind") not in FEASTS:
        return None
    start, end = _parse(f.get("from")), _parse(f.get("until"))
    return f if start and end and start <= at < end else None


def frozen(life: dict, at: datetime) -> tuple:
    f = current(life, at)
    return FROZEN.get(f["kind"], ()) if f else ()


def xp_factor(life: dict, at: datetime) -> int:
    f = current(life, at)
    return XP_FACTOR if f and f["kind"] == "pizza" else 1


def next_boundary(life: dict, at: datetime) -> datetime | None:
    """Prochaine fin de festin après `at` (advance() y coupe ses pas : un gel s'arrête pile à l'heure)."""
    end = _parse((life.get("feast") or {}).get("until")) if isinstance(life.get("feast"), dict) else None
    return end if end and end > at else None


def start(life: dict, kind: str, at: datetime, by: str = "") -> dict:
    """Commence un festin à `at` (effet de départ compris : la Fondue met l'humeur au maximum)."""
    info = FEASTS[kind]
    until = at + timedelta(hours=info["hours"])
    life["feast"] = {"kind": kind, "from": _iso(at), "until": _iso(until), **({"by": by[:40]} if by else {})}
    if kind == "fondue":
        life["g"]["joy"] = 100.0
        party = _parse(life.get("party_until"))
        life["party_until"] = _iso(max(until, party) if party else until)
    return life["feast"]


def roll(life: dict, at: datetime) -> bool:
    """Festin fini et un autre (offert) attend : il commence à la fin du précédent. True si un festin a commencé."""
    f = life.get("feast")
    queue = list(life.get("feast_next") or [])
    end = _parse(f.get("until")) if isinstance(f, dict) else None
    if not queue or (end and end > at):
        return False
    nxt = queue.pop(0)
    life["feast_next"] = queue
    if nxt.get("kind") in FEASTS:
        start(life, nxt["kind"], end if end and end <= at else at, nxt.get("by", ""))
    return True


def receive(life: dict, gift_kind: str, at: datetime, by: str) -> str:
    """Festin offert par un ami : commence tout de suite, ou attend la fin du festin en cours. Renvoie « now » ou
    « later » (ou « full » : file pleine, le cadeau est ouvert sans effet)."""
    kind = GIFT_KINDS.get(gift_kind)
    if not kind or life.get("stage") in ("egg", "dead"):
        return "full"
    if current(life, at) is None and not life.get("feast_next"):
        start(life, kind, at, by)
        return "now"
    queue = list(life.get("feast_next") or [])
    if len(queue) >= QUEUE_MAX:
        return "full"
    life["feast_next"] = queue + [{"kind": kind, "by": by[:40], "at": _iso(at)}]
    return "later"


def buy(life: dict, owner: dict, kind: str, now: datetime, today: str, spend) -> dict:
    """Acheter un festin pour SON Zicou : vivant et réveillé, aucun festin en cours, un achat par jour. `spend(price)`
    débite les pièces (lève une erreur s'il en manque). Modifie life et owner (appelé sur des copies)."""
    info = FEASTS.get(kind)
    if not info:
        raise FeastError("Ce festin n'existe pas.")
    if life.get("stage") in ("egg", "dead"):
        raise FeastError("Il ne peut pas manger de festin pour l'instant.")
    if life.get("asleep"):
        raise FeastError("Chut, il dort 🌙 Le festin attendra son réveil.")
    cur = current(life, now)
    if cur or life.get("feast_next"):
        what = FEASTS[cur["kind"]]["label"] if cur else "un festin offert"
        raise FeastError(f"Un festin à la fois : il savoure encore {what} 😋")
    shop = owner.setdefault("coll", {})
    if shop.get("feast_day") == today:
        raise FeastError("Un festin par jour : il en aura un autre demain 🍽️")
    spend(info["price"])
    shop["feast_day"] = today
    started = start(life, kind, now)
    return {"kind": "feast", "feast": kind, "price": info["price"], "until": started["until"]}


def view(life: dict, owner: dict, now: datetime, today: str) -> dict:
    """Pour l'écran : la carte des festins, celui en cours, ceux qui attendent."""
    cur = current(life, now)
    bought = (owner.get("coll") or {}).get("feast_day") == today
    return {
        "menu": [{"id": k, **{x: v[x] for x in ("label", "emoji", "price", "hours", "effect", "giftable")}}
                 for k, v in FEASTS.items()],
        "active": {"kind": cur["kind"], "until": cur["until"], "by": cur.get("by", ""), **FEASTS[cur["kind"]]} if cur else None,
        "waiting": [{"kind": q.get("kind"), "by": q.get("by", "")} for q in life.get("feast_next") or []
                    if q.get("kind") in FEASTS],
        "bought_today": bought,
    }
