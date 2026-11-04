"""Compagnon — personnage à entretenir (façon Tamagotchi), moteur de vie pur et testable (avis 243907b1981a).

Tout se calcule à partir des dates, sans minuteur serveur : l'état garde les jauges à l'instant `at` et advance() les
fait vivre jusqu'à « maintenant » par pas d'une heure au plus (faim, humeur, énergie, forme, sommeil, maladie, stades,
mort). Les actions (act), les récompenses (rewards : Méninges, jeux de Party, soirées) et les cadeaux d'amis (gifts)
s'appliquent après advance(). projections() dit, sans soins, quand il aura faim, quand il sera en danger et quand il
mourrait : la base s'en sert pour les notifications (aucun calcul de vie en SQL : un seul endroit, ici).

Un compte = un personnage à la fois, en deux parties :
  · life  : le personnage lui-même (montrable aux amis : nom, stade, jauges, tenue…) ;
  · owner : ce qui reste au compte d'une génération à l'autre (série 🔥, tenues débloquées, souvenirs, compteurs du
            jour, curseurs des récompenses) — jamais montré aux autres.
L'horloge est toujours passée en paramètre (`now`) : les tests simulent des jours en une milliseconde.
"""
import copy
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Zurich")
FORMAT = 1
DEFAULT_NAME = "Paillou"          # nom provisoire (mascotte pas encore choisie) ; le skin du navigateur a le même
NAME_MAX = 20

GAUGES = ("food", "joy", "energy", "care")   # Ventre, Humeur, Énergie, Forme (0–100)
FULL = 100.0
START_GAUGES = {"food": 80.0, "joy": 80.0, "energy": 90.0, "care": 90.0}

# ── Rythme de vie (points par heure) ──
FOOD_RATE = 3.2            # ventre plein → vide en ~31 h éveillé
FOOD_SLEEP_FACTOR = 0.5    # endormi, il digère deux fois moins vite
JOY_RATE = 2.4
JOY_SICK_FACTOR = 2.0      # malade, l'humeur baisse deux fois plus vite
JOY_STARVING_FACTOR = 1.5  # ventre vide : l'humeur baisse plus vite
ENERGY_RATE = 3.0          # ~33 h éveillé avant de tomber de sommeil
ENERGY_REGEN = 11.0        # endormi : de 0 à 100 en ~9 h
CARE_RATE = 1.8            # forme (propreté, santé) : ~55 h
STAGE_FACTOR = {"baby": 1.2, "teen": 1.0, "adult": 0.9}   # un bébé a faim plus souvent
STEP_HOURS = 1.0
MAX_SIMULATED_DAYS = 40    # au-delà, il est mort depuis longtemps : on n'en calcule pas plus

# ── Stades ──
EGG_SECONDS = 180          # l'œuf éclot 3 min après avoir été pondu
BABY_HOURS = 24            # bébé pendant 1 jour…
TEEN_HOURS = 72            # … ado pendant 3 jours, puis adulte (à 4 jours)
STAR_CARE, WILD_CARE = 72.0, 55.0   # moyenne des jauges pendant le stade : ≥ 72 « étoile », < 55 « rebelle »
# (repères mesurés : aucun soin ≈ 49, deux repas par jour ≈ 58, un passage toutes les 4 h ≈ 83)
EPS_HOURS = 1e-3                     # arrondis des dates à la microseconde
VARIANTS = ("star", "classic", "wild")

# ── Mort et alertes : seulement après une négligence longue et claire ──
DEATH_STARVING_HOURS = 72  # ventre vide pendant 3 jours d'affilée (≈ 4,5 jours sans aucun repas)
ALERT_HOURS_BEFORE = (48, 12)
HUNGRY_LEVEL = 30.0        # rappel quotidien doux : « X a un petit creux »
LOW = 25.0
PARTY_LEVEL = 85.0         # toutes les jauges au-dessus : air de fête
MEMORIAL_MAX = 12

# ── Actions du jour (remises à zéro à minuit, heure de Zurich) ──
DAILY_LIMITS = {"feed": 6, "play": 5, "cuddle": 8, "heal": 3}
FEED_FOOD, FEED_JOY, FULL_ENOUGH = 30.0, 2.0, 95.0
PLAY_JOY_MIN, PLAY_JOY_SCORE, PLAY_ENERGY, PLAY_FOOD, PLAY_MIN_ENERGY = 12.0, 0.2, 8.0, 4.0, 10.0
PLAY_SCORE_MAX = 100
CUDDLE_JOY = 8.0
HEAL_CARE = 40.0
SLEEPY_ENOUGH = 90.0       # au-dessus, « pas sommeil »

