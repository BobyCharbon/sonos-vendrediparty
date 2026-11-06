"""Compagnon — la boucle quotidienne (lot 1 « donner l'envie de venir tous les jours », 4 novembre 2026).

Calcul pur, horloge (`now`) et hasard (`rng`) en paramètres : les tests simulent des semaines en une milliseconde.
  · coffre du jour : à la 1re visite du jour, « Zicou a trouvé un truc » ; tiré par le SERVEUR à l'ouverture, d'après
    une table pondérée par rareté (app/pet_chest.py : pièces, goûter ou sticker, accessoire Commun → Mythique, avec
    garantie d'un Épique au plus tard au 45e coffre) ; un par jour, non cumulable, jusqu'à minuit ;
  · missions : 3 par jour (soin, jeu, sociale) → coffre bonus à 3/3 ; une mission de la semaine → récompense ;
  · rituels : carte « réveil » le matin (avant 11 h), coucher le soir (21 h – 23 h 30) → « nuit douce » au réveil ;
  · paliers de série (app/pet_streak.py) : récompenses connues d'avance, une fois par compte ; la série demande un
    vrai soin (le coffre seul ne compte pas) ; rien de tout cela pour un compagnon envolé (playtest « Marc ») ;
  · rappel du jour : heure APPRISE (heure habituelle de passage − 15 min, repli 17–20 h), texte écrit par lui.
Économie sans argent réel : pièces, objets et tenues ne s'achètent pas et ne s'échangent pas contre de l'argent ; aucun
lot réel n'est tiré au sort. Tout vit dans owner["loop"] (jamais montré aux amis) ; l'inventaire y est un dictionnaire
{identifiant: quantité} (app/pet_chest.py).
"""
import copy
import statistics
import zlib
from datetime import date, datetime, timedelta

from . import pet, pet_chest, pet_collection, pet_streak, pet_texts

# ── Paliers de série : (pièces, gels offerts, ce qu'on montre d'avance) ──
MILESTONE_REWARDS = {
    3: (30, 0, "30 pièces + Lunettes de soleil 🕶️"),
    7: (50, 0, "50 pièces + Casquette 🧢"),
    14: (80, 1, "80 pièces + 1 gel ❄️"),
    30: (150, 1, "150 pièces + 1 gel ❄️"),
    50: (250, 0, "250 pièces + sticker Médaille d'or 🏅"),
    100: (500, 1, "500 pièces + 1 gel ❄️"),
    365: (1000, 2, "1000 pièces + 2 gels ❄️"),
}

# ── Missions : (id, texte, compteur, nombre) ; {n} = son nom ──
MISSIONS = {
    "care": (("feed2", "Nourris {n} 2 fois", "feed", 2), ("cuddle3", "Fais 3 câlins à {n}", "cuddle", 3),
             ("heal1", "Fais un brin de toilette à {n}", "heal", 1), ("play1", "Joue une fois avec {n}", "play", 1)),
    "game": (("score40", "Dépasse 40 au jeu des notes", "score40", 1), ("brain1", "Fais une partie de Méninges", "brain", 1)),
    "social": (("visit1", "Rends visite à tes amis", "visit", 1),
               ("gift1", "Offre un câlin ou un goûter à un ami", "gift", 1)),
}
WEEKLY = (("care5", "Prends soin de {n} 5 jours cette semaine", "care_day", 5),
          ("friday", "Passe le voir vendredi", "friday", 1),
          ("brain3", "Fais 3 parties de Méninges", "brain", 3),
          ("gift3", "Fais 3 cadeaux à tes amis", "gift", 3),
          ("chest5", "Ouvre 5 coffres du jour", "chest", 5))
TEMPLATES = {m[0]: m[1] for family in MISSIONS.values() for m in family} | {w[0]: w[1] for w in WEEKLY}
WEEK_COINS = 60                  # économie du 4.11.2026 (avant : 120)
SCORE_MISSION = 40               # « mini-jeu > 40 »

# ── Rituels ──
MORNING_END = 11 * 60            # carte « réveil » avant 11 h
TUCK_START, TUCK_END = 21 * 60, 23 * 60 + 30
SOFT_NIGHT = {"energy": 15.0, "joy": 10.0, "care": 5.0}
SOFT_NIGHT_COINS = 6             # économie du 4.11.2026 (avant : 10)
WAKE_ON_VISIT = 50.0             # endormi de fatigue mais assez reposé : il se réveille quand on ouvre l'app
SOFT_NIGHT_HOURS = 6             # « nuit douce » : bordé la veille, sans être réveillé à la main avant 6 h de sommeil

