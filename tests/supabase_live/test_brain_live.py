"""Méninges sur la VRAIE base de test (jamais la prod) : droits (RLS, anonyme, parties d'un autre), bornes anti-triche
de brain_record (score et niveau impossibles, rafale de parties, envois simultanés), cohérence Python ↔ base
(indice, Température, classement) et comparaison qui n'expose que des agrégats.

Comptes : Testeur 1 et Testeur 2 (numéros de test à code fixe). Leurs parties Méninges sont effacées avant et après
(outil supabase/tools/sbq.py, base de TEST seulement)."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from app import accounts as accounts_mod, brain
from tests.supabase_live.test_member_admin_live import GUESTS, KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
TYPICAL = brain.CATALOG["pareil"].median


def sql_test(query: str) -> list:
    """SQL sur la base de TEST (écriture permise : ménage des parties des comptes de test)."""
    out = subprocess.run(["python3", str(ROOT / "supabase/tools/sbq.py"), "test", "rw"], input=query,
                         capture_output=True, text=True, timeout=120, check=True).stdout
    return json.loads(out or "[]")


@pytest.fixture(scope="module")
def players():
    a, b = Session(GUESTS[0]), Session(GUESTS[1])
    wipe = f"delete from public.brain_sessions where user_id in ('{a.uid}', '{b.uid}');"
    sql_test(wipe)
    yield a, b
    sql_test(wipe)


def record(s: Session, game="pareil", score=TYPICAL, level=10, duration_ms=180_000, accuracy=0.9, rt=600):
    return s.rpc("brain_record", p_game=game, p_score=score, p_accuracy=accuracy, p_avg_rt_ms=rt,
                 p_level=level, p_duration_ms=duration_ms)


def test_a_normal_game_is_recorded_with_the_server_index(players):
    a, _ = players
    r = record(a, score=60000, level=20, duration_ms=300_000)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 60000 and body["level"] == 20
    assert body["index"] == brain.game_index("pareil", 60000, 20)


def test_an_impossible_score_is_bounded_by_the_duration(players):
    """2,7 millions de points en 45 s : impossible (≤ 1 500 pts/s pour un robot parfait) → borné, pas refusé."""
    a, _ = players
    r = record(a, game="motif", score=2_702_500, level=10, duration_ms=45_000)
    assert r.status_code == 200, r.text
    assert r.json()["score"] == brain.score_cap(45_000) == 45 * 3000 + 2500


def test_an_impossible_level_is_bounded_by_the_duration(players):
    """Niveau 99 en 2 s sans jamais avoir joué à ce jeu : au plus 1 niveau par seconde depuis le niveau 1."""
    a, _ = players
    r = record(a, game="encre", score=5000, level=99, duration_ms=2_000)
    assert r.status_code == 200, r.text
    assert r.json()["level"] == 3
    assert r.json()["index"] == brain.game_index("encre", 5000, 3)


def test_the_starting_tier_already_reached_is_allowed(players):
    """Départ au palier débloqué : après le niveau 37 (palier 8), une partie courte peut finir au niveau 36-40."""
    a, _ = players
    assert record(a, game="bascule", score=200_000, level=37, duration_ms=600_000).json()["level"] == 37
    r = record(a, game="bascule", score=9000, level=38, duration_ms=5_000)
    assert r.json()["level"] == 38   # départ niveau 36 (palier 8) + 5 s


def test_a_perfect_robot_keeps_the_ceiling(players):
    _, b = players
    r = record(b, game="gouttes", score=50_000_000, level=5000, duration_ms=4 * 3600 * 1000, accuracy=1, rt=150)
    assert r.status_code == 200, r.text
    assert r.json()["score"] == brain.MAX_SCORE and r.json()["level"] == brain.MAX_LEVEL


def test_bad_inputs_are_refused_by_the_database(players):
    a, _ = players
    assert record(a, game="inconnu").status_code == 400
    assert record(a, duration_ms=999).status_code == 400
    assert record(a, accuracy=1.5).status_code == 400
    assert record(a, accuracy=-0.1).status_code == 400
    assert record(a, score=-5, duration_ms=60_000).json()["score"] == 0   # borné à 0


def test_anonymous_and_direct_writes_are_refused(players):
    a, b = players
    key = KEY_FILE.read_text().strip()
    anon = {"apikey": key, "Content-Type": "application/json"}
    for fn, args in (("brain_record", {"p_game": "pareil", "p_score": 1, "p_accuracy": 1, "p_avg_rt_ms": 1,
                                        "p_level": 1, "p_duration_ms": 5000}),
                     ("brain_my_stats", {}), ("brain_compare", {}), ("brain_game_percentile", {"p_game": "pareil"})):
        r = httpx.post(f"{TEST_URL}/rest/v1/rpc/{fn}", headers=anon, json=args, timeout=30)
        assert r.status_code in (401, 403, 404), (fn, r.status_code, r.text)
    for fn in ("brain_index", "brain_profile", "brain_players", "brain_percentile", "brain_party_domains"):
        assert a.rpc(fn).status_code in (401, 403, 404), fn   # fonctions privées : jamais exposées
    row = {"user_id": a.uid, "game": "pareil", "domain": "vitesse", "score": 1, "idx": 2000, "level": 99, "duration_ms": 5000}
    r = httpx.post(f"{TEST_URL}/rest/v1/brain_sessions", headers=a.headers, json=row, timeout=30)
    assert r.status_code in (401, 403), r.text
    r = httpx.patch(f"{TEST_URL}/rest/v1/brain_sessions?user_id=eq.{a.uid}", headers=a.headers, json={"idx": 2000}, timeout=30)
    assert r.status_code in (401, 403) or r.json() == [], r.text
    r = httpx.patch(f"{TEST_URL}/rest/v1/brain_games?id=eq.pareil", headers=a.headers, json={"median": 1}, timeout=30)
    assert r.status_code in (401, 403) or r.json() == [], r.text


def test_nobody_reads_the_games_of_someone_else(players):
    a, b = players
    assert record(b, game="tresor", score=12345, level=7, duration_ms=120_000).status_code == 200
    assert a.get(f"brain_sessions?user_id=eq.{b.uid}").json() == []
    assert all(row["user_id"] == a.uid for row in a.get("brain_sessions?select=user_id").json())
    assert b.get("brain_sessions?select=user_id").json()


def test_compare_and_board_expose_only_aggregates(players):
    a, b = players
    r = a.rpc("brain_compare", p_target=b.uid).json()
    assert set(r) == {"board", "rank", "players", "percentile", "target"}
    for row in r["board"]:
        assert set(row) == {"id", "name", "temperature", "me"}
    assert set(r["target"]) == {"id", "name", "temperature", "domains", "games"}
    assert all(isinstance(v, int) for v in r["target"]["games"].values())
    stats = a.rpc("brain_my_stats").json()
    assert {s["game"] for s in stats["sessions"]} <= {"pareil", "motif", "encre", "bascule"}   # les siennes seulement


def test_python_and_database_agree_on_temperature_and_board(players):
    """Température affichée (Python, profil) = Température du classement (base), au degré près."""
    a, b = players
    for score in (22533, 22534, 22511, 22512):   # indices bruts en x,58 / x,60 / x,19 / x,21 : piège d'arrondi
        assert record(a, game="nuee", score=score, level=10, duration_ms=120_000).status_code == 200
    mine = brain.profile(a.rpc("brain_my_stats").json()["sessions"])
    board = {p["id"]: p["temperature"] for p in a.rpc("brain_compare").json()["board"]}
    assert mine["temperature"] == board[a.uid]
    theirs = brain.profile(b.rpc("brain_my_stats").json()["sessions"])
    assert theirs["temperature"] == board[b.uid]


def test_a_burst_of_games_is_capped_even_when_sent_at_once(players):
    """« 1 000 parties en une minute » : 70 envois simultanés → 60 au plus enregistrés en 10 minutes."""
    _, b = players
    sql_test(f"delete from public.brain_sessions where user_id = '{b.uid}';")
    with ThreadPoolExecutor(max_workers=14) as pool:
        codes = list(pool.map(lambda _: record(b, game="syllabes", score=1000, level=1, duration_ms=5000).status_code,
                              range(70)))
    assert codes.count(200) == 60 and codes.count(400) == 10, codes
    n = sql_test(f"select count(*)::int as n from public.brain_sessions where user_id = '{b.uid}';")[0]["n"]
    assert n == 60


def test_brain_store_through_the_python_layer(players, monkeypatch):
    a, b = players
    monkeypatch.setattr(accounts_mod, "SUPABASE_URL", TEST_URL)
    monkeypatch.setattr(accounts_mod, "SUPABASE_ANON_KEY", KEY_FILE.read_text().strip())
    store = brain.BrainStore(accounts_mod.Accounts(b"secret", httpx.Client(timeout=30)))
    token = a.headers["Authorization"].removeprefix("Bearer ")
    me = store.me(token)
    assert me["temperature"] > 0 and me["games"]["bascule"]["max_tier"] == 8
    cmp = store.compare(token, b.uid)
    assert cmp["target"]["id"] == b.uid and not cmp["target"]["self"]
    g = store.game(token, "pareil")
    assert g["plays"] >= 1 and (g["percentile"] is None or 0 <= g["percentile"] <= 100)


def test_simultaneous_requests_through_the_server(players, monkeypatch):
    """Le même compte envoie 12 parties et lit ses stats en même temps, à travers FastAPI : rien de perdu ni en double,
    « plays » renvoyé par chaque enregistrement est unique (verrou par compte)."""
    from fastapi.testclient import TestClient
    from app import main
    a, _ = players
    monkeypatch.setattr(accounts_mod, "SUPABASE_URL", TEST_URL)
    monkeypatch.setattr(accounts_mod, "SUPABASE_ANON_KEY", KEY_FILE.read_text().strip())
    monkeypatch.setattr(main, "accounts", accounts_mod.Accounts(b"secret", httpx.Client(timeout=30)))
    sql_test(f"delete from public.brain_sessions where user_id = '{a.uid}' and game = 'courant';")
    token = a.headers["Authorization"].removeprefix("Bearer ")
    c = TestClient(main.app)
    body = {"token": token, "game": "courant", "score": 20000, "accuracy": 0.9, "avg_rt_ms": 600, "level": 5,
            "duration_ms": 90_000}

    def work(i):
        if i % 3 == 2:
            return c.post("/api/brain/me", json={"token": token})
        return c.post("/api/brain/result", json={**body, "score": 20000 + i})

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(work, range(18)))
    assert all(r.status_code == 200 for r in replies), [r.text for r in replies if r.status_code != 200]
    plays = sorted(r.json()["plays"] for i, r in enumerate(replies) if i % 3 != 2)
    assert plays == list(range(1, 13))
    assert c.post("/api/brain/me", json={"token": token}).json()["games"]["courant"]["plays"] == 12
