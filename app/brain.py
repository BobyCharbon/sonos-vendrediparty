"""Méninges — entraînement cérébral solo (façon Lumosity, noms et visuels originaux).

Les mini-jeux tournent entièrement dans le navigateur (app/static/brain/) ; seul le résultat d'une partie arrive ici.
Ce module garde le catalogue (15 jeux, 6 domaines), les bornes plausibles de score, la normalisation score brut →
indice 0–2000 et les calculs du profil : Température (°M), domaines, série 🔥, évolution ; l'analyse (forces /
faiblesses, tendance, conseils, vitesse vs précision, progrès, Échauffement) est dans app/brain_analysis.py.

La base (migrations supabase/migrations/20261102210000_brain.sql et 20261103090000_brain_sans_fin.sql) applique la MÊME normalisation et le même calcul de
Température (pour le percentile entre joueurs) : les valeurs du catalogue y sont recopiées et tests/test_brain.py
vérifie qu'elles restent identiques. Toute modification du catalogue se fait donc aux deux endroits.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from . import brain_analysis as A
from .accounts import AccountError

BRAIN_NAME = "Méninges"
INDEX_MAX = 2000
TOP_PER_GAME = 5          # indice d'un jeu = moyenne des 5 meilleures parties…
WINDOW_DAYS = 30          # … des 30 jours qui précèdent la dernière partie de ce jeu
HISTORY_DAYS = 30
LOCAL_MAX = 500           # parties envoyées par un joueur non connecté (calcul seulement, rien n'est gardé)
TZ = ZoneInfo("Europe/Zurich")
FAST_RT_MS, SLOW_RT_MS = 400, 1600   # vitesse 100 % / 0 % (temps de réaction moyen)
BALANCED_MARGIN = 50                 # °M autour de ta moyenne : domaine ni force ni faiblesse

# Domaines : (libellé, emoji). Les 5 premiers forment la Température ; Calcul a son indice à part.
DOMAINS: dict[str, tuple[str, str]] = {
    "vitesse": ("Vitesse", "⚡"),
    "memoire": ("Mémoire", "🧠"),
    "attention": ("Attention", "🎯"),
    "flexibilite": ("Flexibilité", "🔀"),
    "logique": ("Logique", "🧩"),
    "calcul": ("Calcul", "➗"),
}
TEMPERATURE_DOMAINS = ("vitesse", "memoire", "attention", "flexibilite", "logique")


@dataclass(frozen=True)
class Game:
    id: str
    name: str
    domain: str
    seconds: int | None   # durée du chrono ; None = partie sans fin (3 vies), le cas de tous les jeux depuis le 03.11
    median: int           # score brut « typique » (atteint vers le niveau LEVEL_REF) → indice 1000
    spread: int           # largeur de la courbe, en millièmes de logarithme du score (plus grand = plus doux)
    max_score: int        # plafond : un score plus haut est BORNÉ, jamais refusé (robot parfait compris)
    max_seconds: int      # durée maximale comptée d'une partie (au-delà : bornée, jamais refusée)


# Méninges sans fin (03.11.2026) : plus de chrono, 3 vies, paliers de 5 niveaux. Une partie typique dure 2–4 min
# (~20 000 points vers le niveau 10) ; un très bon joueur tient 10–15 min et passe les 100 000 ; le moteur coupe à
# 30 min. L'indice tient compte du score (échelle logarithmique) ET du niveau atteint (voir raw_index).
MAX_RUN_SECONDS = 1800                       # 30 min : le moteur (core.js) arrête la partie, le serveur borne
MAX_SCORE = MAX_RUN_SECONDS * 1500 + 2500    # ~3 réponses/s à ×10 pendant 30 min + bonus final : plafond large
MAX_LEVEL = 999                              # les jeux sans fin montent à 250+ (même plafond : core.js, base)
LEVEL_TIER = 5                               # un palier tous les 5 niveaux (1-5 = palier 1, 6-10 = palier 2…)
SCORE_SPREAD = 800                           # millièmes de ln : ×2,2 sur le score ≈ +1 sur la courbe
SCORE_OFFSET = 500                           # évite ln(0) et adoucit le bas de la courbe
LEVEL_REF = 10                               # niveau « typique » (fin du palier 2) → 1000 avec le score typique
LEVEL_SPREAD = 8                             # +8 niveaux ≈ +1 sur la courbe du niveau
SCORE_WEIGHT, LEVEL_WEIGHT = 0.65, 0.35      # part du score et du niveau dans l'indice
# Anti-triche (QA 03.11) : un score impossible pour la durée de la partie est BORNÉ (même borne en base, migration
# 20261103100000_brain_anti_triche.sql) : deux fois le rythme d'un robot parfait (1 500 pts/s) + le bonus final ×10.
SCORE_PER_SECOND_CAP = 3000
SCORE_BONUS_CAP = 2500
DATE_MIN = datetime(2020, 1, 1, tzinfo=timezone.utc)   # parties locales plus anciennes (horloge remise à zéro) : bornées


def _game(gid: str, name: str, domain: str, median: int) -> Game:
    return Game(gid, name, domain, None, median, SCORE_SPREAD, MAX_SCORE, MAX_RUN_SECONDS)


CATALOG: dict[str, Game] = {g.id: g for g in (
    _game("pareil", "Pareil ?", "vitesse", 22500),
    _game("motif", "Même motif", "vitesse", 21000),
    _game("autoroute", "Trois voies", "attention", 22500),
    _game("grille", "Cases lumineuses", "memoire", 15000),
    _game("deux_avant", "Deux avant", "memoire", 20000),
    _game("tresor", "Jamais deux fois", "memoire", 12500),
    _game("nuee", "Le vol", "attention", 21000),
    _game("aiguillage", "Aiguillages", "attention", 22500),
    _game("intrus", "L'intrus", "attention", 20000),
    _game("encre", "Mot ou encre", "flexibilite", 22500),
    _game("bascule", "Bascule", "flexibilite", 21000),
    _game("courant", "Contre-courant", "flexibilite", 20000),
    _game("balance", "Plus lourd", "calcul", 21000),
    _game("gouttes", "Gouttes", "calcul", 15000),
    _game("syllabes", "Débuts de mots", "logique", 22500),
)}


def tier_of(level: int) -> int:
    """Palier d'un niveau (niveaux 1-5 = palier 1). 0 si jamais joué (niveau 0)."""
    return (int(level) + LEVEL_TIER - 1) // LEVEL_TIER if int(level) > 0 else 0