# ── Rappel du jour : heure apprise ──
VISITS_KEPT = 21
LEARN_DAYS, LEARN_MIN_DAYS, LEAD_MINUTES = 14, 3, 15
EARLIEST, LATEST = 8 * 60, 22 * 60 + 45       # jamais entre 23 h et 8 h
FALLBACK_FROM, FALLBACK_SPAN = 17 * 60, 180   # 17 h – 20 h
SOURCES = ("tab", "notification", "widget", "link")

LOOP_ACTIONS = ("chest", "bonus_chest", "tuck", "treat")
CARE = ("feed", "play", "cuddle", "heal")


def new_loop() -> dict:
    return {"day": "", "c": {}, "chest": None, "missions": None, "week": None, "tucked": "", "tucked_at": None,
            "morning": None, "visits": [], "coins": 0, "inv": {}, "paid": [], "games": []}


def loop_of(owner: dict) -> dict:
    """owner["loop"] complété (un compte d'avant le lot 1 n'en a pas)."""
    loop = owner.get("loop")
    if not isinstance(loop, dict):
        loop = owner["loop"] = {}
    for key, value in new_loop().items():
        loop.setdefault(key, value)   # en place : toutes les références à owner["loop"] restent les mêmes
    return loop


def local(now: datetime) -> datetime:
    return now.astimezone(pet.TZ)


def minute_of(now: datetime) -> int:
    t = local(now)
    return t.hour * 60 + t.minute


def week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def named(item: dict, name: str) -> str:
    """Texte d'une mission avec le nom ACTUEL du compagnon (playtest « Léa » : les missions tirées avant le choix du
    nom disaient encore « Zicou »)."""
    template = TEMPLATES.get(item.get("id"))
    return template.format(n=name) if template else str(item.get("text") or "")


def _pick(rng, seq):
    return seq[rng.randrange(len(seq))]


def _seeded(seed: str, n: int) -> int:
    return zlib.crc32(seed.encode()) % n if n else 0


# ── Visite : nouveau jour, coffre, missions, semaine, rituels ──

def visit(life: dict, owner: dict, now: datetime, rng, src: str | None = None, seed: str = "") -> tuple[dict, dict, list[dict]]:
    """À chaque ouverture. Le 1er passage du jour : coffre offert, 3 missions, carte « réveil » si avant 11 h, bonus
    « nuit douce » si on l'a couché hier soir, heure de passage notée (sauf venue d'une notification). Copies neuves."""
    life, owner = copy.deepcopy(life), copy.deepcopy(owner)
    loop, today, events = loop_of(owner), local(now).date(), []
    _roll_week(loop, owner, today, rng, life)
    events += _soft_night(life, loop, now)
    if (src and life["asleep"] and life["stage"] not in ("egg", "dead") and not loop.get("tucked_at")
            and life["g"]["energy"] >= WAKE_ON_VISIT):
        # Endormi de fatigue (pas bordé pour la nuit) et assez reposé : il se réveille en te voyant. Avant, un passage
        # par jour tombait souvent sur un compagnon endormi, et aucun soin n'était possible (playtest « Marc »).
        life["asleep"] = False
        events.append({"kind": "woke_up"})
    if loop["day"] == today.isoformat():
        return life, owner, events
    loop.update(day=today.isoformat(), c={}, chest={"day": today.isoformat(), "opened": False, "found": None})
    loop["missions"] = {"day": today.isoformat(), "list": _draw_missions(rng, life["name"]), "bonus": "locked",
                        "found": None}
    events.append({"kind": "new_day"})
    if src != "notification":
        loop["visits"] = (loop["visits"] + [[today.isoformat(), minute_of(now)]])[-VISITS_KEPT:]
    if minute_of(now) < MORNING_END:
        loop["morning"] = {"day": today.isoformat(), "text": dream(today, seed)}
    if today.weekday() == pet_streak.FRIDAY:
        events += note(owner, "friday", now)
    return life, owner, events