# ── Récompenses (petits bonus, plafonnés par jour) ──
REWARDS = {   # source → (jauges ajoutées, nombre max par jour)
    "brain": ({"joy": 8.0, "energy": 3.0}, 3),    # une partie de Méninges
    "party": ({"joy": 10.0}, 3),                  # une partie de Party terminée
    "soiree": ({g: 25.0 for g in GAUGES}, 1),     # une soirée (événement) où on était inscrit présent
}
REWARD_WINDOW_HOURS = 48   # une partie plus ancienne ne rapporte plus rien
PARTY_MOOD_HOURS = 3       # après une soirée ou un cadeau : air de fête pendant 3 h
GIFTS = {"hug": ({"joy": 10.0}, "un câlin", "🤗"), "snack": ({"food": 15.0}, "un goûter", "🍪")}

# ── Tenues : (id, libellé, emoji, comment la débloquer) ; le skin du navigateur sait dessiner chacune ──
OUTFITS = (
    ("noeud", "Nœud papillon", "🎀", "Offert dès le premier jour"),
    ("lunettes", "Lunettes de soleil", "🕶️", "Série de 3 jours 🔥"),
    ("casquette", "Casquette", "🧢", "Série de 7 jours 🔥"),
    ("casque", "Casque de DJ", "🎧", "5 parties de Méninges"),
    ("boa", "Collier lumineux", "✨", "Venir à une soirée"),
    ("chapeau", "Chapeau de fête", "🥳", "Recevoir 5 cadeaux d'amis"),
    ("couronne", "Couronne", "👑", "Faire grandir un adulte « étoile »"),
)
OUTFIT_IDS = {o[0] for o in OUTFITS}

ACTIONS = ("feed", "play", "cuddle", "sleep", "wake", "heal", "rename", "outfit", "new_egg")


class PetError(ValueError):
    """Action refusée (limite du jour, déjà endormi…) : message montré tel quel, sans ton culpabilisant."""


# ── Dates ──

def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(value) -> datetime | None:
    if not value:
        return None
    t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def day_of(t: datetime) -> str:
    return t.astimezone(TZ).date().isoformat()


