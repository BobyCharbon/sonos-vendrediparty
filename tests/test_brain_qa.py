"""Méninges, QA serveur (03.11.2026) : entrées extrêmes, triche, arrondis identiques à la base, série 🔥 autour de
minuit (Zurich) et du changement d'heure, rejouabilité des migrations et fichiers prod."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import brain, brain_game, main

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
BRAIN_MIGRATIONS = ["20261102210000_brain", "20261102220000_brain_analyse", "20261102240000_brain_game",
                    "20261103090000_brain_sans_fin", "20261103100000_brain_anti_triche",
                    "20261103101000_brain_perf", "20261103150000_brain_niveaux"]
PROD_APPLY = (ROOT / "supabase" / "prod" / "2026-11-02-meninges-apply.sql").read_text(encoding="utf-8")
PROD_ROLLBACK = (ROOT / "supabase" / "prod" / "2026-11-02-meninges-rollback.sql").read_text(encoding="utf-8")
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def client():
    return TestClient(main.app)


def session(at: str, game="pareil", score=22500, level=10, **kw) -> dict:
    return {"game": game, "score": score, "accuracy": 0.9, "avg_rt_ms": 600, "level": level,
            "duration_ms": 120_000, "played_at": at, **kw}


# ── Entrées extrêmes (joueur non connecté : parties envoyées par le téléphone) ──

@pytest.mark.parametrize("at", ["0001-01-01T00:00:00+14:00", "0001-01-01", "9999-12-31T23:59:59-14:00",
                                "9999-12-31", "1970-01-01T00:00:00Z", "garbage", ""])
def test_local_profile_survives_absurd_dates(client, at):
    """Bug : une date en l'an 1 ou 9999 (horloge du téléphone, partie forgée) faisait planter le calcul (500)."""
    body = {"sessions": [session(at), session("2026-11-02T10:00:00Z")]}
    assert client.post("/api/brain/local", json=body).status_code == 200
    assert client.post("/api/brain/game/local", json={**body, "game": "pareil"}).status_code == 200


def test_a_phone_clock_slightly_ahead_still_counts_the_last_game():
    """Bug : une partie datée de 2 minutes dans le futur (horloge en avance, ou base un peu en avance sur le serveur)
    ne comptait pas dans la Température du profil, alors que la fiche du jeu la comptait."""
    p = brain.profile([session((NOW + timedelta(minutes=2)).isoformat())], now=NOW)
    assert p["temperature"] == brain.game_index("pareil", 22500, 10)
    assert p["domains"]["vitesse"]["index"] == p["temperature"]


def test_far_future_games_are_counted_as_played_now():
    p = brain.profile([session("9999-12-31T00:00:00Z")], now=NOW)
    assert p["streak"]["current"] == 1 and p["history"][-1]["day"] == "2026-11-03"


def test_local_list_is_limited(client):
    many = [session("2026-11-02T10:00:00Z")] * (brain.LOCAL_MAX + 1)
    assert client.post("/api/brain/local", json={"sessions": many}).status_code == 422


@pytest.mark.parametrize("bad", [{"score": -1}, {"score": 10 ** 12}, {"level": 0}, {"level": 10 ** 6},
                                 {"accuracy": 1.01}, {"duration_ms": -1}, {"game": "x"}, {"game": "<script>"},
                                 {"score": "beaucoup"}, {"score": 1.5}, {"played_at": "x" * 41}])
def test_local_rejects_wrong_shapes(client, bad):
    assert client.post("/api/brain/local", json={"sessions": [session("2026-11-02T10:00:00Z", **bad)]}).status_code == 422


def test_unknown_game_in_a_local_list_is_ignored(client):
    r = client.post("/api/brain/local", json={"sessions": [session("2026-11-02T10:00:00Z", game="inconnu")]})
    assert r.status_code == 200 and r.json()["temperature"] == 0


# ── Triche : score impossible pour la durée de la partie ──

def test_an_impossible_score_is_bounded_by_the_duration():
    """2,7 millions de points en 45 s : borné à 3 000 pts/s + 2 500 (deux fois le rythme d'un robot parfait)."""
    r = brain.validate("pareil", brain.MAX_SCORE, 1, 400, 99, 45_000)
    assert r["score"] == brain.score_cap(45_000) == 45 * 3000 + 2500
    assert brain.validate("pareil", 10 ** 8, 1, 400, 120, 1000)["score"] == 5500


def test_a_real_long_game_keeps_its_score():
    """Une vraie partie de 12 minutes à 120 000 points (très bon joueur) n'est pas touchée."""
    assert brain.validate("pareil", 120_000, 0.95, 500, 42, 12 * 60_000)["score"] == 120_000
    assert brain.score_cap(30 * 60_000) >= brain.MAX_SCORE


