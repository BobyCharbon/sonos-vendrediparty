"""« Le Masque » : réponses écrites en secret, mélangées sans prénom, devinettes, masque levé ou gardé (réglé une fois
pour toute la table), votes dévoilés, points, retrait d'une réponse par l'animateur, départs en pleine partie, et
actions vérifiées par le serveur."""
import json
import random

import pytest
from fastapi.testclient import TestClient

from app import games, main, masque
from app.masque_cards import MASQUE_CARDS


def table(n=4, seed=3, mask=None):
    g = games.new_game("masque", host="h", name="Léa")
    for i in range(1, n):
        games.join(g, f"p{i}", f"Ami{i}")
    if mask:
        masque.configure(g, {"mask": mask})
    games.start(g, random.Random(seed))
    return g


def pid(g, gid):
    return next(p["pid"] for p in g["players"] if p["id"] == gid)


def everyone_writes(g):
    for p in g["players"]:
        masque.write(g, p["id"], f"La réponse de {p['name']}")


def slot_of(g, gid):
    return next(i for i, s in enumerate(g["masque"]["slots"]) if s["gid"] == gid)


def test_a_question_is_dealt_and_answers_stay_secret_until_everyone_has_written():
    g = table()
    assert g["phase"] == "write" and g["masque"]["q"]["text"]
    masque.write(g, "h", "Mon secret")
    v = games.view(g, "p1")["masque"]
    assert "Mon secret" not in json.dumps(v)  # personne ne lit la réponse d'un autre avant la devinette
    assert games.view(g, "h")["masque"]["mine"] == "Mon secret"
    assert [w["done"] for w in v["wrote"]] == [True, False, False, False]
    for p in g["players"][1:]:
        masque.write(g, p["id"], "x" * 500)  # coupée à la longueur maximale
    assert g["phase"] == "guess" and all(len(s["text"]) <= masque.MAX_ANSWER for s in g["masque"]["slots"])


def test_guessing_shows_the_others_answers_without_authors_and_never_points_at_ones_own():
    g = table()
    everyone_writes(g)
    v = games.view(g, "p1")["masque"]
    dumped = json.dumps(v)
    assert all(f'"{gid}"' not in dumped for gid in ("h", "p2", "p3"))  # aucun identifiant secret ne sort
    # Avis du 04.11 : sa propre réponse n'apparaît pas (ni entourée, ni marquée) : un voisin ne peut pas la repérer.
    assert "La réponse de Ami1" not in dumped and "mine" not in dumped
    assert len(v["slots"]) == 3 and slot_of(g, "p1") not in [s["i"] for s in v["slots"]]
    assert {a["name"] for a in v["authors"]} == {"Léa", "Ami2", "Ami3"}  # pas soi-même
    # Tous les joueurs voient autant de réponses ; un spectateur (la télé) les voit toutes, sans auteur.
    assert {len(games.view(g, p["id"])["masque"]["slots"]) for p in g["players"]} == {3}
    tv = games.view(g, "")["masque"]
    assert len(tv["slots"]) == 4 and all(set(s) == {"i", "text", "hidden"} for s in tv["slots"])


def test_masks_up_reveal_every_author_who_voted_for_whom_and_points_go_to_finders():
    g = table()
    everyone_writes(g)
    lea, a1 = slot_of(g, "h"), slot_of(g, "p1")
    # Ami2 trouve Léa et Ami1, Ami3 se trompe sur Léa (il pensait Ami2) ; un ancien client envoie encore « unmask ».
    masque.guess(g, "h", {}, unmask=False)
    masque.guess(g, "p1", {})
    masque.guess(g, "p2", {str(lea): pid(g, "h"), str(a1): pid(g, "p1")})
    masque.guess(g, "p3", {str(lea): pid(g, "p2")})
    assert g["phase"] == "reveal"
    rows = g["masque"]["result"]
    assert all(r["open"] for r in rows)  # le masque est celui de la table, pas un choix de chacun
    assert rows[lea]["author"] == "Léa" and rows[lea]["found"] == ["Ami2"]
    assert rows[lea]["votes"] == [{"voter": "Ami2", "guess": "Léa", "right": True},
                                  {"voter": "Ami3", "guess": "Ami2", "right": False}]  # les justes d'abord
    assert rows[a1]["author"] == "Ami1" and rows[a1]["votes"] == [{"voter": "Ami2", "guess": "Ami1", "right": True}]
    assert rows[slot_of(g, "p2")]["votes"] == []
    assert g["masque"]["scores"] == {"p2": 2}  # 1 par auteur trouvé, plus de point pour « lever son masque »
    marks = games.view(g, "p3")["masque"]["my_marks"]
    assert marks[lea] == "wrong" and marks.count(None) == 3  # rouge sur sa devinette fausse, rien ailleurs
    v = games.view(g, "p2")["masque"]
    assert v["my_marks"][lea] == v["my_marks"][a1] == "right"
    assert all(set(r) <= {"text", "hidden", "open", "author", "found", "votes"} for r in v["result"])
    assert all(f'"{gid}"' not in json.dumps(v) for gid in ("h", "p1", "p3"))


