import random

import pytest
from fastapi.testclient import TestClient

from app import games, main
from tests.test_features import admin, snap  # noqa: F401 (fixture)


def undercover(n, white=True, seed=1):
    g = games.new_game("undercover", white=white)
    for i in range(n):
        games.join(g, f"p{i}")
    games.start(g, random.Random(seed))
    return g


def by_role(g, role):
    return [p["id"] for p in g["players"] if p["role"] == role]


def test_roles_and_words_dealt():
    g = undercover(6)
    assert len(by_role(g, "undercover")) == 1 and len(by_role(g, "white")) == 1 and len(by_role(g, "civil")) == 4
    civil, under = g["words"]["civil"], g["words"]["undercover"]
    assert civil != under
    assert all(p["word"] == {"civil": civil, "undercover": under, "white": None}[p["role"]] for p in g["players"])
    assert games.player(g, g["order"][0])["role"] != "white"  # Mr. White ne parle jamais en premier
    assert len(by_role(undercover(4), "white")) == 0  # pas de Mr. White à moins de 5
    assert len(by_role(undercover(10, white=False), "undercover")) == 3


def test_views_hide_secrets():
    g = undercover(5)
    civil = by_role(g, "civil")[0]
    v = games.view(g, civil)
    assert v["me"]["word"] == g["words"]["civil"] and v["me"]["role"] is None
    assert "words" not in v and all("role" not in p and "word" not in p for p in v["players"])
    # Les guest_id (secrets) des joueurs n'apparaissent jamais : seulement des identifiants publics.
    assert not any(p["id"] in str(v) for p in g["players"])
    white = by_role(g, "white")[0]
    assert games.view(g, white)["me"]["role"] == "Mr. White" and games.view(g, white)["me"]["word"] is None
    assert "me" not in games.view(g, "inconnu") and "words" not in games.view(g, "inconnu")


def test_host_who_does_not_play_is_game_master():
    g = games.new_game("undercover", host="boss", name="Boss", plays=False)
    for i in range(4):
        games.join(g, f"p{i}", f"P{i}")
    assert games.player(g, "boss") is None
    games.start(g, random.Random(2))
    v = games.view(g, "boss")
    assert v["is_host"] and v["master"] and v["words"] == g["words"]
    assert all(p["role"] and "word" in p for p in v["players"])
    # Un animateur qui joue ne voit que son propre mot.
    g2 = games.new_game("undercover", host="boss", name="Boss")
    for i in range(3):
        games.join(g2, f"p{i}", f"P{i}")
    games.start(g2, random.Random(3))
    v2 = games.view(g2, "boss")
    assert v2["is_host"] and not v2["master"] and "words" not in v2


def test_host_leaving_hands_over():
    g = games.new_game("whoof", host="h", name="Hôte")
    games.join(g, "a", "Ana")
    games.leave(g, "h")
    assert g["host"] == "a" and g["host_name"] == "Ana"


def test_vote_eliminates_and_civils_win():
    g = undercover(4, white=False)
    under = by_role(g, "undercover")[0]
    games.start_vote(g)
    voters = [p["id"] for p in g["players"]]
    for v in voters:
        games.vote(g, v, under if v != under else next(x for x in voters if x != under))
    assert g["phase"] == "end" and g["winner"] == "civils"
    assert games.view(g, voters[0])["words"] == g["words"]  # tout est dévoilé à la fin


def test_eliminated_reveals_role_not_word():
    g = undercover(5, white=False)
    civil = by_role(g, "civil")
    games.eliminate(g, civil[0])
    out = next(p for p in games.view(g, civil[1])["players"] if not p["alive"])
    assert out["role"] == "Civil" and "word" not in out


def test_tie_revote_then_random():
    g = undercover(4, white=False)
    a, b, c, d = [p["id"] for p in g["players"]]
    games.start_vote(g)
    for voter, target in [(a, b), (b, a), (c, a), (d, b)]:
        games.vote(g, voter, target)
    assert g["phase"] == "vote" and sorted(g["candidates"]) == sorted([a, b])
    with pytest.raises(games.GameError):
        games.vote(g, c, d)  # seulement les ex æquo
    for voter, target in [(a, b), (b, a), (c, a), (d, b)]:
        games.vote(g, voter, target, random.Random(0))
    assert sum(not p["alive"] for p in g["players"]) == 1