class BrainError(ValueError):
    pass


class BrainUnavailable(BrainError):
    """Base injoignable ou en panne (5xx, délai) : passager, à réessayer (HTTP 503). Un refus de la base reste un
    BrainError (HTTP 400), que le téléphone traite comme définitif."""


# ── Normalisation ──

def round_half_up(x: float) -> int:
    """Arrondi identique à floor(x + 0.5) de la base (round() de Python arrondit au pair)."""
    return math.floor(x + 0.5)


def raw_index(game: str, score: int, level: int = LEVEL_REF) -> float:
    """Score brut et niveau atteint → indice 0–2000 non arrondi (même formule que private.brain_index en base).

    Courbe en S d'une note qui mêle le logarithme du score (rapporté au score typique du jeu) et le niveau atteint
    (rapporté au niveau 10) : score typique au niveau 10 = 1000 ; un joueur qui atteint le palier 8 (niveau 36+) avec
    un gros score dépasse 1900, même s'il reste un peu sous le score des meilleurs."""
    g = CATALOG[game]
    s = min(max(int(score), 0), g.max_score)
    lvl = min(max(int(level or 1), 1), MAX_LEVEL)
    z_score = math.log((s + SCORE_OFFSET) / (g.median + SCORE_OFFSET)) / (g.spread / 1000)
    z_level = (lvl - LEVEL_REF) / LEVEL_SPREAD
    return INDEX_MAX / (1 + math.exp(-(SCORE_WEIGHT * z_score + LEVEL_WEIGHT * z_level)))


def game_index(game: str, score: int, level: int = LEVEL_REF) -> int:
    return round_half_up(raw_index(game, score, level))


def score_cap(duration_ms: int) -> int:
    """Score maximal possible pour une partie de cette durée (bornée à 30 min)."""
    played_ms = min(max(int(duration_ms), 0), MAX_RUN_SECONDS * 1000)
    return played_ms * SCORE_PER_SECOND_CAP // 1000 + SCORE_BONUS_CAP


