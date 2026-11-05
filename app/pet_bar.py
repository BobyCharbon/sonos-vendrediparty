"""Zicou — la barre « petit cadeau » (avis de l'admin du 5.11.2026 : « une barre qui se remplit et il peut récupérer des
pièces ou des choses comme ça, qui pousse à venir toutes les 2-3 heures »).

· La barre se remplit en FILL_MINUTES (2 h 30) ; pleine, on touche « Récupérer » : une petite récompense tirée dans
  une petite table aux chances AFFICHÉES (pièces, goûter, XP, rare : poussière d'étoile).
· Pas d'accumulation : pleine, elle attend (rien ne se perd si on ne vient pas, rien ne s'empile non plus).
· Au plus PER_DAY récupérations par jour (jour de Zurich) ; la 4e faite, elle repart le lendemain à 8 h.
· La nuit (23 h – 8 h), elle se met en pause : rien ne pousse à se réveiller. Pleine avant la nuit, elle se récupère
  quand on veut, même la nuit.
· Rien ne la remplit plus vite (ni pièces, ni pub, ni partage, ni invitation) ; rien de payant ; jamais pour boire.
· Calcul et hasard par le SERVEUR : jet HMAC par compte, jour et numéro de récupération (app/pet_store.py), donc
  rejouable après un conflit et vérifiable ; le navigateur ne fait qu'afficher.

Tout vit dans owner["bar"] : {"from", "full_at", "day", "n", "last"}. Calcul pur : `now` et `rng` en paramètres.
Économie (scratchpad economie/rapport.md) : ~2 pièces en moyenne par récupération, 4 au plus par jour, à côté du coffre
du jour (8 à 20) ; la poussière reste rare (3 %).
"""
import copy
from datetime import datetime, time, timedelta

from . import pet, pet_chest, pet_collection, pet_loop, pet_xp

FILL_MINUTES = 150            # 2 h 30 pour se remplir (réglable ici seulement)
PER_DAY = 4                   # récupérations par jour au plus
DAY_START = time(8, 0)        # la barre se remplit de 8 h…
NIGHT_START = time(23, 0)     # … à 23 h (pause la nuit)
MAX_DAYS_AHEAD = 400          # garde-fou des boucles de calcul

TABLE_VERSION = 1
BAR_COINS = (2, 5)
BAR_XP = 10
BAR_DUST = 5
TABLE = (   # poids sur 100, affichés tels quels (« i » de la barre)
    {"cat": "coins", "weight": 60},
    {"cat": "snack", "weight": 20},
    {"cat": "xp", "weight": 17},
    {"cat": "dust", "weight": 3},
)
LABELS = {"coins": f"Pièces ({BAR_COINS[0]} à {BAR_COINS[1]})", "snack": "Un goûter rare pour le sac",
          "xp": f"{BAR_XP} XP pour son niveau", "dust": f"{BAR_DUST} poussières d'étoile"}


class BarError(pet.PetError):
    pass


# ── Heures ──

def _window(d) -> tuple[datetime, datetime]:
    return datetime.combine(d, DAY_START, pet.TZ), datetime.combine(d, NIGHT_START, pet.TZ)


def is_night(now: datetime) -> bool:
    t = now.astimezone(pet.TZ).time()
    return t >= NIGHT_START or t < DAY_START


def full_at(start: datetime, minutes: int = FILL_MINUTES) -> datetime:
    """Quand une barre vide à `start` sera pleine : seules les minutes entre 8 h et 23 h comptent."""
    left, t = timedelta(minutes=minutes), start.astimezone(pet.TZ)
    for _ in range(MAX_DAYS_AHEAD):
        lo, hi = _window(t.date())
        t = max(t, lo)
        if t < hi:
            if left <= hi - t:
                return t + left
            left -= hi - t
        t = _window(t.date() + timedelta(days=1))[0]
    return t


def active_between(a: datetime, b: datetime) -> timedelta:
    """Minutes « de jour » (8 h – 23 h) entre a et b."""
    total, t, end = timedelta(0), a.astimezone(pet.TZ), b.astimezone(pet.TZ)
    for _ in range(MAX_DAYS_AHEAD):
        if t >= end:
            break
        lo, hi = _window(t.date())
        s, e = max(t, lo), min(end, hi)
        if e > s:
            total += e - s
        t = _window(t.date() + timedelta(days=1))[0]
    return total


def when_text(at: datetime, now: datetime) -> str:
    """« vers 16 h 20 », « demain vers 8 h 40 » : une heure calme, jamais un compte à rebours."""
    t, today = at.astimezone(pet.TZ), now.astimezone(pet.TZ).date()
    minute = (t.minute + 4) // 5 * 5   # arrondi aux 5 minutes suivantes
    hour = t.hour + minute // 60
    clock = f"{hour % 24} h" + (f" {minute % 60:02d}" if minute % 60 else "")
    days = (t.date() - today).days
    prefix = "" if days <= 0 else "demain " if days == 1 else f"le {t.day}.{t.month} "
    return f"{prefix}vers {clock}"


# ── État ──

def _fresh(start: datetime, day: str = "", n: int = 0, last: dict | None = None) -> dict:
    return {"from": pet.iso(start), "full_at": pet.iso(full_at(start)), "day": day, "n": n, "last": last}


def ensure(owner: dict, now: datetime) -> bool:
    """Première fois : la barre part de maintenant. Modifie `owner` (appelé sur une copie). True si créée."""
    bar = owner.get("bar")
    if isinstance(bar, dict) and pet.parse(bar.get("full_at")):
        return False
    owner["bar"] = _fresh(now)
    return True