def test_mr_white_guess_wins_with_accents_ignored():
    g = undercover(5)
    white = by_role(g, "white")[0]
    games.start_vote(g)
    games.eliminate(g, white)
    assert g["phase"] == "white_guess"
    with pytest.raises(games.GameError):
        games.white_guess(g, by_role(g, "civil")[0], "x")
    games.white_guess(g, white, games.normalize(g["words"]["civil"]).upper())
    assert g["winner"] == "white"


def test_impostors_win_when_one_civil_left():
    g = undercover(4, white=False)
    civils = by_role(g, "civil")
    games.eliminate(g, civils[0])
    assert g["phase"] == "reveal"
    games.next_step(g)
    games.start_vote(g)
    games.eliminate(g, civils[1])
    assert g["winner"] == "impostors"


def test_late_joiner_waits_for_next_game():
    g = undercover(4, white=False)
    games.join(g, "late", "Retard")
    v = games.view(g, "late")
    assert v["me"]["waiting"] and v["me"]["word"] is None
    assert next(p for p in v["players"] if p["name"] == "Retard")["waiting"]
    games.start_vote(g)
    with pytest.raises(games.GameError):
        games.vote(g, "late", "p0")  # ne vote pas
    with pytest.raises(games.GameError):
        games.vote(g, "p0", next(p["pid"] for p in g["players"] if p["id"] == "late") and "late")  # ni ne peut être visé
    # Les votes des 4 joueurs en lice suffisent à clore le vote.
    under = by_role(g, "undercover")[0]
    for v in ["p0", "p1", "p2", "p3"]:
        games.vote(g, v, under if v != under else next(x for x in ["p0", "p1"] if x != under))
    assert g["phase"] == "end"
    games.restart(g, random.Random(5))
    assert games.player(g, "late")["role"] and not games.player(g, "late")["waiting"]


def test_host_kicks_mid_game():
    g = undercover(5, white=False)
    under = by_role(g, "undercover")[0]
    games.start_vote(g)
    games.vote(g, "p0" if under != "p0" else "p1", under)
    games.kick(g, under)
    # Le seul undercover est parti : les civils gagnent ; il ne peut pas revenir.
    assert g["winner"] == "civils" and games.player(g, under) is None
    with pytest.raises(games.GameError):
        games.join(g, under, "Revenant")
    assert games.view(g, under)["kicked"]


def test_player_can_leave_mid_game():
    g = undercover(4, white=False)
    civil = by_role(g, "civil")[0]
    games.leave(g, civil)
    assert games.player(g, civil) is None and civil not in g["order"]
    games.join(g, civil, "De retour")  # partir de soi-même n'empêche pas de revenir
    assert games.player(g, civil)["waiting"]


def test_whoof_round():
    g = games.new_game("whoof")
    for gid in ("a", "b", "c"):
        games.join(g, gid)
    games.start(g)
    assert g["question"].startswith("Qui de nous")
    games.vote(g, "a", "b")
    games.vote(g, "b", "b")
    games.join(g, "d")  # retardataire accepté
    games.vote(g, "c", "a")
    games.vote(g, "d", "b")
    assert g["phase"] == "results" and g["results"][0] == ["b", 3]
    games.next_step(g)
    assert g["phase"] == "question" and g["votes"] == {}


