"""Méninges, analyse (app/brain_analysis.py) : forces / faiblesses sans bruit, tendance, conseils, vitesse vs précision,
progrès du mois robuste, Échauffement du jour."""
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app import brain, brain_analysis as A

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
FORBIDDEN = re.compile(r"\bQI\b|santé|âge cérébral|cerveau plus jeune|Alzheimer|démence|médical", re.IGNORECASE)


def session(game: str, score: int, days_ago: float = 0, accuracy: float = 0.9, rt: int = 700) -> dict:
    return {"game": game, "score": score, "accuracy": accuracy, "avg_rt_ms": rt, "level": 3, "duration_ms": 45000,
            "played_at": (NOW - timedelta(days=days_ago)).isoformat()}


def many(game: str, score: int, n: int = 3, start: float = 1, **kw) -> list[dict]:
    return [session(game, score, days_ago=start + i * 0.1, **kw) for i in range(n)]


def unbalanced() -> list[dict]:
    """Vitesse très haute, Mémoire très basse, Flexibilité au milieu : 3 parties chacune."""
    return many("pareil", 14000) + many("deux_avant", 2000) + many("encre", 9000)


def texts(p: dict) -> list[str]:
    return [p["insight"], p["speed_profile"]["text"], p["month_progress_text"], *(a["reason"] for a in p["advice"])]


# ── Aucun jeu ──

def test_no_game_invites_to_the_warmup_and_concludes_nothing():
    p = brain.profile([], now=NOW)
    assert "Échauffement" in p["insight"]
    assert p["strengths"] == [] and p["weaknesses"] == []
    assert all(a["status"] == "pas_assez" for a in p["domain_analysis"].values())
    assert all(t["trend"] is None for t in p["recent_trend"].values())
    assert p["speed_profile"]["kind"] is None and p["month_progress"] is None
    assert len(p["advice"]) == 3 and len({a["domain"] for a in p["advice"]}) == 3
    assert all(a["domain"] in brain.TEMPERATURE_DOMAINS for a in p["advice"])
    assert len(p["warmup"]) == 5


# ── Une partie ──

def test_a_single_game_is_not_enough_for_a_conclusion():
    p = brain.profile([session("pareil", 14000)], now=NOW)
    assert p["strengths"] == [] and p["weaknesses"] == []
    assert "pas encore assez de parties" in p["insight"].lower()
    assert p["domain_analysis"]["vitesse"] == {"status": "pas_assez", "label": "Pas encore assez de parties", "plays": 1,
                                               "index": p["domains"]["vitesse"]["index"], "vs_self": None,
                                               "party_avg": None, "vs_party": None}
    assert p["month_progress"] is None and "Pas encore assez" in p["month_progress_text"]
    assert p["recent_trend"]["vitesse"] == {"trend": None, "label": "Pas encore assez de parties", "delta": None, "plays": 1}


def test_one_lucky_game_in_a_domain_does_not_make_a_strength():
    rows = many("encre", 9000) + many("deux_avant", 9000) + [session("pareil", 20000)]
    p = brain.profile(rows, now=NOW)
    assert "vitesse" not in p["strengths"] and p["domain_analysis"]["vitesse"]["status"] == "pas_assez"


# ── Profil déséquilibré ──

def test_unbalanced_profile_names_the_strength_the_weakness_and_a_game_to_play():
    p = brain.profile(unbalanced(), now=NOW)
    assert p["strengths"] == ["vitesse"] and p["weaknesses"] == ["memoire"]
    a = p["domain_analysis"]
    assert a["vitesse"]["status"] == "force" and a["vitesse"]["vs_self"] > brain.BALANCED_MARGIN
    assert a["memoire"]["status"] == "faiblesse" and a["memoire"]["vs_self"] < -brain.BALANCED_MARGIN
    assert a["flexibilite"]["status"] == "equilibre" and a["attention"]["status"] == "pas_assez"
    assert "Vitesse" in p["insight"] and "Mémoire" in p["insight"]
    assert p["advice"][0]["domain"] == "memoire"
    assert brain.CATALOG[p["advice"][0]["game"]].name in p["insight"]
    assert p["insight"].count(".") <= 2