def validate(game: str, score: int, accuracy: float, avg_rt_ms: int, level: int, duration_ms: int) -> dict:
    """Résultat d'une partie, vérifié et borné (le score n'est jamais au-delà du plausible)."""
    g = CATALOG.get(game)
    if g is None:
        raise BrainError("Jeu inconnu")
    if not 0 <= accuracy <= 1:
        raise BrainError("Précision invalide")
    if duration_ms < 1000:
        raise BrainError("Durée de partie invalide")
    # Score, niveau et durée trop grands : bornés (un robot parfait n'est jamais refusé) ; score borné par la durée.
    return {"game": game, "domain": g.domain, "score": min(max(int(score), 0), g.max_score, score_cap(duration_ms)),
            "accuracy": round(float(accuracy), 4), "avg_rt_ms": min(max(int(avg_rt_ms), 0), 20000),
            "level": min(max(int(level), 1), MAX_LEVEL), "duration_ms": min(int(duration_ms), g.max_seconds * 1000)}


# ── Lecture des parties ──

def _when(s: dict, now: datetime) -> datetime:
    """Date d'une partie, en UTC, bornée entre DATE_MIN et maintenant : une horloge de téléphone en avance (ou la base
    un peu en avance sur ce serveur) compte la partie comme jouée maintenant ; l'an 1 ou 9999 ne fait plus planter."""
    v = s.get("played_at")
    if isinstance(v, datetime):
        d = v
    else:
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return now
    d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    try:
        d = d.astimezone(timezone.utc)
    except OverflowError:   # an 1 avec un décalage positif, an 9999 avec un décalage négatif
        return DATE_MIN if d.year <= 1 else now
    return min(max(d, DATE_MIN), now)


def _clean(sessions: list[dict], now: datetime | None = None) -> list[dict]:
    """Parties connues du catalogue, avec leur indice et leur date (les autres sont ignorées). L'indice de chaque
    partie est ARRONDI, comme la colonne idx de la base (private.brain_profile fait ses moyennes sur idx) : la
    Température du profil est ainsi celle du classement, au degré près."""
    now = now or datetime.now(timezone.utc)
    out = []
    for s in sessions or []:
        if not isinstance(s, dict) or s.get("game") not in CATALOG:
            continue
        g = CATALOG[s["game"]]
        level = min(max(int(s.get("level") or 1), 1), MAX_LEVEL)
        out.append({**s, "domain": g.domain, "score": min(max(int(s.get("score") or 0), 0), g.max_score),
                    "level": level, "at": _when(s, now), "raw": game_index(s["game"], s.get("score") or 0, level)})
    return sorted(out, key=lambda s: s["at"])


# ── Indices (même calcul que private.brain_profile) ──

def _game_raw(sessions: list[dict], until: datetime) -> dict[str, float]:
    """Par jeu : moyenne (non arrondie) des 5 meilleurs indices des 30 jours avant la dernière partie de ce jeu."""
    by_game: dict[str, list[dict]] = {}
    for s in sessions:
        if s["at"] <= until:
            by_game.setdefault(s["game"], []).append(s)
    out = {}
    for gid, rows in by_game.items():
        last = max(r["at"] for r in rows)
        window = sorted((r["raw"] for r in rows if r["at"] > last - timedelta(days=WINDOW_DAYS)), reverse=True)
        out[gid] = mean(window[:TOP_PER_GAME])
    return out


def _domain_raw(games_raw: dict[str, float]) -> dict[str, float]:
    by_domain: dict[str, list[float]] = {}
    for gid, v in games_raw.items():
        by_domain.setdefault(CATALOG[gid].domain, []).append(v)
    return {d: mean(v) for d, v in by_domain.items()}


def _temperature(domains_raw: dict[str, float]) -> int:
    counted = [v for d, v in domains_raw.items() if d in TEMPERATURE_DOMAINS]
    return round_half_up(mean(counted)) if counted else 0


def temperature_at(sessions: list[dict], until: datetime) -> int:
    return _temperature(_domain_raw(_game_raw(sessions, until)))


# ── Série, évolution, forces ──

def _day(at: datetime) -> date:
    return at.astimezone(TZ).date()


def streak(days: set[date], today: date) -> dict:
    """Série 🔥 : jours d'affilée avec au moins une partie (encore vivante si la dernière date d'hier) et record."""
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best, prev = max(best, run), d
    current = 0
    d = today if today in days else today - timedelta(days=1)
    while d in days:
        current, d = current + 1, d - timedelta(days=1)
    return {"current": current, "best": best}


