"""Avis 6bad207324a3 : un invité qui joue et se connecte à son compte en même temps n'a plus deux profils.

La place de jeu est renommée pour de bon (app/seat_rename.py) dans chaque jeu : ces tests jouent chaque jeu jusqu'en
pleine manche, renomment, puis vérifient qu'il ne reste aucune trace de l'ancien identifiant et que chaque joueur
voit exactement la même partie qu'avant (le renommé sous son nouvel identifiant, les autres sans rien de neuf)."""
import copy
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import games, main, seat_rename

# Identifiants comme ceux que l'app génère (crypto.randomUUID) ; NEW : identifiant de compte.
A = "5f0c2d3e-1a2b-4c3d-9e8f-0a1b2c3d4e5f"
B = "7a1d3e4f-2b3c-4d5e-8f9a-1b2c3d4e5f60"
C = "9c2e4f5a-3c4d-4e6f-a0b1-2c3d4e5f6071"
D = "b3d5f6a7-4d5e-4f70-b1c2-3d4e5f607182"
NEW = "acct-" + "0123456789abcdef" * 2 + "01234567"
PHONES = {"A": A, "B": B, "C": C, "D": D}
NAMES = {"A": "Lulu", "B": "Léa", "C": "Tom", "D": "Zoé"}

# Chaque jeu joué jusqu'en pleine manche (coups refusés ignorés : le tour peut tomber sur un autre joueur).
SCRIPTS = {
    "undercover": [("A", "start"), ("A", "vote_start"), ("A", "vote", {"target": "@B"}), ("B", "vote", {"target": "@A"})],
    "whoof": [("A", "start"), ("A", "vote", {"target": "@B"}), ("B", "vote", {"target": "@A"})],
    "never": [("A", "start"), ("A", "vote", {"target": "yes"})],
    "likely": [("A", "start"), ("A", "lkvote", {"target": "@B"}), ("B", "lkvote", {"target": "@A"})],
    "debate": [("A", "dbpropose", {"guess": "Pizza ou burger ?"}), ("A", "start"), ("A", "dbvote", {"amount": 1})],
    "beerpong": [("A", "start")],
    "roulette": [("A", "names", {"names": ["Léa", "Tom"]}), ("A", "spin")],
    "blackjack": [("A", "start"), ("A", "bet", {"amount": 5}), ("B", "bet", {"amount": 5}), ("C", "bet", {"amount": 5}),
                  ("A", "hit"), ("B", "hit"), ("C", "hit")],
    "casino": [("A", "start"), ("A", "cbet", {"target": "red", "amount": 5}), ("A", "cready")],
    "divan": [("A", "start"), ("B", "dheart"), ("C", "dheart"), ("A", "dnext"), ("A", "dheart")],
    "tmc": [("A", "start"), ("A", "tanswer", {"guess": "Bleu"}), ("B", "tanswer", {"guess": "Bleu"}),
            ("C", "tanswer", {"guess": "Rouge"}), ("A", "treveal"), ("A", "tjudge", {"amount": 2}), ("A", "start")],
    "pyramid": [("A", "start"), ("A", "pans", {"target": "red"}), ("B", "pans", {"target": "red"}),
                ("C", "pans", {"target": "black"})],
    "biskit": [("A", "start"), ("A", "bdraw"), ("B", "bdraw"), ("C", "bdraw")],
    "quiz": [("A", "start"), ("A", "qans", {"amount": 0}), ("B", "qans", {"amount": 1})],
    "president": [("A", "start")],
    "neon": [("A", "start")],
    "island": [("A", "start")],
    "heist": [("A", "start")],
    "psy": [("A", "start"), ("A", "psyans", {"settings": {"q": 0, "a": 0}}), ("A", "psysub")],
    "masque": [("A", "start"), ("A", "mswrite", {"guess": "J'ai déjà mangé un insecte"}),
               ("B", "mswrite", {"guess": "J'ai peur des pigeons"}), ("C", "mswrite", {"guess": "Je chante sous la douche"}),
               ("D", "mswrite", {"guess": "Je dors avec une peluche"}), ("A", "msguess", {"settings": {"picks": {}, "unmask": True}})],
    "reflet": [("A", "start")] + [(x, "rfpick", {"settings": {"i": 0, "bet": 1}}) for x in "ABCD"]
              + [(x, "rfvote", {"done": True}) for x in "ABCD"],
    "room": [("A", "rvote", {"target": "quiz"}), ("A", "launch", {"settings": {"type": "quiz"}})],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_game_creations", {})
    monkeypatch.setattr(main.store.session, "games", {})
    with TestClient(main.app) as c:
        yield c


def play(c, kind: str) -> str:
    code = c.post("/api/games", json={"type": kind, "guest_id": A, "name": NAMES["A"]}).json()["code"]
    for who in "BCD":
        c.post(f"/api/games/{code}", json={"guest_id": PHONES[who], "action": "join", "name": NAMES[who]})
    for step in SCRIPTS[kind]:
        who, action, extra = (*step, {})[:3]
        g = main.store.session.games[code]
        body = {k: (games.player(g, PHONES[v[1:]])["pid"] if isinstance(v, str) and v.startswith("@") else v)
                for k, v in extra.items()}
        c.post(f"/api/games/{code}", json={"guest_id": PHONES[who], "action": action, **body})
    return code


def same_view(after: dict, before: dict) -> bool:
    """Vues identiques. Tu me connais ? : un duo d'amis s'affiche dans l'ordre (secret) des identifiants, le seul
    détail qui peut changer (qui des deux est nommé en premier)."""
    def norm(v):
        duos = (v.get("tmc") or {}).get("duos")
        if duos:
            v = copy.deepcopy(v)
            for d in v["tmc"]["duos"]:
                d["a"], d["b"] = sorted((d["a"], d["b"]), key=lambda x: x["pid"])
            v["tmc"]["duos"].sort(key=lambda d: (d["a"]["pid"], d["b"]["pid"]))
        return v
    return norm(after) == norm(before)


def without_aliases(g: dict) -> str:
    return json.dumps({k: v for k, v in g.items() if k != "aliases"}, ensure_ascii=False)


@pytest.mark.parametrize("kind", [k for k in games.GAMES if k != "purity"])
def test_every_game_renames_the_seat_everywhere_and_shows_the_same_game(client, monkeypatch, kind):
    code = play(client, kind)
    g = main.store.session.games[code]
    assert A in without_aliases(g)
    before = copy.deepcopy(g)
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now)  # vues comparées au même instant
    assert games.rename_player(g, A, NEW)
    assert A not in without_aliases(g), f"{kind} : identifiant d'invité resté dans l'état"
    assert g["aliases"][A] == NEW and games.player(g, NEW)["pid"] == games.player(before, A)["pid"]
    assert same_view(games.view(g, NEW), games.view(before, A))  # mêmes points, rôle, cartes, réponses secrètes
    for other in (B, C, D):
        assert same_view(games.view(g, other), games.view(before, other))  # rien de neuf (ni l'identifiant du compte) chez les autres
    assert NEW not in json.dumps(games.view(g, B))


