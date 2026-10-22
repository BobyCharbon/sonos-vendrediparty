"""Purify Test : logique du module (score, phases, classement, alcool, persistance)."""
import pytest

from app import purity


def make_game(players):
    # players : liste de (gid, pid, name). gid « acct-… » = compte connecté.
    g = {"type": "purity", "phase": "lobby", "options": {},
         "players": [{"id": gid, "pid": pid, "name": name} for gid, pid, name in players]}
    purity.init(g)
    return g


def answer_all(g, gid, done_indices):
    if g["phase"] == "lobby":
        purity.start(g)
    for i in done_indices:
        purity.answer(g, gid, i, True)
    purity.submit(g, gid)


def test_score_is_percentage_of_not_done():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    # 10 choses « faites » sur TOTAL → score = round(100*(TOTAL-10)/TOTAL)
    for i in range(10):
        purity.answer(g, "acct-a", i, True)
    purity.submit(g, "acct-a")
    purity.reveal(g)
    expected = round(100 * (purity.TOTAL - 10) / purity.TOTAL)
    assert g["purity"]["scores"]["acct-a"] == expected
    assert purity.view(g, "acct-a")["me_score"] == expected


def test_full_pure_and_full_impure_bounds():
    g = make_game([("acct-pure", "p1", "Pur"), ("acct-naughty", "p2", "Sulfureux")])
    purity.start(g)
    purity.submit(g, "acct-pure")  # n'a rien coché → 100 %
    for i in range(purity.TOTAL):
        purity.answer(g, "acct-naughty", i, True)
    purity.submit(g, "acct-naughty")
    purity.reveal(g)
    assert g["purity"]["scores"]["acct-pure"] == 100
    assert g["purity"]["scores"]["acct-naughty"] == 0


def test_ranking_purest_first():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob"), ("acct-c", "p3", "Chloé")])
    purity.start(g)
    answer_all(g, "acct-a", range(5))    # peu de choses faites → plus pur
    answer_all(g, "acct-b", range(40))   # beaucoup → plus sulfureux
    answer_all(g, "acct-c", range(20))
    purity.reveal(g)
    order = [r["name"] for r in purity.ranking(g)]
    assert order == ["Alice", "Chloé", "Bob"]


def test_answer_toggle_off_decrements():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    purity.answer(g, "acct-a", 3, True)
    purity.answer(g, "acct-a", 3, False)  # on décoche
    purity.submit(g, "acct-a")
    purity.reveal(g)
    assert g["purity"]["scores"]["acct-a"] == 100


def test_cannot_answer_after_submit():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    purity.submit(g, "acct-a")
    with pytest.raises(purity.PurityError):
        purity.answer(g, "acct-a", 0, True)


def test_non_participant_cannot_answer():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    with pytest.raises(purity.PurityError):
        purity.answer(g, "acct-intrus", 0, True)


def test_answer_out_of_range_rejected():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    for bad in (-1, purity.TOTAL, purity.TOTAL + 50):
        with pytest.raises(purity.PurityError):
            purity.answer(g, "acct-a", bad, True)


def test_reveal_requires_a_submission():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    with pytest.raises(purity.PurityError):
        purity.reveal(g)


def test_gorgees_only_with_alcohol_and_hits_lowest():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob")])
    purity.configure(g, {"alcohol": True, "sips": 3})
    purity.start(g)
    answer_all(g, "acct-a", range(2))    # pur
    answer_all(g, "acct-b", range(30))   # sulfureux → boit
    purity.reveal(g)
    gg = purity.gorgees(g)
    assert [r["name"] for r in gg] == ["Bob"] and gg[0]["sips"] == 3


def test_no_gorgees_without_alcohol():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob")])
    purity.configure(g, {"alcohol": False, "sips": 3})
    purity.start(g)
    answer_all(g, "acct-a", range(2))
    answer_all(g, "acct-b", range(30))
    purity.reveal(g)
    assert purity.gorgees(g) == []


def test_general_leaderboard_persists_only_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(purity, "STATS_PATH", tmp_path / "purity_stats.json")
    # Un compte (acct-) et un invité anonyme : seul le compte compte au classement général.
    g = make_game([("acct-a", "p1", "Alice"), ("guest-anon-0001", "p2", "Anon")])
    purity.start(g)
    answer_all(g, "acct-a", range(10))
    answer_all(g, "guest-anon-0001", range(10))
    purity.reveal(g)
    lb = purity.leaderboard()
    names = [r["name"] for r in lb["rows"]]
    assert names == ["Alice"] and lb["total"] == 1


def test_leaderboard_keeps_best_score(tmp_path, monkeypatch):
    monkeypatch.setattr(purity, "STATS_PATH", tmp_path / "purity_stats.json")
    for done in (30, 5, 20):  # meilleur = le moins de choses faites (done=5 → plus pur)
        g = make_game([("acct-a", "p1", "Alice")])
        purity.start(g)
        answer_all(g, "acct-a", range(done))
        purity.reveal(g)
    rows = purity.leaderboard()["rows"]
    assert rows[0]["plays"] == 3
    assert rows[0]["best"] == round(100 * (purity.TOTAL - 5) / purity.TOTAL)


def test_view_hides_individual_answers_at_results():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob")])
    purity.start(g)
    answer_all(g, "acct-a", range(3))
    answer_all(g, "acct-b", range(9))
    purity.reveal(g)
    v = purity.view(g, "acct-a")
    assert "ranking" in v and "mine" not in v  # au classement, pas de réponses individuelles
    assert all(set(r.keys()) == {"pid", "name", "score"} for r in v["ranking"])