def test_masks_kept_never_tell_who_wrote_what_nor_who_voted():
    g = table(mask="closed")
    everyone_writes(g)
    lea = slot_of(g, "h")
    masque.guess(g, "h", {}, unmask=True)  # un ancien client qui « lève son masque » n'y change rien
    masque.guess(g, "p1", {str(lea): pid(g, "h")})
    masque.guess(g, "p2", {str(lea): pid(g, "h")})
    masque.guess(g, "p3", {str(lea): pid(g, "p1")})
    for viewer in ("h", "p1", "p2", "p3", ""):
        v = games.view(g, viewer)["masque"]
        row = v["result"][lea]
        assert row["open"] is False and row["author"] is None and row["found"] is None
        assert row["votes"] == [{"guess": "Léa", "n": 2}, {"guess": "Ami1", "n": 1}]  # à qui on a pensé, sans votant
        assert set(v["my_marks"]) == {None}  # ni juste ni faux : rien ne se confirme par élimination
        assert all(set(x) == {"guess", "n"} for r in v["result"] for x in r["votes"])  # jamais le prénom d'un votant
    assert g["masque"]["scores"] == {}
    games.next_step(g, random.Random(1))
    assert games.view(g, "p1")["masque"]["mask"] == "closed"  # toute la partie


def test_the_mask_is_one_setting_for_the_whole_table_chosen_before_the_game():
    g = games.new_game("masque", host="h", name="Léa")
    assert games.view(g, "h")["masque"]["mask"] == "open"  # par défaut : les masques tombent
    for bad in ({"mask": "chacun"}, {"mask": True}, {"mask": ["open"]}):
        with pytest.raises(masque.MasqueError):
            masque.configure(g, bad)
    masque.configure(g, {"mask": "closed"})
    assert g["masque"]["mask"] == "closed"
    games.join(g, "p1", "A")
    games.join(g, "p2", "B")
    games.start(g, random.Random(1))
    with pytest.raises(masque.MasqueError):
        masque.configure(g, {"mask": "open"})  # pas en pleine partie
    del g["masque"]["mask"]  # partie créée avant ce réglage
    assert masque.view(g, "h", True)["mask"] == "open"


def test_cheating_guesses_are_refused():
    g = table()
    everyone_writes(g)
    mine, other = slot_of(g, "p1"), slot_of(g, "p2")
    for picks in ({str(mine): pid(g, "h")},  # sa propre réponse
                  {str(other): pid(g, "p1")},  # soi-même comme auteur
                  {str(other): pid(g, "h"), str(slot_of(g, "p3")): pid(g, "h")},  # un prénom pour deux réponses
                  {"99": pid(g, "h")}, "pas un dict"):
        with pytest.raises(masque.MasqueError):
            masque.guess(g, "p1", picks)
    masque.guess(g, "p1", {})
    with pytest.raises(masque.MasqueError, match="déjà"):
        masque.guess(g, "p1", {})


def test_the_host_can_remove_an_answer_and_reveal_without_waiting():
    g = table()
    everyone_writes(g)
    bad = slot_of(g, "p3")
    masque.hide(g, bad)
    assert next(s for s in games.view(g, "p1")["masque"]["slots"] if s["i"] == bad)["hidden"]
    with pytest.raises(masque.MasqueError, match="Personne"):
        masque.reveal(g)
    masque.guess(g, "p1", {str(bad): pid(g, "p3")})  # choix sur une réponse retirée : ignoré, pas bloquant
    assert g["masque"]["guesses"]["p1"] == {}
    masque.reveal(g)
    assert g["masque"]["result"][bad] == {"text": None, "hidden": True}