def test_game_api_flow_without_music_code():
    clients = [TestClient(main.app) for _ in range(4)]  # aucun n'a saisi le code de la musique
    host, *others = clients
    g = host.post("/api/games", json={"guest_id": "host-abcdef12", "name": "Ludo", "type": "undercover", "plays": False}).json()
    code = g["code"]
    assert len(code) == 4 and g["is_host"] and g["master"]
    for i, c in enumerate(others):
        r = c.post(f"/api/games/{code}", json={"guest_id": f"gamer-{i}-xyz", "name": f"Joueur {i}", "action": "join"})
        assert r.status_code == 200 and r.json()["me"]
    # Seul l'animateur fait avancer la partie.
    assert others[0].post(f"/api/games/{code}", json={"guest_id": "gamer-0-xyz", "action": "start"}).status_code == 403
    assert host.post(f"/api/games/{code}", json={"guest_id": "host-abcdef12", "action": "start"}).json()["phase"] == "words"
    me = others[0].get(f"/api/games/{code}?guest_id=gamer-0-xyz").json()["me"]
    assert me["word"] or me["role"]
    # Vote par identifiant public.
    host.post(f"/api/games/{code}", json={"guest_id": "host-abcdef12", "action": "vote_start"})
    view = others[0].get(f"/api/games/{code}?guest_id=gamer-0-xyz").json()
    target = next(p["pid"] for p in view["players"] if p["pid"] != view["me"]["pid"])
    r = others[0].post(f"/api/games/{code}", json={"guest_id": "gamer-0-xyz", "action": "vote", "target": target})
    assert r.json()["me"]["vote"] == target
    assert TestClient(main.app).get(f"/qr/game/{code}.svg").status_code == 200
    host.post(f"/api/games/{code}", json={"guest_id": "host-abcdef12", "action": "end"})
    assert others[0].get(f"/api/games/{code}").status_code == 404


def test_admin_sees_and_closes_games(admin):  # noqa: F811
    g = TestClient(main.app).post("/api/games", json={"guest_id": "host-zzzz1234", "name": "Zoé", "type": "whoof"}).json()
    listed = admin.get("/api/admin/state").json()["games"]
    assert any(x["code"] == g["code"] and x["host"] == "Zoé" for x in listed)
    admin.post("/api/admin/games/close", json={"guest_id": "admin-console", "action": "end", "target": g["code"]})
    assert g["code"] not in main.store.session.games


