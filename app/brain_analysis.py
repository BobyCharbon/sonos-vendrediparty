"""Méninges — l'analyse du profil : forces / faiblesses, tendance, conseils, vitesse vs précision, progrès, Échauffement.

Tout part des parties « nettoyées » de app/brain.py (_clean : jeu, domaine, indice brut `raw`, date `at`, précision,
temps de réaction). Principes :
- jamais de conclusion sur trop peu de parties : un domaine n'est jugé qu'à partir de MIN_DOMAIN_PLAYS parties, une
  tendance ou un progrès ne se calcule qu'en comparant les premières et les dernières parties d'un MÊME jeu ;
- la moyenne des joueurs Party (fournie par la base, sans le joueur lui-même) ne sert qu'avec PARTY_MIN_PLAYERS joueurs ;
- les phrases sont courtes, bienveillantes et concrètes (un jeu à faire), variées d'un jour à l'autre, et ne parlent
  jamais de santé, de QI ou de « cerveau plus jeune ».
"""
import hashlib
import random
from datetime import date, datetime, timedelta
from statistics import mean

from . import brain as b

MIN_DOMAIN_PLAYS = 3        # parties dans un domaine avant de le classer force / faiblesse
PARTY_MIN_PLAYERS = 3       # autres joueurs Party ayant joué un domaine avant de comparer à leur moyenne
PARTY_MARGIN = 50           # °M d'écart avec la moyenne Party pour le mentionner
TREND_DAYS = 14
TREND_MARGIN = 30           # °M : en deçà, « stable »
TREND_MIN_WEIGHT = 2        # paires (premières / dernières parties d'un même jeu) pour une tendance
MONTH_DAYS = 30
MONTH_MIN_WEIGHT = 3
MONTH_STABLE = 20
EDGE_PLAYS = 3              # premières / dernières parties comparées par jeu
SPEED_MIN_PLAYS = 5
SPEED_HIGH, SPEED_LOW = 55, 35      # vitesse 0–100 (temps de réaction)
ACC_HIGH, ACC_LOW = 85, 75          # précision 0–100
ADVICE_MAX = 3
WARMUP_SIZE = 5

STATUS_LABELS = {"force": "Force", "faiblesse": "À travailler", "equilibre": "Équilibré",
                 "pas_assez": "Pas encore assez de parties"}
TREND_LABELS = {"hausse": "En hausse", "stable": "Stable", "baisse": "En baisse", None: "Pas encore assez de parties"}


def _label(domain: str) -> str:
    return b.DOMAINS[domain][0]


def _pick(options: list[str], salt: int) -> str:
    """Une formulation parmi plusieurs : change d'un jour (ou d'une partie) à l'autre, stable dans une même réponse."""
    return options[salt % len(options)]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


# ── Progrès : premières vs dernières parties d'un même jeu ──