def test_rounds_follow_until_the_chosen_count_then_a_summary():
    g = games.new_game("masque", host="h", name="Léa")
    for i in range(1, 3):
        games.join(g, f"p{i}", f"Ami{i}")
    masque.configure(g, {"count": 5, "cats": ["toi"], "levels": ["leger"]})
    games.start(g, random.Random(1))
    seen = set()
    for _ in range(5):
        seen.add(g["masque"]["q"]["text"])
        everyone_writes(g)
        a1 = slot_of(g, "p1")
        masque.guess(g, "h", {str(a1): pid(g, "p1")})  # Léa trouve Ami1 à chaque question
        for p in g["players"][1:]:
            masque.guess(g, p["id"], {})
        games.next_step(g, random.Random(2))
    assert g["phase"] == "end" and len(seen) == 5  # jamais deux fois la même question
    s = games.view(g, "h")["masque"]["summary"]
    assert s["questions"] == 5 and s["sharp"] == ["Léa"] and set(s["mystery"]) == {"Léa", "Ami2"} and "open" not in s
    assert s["ranking"][0] == {"name": "Léa", "pid": pid(g, "h"), "score": 5}
    assert any("perspicace" in f for f in masque.summary_facts(g))


def test_settings_are_checked_and_only_change_between_games():
    g = games.new_game("masque", host="h", name="Léa")
    for bad in ({"cats": []}, {"cats": ["nope"]}, {"levels": []}, {"count": 7}):
        with pytest.raises(masque.MasqueError):
            masque.configure(g, bad)
    assert g["masque"]["levels"] == ["leger", "profond"]  # l'intime n'est jamais coché d'office
    games.join(g, "p1", "A")
    games.join(g, "p2", "B")
    games.start(g, random.Random(1))
    with pytest.raises(masque.MasqueError):
        masque.configure(g, {"count": 5})


def test_swap_only_before_anyone_answers_and_three_players_minimum():
    g = table()
    first = g["masque"]["q"]["text"]
    masque.swap(g, random.Random(9))
    assert g["masque"]["q"]["text"] != first and g["masque"]["n"] == 1
    masque.write(g, "h", "déjà")
    with pytest.raises(masque.MasqueError):
        masque.swap(g)
    small = games.new_game("masque", host="h", name="Léa")
    games.join(small, "p1", "A")
    with pytest.raises(games.GameError, match="3 joueurs"):
        games.start(small, random.Random(1))


def test_a_player_leaving_never_blocks_the_game():
    g = table(5)
    for p in g["players"][:4]:
        masque.write(g, p["id"], "ok")
    games.leave(g, "p4")  # le seul qui manquait s'en va : la devinette commence
    assert g["phase"] == "guess"
    for p in g["players"][:3]:
        masque.guess(g, p["id"], {})
    gone = slot_of(g, "p3")
    games.leave(g, "p3")  # le dernier qui devait choisir part : la révélation arrive
    row = g["masque"]["result"][gone]
    assert g["phase"] == "reveal" and not row["hidden"] and row["author"] == "Ami3"  # masques levés : son prénom figé
    games.leave(g, "p2")
    assert g["phase"] == "end"  # à deux, ce n'est plus un jeu


def test_every_card_is_well_formed():
    assert len(MASQUE_CARDS) == len({c[2] for c in MASQUE_CARDS})  # aucune question en double
    for cat, level, text in MASQUE_CARDS:
        assert cat in masque.CATS and level in masque.LEVELS and 5 < len(text) <= 160


def test_actions_are_checked_by_the_server():
    before = set(main.store.session.games)
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    ids = ["ms-host-00000001", "ms-phone-0000001", "ms-phone-0000002"]
    try:
        code = c.post("/api/games", json={"type": "masque", "guest_id": ids[0], "name": "Boby"}).json()["code"]
        for i, gid in enumerate(ids[1:]):
            c.post(f"/api/games/{code}", json={"guest_id": gid, "action": "join", "name": f"Ami{i}"})
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "msset", "settings": {"count": 5}}).status_code == 403
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "start"}).status_code == 200
        for gid in ids:
            r = c.post(f"/api/games/{code}", json={"guest_id": gid, "action": "mswrite", "guess": f"<b>{gid[-1]}</b> ma réponse"})
            assert r.status_code == 200
        v = r.json()["masque"]
        assert r.json()["phase"] == "guess"
        assert len(v["slots"]) == 2 and len(v["authors"]) == 2  # sa propre réponse n'est pas dans sa liste
        target = v["slots"][0]["i"]
        r = c.post(f"/api/games/{code}", json={"guest_id": ids[2], "action": "msguess",
                                               "settings": {"picks": {str(target): v["authors"][0]["pid"]}}})
        assert r.status_code == 200 and r.json()["masque"]["sent"]
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "msreveal"}).status_code == 403
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "msreveal"}).status_code == 200
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "dbvote", "amount": 1}).status_code == 400
        # « Signaler » (tout joueur, pas seulement l'animateur) : la réponse sort pour toute la table, l'admin le voit.
        g = main.store.session.games[code]
        other = next(i for i, sl in enumerate(g["masque"]["slots"]) if sl["gid"] == ids[2])
        r = c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "msreport", "amount": other})
        assert r.status_code == 200
        assert r.json()["masque"]["result"][other] == {"text": None, "hidden": True, "reported": True}
        entry = main.journal.read(limit=1)[0]
        assert entry["action"] == "game.report" and entry["details"]["text"] == "<b>2</b> ma réponse"
        assert entry["details"]["author_id"] == ids[2]
    finally:
        for k in set(main.store.session.games) - before:
            main.store.session.games.pop(k, None)
        main._game_creations.clear()