def test_game_creation_rate_limited():
    main._game_creations.clear()  # les autres tests ont créé des parties depuis la même adresse
    c = TestClient(main.app)
    codes = [c.post("/api/games", json={"guest_id": f"spam-{i}-abcd", "name": "X", "type": "whoof"}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_host_reorders_speaking_order_and_lobby():
    g = games.new_game("undercover", host="h", name="H")
    for i in range(3):
        games.join(g, f"p{i}", f"P{i}")
    games.move(g, "p2", -1)
    assert [p["id"] for p in g["players"]] == ["h", "p0", "p2", "p1"]
    games.start(g, random.Random(4))
    first, second = g["order"][:2]
    games.move(g, second, -1)
    assert g["order"][:2] == [second, first]
    games.move(g, second, -1)  # déjà en tête : ne bouge plus
    assert g["order"][0] == second


def test_game_codes_are_digits_and_never_the_music_pin():
    assert all(games.new_code(set()).isdigit() for _ in range(50))
    taken = {f"{i:04d}" for i in range(10000)} - {"0042"}
    assert games.new_code(taken) == "0042"


@pytest.mark.parametrize("mode, pool", [("soft", games.WHOOF_QUESTIONS), ("awkward", games.WHOOF_AWKWARD), ("hot", games.WHOOF_HOT)])
def test_whoof_modes_pick_from_their_pool_without_repeats(mode, pool):
    g = games.new_game("whoof", host="h", name="H", mode=mode, sips=3)
    games.join(g, "a", "A")
    games.start(g)
    seen = set()
    for _ in range(len(pool)):
        seen.add(g["question"])
        assert g["question"][len("Qui de nous "):-2] in pool
        games.next_step(g)
    assert len(seen) == len(pool)  # toutes les questions avant de repasser par une déjà posée
    assert games.view(g, "h")["options"]["sips"] == 3 and games.view(g, "h")["mode"]


def test_whoof_rejects_unknown_mode_and_clamps_sips():
    with pytest.raises(games.GameError):
        games.new_game("whoof", mode="nope")
    assert games.new_game("whoof", sips=99)["options"]["sips"] == 10


def test_never_have_i_ever_round():
    g = games.new_game("never", host="h", name="H", mode="awkward", sips=2)
    games.join(g, "a", "Ana")
    games.start(g)
    assert g["question"].startswith("Je n'ai jamais ") and g["question"][len("Je n'ai jamais "):-1] in games.NEVER_AWKWARD
    with pytest.raises(games.GameError):
        games.vote(g, "a", "peut-être")
    games.vote(g, "a", "yes")
    assert games.view(g, "a")["me"]["vote"] == "yes"
    games.vote(g, "h", "no")
    v = games.view(g, "h")
    assert v["phase"] == "results" and {r["name"]: r["answer"] for r in v["results"]} == {"Ana": "yes", "H": "no"}
    assert v["mode"] == "😬 Malaisant" and games.summary(g)["name"] == "Je n'ai jamais · 😬 Malaisant"


def test_roulette_names_and_spin():
    g = games.new_game("roulette", host="h", name="H", plays=False)
    games.set_names(g, ["  Léa ", "Tom", "léa", "", "Zoé"])
    assert g["names"] == ["Léa", "Tom", "Zoé"]  # nettoyés, sans doublon
    games.spin(g, random.Random(1))
    v = games.view(g, "spectateur")
    assert v["phase"] == "spun" and v["spin"]["names"][v["spin"]["index"]] == v["history"][0]
    games.set_names(g, ["Seul"])
    with pytest.raises(games.GameError):
        games.spin(g)


def rigged(g, cards):
    """Sabot truqué : les cartes sont tirées dans l'ordre donné."""
    g["bj"]["shoe"] = ["2S"] * 60 + list(reversed(cards))


def test_blackjack_values():
    assert games.bj_value(["AS", "KD"]) == (21, True)
    assert games.bj_value(["AS", "AD", "9C"]) == (21, True)
    assert games.bj_value(["KS", "QD", "5C"]) == (25, False)


def test_blackjack_round_with_chips():
    g = games.new_game("blackjack", host="a", name="Ana")
    games.join(g, "b", "Bob")
    games.start(g)
    assert g["phase"] == "bet"
    with pytest.raises(games.GameError):
        games.bj_bet(g, "a", 500)  # plus que ses jetons
    g["bj"]["shoe"] = []
    games.bj_bet(g, "a", 10)
    # Ordre de distribution : Ana 2 cartes, Bob 2 cartes, croupier 2 cartes, puis tirages.
    rigged(g, ["TS", "9H", "AS", "KD", "TC", "7D", "5S"])
    games.bj_bet(g, "b", 20)  # tout le monde a misé : distribution automatique
    assert g["phase"] == "play" and g["bj"]["hands"]["b"]["status"] == "blackjack"
    assert games.view(g, "b")["bj"]["dealer"][1] == "??"  # carte cachée du croupier
    with pytest.raises(games.GameError):
        games.bj_hit(g, "b")  # pas son tour
    games.bj_stand(g, "a")  # Ana reste sur 19, croupier 17
    assert g["phase"] == "results"
    assert g["bj"]["hands"]["a"]["result"] == "win" and g["bj"]["chips"]["a"] == 110
    assert g["bj"]["hands"]["b"]["result"] == "blackjack" and g["bj"]["chips"]["b"] == 130
    games.next_step(g)
    assert g["phase"] == "bet" and g["bj"]["hands"] == {}


def test_blackjack_drinks_mode_bets_sips():
    g = games.new_game("blackjack", host="a", name="Ana", sips=3)  # mise max 3 gorgées
    games.start(g)
    with pytest.raises(games.GameError):
        games.bj_bet(g, "a", 4)
    rigged(g, ["5S", "6H", "TC", "7D", "TD"])
    games.bj_bet(g, "a", 2)
    games.bj_double(g, "a")  # 5+6+10 = 21 contre 17 ; mise doublée à 4 gorgées
    h = g["bj"]["hands"]["a"]
    assert h["bet"] == 4 and h["result"] == "win" and h["sips"] == 8  # gagné : distribue le double
    assert g["bj"]["chips"]["a"] == 100  # aucun jeton en jeu


@pytest.mark.parametrize("cards, sips", [
    (["TS", "6H", "TC", "9D", "KD"], -2),  # 16 contre 19 : perdu, bois sa mise
    (["AS", "KH", "TC", "9D"], 6),  # blackjack : distribue le triple
    (["TS", "9H", "TC", "9D"], 0),  # 19 partout : égalité
])
def test_blackjack_drinks_outcomes(cards, sips):
    g = games.new_game("blackjack", host="a", name="Ana", sips=5)
    games.start(g)
    rigged(g, cards)
    games.bj_bet(g, "a", 2)
    if g["phase"] == "play":
        games.bj_stand(g, "a")
    assert g["bj"]["hands"]["a"]["sips"] == sips


def test_blackjack_player_leaving_on_his_turn_passes_hand():
    g = games.new_game("blackjack", host="a", name="Ana")
    games.join(g, "b", "Bob")
    games.start(g)
    rigged(g, ["TS", "6H", "9S", "7H", "TC", "8D"])
    games.bj_bet(g, "a", 5)
    games.bj_bet(g, "b", 5)
    assert g["bj"]["seats"][g["bj"]["turn"]] == "a"
    games.leave(g, "a")
    assert g["bj"]["seats"][g["bj"]["turn"]] == "b"
    games.bj_stand(g, "b")
    assert g["phase"] == "results"


def test_old_or_unknown_games_do_not_break_pages(admin):  # noqa: F811
    old = games.new_game("blackjack")
    old.update(type="blackjack_drinks", code="9991")
    gone = games.new_game("whoof")
    gone.update(type="jeu_supprime", code="9992")
    main.store.session.games.update({"9991": old, "9992": gone})
    assert admin.get("/api/admin/state").status_code == 200
    assert main.store.session.games["9991"]["type"] == "blackjack" and main.store.session.games["9991"]["options"]["sips"] == 2
    assert "9992" not in main.store.session.games
    assert TestClient(main.app).get("/api/games/9991").status_code == 200


def test_sips_tally_across_games():
    g = games.new_game("never", host="h", name="H", sips=2)
    games.join(g, "a", "A")
    games.start(g)
    games.vote(g, "a", "yes")
    games.vote(g, "h", "no")
    assert games.view(g, "a")["me"]["drink"] == 2 and games.view(g, "h")["me"]["drink"] == 0
    w = games.new_game("whoof", host="h", name="H", sips=3)
    games.join(w, "a", "A")
    games.start(w)
    games.vote(w, "a", "h")
    games.vote(w, "h", "h")
    assert next(p for p in games.view(w, "a")["players"] if p["name"] == "H")["drink"] == 3


def test_blackjack_log_and_give_tally():
    g = games.new_game("blackjack", host="a", name="Ana", sips=1)
    games.start(g)
    rigged(g, ["5S", "6H", "TC", "7D", "TD"])
    games.bj_bet(g, "a", 1)
    games.bj_hit(g, "a")  # 5+6+10 = 21 : reste automatiquement
    log = [e["text"] for e in games.view(g, "a")["bj"]["log"]]
    assert "tire 10♦ → 21" in log and any(t.startswith("retourne 7♦") for t in log)
    assert games.view(g, "a")["me"]["give"] == 2  # gagné : distribue le double de sa mise


def test_21_with_three_cards_is_not_a_blackjack():
    g = games.new_game("blackjack", host="a", name="Ana", sips=3)
    games.start(g)
    rigged(g, ["5S", "6H", "TC", "7D", "TD"])
    games.bj_bet(g, "a", 2)
    games.bj_hit(g, "a")  # 5 + 6 + 10 = 21, mais en 3 cartes
    h = g["bj"]["hands"]["a"]
    assert h["result"] == "win" and h["sips"] == 4  # simple victoire : le double, pas le triple


class FixedRng(random.Random):
    def __init__(self, n):
        super().__init__(0)
        self.n = n

    def randrange(self, *args):
        return self.n


def casino(sips=0):
    g = games.new_game("casino", host="a", name="Ana", sips=sips)
    games.join(g, "b", "Bob")
    games.start(g)
    return g


def test_casino_chips_payouts():
    g = casino()
    games.casino_bet(g, "a", "n:17", 10)      # plein gagnant : +350
    games.casino_bet(g, "a", "color:red", 10)  # 17 est noir : -10
    games.casino_bet(g, "b", "dozen:2", 20)    # 13-24 : +40
    with pytest.raises(games.GameError):
        games.casino_bet(g, "b", "n:37", 5)
    with pytest.raises(games.GameError):
        games.casino_bet(g, "b", "color:violet", 5)
    with pytest.raises(games.GameError):
        games.casino_bet(g, "b", "half:low", 81)  # plus que ses jetons
    games.casino_spin(g, FixedRng(17))
    c = g["casino"]
    assert c["results"]["a"]["net"] == 340 and c["results"]["a"]["jackpot"] and c["chips"]["a"] == 440
    assert c["results"]["b"]["net"] == 40 and c["chips"]["b"] == 140
    with pytest.raises(games.GameError):
        games.casino_bet(g, "a", "n:1", 5)  # rien ne va plus
    v = games.view(g, "b")["casino"]
    assert v["history"][0] == 17 and v["me"]["result"]["net"] == 40


def test_casino_zero_and_sips_mode():
    g = casino(sips=3)
    games.casino_bet(g, "a", "color:red", 2)
    with pytest.raises(games.GameError):
        games.casino_bet(g, "a", "n:5", 2)  # 3 gorgées max par tour
    games.casino_bet(g, "a", "n:5", 1)
    games.casino_bet(g, "b", "n:0", 1)
    games.casino_spin(g, FixedRng(0))
    r = g["casino"]["results"]
    assert r["a"] == {"staked": 3, "drink": 4, "give": 0, "net": 0, "jackpot": False}  # 3 perdues + 1 (zéro)
    assert r["b"]["give"] == 10 and r["b"]["drink"] == 0  # plein sur le 0 : jackpot, pas de pénalité
    assert games.view(g, "a")["me"]["drink"] == 4


def test_casino_even_money_rules():
    assert games.casino_wins("color", "red", 1) and not games.casino_wins("color", "red", 2)
    assert games.casino_wins("parity", "even", 2) and not games.casino_wins("parity", "even", 0)
    assert games.casino_wins("half", "high", 19) and games.casino_wins("dozen", "3", 36)


def test_divan_turns_joker_and_hearts():
    g = games.new_game("divan", host="h", name="Hôte")
    games.join(g, "a", "Ana")
    games.divan_set_cats(g, ["childhood"])
    with pytest.raises(games.GameError):
        games.divan_set_cats(g, ["inconnue"])
    games.start(g)
    v = games.view(g, "h")["divan"]
    assert v["current"]["name"] == "Hôte" and v["card"]["cat"] == "childhood" and v["my_turn"]
    games.divan_heart(g, "a")
    games.divan_heart(g, "a")  # une seule fois par carte
    assert games.view(g, "h")["divan"]["hearts"] == 1
    with pytest.raises(games.GameError):
        games.divan_next(g, "a")  # Ana n'est ni sur le divan ni animatrice
    first = g["divan"]["card"]["text"]
    games.divan_joker(g, "h")
    assert g["divan"]["card"]["text"] != first and g["divan"]["hearts"] == []
    with pytest.raises(games.GameError):
        games.divan_joker(g, "h")  # un seul joker par tour
    games.divan_next(g, "h")
    v = games.view(g, "a")["divan"]
    assert v["current"]["name"] == "Ana" and v["my_turn"] and not v["joker"]
    assert all(len(set(q)) >= 1000 for q in games.DIVAN_CARDS.values())  # 1000 cartes au moins par catégorie
    every = [q for cards in games.DIVAN_CARDS.values() for q in cards]
    assert len(every) == len(set(every))  # aucun doublon, même d'une catégorie à l'autre


def test_divan_couple_mode_is_exclusive():
    g = games.new_game("divan", host="h", name="Hôte")
    assert "couple" not in g["divan"]["cats"]  # pas proposé par défaut entre amis
    assert {"dreams", "whatif"} <= set(g["divan"]["cats"])
    games.divan_set_cats(g, ["emotions", "couple"])
    assert g["divan"]["cats"] == ["couple"]


def test_players_learn_the_host_ended_the_game():
    host, other = TestClient(main.app), TestClient(main.app)
    main._game_creations.clear()
    g = host.post("/api/games", json={"guest_id": "host-end-0001", "name": "Ludo", "type": "whoof"}).json()
    host.post(f"/api/games/{g['code']}", json={"guest_id": "host-end-0001", "action": "end"})
    r = other.get(f"/api/games/{g['code']}?guest_id=player-end-01")
    assert r.status_code == 404
    assert r.json()["detail"]["ended"] == {**r.json()["detail"]["ended"], "by": "host", "host": "Ludo", "game": "Qui de nous ?"}


def test_elapsed_since_creation():
    g = games.new_game("undercover", host="h", name="Hôte")
    g["created_at"] -= 125
    assert 125 <= games.view(g, "h")["elapsed"] < 127
    assert 125 <= games.summary(g)["elapsed"] < 127


def test_divan_back_undoes_next_and_joker():
    g = games.new_game("divan", host="h", name="Hôte")
    games.join(g, "a", "Ana")
    games.join(g, "b", "Bob")
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.divan_back(g, "h")  # rien à annuler
    first, used = dict(g["divan"]["card"]), len(g["divan"]["used"])
    games.divan_heart(g, "a")
    games.divan_next(g, "h", random.Random(2))
    assert g["divan"]["turn"] == 1 and g["divan"]["hearts"] == []
    games.divan_joker(g, "a", random.Random(3))
    games.divan_back(g, "a")  # Ana annule son joker
    assert not g["divan"]["joker"]
    with pytest.raises(games.GameError):
        games.divan_back(g, "b")  # Bob n'est ni sur le divan, ni animateur, ni l'auteur de l'action
    games.divan_back(g, "h")
    d = g["divan"]
    assert d["card"] == first and d["turn"] == 0 and d["hearts"] == ["a"] and len(d["used"]) == used
    assert g["round"] == first["id"]


def test_tmc_duo_answers_and_scores():
    g = games.new_game("tmc", host="h", name="Hôte", plays=False)  # l'animateur ne joue pas
    games.join(g, "a", "Ana")
    with pytest.raises(games.GameError):
        games.start(g)  # il faut au moins 2 joueurs
    games.join(g, "b", "Bob")
    games.join(g, "c", "Cléo")
    games.start(g, random.Random(1))
    d = g["tmc"]["duo"]
    guesser, subject = d["guesser"], d["subject"]
    other = next(p["id"] for p in g["players"] if p["id"] not in (guesser, subject))
    with pytest.raises(games.GameError):
        games.tmc_answer(g, other, "Tesla")  # pas dans le duo
    games.tmc_answer(g, subject, "Une 2CV")
    v = games.view(g, guesser)["tmc"]["duo"]
    assert v["role"] == "guesser" and v["answers"] is None  # la réponse du sujet reste cachée
    games.tmc_answer(g, guesser, "2CV")
    assert g["phase"] == "judge"
    with pytest.raises(games.GameError):
        games.tmc_judge(g, guesser, 2)  # le devin ne se juge pas lui-même
    games.tmc_judge(g, subject, 2)
    assert g["phase"] == "scored" and g["tmc"]["scores"][guesser] == 1
    t = games.view(g, other)["tmc"]
    assert t["ranking"][0]["name"] == games.player(g, guesser)["name"] and t["pairs"][0]["pct"] == 100
    # Duos suivants : chaque sens de chaque paire passe avant qu'un duo ne revienne.
    seen = {(guesser, subject)}
    for _ in range(5):
        games.next_step(g, random.Random(len(seen)))
        d = g["tmc"]["duo"]
        games.tmc_answer(g, d["subject"], "x")
        games.tmc_answer(g, d["guesser"], "y")
        games.tmc_judge(g, "h", 1)  # l'animateur peut juger : presque = ½ point
        seen.add((d["guesser"], d["subject"]))
    assert len(seen) == 6
    games.tmc_finish(g)
    assert g["phase"] == "end" and games.view(g, "h")["tmc"]["duos"]


def test_tmc_player_leaving_mid_duo():
    g = games.new_game("tmc", host="h", name="Hôte")
    for i in "abc":
        games.join(g, i, i.upper())
    games.start(g, random.Random(4))
    gone = g["tmc"]["duo"]["subject"]
    games.leave(g, gone)
    d = g["tmc"]["duo"]
    assert gone not in (d["guesser"], d["subject"]) and g["phase"] == "answer"
