"""Méninges — entraînement cérébral solo (façon Lumosity, noms et visuels originaux).

Les mini-jeux tournent entièrement dans le navigateur (app/static/brain/) ; seul le résultat d'une partie arrive ici.
Ce module garde le catalogue (15 jeux, 6 domaines), les bornes plausibles de score, la normalisation score brut →
indice 0–2000 et tous les calculs du profil : Température (°M), domaines, forces / faiblesses, série 🔥, évolution.

La base (migration supabase/migrations/20261102210000_brain.sql) applique la MÊME normalisation et le même calcul de
Température (pour le percentile entre joueurs) : les valeurs du catalogue y sont recopiées et tests/test_brain.py
vérifie qu'elles restent identiques. Toute modification du catalogue se fait donc aux deux endroits.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

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
    seconds: int | None   # durée du chrono ; None = le jeu se termine seul (essais, vies)
    median: int           # score brut « typique » → indice 1000
    spread: int           # largeur de la courbe (plus grand = indice qui monte plus doucement)
    max_score: int        # au-delà : score impossible, borné
    max_seconds: int      # durée maximale plausible d'une partie


# Calibrage (02.11.2026, moteur réel) : un joueur qui tape au hasard tombe vers 300–550 °M, le score typique vaut
# 1000, un très bon humain (~1,7 × typique) vers 1650. Le robot parfait des agents jeux (syllabes ≈ 73 000,
# balance ≈ 39 000) reste sous la borne : un score trop haut est borné, jamais rejeté. À recalibrer sur les vraies parties.
def _timed(gid: str, name: str, domain: str, seconds: int, median: int) -> Game:
    # Chrono : au mieux ~3 réponses/s, presque toutes à ×10 (500 pts), + le bonus final (2 500).
    return Game(gid, name, domain, seconds, median, round(median * 0.45), seconds * 1500 + 2500, seconds + 30)


def _open(gid: str, name: str, domain: str, median: int) -> Game:
    # Sans chrono (essais, vies) : la partie peut durer, la borne est large.
    return Game(gid, name, domain, None, median, round(median * 0.45), 250000, 1800)


CATALOG: dict[str, Game] = {g.id: g for g in (
    _timed("pareil", "Pareil ?", "vitesse", 45, 9000),
    _timed("motif", "Même motif", "vitesse", 45, 8500),
    _timed("autoroute", "Trois voies", "attention", 60, 9000),
    _open("grille", "Cases lumineuses", "memoire", 6000),
    _timed("deux_avant", "Deux avant", "memoire", 45, 8000),
    _open("tresor", "Jamais deux fois", "memoire", 5000),
    _timed("nuee", "Le vol", "attention", 45, 8500),
    _timed("aiguillage", "Aiguillages", "attention", 120, 9000),
    _timed("intrus", "L'intrus", "attention", 45, 8000),
    _timed("encre", "Mot ou encre", "flexibilite", 45, 9000),
    _timed("bascule", "Bascule", "flexibilite", 45, 8500),
    _timed("courant", "Contre-courant", "flexibilite", 45, 8000),
    _timed("balance", "Plus lourd", "calcul", 45, 8500),
    _open("gouttes", "Gouttes", "calcul", 6000),
    _timed("syllabes", "Débuts de mots", "logique", 60, 9000),
)}


class BrainError(ValueError):
    pass


# ── Normalisation ──

def round_half_up(x: float) -> int:
    """Arrondi identique à floor(x + 0.5) de la base (round() de Python arrondit au pair)."""
    return math.floor(x + 0.5)


def raw_index(game: str, score: int) -> float:
    """Score brut → indice 0–2000 non arrondi : courbe en S centrée sur le score typique du jeu (1000 = typique)."""
    g = CATALOG[game]
    s = min(max(int(score), 0), g.max_score)
    return INDEX_MAX / (1 + math.exp(-(s - g.median) / g.spread))


def game_index(game: str, score: int) -> int:
    return round_half_up(raw_index(game, score))


def validate(game: str, score: int, accuracy: float, avg_rt_ms: int, level: int, duration_ms: int) -> dict:
    """Résultat d'une partie, vérifié et borné (le score n'est jamais au-delà du plausible)."""
    g = CATALOG.get(game)
    if g is None:
        raise BrainError("Jeu inconnu")
    if not 0 <= accuracy <= 1:
        raise BrainError("Précision invalide")
    if not 1000 <= duration_ms <= g.max_seconds * 1000:
        raise BrainError("Durée de partie invalide")
    return {"game": game, "domain": g.domain, "score": min(max(int(score), 0), g.max_score),
            "accuracy": round(float(accuracy), 4), "avg_rt_ms": min(max(int(avg_rt_ms), 0), 20000),
            "level": min(max(int(level), 1), 99), "duration_ms": int(duration_ms)}


# ── Lecture des parties ──

def _when(s: dict) -> datetime:
    v = s.get("played_at")
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _clean(sessions: list[dict]) -> list[dict]:
    """Parties connues du catalogue, avec leur indice et leur date (les autres sont ignorées)."""
    out = []
    for s in sessions or []:
        if not isinstance(s, dict) or s.get("game") not in CATALOG:
            continue
        g = CATALOG[s["game"]]
        out.append({**s, "domain": g.domain, "score": min(max(int(s.get("score") or 0), 0), g.max_score),
                    "at": _when(s), "raw": raw_index(s["game"], s.get("score") or 0)})
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


def strengths_weaknesses(domains: dict[str, int]) -> tuple[list[str], list[str]]:
    """Domaines nettement au-dessus / en dessous de ta propre moyenne (au moins 2 domaines joués)."""
    if len(domains) < 2:
        return [], []
    avg = mean(domains.values())
    strong = sorted((d for d, v in domains.items() if v > avg + BALANCED_MARGIN), key=lambda d: -domains[d])
    weak = sorted((d for d, v in domains.items() if v < avg - BALANCED_MARGIN), key=lambda d: domains[d])
    return strong, weak


def insight(domains: dict[str, int], strong: list[str], weak: list[str], plays: int) -> str:
    if not plays:
        return "Lance ton premier Échauffement pour mesurer ta Température."
    if len(domains) < 2:
        return "Essaie des jeux d'autres domaines pour découvrir tes forces."
    if not strong or not weak:
        return "Tes domaines sont très équilibrés : continue l'Échauffement chaque jour."
    s, w = strong[0], weak[0]
    return (f"Ta force : {_label(s)} ({_fmt(domains[s])} °M). À travailler : {_label(w)} "
            f"({_fmt(domains[w])} °M) — l'Échauffement en propose chaque jour.")


def speed_vs_accuracy(recent: list[dict]) -> dict:
    rts = [int(s.get("avg_rt_ms") or 0) for s in recent if int(s.get("avg_rt_ms") or 0) > 0]
    accs = [float(s["accuracy"]) for s in recent if s.get("accuracy") is not None]
    speed = 0
    if rts:
        speed = round_half_up(100 * (SLOW_RT_MS - mean(rts)) / (SLOW_RT_MS - FAST_RT_MS))
    return {"speed": min(max(speed, 0), 100), "accuracy": min(max(round_half_up(100 * mean(accs)), 0), 100) if accs else 0}


# ── Profil complet (réponse de /api/brain/me) ──

def profile(sessions: list[dict], percentile: int | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    rows = _clean(sessions)
    games_raw = _game_raw(rows, now)
    domains_raw = _domain_raw(games_raw)
    domains_idx = {d: round_half_up(v) for d, v in domains_raw.items()}
    per_game: dict[str, list[dict]] = {}
    for s in rows:
        per_game.setdefault(s["game"], []).append(s)
    games = {gid: {"index": round_half_up(games_raw[gid]) if gid in games_raw else 0,
                   "best": max((s["score"] for s in per_game.get(gid, [])), default=0),
                   "plays": len(per_game.get(gid, [])),
                   "last_level": int(per_game[gid][-1].get("level") or 1) if gid in per_game else 0}
             for gid in CATALOG}
    domains = {d: {"index": domains_idx.get(d, 0), "played": sum(games[g]["plays"] for g in CATALOG if CATALOG[g].domain == d)}
               for d in DOMAINS}
    today = _day(now)
    strong, weak = strengths_weaknesses(domains_idx)
    temp = _temperature(domains_raw)
    month_ago = now - timedelta(days=30)
    before = [s for s in rows if s["at"] <= month_ago]
    recent = [s for s in rows if s["at"] > month_ago]
    return {
        "name": BRAIN_NAME,
        "temperature": temp,
        "domains": domains,
        "games": games,
        "streak": streak({_day(s["at"]) for s in rows}, today),
        "history": _history(rows, today),
        "strengths": strong,
        "weaknesses": weak,
        "insight": insight(domains_idx, strong, weak, len(rows)),
        "percentile": percentile,
        "speed_vs_accuracy": speed_vs_accuracy(recent),
        "month_progress": temp - temperature_at(before, month_ago) if before else None,
    }


def catalog() -> dict:
    """Catalogue public (libellés des domaines et des jeux) : pour les écrans de stats web et iOS."""
    return {"name": BRAIN_NAME,
            "domains": [{"id": d, "label": lab, "icon": ico, "in_temperature": d in TEMPERATURE_DOMAINS}
                        for d, (lab, ico) in DOMAINS.items()],
            "games": [{"id": g.id, "name": g.name, "domain": g.domain, "seconds": g.seconds} for g in CATALOG.values()]}


# ── Base Supabase (fonctions brain_*), avec la session du membre ──

class BrainStore:
    def __init__(self, accounts):
        self.accounts = accounts  # app.accounts.Accounts

    def _call(self, token: str, name: str, args: dict, fallback: str):
        """Jeton vérifié d'abord (AccountError → 401) ; un refus de la base (compte inactif, limite…) → BrainError (400)."""
        self.accounts._uid(token)
        try:
            return self.accounts._rpc_json(token, name, args, fallback)
        except AccountError as e:
            raise BrainError(str(e)) from e

    def record(self, token: str, result: dict) -> dict:
        r = self._call(token, "brain_record", {
            "p_game": result["game"], "p_score": result["score"], "p_accuracy": result["accuracy"],
            "p_avg_rt_ms": result["avg_rt_ms"], "p_level": result["level"], "p_duration_ms": result["duration_ms"],
        }, "Ta partie n'a pas pu être enregistrée. Réessaie dans un instant.")
        r = r if isinstance(r, dict) else {}
        return {"saved": True, "index": int(r.get("index") or game_index(result["game"], result["score"])),
                "best": int(r.get("best") or result["score"]), "record": bool(r.get("record")), "plays": int(r.get("plays") or 1)}

    def me(self, token: str) -> dict:
        r = self._call(token, "brain_my_stats", {}, "Tes statistiques n'ont pas pu être lues.")
        r = r if isinstance(r, dict) else {}
        pct = r.get("percentile")
        return profile(r.get("sessions") or [], int(pct) if isinstance(pct, (int, float)) else None)

    def compare(self, token: str, target: str | None) -> dict:
        r = self._call(token, "brain_compare", {"p_target": target}, "Le classement n'a pas pu être lu.")
        r = r if isinstance(r, dict) else {}
        board = [{"id": p.get("id"), "name": " ".join(str(p.get("name") or "?").split())[:30],
                  "temperature": int(p.get("temperature") or 0), "me": bool(p.get("me"))}
                 for p in (r.get("board") or []) if isinstance(p, dict)]
        return {"board": board, "rank": r.get("rank"), "players": int(r.get("players") or 0),
                "percentile": r.get("percentile"), "target": r.get("target")}