def progress(rows: list[dict]) -> tuple[int, int] | None:
    """(écart en °M, nombre de paires comparées) : par jeu joué au moins 2 fois, moyenne des k dernières parties moins
    moyenne des k premières (k ≤ 3), pondérée par k. Comparer jeu par jeu évite qu'un simple changement de jeux
    (un jeu plus facile en fin de mois) passe pour un progrès. None sans aucun jeu joué 2 fois."""
    by_game: dict[str, list[float]] = {}
    for s in sorted(rows, key=lambda s: s["at"]):
        by_game.setdefault(s["game"], []).append(s["raw"])
    pairs = []
    for values in by_game.values():
        k = min(EDGE_PLAYS, len(values) // 2)
        if k:
            pairs.append((mean(values[-k:]) - mean(values[:k]), k))
    weight = sum(k for _, k in pairs)
    if not weight:
        return None
    return b.round_half_up(sum(d * k for d, k in pairs) / weight), weight


def month_progress(rows: list[dict], now: datetime) -> int | None:
    recent = [s for s in rows if s["at"] > now - timedelta(days=MONTH_DAYS)]
    p = progress(recent)
    return p[0] if p and p[1] >= MONTH_MIN_WEIGHT else None


def month_text(value: int | None) -> str:
    if value is None:
        return "Pas encore assez de parties ce mois-ci pour mesurer un progrès : rejoue quelques jeux déjà essayés."
    if value > MONTH_STABLE:
        return f"+{b._fmt(value)} °M entre tes premières et tes dernières parties du mois."
    if value < -MONTH_STABLE:
        return f"{b._fmt(value)} °M sur le mois : ça arrive après une pause ou des niveaux plus durs, ça remonte vite."
    return "Stable sur le mois : tes dernières parties valent tes premières."


def recent_trend(rows: list[dict], now: datetime) -> dict:
    """Par domaine, sur 14 jours : hausse / stable / baisse (None = pas assez de parties pour le dire)."""
    since = now - timedelta(days=TREND_DAYS)
    out = {}
    for d in b.DOMAINS:
        window = [s for s in rows if s["domain"] == d and since < s["at"] <= now]
        p = progress(window)
        delta = p[0] if p and p[1] >= TREND_MIN_WEIGHT else None
        trend = None if delta is None else "hausse" if delta > TREND_MARGIN else "baisse" if delta < -TREND_MARGIN else "stable"
        out[d] = {"trend": trend, "label": TREND_LABELS[trend], "delta": delta, "plays": len(window)}
    return out


# ── Forces / faiblesses ──

def _party_avg(party: dict | None, domain: str) -> int | None:
    info = ((party or {}).get("domains") or {}).get(domain)
    if not isinstance(info, dict) or int(info.get("players") or 0) < PARTY_MIN_PLAYERS:
        return None
    try:
        return int(info["avg"])
    except (KeyError, TypeError, ValueError):
        return None


def domain_analysis(domains_idx: dict[str, int], plays: dict[str, int], party: dict | None) -> dict:
    """Chaque domaine comparé à ta moyenne (domaines assez joués) et, si possible, à la moyenne des joueurs Party."""
    judged = {d: v for d, v in domains_idx.items() if plays.get(d, 0) >= MIN_DOMAIN_PLAYS}
    avg = mean(judged.values()) if len(judged) >= 2 else None
    out = {}
    for d in b.DOMAINS:
        party_avg = _party_avg(party, d)
        vs_self = b.round_half_up(judged[d] - avg) if d in judged and avg is not None else None
        status = "pas_assez" if vs_self is None else (
            "force" if vs_self > b.BALANCED_MARGIN else "faiblesse" if vs_self < -b.BALANCED_MARGIN else "equilibre")
        out[d] = {"status": status, "label": STATUS_LABELS[status], "plays": plays.get(d, 0),
                  "index": domains_idx.get(d, 0), "vs_self": vs_self, "party_avg": party_avg,
                  "vs_party": domains_idx[d] - party_avg if party_avg is not None and d in judged else None}
    return out


def strengths_weaknesses(analysis: dict) -> tuple[list[str], list[str]]:
    strong = sorted((d for d, a in analysis.items() if a["status"] == "force"), key=lambda d: -analysis[d]["index"])
    weak = sorted((d for d, a in analysis.items() if a["status"] == "faiblesse"), key=lambda d: analysis[d]["index"])
    return strong, weak


def _strength_sentence(d: str, a: dict, salt: int) -> str:
    s = _label(d)
    if a["vs_party"] is not None and a["vs_party"] > PARTY_MARGIN:
        return _pick([f"En {s}, tu dépasses la moyenne Party de {b._fmt(a['vs_party'])} °M.",
                      f"{s} : {b._fmt(a['vs_party'])} °M au-dessus de la moyenne Party, bravo."], salt)
    v = b._fmt(a["index"])
    return _pick([f"Ta force : {s} ({v} °M).", f"{s} est ton point fort en ce moment ({v} °M).",
                  f"Tu brilles en {s} ({v} °M)."], salt)


def _weakness_sentence(d: str, a: dict, game: str | None, salt: int) -> str:
    w = _label(d)
    if a["vs_party"] is not None and a["vs_party"] >= 0:
        return f"{w} est ton domaine le moins avancé, et pourtant déjà au-dessus de la moyenne Party."
    g = b.CATALOG[game].name if game else "l'Échauffement"
    return _pick([f"À travailler : {w} — {g} est un bon point de départ.",
                  f"{w} a le plus de marge : quelques parties de {g} feront la différence.",
                  f"Pour équilibrer, mise sur {w} cette semaine, par exemple avec {g}."], salt)


def insight(analysis: dict, strong: list[str], weak: list[str], total: int, advice: list[dict], salt: int) -> str:
    """1 ou 2 phrases : ce qui ressort de ton profil, avec un jeu concret à faire."""
    if not total:
        return "Lance ton premier Échauffement pour mesurer ta Température."
    if all(a["status"] == "pas_assez" for a in analysis.values()):
        return _pick([f"Pas encore assez de parties pour parler de forces : il en faut {MIN_DOMAIN_PLAYS} dans au moins "
                      "deux domaines. L'Échauffement du jour t'y aide.",
                      "Pas encore assez de parties pour tirer des conclusions. Varie les domaines et ton profil se "
                      "dessinera en quelques jours."], salt)
    game_for = {x["domain"]: x["game"] for x in reversed(advice)}
    if strong and weak:
        return f"{_strength_sentence(strong[0], analysis[strong[0]], salt)} " \
               f"{_weakness_sentence(weak[0], analysis[weak[0]], game_for.get(weak[0]), salt)}"
    if strong:
        return f"{_strength_sentence(strong[0], analysis[strong[0]], salt)} Tes autres domaines sont bien équilibrés."
    if weak:
        return f"Tes domaines sont plutôt équilibrés. {_weakness_sentence(weak[0], analysis[weak[0]], game_for.get(weak[0]), salt)}"
    return _pick(["Tes domaines sont très équilibrés : continue l'Échauffement chaque jour.",
                  "Aucun domaine ne se détache : ton profil est régulier. Varie les jeux pour garder cet équilibre."], salt)


# ── Conseils : 1 à 3 jeux à faire ──

def _domain_priority(analysis: dict, trends: dict) -> list[tuple[str, str]]:
    """Domaines dans l'ordre où les travailler, avec la raison : faible, en baisse, pas assez joué, puis le plus bas."""
    order: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(ds, why):
        for d in ds:
            if d not in seen:
                seen.add(d)
                order.append((d, why))

    by_index = sorted(b.DOMAINS, key=lambda d: (analysis[d]["index"], list(b.DOMAINS).index(d)))
    add([d for d in by_index if analysis[d]["status"] == "faiblesse"], "faiblesse")
    add([d for d in by_index if trends[d]["trend"] == "baisse"], "baisse")
    unplayed = sorted((d for d in b.DOMAINS if analysis[d]["status"] == "pas_assez"),
                      key=lambda d: (d not in b.TEMPERATURE_DOMAINS, analysis[d]["plays"], list(b.DOMAINS).index(d)))
    add(unplayed, "pas_assez")
    add(by_index, "entretien")
    return order


def _least_played(domain: str, game_plays: dict[str, int]) -> str:
    return min((g for g in b.CATALOG if b.CATALOG[g].domain == domain), key=lambda g: game_plays.get(g, 0))


def _reason(why: str, domain: str, game: str, analysis: dict, game_plays: dict[str, int]) -> str:
    d, n = _label(domain), game_plays.get(game, 0)
    if why == "faiblesse":
        if not n:
            return f"{d} est ton domaine à travailler, et ce jeu-là est tout neuf pour toi."
        return f"{d} est ton domaine à travailler : c'est le jeu que tu y as le moins joué ({n} fois)."
    if why == "baisse":
        return f"{d} est en baisse ces {TREND_DAYS} derniers jours : une partie pour reprendre le fil."
    if why == "pas_assez":
        left = MIN_DOMAIN_PLAYS - analysis[domain]["plays"]
        if not analysis[domain]["plays"]:
            return f"Jamais joué en {d} : de quoi découvrir ce domaine."
        return f"Encore {_plural(left, 'partie')} en {d} pour mesurer ce domaine."
    return f"Peu joué : entretient ton niveau en {d}."


def advice(analysis: dict, trends: dict, game_plays: dict[str, int]) -> list[dict]:
    """1 à 3 jeux, chacun d'un domaine différent : le moins joué du domaine qui en a le plus besoin."""
    out = []
    for domain, why in _domain_priority(analysis, trends)[:ADVICE_MAX]:
        game = _least_played(domain, game_plays)
        out.append({"game": game, "name": b.CATALOG[game].name, "domain": domain,
                    "reason": _reason(why, domain, game, analysis, game_plays)})
    return out


# ── Vitesse vs précision ──

SPEED_PROFILES = {
    "rapide_precis": ("Rapide et précis", "Vitesse et précision vont de pair chez toi : vise des séries plus longues "
                                          "pour monter de niveau."),
    "rapide_imprecis": ("Rapide mais imprécis", "Tu réponds vite, quitte à te tromper : ralentis d'un rien, les bonnes "
                                                "réponses en série font grimper le multiplicateur."),
    "precis_lent": ("Précis mais lent", "Tu te trompes rarement : ose répondre un peu plus vite, ta précision suivra."),
    "equilibre": ("Équilibré", "Ni trop vite ni trop prudent : garde ce rythme et gagne un peu de vitesse partie après partie."),
    None: ("Pas encore assez de parties", "Encore quelques parties pour savoir si tu es plutôt rapide ou plutôt précis."),
}


def speed_profile(recent: list[dict], sva: dict) -> dict:
    timed = [s for s in recent if int(s.get("avg_rt_ms") or 0) > 0]
    kind = None
    if len(timed) >= SPEED_MIN_PLAYS:
        speed, acc = sva["speed"], sva["accuracy"]
        if acc >= ACC_HIGH and speed >= SPEED_HIGH:
            kind = "rapide_precis"
        elif acc < ACC_LOW and speed >= SPEED_LOW:
            kind = "rapide_imprecis"
        elif speed < SPEED_LOW and acc >= ACC_LOW:
            kind = "precis_lent"
        else:
            kind = "equilibre"
    label, text = SPEED_PROFILES[kind]
    return {"kind": kind, "label": label, "text": text}


# ── L'Échauffement : 5 jeux du jour ──

def _day_rng(day: date) -> random.Random:
    return random.Random(int(hashlib.sha256(day.isoformat().encode()).hexdigest()[:12], 16))


def warmup(stats: dict, day: date, available: list[str] | None = None) -> list[str]:
    """5 jeux du jour, déterministes pour un même profil et un même jour : un par domaine de la Température (les 5),
    les domaines à travailler en tête avec leur jeu le moins joué, les autres dans un ordre et avec un jeu tirés au
    sort du jour (les jeux peu joués plus souvent). Un domaine sans jeu disponible est remplacé (Calcul d'abord).
    `stats` = le profil (réponse de /api/brain/me) ; `available` = jeux connus du navigateur (tous par défaut)."""
    rng = _day_rng(day)
    pool = [g for g in b.CATALOG if available is None or g in set(available)]
    plays = {g: int(((stats.get("games") or {}).get(g) or {}).get("plays") or 0) for g in b.CATALOG}
    weak = [d for d in (stats.get("weaknesses") or []) if d in b.TEMPERATURE_DOMAINS]
    others = [d for d in b.TEMPERATURE_DOMAINS if d not in weak]
    rng.shuffle(others)
    picks: list[str] = []
    for d in weak + others + ["calcul"]:
        options = [g for g in pool if b.CATALOG[g].domain == d]
        if not options or len(picks) >= WARMUP_SIZE:
            continue
        if d in weak:
            picks.append(min(options, key=lambda g: plays[g]))
        else:
            picks.append(rng.choices(options, weights=[1 / (1 + plays[g]) for g in options])[0])
    rest = [g for g in pool if g not in picks]
    rng.shuffle(rest)
    return picks + rest[:WARMUP_SIZE - len(picks)]