def test_malformed_settings_and_guesses_are_refused_cleanly():
    g = games.new_game("masque", host="h", name="Léa")
    for bad in ({"cats": [["toi"]]}, {"levels": [{"x": 1}]}, {"count": 5.0}, {"count": True}):
        with pytest.raises(masque.MasqueError):
            masque.configure(g, bad)
    g = table()
    everyone_writes(g)
    other = slot_of(g, "p2")
    for pick in (["x"], {"a": 1}, None):
        with pytest.raises(masque.MasqueError):
            masque.guess(g, "p1", {str(other): pick})


def test_invisible_answers_are_refused_and_hidden_texts_never_leave_the_server():
    g = table()
    with pytest.raises(masque.MasqueError):
        masque.write(g, "h", "​‍‮\x07 ")
    everyone_writes(g)
    bad = slot_of(g, "p3")
    masque.hide(g, bad)
    assert next(s for s in games.view(g, "p1")["masque"]["slots"] if s["i"] == bad)["text"] is None


def test_a_seat_is_never_taken_back_by_name_during_a_secret_game():
    g = table()
    assert main.reclaim_seat(g, "intrus-0000000001", "Ami1", "") == "intrus-0000000001"


def test_a_pick_made_impossible_never_blocks_sending_and_names_stay_put():
    # Retour des tests : le prénom choisi part (ou la réponse est retirée) → l'envoi était refusé, la partie figée.
    g = table(5)
    everyone_writes(g)
    target = slot_of(g, "p3")
    names_before = [a["name"] for a in games.view(g, "p1")["masque"]["authors"]]
    games.leave(g, "p3")
    assert [a["name"] for a in games.view(g, "p1")["masque"]["authors"]] == names_before  # rien ne trahit p3
    masque.hide(g, slot_of(g, "p4"))
    masque.guess(g, "p1", {str(target): next(a["pid"] for a in g["masque"]["authors"] if a["gid"] == "p3")})
    assert g["masque"]["sent"]["p1"]


def test_reshuffling_never_shows_the_same_question_twice_in_a_row():
    g = table()
    S = g["masque"]
    for seed in range(40):
        before = S["q"]["text"]
        S["used"] = list(masque.deck(S))  # paquet épuisé
        masque.swap(g, random.Random(seed))
        assert S["q"]["text"] != before


def test_answers_go_through_the_common_filter():
    """B3 (audit du 04.11) : la réponse s'affiche à toute la table et sur la TV ; filtre commun, liens et numéros refusés."""
    g = table()
    with pytest.raises(masque.MasqueError, match="refusée"):
        masque.write(g, "p1", "va voir www.exemple.com")
    with pytest.raises(masque.MasqueError, match="refusée"):
        masque.write(g, "p1", "appelle le 079 123 45 67")
    masque.write(g, "p1", "Mon premier concert, à 12 ans")
    assert masque.state(g)["answers"]["p1"] == "Mon premier concert, à 12 ans"


def test_a_player_reports_an_answer_while_guessing():
    g = table()
    everyone_writes(g)
    other = slot_of(g, "p2")
    reported = masque.report(g, "p1", other)
    assert reported == {"text": masque.state(g)["slots"][other]["text"], "author": "p2"}
    view = masque.view(g, "p1", False)
    assert next(s for s in view["slots"] if s["i"] == other) == {"i": other, "text": None, "hidden": True}
    assert masque.report(g, "p1", other) is None  # déjà retirée
    with pytest.raises(masque.MasqueError):
        masque.report(g, "p2", slot_of(g, "p2"))  # pas sa propre réponse
