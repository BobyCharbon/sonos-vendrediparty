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


def test_score_is_percentage_of_done():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    # 10 choses « faites » sur TOTAL → impureté = round(100*10/TOTAL)
    for i in range(10):
        purity.answer(g, "acct-a", i, True)
    purity.submit(g, "acct-a")
    purity.reveal(g)
    expected = round(100 * 10 / purity.TOTAL)
    assert g["purity"]["scores"]["acct-a"] == expected
    assert purity.view(g, "acct-a")["me_score"] == expected


def test_full_pure_and_full_impure_bounds():
    g = make_game([("acct-pure", "p1", "Pur"), ("acct-naughty", "p2", "Sulfureux")])
    purity.start(g)
    purity.submit(g, "acct-pure")  # n'a rien coché → 0 % d'impureté
    for i in range(purity.TOTAL):
        purity.answer(g, "acct-naughty", i, True)
    purity.submit(g, "acct-naughty")
    purity.reveal(g)
    assert g["purity"]["scores"]["acct-pure"] == 0
    assert g["purity"]["scores"]["acct-naughty"] == 100


def test_ranking_most_impure_first():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob"), ("acct-c", "p3", "Chloé")])
    purity.start(g)
    answer_all(g, "acct-a", range(5))    # peu de choses faites → plus sage
    answer_all(g, "acct-b", range(40))   # beaucoup → plus sulfureux, en tête
    answer_all(g, "acct-c", range(20))
    purity.reveal(g)
    order = [r["name"] for r in purity.ranking(g)]
    assert order == ["Bob", "Chloé", "Alice"]


def test_answer_toggle_off_decrements():
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    purity.answer(g, "acct-a", 3, True)
    purity.answer(g, "acct-a", 3, False)  # on décoche
    purity.submit(g, "acct-a")
    purity.reveal(g)
    assert g["purity"]["scores"]["acct-a"] == 0


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


def test_gorgees_only_with_alcohol_and_hit_the_most_impure():
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


def test_leaderboard_keeps_the_impurity_record_and_ranks_it_first(tmp_path, monkeypatch):
    monkeypatch.setattr(purity, "STATS_PATH", tmp_path / "purity_stats.json")
    for done in (30, 5, 20):  # record = le plus de choses faites (done=30)
        g = make_game([("acct-a", "p1", "Alice")])
        purity.start(g)
        answer_all(g, "acct-a", range(done))
        purity.reveal(g)
    g = make_game([("acct-b", "p2", "Bob")])
    purity.start(g)
    answer_all(g, "acct-b", range(10))
    purity.reveal(g)
    rows = purity.leaderboard()["rows"]
    assert [r["name"] for r in rows] == ["Alice", "Bob"]
    assert rows[0]["plays"] == 3
    assert rows[0]["best"] == round(100 * 30 / purity.TOTAL)
    assert rows[0]["last"] == round(100 * 20 / purity.TOTAL)


def test_profile_keeps_the_last_test_by_category_for_its_owner_only(tmp_path, monkeypatch):
    monkeypatch.setattr(purity, "STATS_PATH", tmp_path / "purity_stats.json")
    first_drug = next(i for i, (c, _) in enumerate(purity.QUESTIONS) if c == "drugs")
    for done in ([0, 1, 2], [0, first_drug]):
        g = make_game([("acct-a", "p1", "Alice")])
        purity.start(g)
        answer_all(g, "acct-a", done)
        purity.reveal(g)
    me = purity.profile("acct-a")
    assert me["plays"] == 2 and me["last"] == 2 and me["best"] == 3 and me["last_at"] > 0
    cats = {r["id"]: r for r in me["categories"]}
    assert [r["id"] for r in me["categories"]] == list(purity.CATEGORIES)
    assert (cats["drugs"]["yes"], cats["drugs"]["total"], cats["drugs"]["pct"]) == (1, 10, 10)
    assert cats["relations"]["yes"] == 1 and cats["rules"]["pct"] == 0
    assert "categories" not in str(purity.leaderboard())  # le profil par catégorie ne sort jamais du classement public
    assert purity.profile("acct-inconnu") == {"plays": 0}