def _history(sessions: list[dict], today: date) -> list[dict]:
    if not sessions:
        return []
    first = _day(sessions[0]["at"])
    start = max(first, today - timedelta(days=HISTORY_DAYS - 1))
    out = []
    d = start
    while d <= today:
        end = datetime.combine(d + timedelta(days=1), datetime.min.time(), TZ)
        out.append({"day": d.isoformat(), "temperature": temperature_at(sessions, end)})
        d += timedelta(days=1)
    return out


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _label(domain: str) -> str:
    return DOMAINS[domain][0]


def speed_vs_accuracy(recent: list[dict]) -> dict:
    rts = [int(s.get("avg_rt_ms") or 0) for s in recent if int(s.get("avg_rt_ms") or 0) > 0]
    accs = [float(s["accuracy"]) for s in recent if s.get("accuracy") is not None]
    speed = 0
    if rts:
        speed = round_half_up(100 * (SLOW_RT_MS - mean(rts)) / (SLOW_RT_MS - FAST_RT_MS))
    return {"speed": min(max(speed, 0), 100), "accuracy": min(max(round_half_up(100 * mean(accs)), 0), 100) if accs else 0}


# ── Profil complet (réponse de /api/brain/me) ──

def _game_summary(rows: list[dict], raw: float | None) -> dict:
    """Un jeu dans le profil ; max_level / max_tier (ajoutés le 03.11) : palier le plus haut débloqué, pour le choix
    du palier de départ sur un autre appareil."""
    max_level = max((int(s.get("level") or 1) for s in rows), default=0)
    return {"index": round_half_up(raw) if raw is not None else 0,
            "best": max((s["score"] for s in rows), default=0),
            "plays": len(rows),
            "last_level": int(rows[-1].get("level") or 1) if rows else 0,
            "max_level": max_level,
            "max_tier": tier_of(max_level)}


def profile(sessions: list[dict], percentile: int | None = None, now: datetime | None = None,
            party: dict | None = None) -> dict:
    """`party` (facultatif, base) : {"domains": {domaine: {"avg": indice moyen, "players": n}}} des AUTRES joueurs."""
    now = now or datetime.now(timezone.utc)
    rows = _clean(sessions, now)
    games_raw = _game_raw(rows, now)
    domains_raw = _domain_raw(games_raw)
    domains_idx = {d: round_half_up(v) for d, v in domains_raw.items()}
    per_game: dict[str, list[dict]] = {}
    for s in rows:
        per_game.setdefault(s["game"], []).append(s)
    games = {gid: _game_summary(per_game.get(gid, []), games_raw.get(gid)) for gid in CATALOG}
    domains = {d: {"index": domains_idx.get(d, 0), "played": sum(games[g]["plays"] for g in CATALOG if CATALOG[g].domain == d)}
               for d in DOMAINS}
    today = _day(now)
    game_plays = {g: v["plays"] for g, v in games.items()}
    analysis = A.domain_analysis(domains_idx, {d: v["played"] for d, v in domains.items()}, party)
    strong, weak = A.strengths_weaknesses(analysis)
    trends = A.recent_trend(rows, now)
    advice = A.advice(analysis, trends, game_plays)
    recent = [s for s in rows if s["at"] > now - timedelta(days=30)]
    sva = speed_vs_accuracy(recent)
    month = A.month_progress(rows, now)
    salt = today.toordinal() + len(rows)
    out = {
        "name": BRAIN_NAME,
        "temperature": _temperature(domains_raw),
        "domains": domains,
        "games": games,
        "streak": streak({_day(s["at"]) for s in rows}, today),
        "history": _history(rows, today),
        "strengths": strong,
        "weaknesses": weak,
        "insight": A.insight(analysis, strong, weak, len(rows), advice, salt),
        "percentile": percentile,
        "speed_vs_accuracy": sva,
        "month_progress": month,
        # Champs d'analyse (ajoutés ; les écrans plus anciens les ignorent).
        "domain_analysis": analysis,
        "recent_trend": trends,
        "advice": advice,
        "speed_profile": A.speed_profile(recent, sva),
        "month_progress_text": A.month_text(month),
    }
    return {**out, "warmup": A.warmup(out, today)}