def test_the_sql_bound_is_the_same_as_the_server_bound():
    sql = " ".join((MIGRATIONS / "20261103100000_brain_anti_triche.sql").read_text(encoding="utf-8").split())
    per_ms = brain.SCORE_PER_SECOND_CAP // 1000
    assert f"g.max_score, dur * {per_ms} + {brain.SCORE_BONUS_CAP})" in sql
    assert "pg_advisory_xact_lock" in sql


# ── Arrondis : la Température du profil (Python) = celle du classement (base) ──

def test_temperature_rounds_each_game_like_the_database():
    """Bug : la base arrondit l'indice de CHAQUE partie (colonne idx) avant les moyennes ; Python faisait les moyennes
    sur les indices non arrondis. Indices bruts 1000,58 ×2 et 1000,19 ×2 : base 1001 °M, Python affichait 1000 °M."""
    at = "2026-11-02T10:00:00Z"
    rows = [session(at, score=s) for s in (22533, 22534, 22511, 22512)]
    db_like = brain.round_half_up(sum(brain.game_index("pareil", s, 10) for s in (22533, 22534, 22511, 22512)) / 4)
    assert db_like == 1001
    assert brain.profile(rows, now=NOW)["temperature"] == 1001
    assert brain_game.game_detail(rows, "pareil", now=NOW)["index"] == 1001


# ── Série 🔥 : minuit à Zurich, changement d'heure ──

def test_streak_uses_midnight_in_zurich_not_utc():
    """22:30 UTC le 1er novembre = 23:30 le 1er à Zurich ; 23:30 UTC = 00:30 le 2 (heure d'hiver, UTC+1) : 2 jours."""
    p = brain.profile([session("2026-11-01T22:30:00Z"), session("2026-11-01T23:30:00Z")], now=NOW)
    assert p["streak"] == {"current": 2, "best": 2}   # en UTC, ce serait 1 seul jour
    p = brain.profile([session("2026-11-01T23:30:00Z"), session("2026-11-02T22:59:00Z")], now=NOW)
    assert p["streak"]["current"] == 1   # même jour à Zurich (2 novembre), hier → série encore vivante


def test_streak_and_history_across_the_dst_change():
    """Nuit du 24 au 25 octobre 2026 : 03:00 → 02:00 ; une journée de 25 heures ne casse ni la série ni la courbe."""
    days = ["2026-10-24T21:30:00Z", "2026-10-25T22:30:00Z", "2026-10-26T22:30:00Z"]   # 23:30 à Zurich chaque soir
    now = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
    p = brain.profile([session(d) for d in days], now=now)
    assert p["streak"] == {"current": 3, "best": 3}
    assert [h["day"] for h in p["history"]] == ["2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27"]
    spring = brain.profile([session("2026-03-28T22:30:00Z"), session("2026-03-29T21:30:00Z")],
                           now=datetime(2026, 3, 30, 8, 0, tzinfo=timezone.utc))
    assert spring["streak"] == {"current": 2, "best": 2}   # 23:30 le 28, 23:30 le 29 (heure d'été)


# ── Analyse sur profils extrêmes ──

def test_analysis_on_extreme_profiles():
    at = "2026-11-02T10:00:00Z"
    robot = [session(at, game=g, score=brain.MAX_SCORE, level=99) for g in brain.CATALOG for _ in range(5)]
    zero = [session(at, game=g, score=0, level=1, avg_rt_ms=0, accuracy=0) for g in brain.CATALOG for _ in range(5)]
    one_domain = [session(at, score=s) for s in range(0, 300_000, 1000)]
    for rows in (robot, zero, one_domain, robot + zero):
        p = brain.profile(rows, now=NOW, party={"domains": {"vitesse": {"avg": 2000, "players": 3}}})
        assert 0 <= p["temperature"] <= brain.INDEX_MAX and p["insight"]
        assert 0 <= p["speed_vs_accuracy"]["speed"] <= 100


# ── Migrations et fichiers prod ──

def test_brain_migrations_are_replayable():
    for name in BRAIN_MIGRATIONS:
        sql = (MIGRATIONS / f"{name}.sql").read_text(encoding="utf-8").lower()
        assert not re.search(r"^\s*create (table|index) (?!if not exists)", sql, re.M), name
        for policy in re.findall(r'^\s*create policy ("[^"]+")', sql, re.M):
            assert f"drop policy if exists {policy}" in sql, (name, policy)
        assert not re.search(r"^\s*create trigger", sql, re.M) or "drop trigger if exists" in sql, name
        assert not re.search(r"^\s*create function", sql, re.M), name
        assert "drop table" not in sql and "drop column" not in sql, name


def test_prod_apply_contains_every_brain_migration_in_order():
    positions = []
    for name in BRAIN_MIGRATIONS:
        body = (MIGRATIONS / f"{name}.sql").read_text(encoding="utf-8").strip()
        assert body in PROD_APPLY, name
        positions.append(PROD_APPLY.index(body))
        version = name.split("_", 1)[0]
        assert f"values ('{version}'" in PROD_APPLY and f"version = '{version}'" in PROD_ROLLBACK
    assert positions == sorted(positions)
    assert PROD_APPLY.strip().startswith("--") and PROD_APPLY.strip().endswith("commit;")