def _soft_night(life: dict, loop: dict, now: datetime) -> list[dict]:
    """Bonus « nuit douce » le lendemain d'un coucher (21 h – 23 h 30), une fois, et seulement s'il a dormi au moins
    6 h sans être réveillé à la main (playtest : coucher puis réveiller tout de suite gardait le bonus)."""
    tucked = pet.parse(loop.get("tucked_at"))
    if not tucked:
        return []
    late = (local(now).date() - local(tucked).date()).days
    if late < 1 or now - tucked < timedelta(hours=SOFT_NIGHT_HOURS):
        return []
    loop["tucked_at"] = None
    if late > 1 or life["stage"] in ("egg", "dead"):
        return []   # passé trop tard (plus le lendemain) : le bonus est perdu, sans reproche
    pet._add(life, SOFT_NIGHT)
    loop["coins"] += SOFT_NIGHT_COINS
    return [{"kind": "soft_night", "coins": SOFT_NIGHT_COINS}]


def woke(owner: dict, now: datetime) -> list[dict]:
    """Rallumé à la main moins de 6 h après le coucher : pas de nuit douce cette fois (dit gentiment)."""
    loop = loop_of(owner)
    tucked = pet.parse(loop.get("tucked_at"))
    if not tucked or now - tucked >= timedelta(hours=SOFT_NIGHT_HOURS):
        return []
    loop["tucked_at"] = None
    return [{"kind": "woke_early"}]


def dream(today: date, seed: str) -> str:
    """Un rêve différent chaque jour (ordre propre à chaque compte, sans répétition avant d'avoir tout vu)."""
    order = sorted(range(len(pet_texts.DREAMS)), key=lambda i: zlib.crc32(f"{seed}:{i}".encode()))
    return pet_texts.DREAMS[order[today.toordinal() % len(order)]]


def _draw_missions(rng, name: str) -> list[dict]:
    out = []
    for family in ("care", "game", "social"):
        mid, text, counter, need = _pick(rng, MISSIONS[family])
        out.append({"id": mid, "family": family, "text": text.format(n=name), "counter": counter, "need": need,
                    "have": 0})
    return out


def _roll_week(loop: dict, owner: dict, today: date, rng, life: dict) -> None:
    key = week_key(today)
    if (loop.get("week") or {}).get("key") == key:
        return
    # Tirée un vendredi ou après, « Passe le voir vendredi » se validait aussitôt (ou devenait impossible) : une autre,
    # avec le même tirage (HMAC du compte et du jour).
    choices = WEEKLY if today.weekday() < pet_streak.FRIDAY else tuple(w for w in WEEKLY if w[0] != "friday")
    mid, text, counter, need = _pick(rng, choices)
    loop["week"] = {"key": key, "id": mid, "text": text.format(n=life["name"]), "counter": counter, "need": need,
                    "have": 0, "done": False}


# ── Progrès (missions du jour, mission de la semaine) ──

def note(owner: dict, what: str, now: datetime, n: int = 1) -> list[dict]:
    """Compte une chose faite aujourd'hui (feed, play, cuddle, heal, score40, brain, visit, gift, chest, friday) et
    fait avancer les missions. Modifie `owner` (appelé sur une copie). Renvoie les événements (mission, bonus, semaine)."""
    loop, today, events = loop_of(owner), local(now).date().isoformat(), []
    if loop["day"] != today:
        return events   # pas encore passé aujourd'hui (visit d'abord) : rien
    c = loop["c"]
    first_care = what in CARE and not any(c.get(k) for k in CARE)
    c[what] = c.get(what, 0) + n
    missions = loop.get("missions") or {}
    for m in missions.get("list", []):
        if m["counter"] == what and m["have"] < m["need"]:
            m["have"] = min(m["need"], m["have"] + n)
            if m["have"] >= m["need"]:
                events.append({"kind": "mission", "id": m["id"], "text": m["text"]})
    if missions.get("bonus") == "locked" and missions.get("list") and all(m["have"] >= m["need"] for m in missions["list"]):
        missions["bonus"] = "ready"
        events.append({"kind": "bonus_ready"})
    events += _week_progress(loop, what, n)
    if first_care:
        events += _week_progress(loop, "care_day", 1)
    return events


def _week_progress(loop: dict, what: str, n: int) -> list[dict]:
    week = loop.get("week") or {}
    if week.get("done") or week.get("counter") != what:
        return []
    week["have"] = min(week["need"], week["have"] + n)
    if week["have"] < week["need"]:
        return []
    week["done"] = True
    loop["coins"] += WEEK_COINS
    return [{"kind": "week_done", "id": week.get("id"), "text": week["text"], "coins": WEEK_COINS}]


def after_care(owner: dict, action: str, score: int, now: datetime) -> list[dict]:
    """Après un soin réussi (app/pet.act) : missions du jour et de la semaine."""
    events = note(owner, action, now) if action in CARE else []
    if action == "play" and score > SCORE_MISSION:
        events += note(owner, "score40", now)
    return events