def test_insight_varies_from_day_to_day_but_stays_clean():
    rows = unbalanced()
    seen = {brain.profile(rows, now=NOW + timedelta(days=i))["insight"] for i in range(6)}
    assert len(seen) >= 2
    for i in range(6):
        p = brain.profile(rows, now=NOW + timedelta(days=i))
        assert not any(FORBIDDEN.search(t) for t in texts(p))


def test_party_average_is_used_only_with_enough_players():
    rows = unbalanced()
    party = {"domains": {"vitesse": {"avg": 1000, "players": 3}, "memoire": {"avg": 200, "players": 5},
                         "flexibilite": {"avg": 900, "players": 2}}}
    p = brain.profile(rows, now=NOW, party=party)
    a = p["domain_analysis"]
    assert a["vitesse"]["party_avg"] == 1000 and a["vitesse"]["vs_party"] > 0
    assert a["flexibilite"]["party_avg"] is None
    assert "moyenne Party" in p["insight"]
    # Même la faiblesse est au-dessus des autres : on le dit, sans fausse alerte.
    assert "au-dessus de la moyenne Party" in p["insight"]


def test_balanced_profile_says_so():
    rows = many("pareil", 9000) + many("deux_avant", 8000) + many("encre", 9000)
    p = brain.profile(rows, now=NOW)
    assert p["strengths"] == [] and p["weaknesses"] == [] and "équilibr" in p["insight"]


# ── Tendance sur 14 jours ──

def test_recent_trend_compares_first_and_last_games_of_each_game():
    up = [session("pareil", s, days_ago=12 - i) for i, s in enumerate([6000, 6500, 7000, 11000, 12000, 12500])]
    down = [session("deux_avant", s, days_ago=12 - i) for i, s in enumerate([11000, 10500, 10000, 6000, 5500, 5000])]
    flat = [session("encre", 9000, days_ago=12 - i) for i in range(6)]
    t = brain.profile(up + down + flat, now=NOW)["recent_trend"]
    assert t["vitesse"]["trend"] == "hausse" and t["vitesse"]["label"] == "En hausse" and t["vitesse"]["delta"] > 0
    assert t["memoire"]["trend"] == "baisse" and t["memoire"]["delta"] < 0
    assert t["flexibilite"]["trend"] == "stable" and t["flexibilite"]["delta"] == 0
    assert t["attention"]["trend"] is None and t["attention"]["plays"] == 0


def test_trend_ignores_games_older_than_14_days():
    old = [session("pareil", 2000, days_ago=20 + i) for i in range(3)]
    recent = [session("pareil", 9000, days_ago=i) for i in range(4)]
    t = brain.profile(old + recent, now=NOW)["recent_trend"]["vitesse"]
    assert t["trend"] == "stable" and t["plays"] == 4


def test_switching_to_an_easier_game_is_not_a_trend():
    """Mémoire : un jeu difficile au début, un jeu « facile » à la fin, chacun stable → stable, pas « en hausse »."""
    rows = [session("deux_avant", 4000, days_ago=10 - i * 0.1) for i in range(4)]
    rows += [session("grille", 9000, days_ago=2 - i * 0.1) for i in range(4)]
    assert brain.profile(rows, now=NOW)["recent_trend"]["memoire"]["trend"] == "stable"


# ── Conseils ──

def test_advice_targets_the_weak_domain_and_its_least_played_game():
    rows = unbalanced() + many("grille", 2000, n=4)
    p = brain.profile(rows, now=NOW)
    first = p["advice"][0]
    assert first["domain"] == "memoire" and first["game"] == "tresor"     # jamais joué, alors que grille l'a été 4 fois
    assert first["name"] == "Jamais deux fois" and "Mémoire" in first["reason"]
    assert 1 <= len(p["advice"]) <= 3 and len({a["domain"] for a in p["advice"]}) == len(p["advice"])