# ── Base indisponible : 503 (le téléphone garde la partie), pas 400 (le téléphone l'abandonne) ──

def _down_base(status: int | None):
    """Faux Supabase : le jeton est bon, mais les fonctions brain_* répondent `status` (None = délai dépassé)."""
    import httpx

    def handler(request: httpx.Request):
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "9a8b7c6d-1111-4222-8333-444455556666"})
        if status is None:
            raise httpx.ReadTimeout("délai", request=request)
        return httpx.Response(status, json={"message": "limit: Assez de parties pour aujourd'hui. Reviens demain !"})
    return handler


@pytest.mark.parametrize("status", [500, 502, 503, None])
def test_a_database_outage_is_not_a_final_refusal(monkeypatch, status):
    """Bug : une panne passagère de la base (5xx, délai dépassé) répondait 400 ; core.js (syncLocal) traite 400 comme un
    refus définitif et efface la partie jouée hors connexion. Il faut 503 : la partie reste sur le téléphone."""
    import httpx
    from app import accounts as accounts_mod
    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(_down_base(status))))
    monkeypatch.setattr(main, "accounts", acc)
    c = TestClient(main.app)
    tok = "t" * 40
    body = {"token": tok, "game": "pareil", "score": 1000, "accuracy": 0.9, "avg_rt_ms": 600, "level": 1, "duration_ms": 9000}
    assert c.post("/api/brain/result", json=body).status_code == 503
    assert c.post("/api/brain/me", json={"token": tok}).status_code == 503
    assert c.post("/api/brain/compare", json={"token": tok}).status_code == 503


def test_a_database_refusal_stays_a_400_with_its_message(monkeypatch):
    import httpx
    from app import accounts as accounts_mod
    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(_down_base(400))))
    monkeypatch.setattr(main, "accounts", acc)
    body = {"token": "t" * 40, "game": "pareil", "score": 1000, "accuracy": 0.9, "avg_rt_ms": 600, "level": 1,
            "duration_ms": 9000}
    r = TestClient(main.app).post("/api/brain/result", json=body)
    assert r.status_code == 400 and r.json()["detail"] == "Assez de parties pour aujourd'hui. Reviens demain !"


def test_perf_migration_keeps_the_signatures_and_the_rollback_drops_the_new_function():
    """20261103101000 : mêmes fonctions publiques (même signature), une nouvelle fonction privée, retirée au retour arrière."""
    sql = (MIGRATIONS / "20261103101000_brain_perf.sql").read_text(encoding="utf-8")
    for sig in ("private.brain_players() returns table (user_id uuid, temperature integer)",
                "private.brain_party_domains(p_except uuid) returns jsonb", "public.brain_my_stats() returns jsonb",
                "public.brain_compare(p_target uuid default null) returns jsonb", "public.brain_game_percentile(p_game text) returns jsonb"):
        assert f"create or replace function {sig}" in sql, sig
    assert "from public, anon, authenticated" in sql and "private.brain_domain_scores()" in PROD_ROLLBACK


def test_an_expired_token_at_the_database_is_a_401(monkeypatch):
    """Jeton expiré entre la vérification (gardée 5 min) et l'appel : 401 (le téléphone garde la partie et se
    reconnecte), pas 400 (partie abandonnée)."""
    import httpx
    from app import accounts as accounts_mod
    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(_down_base(401))))
    monkeypatch.setattr(main, "accounts", acc)
    body = {"token": "t" * 40, "game": "pareil", "score": 1000, "accuracy": 0.9, "avg_rt_ms": 600, "level": 1,
            "duration_ms": 9000}
    assert TestClient(main.app).post("/api/brain/result", json=body).status_code == 401


def test_the_synced_played_at_sent_by_the_phone_is_accepted_and_ignored(monkeypatch):
    """core.js renvoie désormais played_at avec les parties jouées hors connexion : accepté (pas de 422), mais la date
    retenue reste celle de l'enregistrement (les limites par jour / 10 min de la base comptent sur cette date)."""
    import httpx
    from app import accounts as accounts_mod
    sent = []

    def handler(request: httpx.Request):
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "9a8b7c6d-1111-4222-8333-444455556666"})
        sent.append(__import__("json").loads(request.content))
        return httpx.Response(200, json={"index": 500, "best": 1000, "record": True, "plays": 1})
    monkeypatch.setattr(main, "accounts", accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler))))
    body = {"token": "t" * 40, "game": "pareil", "score": 1000, "accuracy": 0.9, "avg_rt_ms": 600, "level": 1,
            "duration_ms": 9000, "played_at": "2026-10-01T10:00:00.000Z"}
    assert TestClient(main.app).post("/api/brain/result", json=body).status_code == 200
    assert "p_played_at" not in sent[-1] and "played_at" not in sent[-1]