def claimed_today(owner: dict, now: datetime) -> int:
    bar = owner.get("bar") if isinstance(owner.get("bar"), dict) else {}
    return int(bar.get("n") or 0) if bar.get("day") == pet.day_of(now) else 0


def odds() -> list[dict]:
    total = sum(r["weight"] for r in TABLE)
    return [{"kind": r["cat"], "label": LABELS[r["cat"]], "pct": round(100 * r["weight"] / total, 1),
             "text": pet_chest.odds_text(r["weight"], total)} for r in TABLE]


def view(life: dict, owner: dict, now: datetime, with_odds: bool = True) -> dict:
    """Pour l'écran et la pastille. state : filling (se remplit), full (à récupérer), rest (4/4 aujourd'hui),
    off (compagnon envolé)."""
    bar = owner.get("bar") if isinstance(owner.get("bar"), dict) else _fresh(now)
    start, done = pet.parse(bar.get("from")) or now, pet.parse(bar.get("full_at")) or full_at(now)
    n = claimed_today(owner, now)
    if life.get("stage") == "dead":
        state = "off"
    elif now >= done:
        state = "full"
    elif n >= PER_DAY:
        state = "rest"
    else:
        state = "filling"
    span = active_between(start, done).total_seconds() or FILL_MINUTES * 60
    progress = 1.0 if now >= done else max(0.0, 1 - active_between(now, done).total_seconds() / span)
    out = {"state": state, "progress": round(progress, 4), "from": pet.iso(start), "full_at": pet.iso(done),
           "when": when_text(done, now), "left_s": max(0, int((done - now).total_seconds())),
           "today": n, "per_day": PER_DAY, "fill_minutes": FILL_MINUTES, "night": is_night(now),
           "last": bar.get("last")}
    if with_odds:
        out["odds"] = odds()
    return out


# ── Récupérer ──

def draw(rng) -> dict:
    """Une récompense de la petite table (jet gardé dans le résultat : vérifiable)."""
    total = sum(r["weight"] for r in TABLE)
    roll = rng.random()
    pick, acc = TABLE[-1]["cat"], 0
    for r in TABLE:
        acc += r["weight"]
        if roll * total < acc:
            pick = r["cat"]
            break
    out = {"kind": pick, "roll": round(roll, 6), "v": TABLE_VERSION}
    if pick == "coins":
        n = rng.randint(*BAR_COINS)
        return out | {"amount": n, "emoji": "🪙", "label": f"{n} pièces"}
    if pick == "snack":
        key = sorted(pet_chest.SNACKS)[rng.randrange(len(pet_chest.SNACKS))]
        label, emoji, _ = pet_chest.SNACKS[key]
        return out | {"item": f"snack:{key}", "amount": 1, "emoji": emoji, "label": label}
    if pick == "xp":
        return out | {"amount": BAR_XP, "emoji": "⭐", "label": f"{BAR_XP} XP"}
    return out | {"amount": BAR_DUST, "emoji": "✨", "label": f"{BAR_DUST} poussières d'étoile"}


def _give(owner: dict, found: dict, now: datetime) -> list[dict]:
    if found["kind"] == "coins":
        pet_loop.loop_of(owner)["coins"] += found["amount"]
    elif found["kind"] == "snack":
        loop = pet_loop.loop_of(owner)
        loop["inv"] = pet_chest.add(loop["inv"], found["item"])
    elif found["kind"] == "dust":
        coll = pet_collection.coll_of(owner)
        coll["dust"] = int(coll.get("dust", 0)) + found["amount"]
    else:
        xp = pet_xp._state(owner, now)
        before = pet_xp.level_of(xp.get("total", 0))
        xp["total"] = int(xp.get("total", 0)) + found["amount"]
        after = pet_xp.level_of(xp["total"])
        if (after["level"], after["stars"]) > (before["level"], before["stars"]):
            return [{"kind": "xp", "xp": found["amount"], "level": after["level"], "stars": after["stars"],
                     "level_up": True}]
    return []


def claim(life: dict, owner: dict, now: datetime, rng) -> tuple[dict, dict, list[dict]]:
    """Récupère la barre pleine. Copie neuve de `owner`, la récompense, les événements (niveau). BarError si elle
    n'est pas pleine, si les 4 du jour sont faites ou si le compagnon s'est envolé (messages doux)."""
    if life.get("stage") == "dead":
        raise BarError("Il s'est envolé… Fais éclore un nouvel œuf pour retrouver la barre 🥚")
    owner = copy.deepcopy(owner)
    ensure(owner, now)
    bar, n = owner["bar"], claimed_today(owner, now)
    if n >= PER_DAY:
        raise BarError(f"Déjà {PER_DAY} cadeaux aujourd'hui. La barre repart demain à 8 h 🌙")
    done = pet.parse(bar.get("full_at")) or full_at(now)
    if now < done:
        raise BarError(f"La barre se remplit encore : pleine {when_text(done, now)} 🎁")
    found = draw(rng)
    events = _give(owner, found, now)
    n, today = n + 1, pet.day_of(now)
    tomorrow = now.astimezone(pet.TZ).date() + timedelta(days=1)
    restart = now if n < PER_DAY else datetime.combine(tomorrow, DAY_START, pet.TZ)
    shown = {k: found[k] for k in ("kind", "emoji", "label", "amount")}
    owner["bar"] = _fresh(restart, today, n, last=shown | {"at": pet.iso(now)})
    return owner, found, events