def streak_rewards(owner: dict, streak_events: list[dict]) -> list[dict]:
    """Paliers franchis : pièces (et gels) ; les tenues de palier se débloquent par pet.unlock(). Chaque palier ne paie
    qu'UNE fois par compte (playtest : « 3 jours, pause, 3 jours… » repayait le palier 3 à chaque nouvelle série)."""
    loop, out = loop_of(owner), []
    for e in streak_events:
        if e["kind"] != "milestone" or e["days"] not in MILESTONE_REWARDS or e["days"] in loop["paid"]:
            continue
        loop["paid"] = sorted(set(loop["paid"]) | {e["days"]})
        coins, freezes, label = MILESTONE_REWARDS[e["days"]]
        loop["coins"] += coins
        if freezes:
            s = owner["streak"]
            s["freezes"] = min(pet_streak.MAX_FREEZES, s.get("freezes", 0) + freezes)
        if e["days"] == 50:
            loop["inv"] = pet_chest.add(loop["inv"], pet_chest.GOLD_STICKER)
        out.append({"kind": "milestone_reward", "days": e["days"], "label": label})
    return out


# ── Coffres ──

def draw(rng, owner: dict, bonus: bool = False, ctx: dict | None = None) -> dict:
    """Tirage du serveur (table pondérée par rareté de app/pet_chest.py, garantie anti-malchance comprise).
    ctx : ce que sait la base — owned (objets déjà à lui, exemplaires numérotés compris), mythic_left (Mythiques encore
    disponibles)."""
    loop, coll, ctx = loop_of(owner), pet_collection.coll_of(owner), ctx or {}
    owned = ctx.get("owned") if ctx.get("owned") is not None else pet_collection.owned(owner)
    return pet_chest.draw(rng, loop["inv"], set(owned), pity=coll["pity"], mythic_left=ctx.get("mythic_left"), bonus=bonus,
                          today=ctx.get("today"))


def _found(owner: dict, loop: dict, rng, bonus: bool, ctx: dict | None) -> dict:
    coll = pet_collection.coll_of(owner)
    raw = draw(rng, owner, bonus=bonus, ctx=ctx)
    pet_chest.note_chest(coll, raw)
    return pet_chest.apply(loop, raw, coll)


def act(life: dict, owner: dict, action: str, now: datetime, rng, item: str = "", ctx: dict | None = None) -> tuple[dict, dict, dict]:
    """Actions de la boucle : coffre du jour, coffre bonus, coucher, goûter rare. Copies neuves ; PetError si
    impossible (message doux). Un Légendaire ou un Mythique tiré est marqué « mint » : app/pet_store.py le frappe."""
    if action not in LOOP_ACTIONS:
        raise pet.PetError("Action inconnue")
    life, owner = copy.deepcopy(life), copy.deepcopy(owner)
    life_events = pet.advance(life, now, owner)
    if life["stage"] == "dead":   # playtest : coffre et série continuaient par appels directs, compagnon envolé
        raise pet.PetError("Il s'est envolé… Fais éclore un nouvel œuf pour retrouver le coffre du jour 🥚")
    life, owner, visit_events = visit(life, owner, now, rng)
    loop, effect = loop_of(owner), {"action": action, "events": life_events, "loop": visit_events, "streak": []}
    if action in ("chest", "bonus_chest"):
        effect["found"] = _open(owner, loop, action, now, rng, effect, ctx)
    elif action == "tuck":
        effect["text"] = _tuck(life, owner, loop, now, effect)
    else:
        _treat(life, loop, item, now)
        pet.note_care(life, now)
        effect["streak"] = pet.note_streak(owner, now)
        effect["loop"] += note(owner, "feed", now) + streak_rewards(owner, effect["streak"])
    effect["unlocked"] = pet.unlock(owner)
    return life, owner, effect