def catalog() -> dict:
    """Catalogue public (libellés des domaines et des jeux) : pour les écrans de stats web et iOS."""
    return {"name": BRAIN_NAME,
            "domains": [{"id": d, "label": lab, "icon": ico, "in_temperature": d in TEMPERATURE_DOMAINS}
                        for d, (lab, ico) in DOMAINS.items()],
            "games": [{"id": g.id, "name": g.name, "domain": g.domain, "seconds": g.seconds} for g in CATALOG.values()]}


# ── Comparaison avec un autre membre (fiche profil) : agrégats seulement, jamais le détail de ses parties ──

def _clean_name(name) -> str:
    return " ".join(str(name or "?").split())[:30]


def _int_domains(raw) -> dict[str, int]:
    """Indices par domaine venant de la base, limités aux domaines connus et bornés 0–2000."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for d, v in raw.items():
        if d in DOMAINS and isinstance(v, (int, float)):
            out[d] = min(max(int(v), 0), INDEX_MAX)
    return out


def _who_leads(gaps: dict[str, int]) -> tuple[str, int] | None:
    best = max(gaps.items(), key=lambda kv: kv[1], default=None)
    return best if best and best[1] > 0 else None


def compare_verdict(name: str, mine: dict[str, int], theirs: dict[str, int], is_self: bool) -> str:
    """Une phrase : où chacun est le plus fort (domaines joués par les deux)."""
    if is_self:
        return "C'est toi ! Ouvre la fiche d'un autre membre pour te comparer."
    if not theirs:
        return f"{name} n'a pas encore joué à Méninges."
    if not mine:
        return f"Joue à Méninges pour te comparer à {name}."
    common = [d for d in DOMAINS if d in mine and d in theirs]
    if not common:
        return f"Vous n'avez pas encore joué aux mêmes domaines que {name}."
    me_lead = _who_leads({d: mine[d] - theirs[d] for d in common})
    them_lead = _who_leads({d: theirs[d] - mine[d] for d in common})
    if not me_lead and not them_lead:
        return f"Égalité parfaite avec {name} dans vos domaines communs."
    if not them_lead:
        return f"Tu devances {name} partout, surtout en {_label(me_lead[0])} (+{_fmt(me_lead[1])} °M)."
    if not me_lead:
        return f"{name} te devance partout, surtout en {_label(them_lead[0])} (+{_fmt(them_lead[1])} °M)."
    return (f"Ton point fort : {_label(me_lead[0])} (+{_fmt(me_lead[1])} °M) ; "
            f"celui de {name} : {_label(them_lead[0])} (+{_fmt(them_lead[1])} °M).")


def _bounded_index(value) -> int:
    """Indice venu de la base, ramené entre 0 et INDEX_MAX (valeur absurde ou illisible : 0, jamais d'erreur 500)."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    return 0 if math.isnan(number) else int(min(max(number, 0), INDEX_MAX))


def compare_target(raw, mine_temperature: int, mine: dict[str, int], my_id: str) -> dict | None:
    """Champ target de /api/brain/compare : Températures et domaines des deux, côte à côte, et la phrase-bilan."""
    if not isinstance(raw, dict) or not raw.get("id"):
        return None
    name = _clean_name(raw.get("name"))
    theirs = _int_domains(raw.get("domains"))
    is_self = str(raw["id"]) == str(my_id)
    rows = [{"domain": d, "label": lab, "icon": ico, "me": mine.get(d), "them": theirs.get(d)}
            for d, (lab, ico) in DOMAINS.items() if d in mine or d in theirs]
    return {"id": raw["id"], "name": name, "self": is_self,
            "played": bool(theirs), "temperature": _bounded_index(raw.get("temperature")) if theirs else 0,
            "me_played": bool(mine), "me_temperature": mine_temperature if mine else 0,
            "rows": rows, "verdict": compare_verdict(name, mine, theirs, is_self)}


# ── Base Supabase (fonctions brain_*), avec la session du membre ──

class BrainStore:
    def __init__(self, accounts):
        self.accounts = accounts  # app.accounts.Accounts

    def _call(self, token: str, name: str, args: dict, fallback: str):
        """Jeton vérifié d'abord (AccountError → 401) ; un refus de la base (compte inactif, limite…) → BrainError (400) ;
        une panne (5xx, délai dépassé) → BrainUnavailable (503) : le téléphone garde la partie et la renverra."""
        self.accounts._uid(token)
        try:
            r = self.accounts._get("POST", f"/rest/v1/rpc/{name}", token, json=args)
        except AccountError as e:
            raise BrainUnavailable(str(e)) from e
        if r.status_code >= 500:
            raise BrainUnavailable(fallback or "Méninges ne répond pas. Réessaie dans un instant.")
        if r.status_code == 401:   # jeton expiré entre-temps (vérification gardée 5 min) : à reconnecter, pas un refus
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        if r.status_code != 200:
            try:
                message = str(r.json().get("message", ""))
            except ValueError:
                message = ""
            raise BrainError(message.split(": ", 1)[-1] if message else fallback)
        try:
            return r.json()
        except ValueError as e:
            raise BrainUnavailable(fallback) from e

    def record(self, token: str, result: dict) -> dict:
        r = self._call(token, "brain_record", {
            "p_game": result["game"], "p_score": result["score"], "p_accuracy": result["accuracy"],
            "p_avg_rt_ms": result["avg_rt_ms"], "p_level": result["level"], "p_duration_ms": result["duration_ms"],
        }, "Ta partie n'a pas pu être enregistrée. Réessaie dans un instant.")
        r = r if isinstance(r, dict) else {}
        fallback = game_index(result["game"], result["score"], result["level"])
        return {"saved": True, "index": int(r.get("index") or fallback),
                "best": int(r.get("best") or result["score"]), "record": bool(r.get("record")), "plays": int(r.get("plays") or 1)}

    def me(self, token: str) -> dict:
        r = self._call(token, "brain_my_stats", {}, "Tes statistiques n'ont pas pu être lues.")
        r = r if isinstance(r, dict) else {}
        pct = r.get("percentile")
        party = r.get("party") if isinstance(r.get("party"), dict) else None
        return profile(r.get("sessions") or [], int(pct) if isinstance(pct, (int, float)) else None, party=party)

    def game(self, token: str, game: str) -> dict:
        """Statistiques d'un jeu ; percentile du jeu entre joueurs si la base le fournit (brain_game_percentile,
        migration 20261102240000), sinon null : la fiche reste complète sans lui."""
        if game not in CATALOG:
            raise BrainError("Jeu inconnu")
        r = self._call(token, "brain_my_stats", {}, "Tes statistiques n'ont pas pu être lues.")
        r = r if isinstance(r, dict) else {}
        try:
            pct = self._call(token, "brain_game_percentile", {"p_game": game}, "")
        except BrainError:
            pct = None  # fonction pas encore en base : pas de percentile
        pct = pct.get("percentile") if isinstance(pct, dict) else pct
        from .brain_game import game_detail  # module à part (importe celui-ci)
        return game_detail(r.get("sessions") or [], game, int(pct) if isinstance(pct, (int, float)) else None)

    def _my_domains(self, token: str) -> tuple[int, dict[str, int]]:
        """Ma Température et mes indices par domaine (même calcul que la base), pour la comparaison."""
        r = self._call(token, "brain_my_stats", {}, "Tes statistiques n'ont pas pu être lues.")
        now = datetime.now(timezone.utc)
        rows = _clean((r if isinstance(r, dict) else {}).get("sessions") or [], now)
        domains_raw = _domain_raw(_game_raw(rows, now))
        return _temperature(domains_raw), {d: round_half_up(v) for d, v in domains_raw.items()}

    def compare(self, token: str, target: str | None) -> dict:
        mine = self._my_domains(token) if target else None
        r = self._call(token, "brain_compare", {"p_target": target}, "Le classement n'a pas pu être lu.")
        r = r if isinstance(r, dict) else {}
        board = [{"id": p.get("id"), "name": " ".join(str(p.get("name") or "?").split())[:30],
                  "temperature": int(p.get("temperature") or 0), "me": bool(p.get("me"))}
                 for p in (r.get("board") or []) if isinstance(p, dict)]
        return {"board": board, "rank": r.get("rank"), "players": int(r.get("players") or 0),
                "percentile": r.get("percentile"),
                "target": compare_target(r.get("target"), *mine, self.accounts._uid(token)) if mine else None}