def hours(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600


def clamp(x: float, lo: float = 0.0, hi: float = FULL) -> float:
    return max(lo, min(hi, x))


# ── Création ──

def new_owner() -> dict:
    return {"v": FORMAT, "day": "", "uses": {}, "streak": {"count": 0, "last": "", "best": 0},
            "unlocked": ["noeud"], "stats": {"feeds": 0, "plays": 0, "cuddles": 0, "heals": 0, "brain": 0, "party": 0,
                                              "soirees": 0, "gifts_received": 0, "stars": 0, "eggs": 0},
            "claimed": {"brain": "", "party": "", "events": []}, "memorial": [], "record_hours": 0.0}


def new_life(now: datetime, gen: int = 1, name: str = DEFAULT_NAME) -> dict:
    return {"v": FORMAT, "gen": gen, "name": name, "stage": "egg", "variant": "classic", "born_at": iso(now),
            "hatched_at": None, "evolved_at": None, "died_at": None, "at": iso(now), "g": dict(START_GAUGES),
            "asleep": False, "sick": False, "starving_h": 0.0, "care_sum": 0.0, "care_h": 0.0, "outfit": None,
            "party_until": None}


def new_pet(now: datetime) -> tuple[dict, dict]:
    owner = new_owner()
    owner["stats"]["eggs"] = 1
    return new_life(now), owner


# ── Vie ──

def _hatch(life: dict, at: datetime) -> None:
    life.update(stage="baby", hatched_at=iso(at), evolved_at=iso(at), at=iso(at), g=dict(START_GAUGES))


def _variant(life: dict) -> str:
    avg = life["care_sum"] / life["care_h"] if life["care_h"] > 0 else 50.0
    return "star" if avg >= STAR_CARE else "wild" if avg < WILD_CARE else "classic"


def _evolve(life: dict, at: datetime, owner: dict | None, events: list) -> None:
    """Bébé → ado → adulte selon l'âge ; la forme dépend de la moyenne des soins pendant le stade."""
    hatched = parse(life["hatched_at"])
    age = hours(hatched, at)
    nxt = "teen" if life["stage"] == "baby" and age >= BABY_HOURS - EPS_HOURS else \
          "adult" if life["stage"] == "teen" and age >= BABY_HOURS + TEEN_HOURS - EPS_HOURS else None
    if not nxt:
        return
    life.update(stage=nxt, variant=_variant(life), evolved_at=iso(at), care_sum=0.0, care_h=0.0)
    events.append({"kind": "evolved", "stage": nxt, "variant": life["variant"]})
    if owner is not None and nxt == "adult" and life["variant"] == "star":
        owner["stats"]["stars"] = owner["stats"].get("stars", 0) + 1


def _die(life: dict, at: datetime, owner: dict | None, events: list) -> None:
    life.update(stage="dead", died_at=iso(at), at=iso(at), asleep=False)
    events.append({"kind": "died"})
    if owner is None:
        return
    lived = age_hours(life, at)
    owner["record_hours"] = round(max(owner.get("record_hours", 0.0), lived), 2)
    owner["memorial"] = ([{"gen": life["gen"], "name": life["name"], "variant": life["variant"],
                           "born_at": life["born_at"], "died_at": life["died_at"], "hours": round(lived, 2)}]
                         + owner.get("memorial", []))[:MEMORIAL_MAX]


def _step(life: dict, dt: float) -> float:
    """Fait vivre le personnage dt heures ; renvoie le nombre d'heures passées ventre vide pendant ce pas."""
    g, k = life["g"], STAGE_FACTOR.get(life["stage"], 1.0)
    food_rate = FOOD_RATE * k * (FOOD_SLEEP_FACTOR if life["asleep"] else 1.0)
    food_before = g["food"]
    starving = dt if food_before <= 0 else max(0.0, dt - food_before / food_rate)
    g["food"] = clamp(food_before - food_rate * dt)
    joy_rate = JOY_RATE * (JOY_SICK_FACTOR if life["sick"] else 1.0) * (JOY_STARVING_FACTOR if starving > 0 else 1.0)
    g["joy"] = clamp(g["joy"] - joy_rate * dt)
    g["care"] = clamp(g["care"] - CARE_RATE * dt)
    if life["asleep"]:
        g["energy"] = clamp(g["energy"] + ENERGY_REGEN * dt)
        if g["energy"] >= FULL:
            life["asleep"] = False   # bien reposé : il se réveille tout seul
    else:
        g["energy"] = clamp(g["energy"] - ENERGY_RATE * k * dt)
        if g["energy"] <= 0:
            life["asleep"] = True    # épuisé : il s'endort tout seul
    if g["care"] <= 0:
        life["sick"] = True
    life["care_sum"] += dt * sum(g.values()) / len(GAUGES)
    life["care_h"] += dt
    return starving


def advance(life: dict, now: datetime, owner: dict | None = None) -> list[dict]:
    """Fait vivre `life` (et met à jour `owner` : souvenirs, record) jusqu'à `now`. Renvoie les événements survenus
    (éclosion, évolution, mort). Ne recule jamais : un `now` plus ancien que `at` ne change rien."""
    events: list[dict] = []
    if life["stage"] == "dead":
        return events
    if life["stage"] == "egg":
        hatch = parse(life["born_at"]) + timedelta(seconds=EGG_SECONDS)
        if now < hatch:
            return events
        _hatch(life, hatch)
        events.append({"kind": "hatched"})
    at = parse(life["at"])
    end = min(now, at + timedelta(days=MAX_SIMULATED_DAYS))
    while at < end:
        dt = min(STEP_HOURS, hours(at, end))
        before = life["starving_h"]
        starving = _step(life, dt)
        life["starving_h"] = before + starving if starving > 0 else 0.0
        if starving > 0 and life["g"]["food"] > 0:   # n'arrive pas : garde-fou
            life["starving_h"] = 0.0
        if life["starving_h"] >= DEATH_STARVING_HOURS:
            died = at + timedelta(hours=dt - (life["starving_h"] - DEATH_STARVING_HOURS))
            life["starving_h"] = float(DEATH_STARVING_HOURS)
            _die(life, died, owner, events)
            return events
        at = at + timedelta(hours=dt)
        _evolve(life, at, owner, events)
    life["at"] = iso(max(at, parse(life["at"])))
    if now > end:   # mort depuis longtemps (jamais atteint : la mort arrive avant 40 jours)
        life["at"] = iso(now)
    return events


def age_hours(life: dict, now: datetime) -> float:
    start = parse(life.get("hatched_at"))
    if not start:
        return 0.0
    stop = parse(life.get("died_at")) or now
    return max(0.0, hours(start, stop))


# ── Projections (notifications) ──

def projections(life: dict, now: datetime) -> dict:
    """Sans aucun soin à partir de maintenant : quand il aura un petit creux (rappel du jour), quand son ventre sera
    vide, quand il mourrait. None si cela n'arrive pas (œuf, déjà mort)."""
    if life["stage"] in ("dead",):
        return {"hungry_at": None, "starving_at": None, "dies_at": None}
    sim = copy.deepcopy(life)
    t = now
    if sim["stage"] == "egg":
        t = max(now, parse(sim["born_at"]) + timedelta(seconds=EGG_SECONDS))
        advance(sim, t)
    else:
        advance(sim, now)
    hungry = t if sim["g"]["food"] < HUNGRY_LEVEL else None
    starving = t - timedelta(hours=sim["starving_h"]) if sim["starving_h"] > 0 or sim["g"]["food"] <= 0 else None
    limit = t + timedelta(days=MAX_SIMULATED_DAYS)
    while sim["stage"] != "dead" and t < limit:
        nxt = t + timedelta(hours=STEP_HOURS)
        prev_food = sim["g"]["food"]
        advance(sim, nxt)
        if hungry is None and sim["g"]["food"] < HUNGRY_LEVEL:
            hungry = _crossing(t, nxt, prev_food, sim["g"]["food"], HUNGRY_LEVEL)
        if starving is None and sim["g"]["food"] <= 0:
            starving = _crossing(t, nxt, prev_food, 0.0, 0.0)
        t = nxt
    dies = parse(sim["died_at"]) if sim["stage"] == "dead" else None
    if dies:
        starving = dies - timedelta(hours=DEATH_STARVING_HOURS)   # exact (l'interpolation n'est qu'une estimation)
    return {"hungry_at": iso(hungry) if hungry else None, "starving_at": iso(starving) if starving else None,
            "dies_at": iso(dies) if dies else None}


def _crossing(a: datetime, b: datetime, before: float, after: float, level: float) -> datetime:
    """Instant où une jauge qui descend linéairement de `before` à `after` passe sous `level`."""
    if before <= level or before == after:
        return a
    return a + (b - a) * clamp((before - level) / (before - after), 0.0, 1.0)


# ── Compteurs du jour, série 🔥, tenues ──

def _roll_day(owner: dict, now: datetime) -> None:
    today = day_of(now)
    if owner.get("day") != today:
        owner["day"], owner["uses"] = today, {}


def _note_care_day(owner: dict, now: datetime) -> None:
    today = day_of(now)
    s = owner["streak"]
    if s.get("last") == today:
        return
    yesterday = (now.astimezone(TZ).date() - timedelta(days=1)).isoformat()
    s["count"] = s.get("count", 0) + 1 if s.get("last") == yesterday else 1
    s["last"], s["best"] = today, max(s.get("best", 0), s["count"])


def streak_now(owner: dict, now: datetime) -> int:
    """Série en cours : elle tient tant qu'on est passé aujourd'hui ou hier."""
    s = owner.get("streak") or {}
    today = now.astimezone(TZ).date()
    alive = s.get("last") in (today.isoformat(), (today - timedelta(days=1)).isoformat())
    return int(s.get("count", 0)) if alive else 0


def _unlock_rules(owner: dict) -> dict[str, bool]:
    st, best = owner["stats"], owner["streak"].get("best", 0)
    return {"noeud": True, "lunettes": best >= 3, "casquette": best >= 7, "casque": st.get("brain", 0) >= 5,
            "boa": st.get("soirees", 0) >= 1, "chapeau": st.get("gifts_received", 0) >= 5, "couronne": st.get("stars", 0) >= 1}


def unlock(owner: dict) -> list[str]:
    """Débloque les tenues gagnées ; renvoie les nouvelles (jamais retirées ensuite)."""
    have = set(owner.get("unlocked", []))
    new = [oid for oid, ok in _unlock_rules(owner).items() if ok and oid not in have]
    owner["unlocked"] = [o[0] for o in OUTFITS if o[0] in have or o[0] in new]
    return new


# ── Actions ──

def _use(owner: dict, action: str) -> None:
    limit = DAILY_LIMITS.get(action)
    if limit is None:
        return
    used = owner["uses"].get(action, 0)
    if used >= limit:
        raise PetError(LIMIT_MESSAGES[action])
    owner["uses"][action] = used + 1


LIMIT_MESSAGES = {"feed": "Il a assez mangé pour aujourd'hui : reviens demain 🍕",
                  "play": "Assez joué pour aujourd'hui, il a besoin de souffler 🎵",
                  "cuddle": "Il a eu plein de câlins aujourd'hui 💜",
                  "heal": "Il a déjà été bien soigné aujourd'hui 🧼"}


def _add(life: dict, gains: dict) -> None:
    for k, v in gains.items():
        life["g"][k] = clamp(life["g"][k] + v)
    if life["g"]["food"] > 0:
        life["starving_h"] = 0.0   # un repas (même petit) arrête le compte à rebours


def clean_name(name: str) -> str:
    text = " ".join("".join(c for c in str(name or "") if c.isprintable()).split())[:NAME_MAX]
    if not text:
        raise PetError("Choisis un nom (20 lettres au plus).")
    return text


def act(life: dict, owner: dict, action: str, now: datetime, score: int = 0, name: str = "", outfit: str = "") -> tuple[dict, dict, dict]:
    """Applique une action du propriétaire. Renvoie (life, owner, effet) — copies neuves, les entrées ne changent pas.
    Lève PetError si l'action n'est pas possible maintenant (le message dit pourquoi, gentiment)."""
    if action not in ACTIONS:
        raise PetError("Action inconnue")
    life, owner = copy.deepcopy(life), copy.deepcopy(owner)
    events = advance(life, now, owner)
    _roll_day(owner, now)
    stage = life["stage"]
    if action == "new_egg":
        if stage != "dead":
            raise PetError("Ton compagnon est toujours là !")
        life = new_life(now, life["gen"] + 1, life["name"])
        owner["stats"]["eggs"] = owner["stats"].get("eggs", 0) + 1
        return life, owner, {"action": action, "events": events + [{"kind": "egg"}], "unlocked": []}
    if stage == "dead":
        raise PetError("Il s'est envolé… Tu peux faire éclore un nouvel œuf.")
    if action == "rename":
        life["name"] = clean_name(name)
        return life, owner, {"action": action, "events": events, "unlocked": []}
    if action == "outfit":
        if outfit and (outfit not in OUTFIT_IDS or outfit not in owner["unlocked"]):
            raise PetError("Cette tenue n'est pas encore débloquée.")
        life["outfit"] = outfit or None
        return life, owner, {"action": action, "events": events, "unlocked": []}
    if stage == "egg":
        raise PetError("Patience, l'œuf est en train d'éclore 🥚")
    _care_action(life, owner, action, score)
    if action in ("feed", "play", "cuddle", "heal"):
        _note_care_day(owner, now)
    return life, owner, {"action": action, "events": events, "unlocked": unlock(owner)}


def _care_action(life: dict, owner: dict, action: str, score: int) -> None:
    g, st = life["g"], owner["stats"]
    if action == "sleep":
        if life["asleep"]:
            raise PetError("Il dort déjà 😴")
        if g["energy"] >= SLEEPY_ENOUGH:
            raise PetError("Il n'a pas sommeil, il est en pleine forme ⚡")
        life["asleep"] = True
        return
    if action == "wake":
        if not life["asleep"]:
            raise PetError("Il est déjà réveillé ☀️")
        life["asleep"] = False
        return
    if life["asleep"]:
        raise PetError("Chut, il dort 🌙 Rallume la lumière pour le réveiller.")
    if action == "feed":
        if g["food"] >= FULL_ENOUGH:
            raise PetError("Il n'a plus faim pour l'instant 😋")
        _use(owner, "feed")
        _add(life, {"food": FEED_FOOD, "joy": FEED_JOY})
        st["feeds"] = st.get("feeds", 0) + 1
    elif action == "play":
        if g["energy"] < PLAY_MIN_ENERGY:
            raise PetError("Il est trop fatigué pour jouer : éteins-lui la lumière 🌙")
        _use(owner, "play")
        s = max(0, min(PLAY_SCORE_MAX, int(score)))
        _add(life, {"joy": PLAY_JOY_MIN + s * PLAY_JOY_SCORE, "energy": -PLAY_ENERGY, "food": -PLAY_FOOD})
        st["plays"] = st.get("plays", 0) + 1
    elif action == "cuddle":
        _use(owner, "cuddle")
        _add(life, {"joy": CUDDLE_JOY})
        st["cuddles"] = st.get("cuddles", 0) + 1
    elif action == "heal":
        if g["care"] >= FULL_ENOUGH and not life["sick"]:
            raise PetError("Il est tout propre et en pleine forme ✨")
        _use(owner, "heal")
        _add(life, {"care": HEAL_CARE})
        life["sick"] = False
        st["heals"] = st.get("heals", 0) + 1


# ── Récompenses et cadeaux (appliqués à l'ouverture) ──

def rewards(life: dict, owner: dict, now: datetime, brain_times: list[str], party_times: list[str],
            events: list[dict]) -> tuple[dict, dict, list[dict]]:
    """Petits bonus pour ce qu'on a fait ailleurs dans Party : parties de Méninges, parties de Party terminées, soirées
    (événement commencé, inscrit présent). Chaque source a un curseur (rien n'est compté deux fois) et un plafond par
    jour ; un personnage en œuf ou envolé ne reçoit rien, mais les curseurs avancent quand même."""
    life, owner = copy.deepcopy(life), copy.deepcopy(owner)
    _roll_day(owner, now)
    got: list[dict] = []
    alive = life["stage"] not in ("egg", "dead")
    claimed = owner["claimed"]
    oldest = now - timedelta(hours=REWARD_WINDOW_HOURS)
    for source, times in (("brain", brain_times), ("party", party_times)):
        cursor = parse(claimed.get(source)) or oldest
        fresh = sorted(t for t in (parse(x) for x in times or []) if t and max(cursor, oldest) < t <= now)
        if fresh:
            claimed[source] = iso(fresh[-1])
        for _ in fresh:
            got += _reward(life, owner, source, alive, now)
    seen = set(claimed.get("events", []))
    for ev in events or []:
        eid, start = str(ev.get("id") or ""), parse(ev.get("starts_at"))
        if not eid or eid in seen or not start or not (now - timedelta(days=7) <= start <= now):
            continue
        seen.add(eid)
        claimed["events"] = ([eid] + claimed.get("events", []))[:20]
        got += _reward(life, owner, "soiree", alive, now)
    return life, owner, got


def _reward(life: dict, owner: dict, source: str, alive: bool, now: datetime) -> list[dict]:
    gains, per_day = REWARDS[source]
    stat = {"brain": "brain", "party": "party", "soiree": "soirees"}[source]
    owner["stats"][stat] = owner["stats"].get(stat, 0) + 1
    key = f"reward_{source}"
    if not alive or owner["uses"].get(key, 0) >= per_day:
        return []
    owner["uses"][key] = owner["uses"].get(key, 0) + 1
    _add(life, gains)
    if source == "soiree":
        life["party_until"] = iso(now + timedelta(hours=PARTY_MOOD_HOURS))
    return [{"kind": "reward", "source": source}]


def gifts(life: dict, owner: dict, now: datetime, received: list[dict]) -> tuple[dict, dict, list[dict]]:
    """Cadeaux des amis (un par ami et par jour, limité par la base) : appliqués à l'ouverture."""
    life, owner = copy.deepcopy(life), copy.deepcopy(owner)
    applied = []
    for gift in received or []:
        kind = gift.get("kind")
        if kind not in GIFTS:
            continue
        owner["stats"]["gifts_received"] = owner["stats"].get("gifts_received", 0) + 1
        if life["stage"] not in ("egg", "dead"):
            _add(life, GIFTS[kind][0])
            life["party_until"] = iso(now + timedelta(hours=PARTY_MOOD_HOURS))
        applied.append({"id": gift.get("id"), "kind": kind, "from": str(gift.get("from_name") or "Un ami")[:40]})
    return life, owner, applied


# ── Ce qu'on montre ──

def emotion(life: dict, now: datetime) -> str:
    """Une émotion pour le dessin : egg, ghost, sleep, sick, hungry, tired, sad, party, happy."""
    stage, g = life["stage"], life["g"]
    if stage == "egg":
        return "egg"
    if stage == "dead":
        return "ghost"
    if life["asleep"]:
        return "sleep"
    if life["sick"]:
        return "sick"
    if g["food"] < LOW:
        return "hungry"
    if g["energy"] < LOW:
        return "tired"
    if g["joy"] < LOW:
        return "sad"
    party = parse(life.get("party_until"))
    if (party and party > now) or min(g.values()) >= PARTY_LEVEL:
        return "party"
    return "happy"


MOOD_LINES = {
    "egg": "Quelque chose bouge dans l'œuf…",
    "ghost": "{n} s'est envolé. Merci pour tous ces moments ✨",
    "sleep": "{n} fait de beaux rêves 🌙",
    "sick": "{n} n'est pas dans son assiette : un petit soin lui ferait du bien 🧼",
    "hungry": "{n} a un petit creux 🍕",
    "tired": "{n} bâille… une petite sieste ? 🌙",
    "sad": "{n} aimerait jouer avec toi 🎵",
    "party": "{n} est en mode fête ! 🪩",
    "happy": "{n} est tout content de te voir 💜",
}


def mood_line(life: dict, now: datetime) -> str:
    return MOOD_LINES[emotion(life, now)].format(n=life["name"])


def next_stage_in(life: dict, now: datetime) -> int | None:
    """Secondes avant l'éclosion ou l'évolution suivante (None pour un adulte ou un personnage envolé)."""
    if life["stage"] == "egg":
        return max(0, math.ceil((parse(life["born_at"]) + timedelta(seconds=EGG_SECONDS) - now).total_seconds()))
    hatched = parse(life.get("hatched_at"))
    target = {"baby": BABY_HOURS, "teen": BABY_HOURS + TEEN_HOURS}.get(life["stage"])
    if not hatched or target is None:
        return None
    return max(0, math.ceil((hatched + timedelta(hours=target) - now).total_seconds()))


def public_life(life: dict) -> dict:
    """Ce que voient les amis : le personnage seulement (jamais les souvenirs, compteurs ou curseurs du compte)."""
    keep = ("v", "gen", "name", "stage", "variant", "born_at", "hatched_at", "evolved_at", "died_at", "at", "g", "asleep",
            "sick", "starving_h", "care_sum", "care_h", "outfit", "party_until")
    return {k: copy.deepcopy(life.get(k)) for k in keep}


def friend_view(life: dict, now: datetime) -> dict:
    """Personnage d'un ami, vécu jusqu'à maintenant (sans rien enregistrer) : émotion et stade, pas de jauges exactes."""
    life = copy.deepcopy(life)
    advance(life, now)
    return {"name": life["name"], "stage": life["stage"], "variant": life["variant"], "emotion": emotion(life, now),
            "outfit": life.get("outfit"), "age_hours": round(age_hours(life, now), 1), "gen": life["gen"],
            "line": mood_line(life, now)}


def view(life: dict, owner: dict, now: datetime) -> dict:
    """Écran du propriétaire (life et owner déjà vécus jusqu'à maintenant)."""
    proj = projections(life, now)
    uses = owner.get("uses", {}) if owner.get("day") == day_of(now) else {}
    unlocked = set(owner.get("unlocked", []))
    danger = None
    if life["stage"] not in ("egg", "dead") and life["starving_h"] > 0 and proj["dies_at"]:
        danger = {"hours_left": max(0, math.floor(hours(now, parse(proj["dies_at"]))))}
    return {
        "name": life["name"], "gen": life["gen"], "stage": life["stage"], "variant": life["variant"],
        "emotion": emotion(life, now), "line": mood_line(life, now), "asleep": life["asleep"], "sick": life["sick"],
        "gauges": {k: round(v) for k, v in life["g"].items()}, "outfit": life.get("outfit"),
        "age_hours": round(age_hours(life, now), 1), "next_stage_in": next_stage_in(life, now),
        "born_at": life["born_at"], "died_at": life.get("died_at"), "danger": danger,
        "left": {a: max(0, n - uses.get(a, 0)) for a, n in DAILY_LIMITS.items()}, "limits": dict(DAILY_LIMITS),
        "streak": streak_now(owner, now), "best_streak": owner.get("streak", {}).get("best", 0),
        "record_hours": owner.get("record_hours", 0.0), "memorial": owner.get("memorial", [])[:MEMORIAL_MAX],
        "stats": dict(owner.get("stats", {})),
        "outfits": [{"id": i, "label": label, "emoji": emo, "hint": hint, "unlocked": i in unlocked}
                    for i, label, emo, hint in OUTFITS],
        "hungry_at": proj["hungry_at"], "dies_at": proj["dies_at"],
    }