def _open(owner: dict, loop: dict, action: str, now: datetime, rng, effect: dict, ctx: dict | None = None) -> dict:
    if action == "chest":
        chest = loop.get("chest") or {}
        if chest.get("opened"):
            raise pet.PetError("Tu as déjà ouvert le coffre du jour. Un nouveau t'attend demain 🎁")
        found = _found(owner, loop, rng, False, ctx)
        loop["chest"] = {**chest, "opened": True, "found": found}
        effect["loop"] += note(owner, "chest", now)   # le coffre seul ne compte pas pour la série (il faut un soin)
        return found
    missions = loop.get("missions") or {}
    if missions.get("bonus") != "ready":
        raise pet.PetError("Le coffre bonus s'ouvre quand les 3 missions du jour sont faites 🎯"
                           if missions.get("bonus") == "locked" else "Coffre bonus déjà ouvert aujourd'hui 🎁")
    found = _found(owner, loop, rng, True, ctx)
    loop["missions"] = {**missions, "bonus": "opened", "found": found}
    return found


def _tuck(life: dict, owner: dict, loop: dict, now: datetime, effect: dict) -> str:
    m, today = minute_of(now), local(now).date().isoformat()
    if not TUCK_START <= m < TUCK_END:
        raise pet.PetError("Le coucher, c'est le soir entre 21 h et 23 h 30 🌙")
    if life["stage"] in ("egg", "dead"):
        raise pet.PetError("Patience, l'œuf est en train d'éclore 🥚" if life["stage"] == "egg"
                           else "Il s'est envolé… Tu peux faire éclore un nouvel œuf.")
    if loop.get("tucked") == today:
        raise pet.PetError("Il est déjà bordé pour la nuit 🌙")
    life["asleep"] = True
    loop["tucked"], loop["tucked_at"] = today, pet.iso(now)
    return pet_texts.LULLABIES[local(now).date().toordinal() % len(pet_texts.LULLABIES)]


def _treat(life: dict, loop: dict, item: str, now: datetime) -> None:
    key = f"snack:{item}"
    if item not in pet_chest.SNACKS or loop["inv"].get(key, 0) <= 0:
        raise pet.PetError("Ce goûter n'est plus dans ton sac.")
    if life["stage"] in ("egg", "dead"):
        raise pet.PetError("Il ne peut pas goûter pour l'instant.")
    if life["asleep"]:
        raise pet.PetError("Chut, il dort 🌙 Garde ton goûter pour son réveil.")
    loop["inv"] = pet_chest.add(loop["inv"], key, -1)
    pet._add(life, pet_chest.SNACKS[item][2])


# ── Rappel du jour : heure apprise et texte ──

def learned_minute(visits: list, seed: str) -> int:
    """Heure habituelle de passage (médiane des 14 derniers premiers passages, hors notifications) − 15 min, entre
    8 h et 22 h 45 ; sans assez de jours : un moment fixe entre 17 h et 20 h propre à chaque compte."""
    minutes = [int(v[1]) for v in (visits or [])[-LEARN_DAYS:] if isinstance(v, (list, tuple)) and len(v) == 2]
    if len(minutes) < LEARN_MIN_DAYS:
        return FALLBACK_FROM + _seeded(seed, FALLBACK_SPAN)
    return int(max(EARLIEST, min(LATEST, statistics.median(minutes) - LEAD_MINUTES)))


def nudge(life: dict, owner: dict, now: datetime, seed: str, hungry_at: str | None = None) -> dict | None:
    """Rappel de demain, préparé à chaque enregistrement (la base l'envoie à l'heure dite si on n'est pas encore passé,
    jamais la nuit ni pendant une soirée, au plus une notification par jour). None : pas de rappel (œuf, envolé)."""
    if life["stage"] in ("egg", "dead"):
        return None
    loop, tomorrow = loop_of(copy.deepcopy(owner)), local(now).date() + timedelta(days=1)
    minute = learned_minute(loop["visits"], seed)
    at = datetime.combine(tomorrow, datetime.min.time(), pet.TZ) + timedelta(minutes=minute)
    title = life["name"]
    count = pet_streak.current(owner.get("streak"), local(now).date())
    daily = _daily_text(loop, at, hungry_at, count, f"{seed}:{tomorrow}", life["name"])
    out = {"day": tomorrow.isoformat(), "minute": minute, "kind": "pet_daily", "title": title, "body": daily,
           "alt_title": title, "alt_body": daily}
    nxt = count + 1 if count else 0
    if nxt in MILESTONE_REWARDS and nxt not in loop["paid"]:
        out.update(kind="pet_streak", body=pet_texts.NUDGE_MILESTONE.format(m=nxt, reward=MILESTONE_REWARDS[nxt][2]))
    return out