def test_purify_seat_is_renamed_with_its_private_answers():
    from app import purity
    g = games.new_game("purity", A, "Lulu", code="4242")
    games.join(g, B, "Léa")
    games.start(g)
    purity.answer(g, A, 0, True)
    purity.submit(g, A)
    before = copy.deepcopy(g)
    assert games.rename_player(g, A, NEW)
    assert A not in without_aliases(g)
    assert g["purity"]["answers"][NEW] == before["purity"]["answers"][A] and g["purity"]["submitted"][NEW]


def test_rename_refuses_ids_that_could_mean_something_else():
    g = games.new_game("undercover", "undercover", "Lulu", code="4243")  # identifiant choisi égal au type du jeu
    games.join(g, B, "Léa")
    assert not games.rename_player(g, "undercover", NEW) and g["type"] == "undercover"
    assert not seat_rename.can_rename(g, "acct-" + "1" * 40, NEW)  # une place de compte ne change jamais de compte
    g2 = games.new_game("undercover", A, "Lulu", code="4244")
    games.join(g2, NEW, "Lulu")
    assert not games.rename_player(g2, A, NEW)  # le compte y a déjà sa place : pas de fusion de deux places
    g3 = games.new_game("undercover", A, "Lulu", code="4245")
    g3["kicked"] = [NEW]
    assert not games.rename_player(g3, A, NEW)  # compte banni de la partie : il n'hérite pas d'une place
    g4 = games.new_game("undercover", A, "Lulu", code="4248")
    assert not games.rename_player(g4, games.player(g4, A)["pid"] + "0000", NEW)  # pas un joueur


def test_room_points_earned_before_and_after_the_link_add_up():
    room = games.new_game("room", A, "Lulu", code="4246")
    room.update(rpts={A: 3, NEW: 2}, rtally={A: {"drink": 1, "give": 0}, NEW: {"drink": 2, "give": 1}},
                rnames={A: "Lulu", NEW: "Lulu (compte)"})
    assert games.rename_player(room, A, NEW)
    assert room["rpts"] == {NEW: 5} and room["rtally"] == {NEW: {"drink": 3, "give": 1}}
    assert room["rnames"] == {NEW: "Lulu (compte)"}


def test_tmc_pairs_keyed_by_both_players_follow_the_rename():
    g = games.new_game("tmc", A, "Lulu", code="4247")
    games.join(g, B, "Léa")
    g["tmc"]["pairs"] = {f"{A}>{B}": {"asked": 1, "pts": 1.0}, f"{B}>{A}": {"asked": 2, "pts": 0.5}}
    assert games.rename_player(g, A, NEW)
    assert set(g["tmc"]["pairs"]) == {f"{NEW}>{B}", f"{B}>{NEW}"}