def test_advice_points_to_a_falling_domain():
    rows = many("pareil", 9000) + many("deux_avant", 9000)
    rows += [session("encre", s, days_ago=10 - i) for i, s in enumerate([12000, 12000, 12000, 6000, 6000, 6000])]
    p = brain.profile(rows, now=NOW)
    assert p["recent_trend"]["flexibilite"]["trend"] == "baisse"
    falling = [a for a in p["advice"] if a["domain"] == "flexibilite"]
    assert falling and "baisse" in falling[0]["reason"]


# ── Vitesse vs précision ──

def test_speed_profile_needs_a_few_games():
    assert brain.profile(many("pareil", 9000, n=4), now=NOW)["speed_profile"]["kind"] is None


def test_speed_profiles():
    def kind(rt, acc):
        return brain.profile(many("pareil", 9000, n=5, rt=rt, accuracy=acc), now=NOW)["speed_profile"]
    fast_sloppy, slow_precise = kind(450, 0.6), kind(1500, 0.97)
    assert fast_sloppy["kind"] == "rapide_imprecis" and fast_sloppy["label"] == "Rapide mais imprécis"
    assert slow_precise["kind"] == "precis_lent" and slow_precise["label"] == "Précis mais lent"
    assert kind(450, 0.95)["kind"] == "rapide_precis"
    assert kind(1000, 0.8)["kind"] == "equilibre"
    assert all(kind(rt, acc)["text"] for rt, acc in ((450, 0.6), (1500, 0.97), (1000, 0.8)))


# ── Progrès du mois ──

def test_month_progress_compares_first_and_last_games_not_a_single_score():
    rows = [session("pareil", s, days_ago=25 - i) for i, s in enumerate([6000, 6000, 6000, 9000, 9000, 9000])]
    p = brain.profile(rows, now=NOW)
    expected = brain.game_index("pareil", 9000) - brain.game_index("pareil", 6000)
    assert abs(p["month_progress"] - expected) <= 1 and p["month_progress"] > 0
    assert p["month_progress_text"].startswith("+")
    # Une seule partie exceptionnelle ne fait pas le progrès du mois.
    lucky = rows[:5] + [session("pareil", 30000, days_ago=1)]
    assert brain.profile(lucky, now=NOW)["month_progress"] < brain.game_index("pareil", 30000) - brain.game_index("pareil", 6000)


def test_month_progress_ignores_games_older_than_30_days_and_needs_enough_pairs():
    rows = [session("pareil", 2000, days_ago=40)] + [session("pareil", 9000, days_ago=i) for i in range(2)]
    assert brain.profile(rows, now=NOW)["month_progress"] is None
    flat = [session("pareil", 9000, days_ago=i) for i in range(6)]
    p = brain.profile(flat, now=NOW)
    assert p["month_progress"] == 0 and "Stable" in p["month_progress_text"]


# ── L'Échauffement ──

def test_warmup_covers_the_5_temperature_domains_and_is_the_same_all_day():
    p = brain.profile(unbalanced(), now=NOW)
    w = A.warmup(p, date(2026, 11, 2))
    assert len(w) == 5 and len(set(w)) == 5
    assert {brain.CATALOG[g].domain for g in w} == set(brain.TEMPERATURE_DOMAINS)
    assert A.warmup(p, date(2026, 11, 2)) == w == p["warmup"]


def test_warmup_puts_the_weak_domain_first_and_changes_from_day_to_day():
    p = brain.profile(unbalanced(), now=NOW)
    days = [A.warmup(p, date(2026, 11, 1) + timedelta(days=i)) for i in range(10)]
    assert all(brain.CATALOG[w[0]].domain == "memoire" for w in days)
    assert len({tuple(w) for w in days}) > 1


def test_warmup_without_games_of_a_domain_fills_with_others():
    available = [g for g in brain.CATALOG if brain.CATALOG[g].domain != "logique"]
    w = A.warmup(brain.profile([], now=NOW), date(2026, 11, 2), available)
    assert len(w) == 5 and set(w) <= set(available) and "calcul" in {brain.CATALOG[g].domain for g in w}


def test_warmup_accepts_an_empty_or_partial_stats_dict():
    assert len(A.warmup({}, date(2026, 11, 2))) == 5