def test_legacy_purity_stats_are_converted_to_impurity(tmp_path, monkeypatch):
    path = tmp_path / "purity_stats.json"
    monkeypatch.setattr(purity, "STATS_PATH", path)
    # Ancien format : scores de pureté (meilleur = le plus pur).
    path.write_text('{"acct-a": {"name": "Alice", "plays": 2, "best": 90, "last": 70}}')
    row = purity.leaderboard()["rows"][0]
    assert (row["best"], row["last"], row["plays"]) == (30, 30, 2)
    assert purity.profile("acct-a")["categories"] == []  # pas de détail par catégorie avant la conversion


def test_view_hides_individual_answers_at_results():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob")])
    purity.start(g)
    answer_all(g, "acct-a", range(3))
    answer_all(g, "acct-b", range(9))
    purity.reveal(g)
    v = purity.view(g, "acct-a")
    assert "ranking" in v and "mine" not in v  # au classement, pas de réponses individuelles
    assert all(set(r.keys()) == {"pid", "name", "score"} for r in v["ranking"])


def test_questions_are_grouped_by_category_in_display_order():
    order = list(purity.CATEGORIES)
    cats = [c for c, _ in purity.QUESTIONS]
    assert purity.TOTAL == 100 and set(cats) == set(order)
    assert cats == sorted(cats, key=order.index)  # posées catégorie par catégorie
    g = make_game([("acct-a", "p1", "Alice")])
    purity.start(g)
    v = purity.view(g, "acct-a")
    assert [c["id"] for c in v["categories"]] == order
    assert v["questions"][0] == {"i": 0, "text": purity.QUESTIONS[0][1], "cat": "relations"}


def test_category_breakdown_is_shown_only_to_its_owner():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob")])
    purity.start(g)
    first_drug = next(i for i, (c, _) in enumerate(purity.QUESTIONS) if c == "drugs")
    answer_all(g, "acct-a", [0, 1, first_drug])
    answer_all(g, "acct-b", [])
    purity.reveal(g)
    mine = {r["id"]: r for r in purity.view(g, "acct-a")["me_categories"]}
    assert (mine["relations"]["yes"], mine["relations"]["total"]) == (2, 22)
    assert (mine["drugs"]["yes"], mine["drugs"]["total"], mine["drugs"]["pct"]) == (1, 10, 10)
    assert mine["rules"]["pct"] == 0 and mine["drugs"]["label"] == "Drogues"
    assert all(r["pct"] == 0 for r in purity.view(g, "acct-b")["me_categories"])
    assert "me_categories" not in purity.view(g, "acct-intrus")  # un spectateur n'a pas de profil


def test_every_question_is_unique():
    texts = [t.casefold() for _, t in purity.QUESTIONS]
    assert len(set(texts)) == len(texts) == 100


def test_no_question_depends_on_anatomy_so_100_percent_is_reachable():
    texts = " ".join(t.casefold() for _, t in purity.QUESTIONS)
    for word in ("fellation", "cunnilingus", "pendant les règles"):
        assert word not in texts
    assert "as-tu déjà reçu du sexe oral ?" in texts and "as-tu déjà pratiqué le sexe oral sur quelqu’un ?" in texts


def test_nobody_drinks_or_is_called_naughty_when_everyone_is_pure():
    g = make_game([("acct-a", "p1", "Alice"), ("acct-b", "p2", "Bob")])
    purity.configure(g, {"alcohol": True, "sips": 3})
    purity.start(g)
    answer_all(g, "acct-a", [])
    answer_all(g, "acct-b", [])
    purity.reveal(g)
    assert purity.gorgees(g) == []
    assert purity.summary_facts(g) == ["Que des anges : 0 % d'impureté pour tout le monde"]


def test_profile_tolerates_an_incomplete_row(tmp_path, monkeypatch):
    path = tmp_path / "purity_stats.json"
    monkeypatch.setattr(purity, "STATS_PATH", path)
    path.write_text('{"acct-a": {"v": 2, "name": "Alice"}}')
    assert purity.profile("acct-a") == {"name": "Alice", "plays": 0, "best": 0, "last": 0, "last_at": 0, "categories": []}