def _daily_text(loop: dict, at: datetime, hungry_at: str | None, count: int, seed: str, name: str) -> str:
    """Ce qui se passe vraiment : un petit creux d'ici là (sans soin), la mission de la semaine presque faite, la
    série en cours, sinon le coffre du jour (textes variés, un par jour)."""
    hungry = pet.parse(hungry_at)
    if hungry and hungry <= at:
        return pet_texts.NUDGE_HUNGRY[_seeded(seed, len(pet_texts.NUDGE_HUNGRY))]
    week = loop.get("week") or {}
    left = week.get("need", 0) - week.get("have", 0)
    options = list(pet_texts.NUDGE_CHEST)
    if week and not week.get("done") and 0 < left <= 2:
        text = named(week, name)
        options.append(pet_texts.NUDGE_WEEK.format(k=left, text=text[0].lower() + text[1:]))
    if count >= 3:
        options.append(pet_texts.NUDGE_STREAK.format(c=count + 1))
    return options[_seeded(seed, len(options))]


# ── Ce qu'on montre ──

def view(life: dict, owner: dict, now: datetime, ctx: dict | None = None) -> dict:
    loop, today, m = loop_of(copy.deepcopy(owner)), local(now).date(), minute_of(now)
    pity = int((owner.get("coll") or {}).get("pity", 0))
    is_today = loop["day"] == today.isoformat()
    chest = loop.get("chest") if is_today else None
    missions = loop.get("missions") if is_today else None
    s = pet_streak.normalized(owner.get("streak"))
    count = pet_streak.current(s, today)
    nxt = pet_streak.next_milestone(count)
    lost = s.get("lost") if s.get("lost") and (s["lost"].get("until") or "") >= today.isoformat() else None
    return {
        "coins": loop["coins"],
        "chest": {"state": "opened" if chest and chest.get("opened") else "ready", "found": (chest or {}).get("found")},
        "odds": pet_chest.odds(pity, (ctx or {}).get("mythic_left")),
        "bonus_odds": pet_chest.odds(pity, (ctx or {}).get("mythic_left"), bonus=True),
        "pity_left": pet_chest.pity_left(pity), "pity": pet_chest.PITY,
        "streak": {"count": count, "best": s.get("best", 0), "freezes": s.get("freezes", 0),
                   "today": s.get("last") == today.isoformat(),   # la journée compte déjà (sinon : la règle est affichée)
                   "max_freezes": pet_streak.MAX_FREEZES, "respite": _respite(s, today),
                   "next": {"days": nxt, "reward": _reward_label(nxt, loop)} if nxt else None,
                   "milestones": [{"days": d, "reward": _reward_label(d, loop), "reached": s.get("best", 0) >= d}
                                  for d in MILESTONE_REWARDS],
                   "repair": {"was": lost["count"], "until": lost["until"], "brain": lost["brain"], "care": lost["care"]}
                   if lost else None},
        "missions": [{"id": x["id"], "family": x["family"], "counter": x.get("counter"), "text": named(x, life["name"]),
                      "need": x["need"], "have": x["have"]} for x in (missions or {}).get("list", [])],
        "bonus": (missions or {}).get("bonus", "locked"), "bonus_found": (missions or {}).get("found"),
        "week": _week_view(loop.get("week"), life["name"]),
        "morning": (loop.get("morning") or {}).get("text") if m < MORNING_END and
        (loop.get("morning") or {}).get("day") == today.isoformat() else None,
        "evening": {"tucked": loop.get("tucked") == today.isoformat()} if TUCK_START <= m < TUCK_END else None,
        "bag": pet_chest.bag(loop["inv"]),
        "stickers": pet_chest.stickers(loop["inv"]),
        "pieces": [],   # anciens morceaux de tenue : convertis en poussière (app/pet_collection.py)
    }


def _reward_label(days: int, loop: dict) -> str:
    """Ce que rapporte un palier ; déjà gagné (une fois par compte) : on le dit."""
    return "Déjà gagné ✅" if days in loop.get("paid", []) else MILESTONE_REWARDS[days][2]


def _respite(s: dict, today: date) -> str | None:
    """« friday » : passer aujourd'hui protège demain samedi ; « saturday » : aujourd'hui est protégé (passé vendredi)."""
    if today.weekday() == pet_streak.FRIDAY:
        return "friday"
    if today.weekday() == pet_streak.SATURDAY and s.get("last") == (today - timedelta(days=1)).isoformat():
        return "saturday"
    return None


def _week_view(week: dict | None, name: str) -> dict | None:
    if not week:
        return None
    return {"text": named(week, name), "need": week["need"], "have": week["have"], "done": week["done"], "coins": WEEK_COINS}
