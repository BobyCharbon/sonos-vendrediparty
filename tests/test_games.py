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
    games.ban(g, under)
    # Le seul undercover est parti : les civils gagnent ; banni, il ne peut pas revenir.
    assert g["winner"] == "civils" and games.player(g, under) is None
    with pytest.raises(games.GameError):
        games.join(g, under, "Revenant")
    assert games.view(g, under)["kicked"]


def test_excluded_player_can_come_back():
    g = undercover(4, white=False)
    civil = by_role(g, "civil")[0]
    games.kick(g, civil)
    v = games.view(g, civil)
    assert games.player(g, civil) is None and v["excluded"] and not v["kicked"]
    games.join(g, civil, "De retour")  # exclu (absent) : il peut revenir quand il veut
    assert games.player(g, civil) and not games.view(g, civil)["excluded"]


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


def test_whoof_vote_cannot_be_changed():
    """Qui de nous ? : un vote est définitif (retour 26.10 : « interdit de changer de vote »)."""
    g = games.new_game("whoof")
    for gid in ("a", "b", "c"):
        games.join(g, gid)
    games.start(g)
    games.vote(g, "a", "b")
    with pytest.raises(games.GameError):
        games.vote(g, "a", "c")
    assert g["votes"]["a"] == "b"


def test_never_answer_can_still_be_changed():
    g = games.new_game("never")
    for gid in ("a", "b"):
        games.join(g, gid)
    games.start(g)
    games.vote(g, "a", "yes")
    games.vote(g, "a", "no")
    assert g["votes"]["a"] == "no"


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


@pytest.mark.parametrize("mode, pool", [("soft", games.WHOOF_SOFT), ("awkward", games.WHOOF_AWKWARD), ("hot", games.WHOOF_HOT)])
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
    with pytest.raises(games.GameError):
        games.tmc_answer(g, guesser, "Tesla")  # le devin parle à voix haute, il n'écrit rien
    games.tmc_answer(g, subject, "Une 2CV")
    assert g["phase"] == "guess"
    v = games.view(g, "h")["tmc"]["duo"]
    assert v["answer"] is None  # cachée jusqu'à la révélation, même pour l'animateur
    assert games.view(g, subject)["tmc"]["duo"]["mine"] == "Une 2CV"
    games.tmc_reveal(g)
    assert games.view(g, guesser)["tmc"]["duo"]["answer"] == "Une 2CV"
    with pytest.raises(games.GameError):
        games.tmc_judge(g, subject, 2)  # seul l'animateur attribue les points
    games.tmc_judge(g, "h", 2)
    assert g["phase"] == "scored" and g["tmc"]["scores"][guesser] == 1
    t = games.view(g, subject)["tmc"]
    assert t["ranking"][0]["name"] == games.player(g, guesser)["name"] and t["pairs"][0]["pct"] == 100
    # Duos suivants : chaque sens de chaque paire passe avant qu'un duo ne revienne.
    seen = {(guesser, subject)}
    for _ in range(5):
        games.next_step(g, random.Random(len(seen)))
        d = g["tmc"]["duo"]
        games.tmc_answer(g, d["subject"], "x")
        games.tmc_reveal(g)
        games.tmc_judge(g, "h", 1)  # presque = ½ point
        seen.add((d["guesser"], d["subject"]))
    assert len(seen) == 6
    games.tmc_finish(g)
    assert g["phase"] == "end" and games.view(g, "h")["tmc"]["duos"]


def test_tmc_questions_bank():
    from app.tmc_questions import TMC_QUESTIONS
    assert len(TMC_QUESTIONS) >= 300 and len(set(TMC_QUESTIONS)) == len(TMC_QUESTIONS)


def test_tmc_player_leaving_mid_duo():
    g = games.new_game("tmc", host="h", name="Hôte")
    for i in "abc":
        games.join(g, i, i.upper())
    games.start(g, random.Random(4))
    gone = g["tmc"]["duo"]["subject"]
    games.leave(g, gone)
    d = g["tmc"]["duo"]
    assert gone not in (d["guesser"], d["subject"]) and g["phase"] == "answer"


def test_manual_players_without_phone():
    # Le Divan : l'animateur ajoute des participants tapés à la main et mène pour eux.
    g = games.new_game("divan", host="h", name="Hôte")
    games.add_guest(g, "  Mamie  ")
    with pytest.raises(games.GameError):
        games.add_guest(g, " ")
    assert [p["name"] for p in g["players"]] == ["Hôte", "Mamie"] and g["players"][1]["manual"]
    assert [p["manual"] for p in games.view(g, "h")["players"]] == [False, True]
    games.start(g, random.Random(1))
    games.divan_next(g, "h")  # Mamie sur le divan : l'animateur fait avancer
    assert games.view(g, "h")["divan"]["current"]["name"] == "Mamie"
    with pytest.raises(games.GameError):
        games.add_guest(games.new_game("undercover", host="h"), "Zoé")  # pas dans tous les jeux

    # Je n'ai jamais : l'animateur saisit la réponse du participant sans téléphone.
    g = games.new_game("never", host="h", name="Hôte")
    games.add_guest(g, "Papi")
    papi = g["players"][1]["id"]
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.vote_for(g, "h", "yes")  # l'animateur a un téléphone : il vote lui-même
    games.vote_for(g, papi, "yes")
    assert next(p for p in games.view(g, "h")["players"] if p["name"] == "Papi")["answer"] == "yes"
    games.vote(g, "h", "no")
    assert g["phase"] == "results" and [papi, "yes"] in g["results"]

    # Tu me connais ? : sujet sans téléphone, l'animateur lui prête le sien.
    g = games.new_game("tmc", host="h", name="Hôte")
    games.add_guest(g, "Léa")
    games.start(g, random.Random(1))
    d = g["tmc"]["duo"]
    if d["subject"] == "h":
        games.tmc_answer(g, "h", "Rouge")
    else:
        assert games.view(g, "h")["tmc"]["duo"]["proxy"]
        games.tmc_answer(g, "h", "Rouge")
        assert games.view(g, "h")["tmc"]["duo"]["mine"] is None  # l'animateur ne la revoit pas
    assert g["phase"] == "guess"


def test_host_leaving_never_passes_to_manual_player():
    g = games.new_game("divan", host="h", name="Hôte")
    games.add_guest(g, "Mamie")
    games.join(g, "a", "Ana")
    games.leave(g, "h")
    assert g["host"] == "a"


# --- Pyramide ---

def pyramid(n=2, floors=5, seed=7):
    g = games.new_game("pyramid", host="p0", name="P0")
    for i in range(1, n):
        games.join(g, f"p{i}", f"P{i}")
    g["options"]["floors"] = floors
    games.start(g, random.Random(seed))
    return g


def test_pyramid_limits_players_to_one_deck():
    assert games.pyr_max_players(5) == 9 and games.pyr_max_players(8) == 4
    with pytest.raises(games.GameError):
        pyramid(n=5, floors=8)
    assert [games.pyr_floor(5, i) for i in (0, 4, 5, 14)] == [1, 1, 2, 5]


def test_pyramid_deal_rules_and_hidden_hands():
    g = pyramid()
    P = g["pyr"]
    P["deck"] += ["3S", "KD", "9H", "5C", "QC", "8H", "2S", "AD"]  # tirés depuis la fin
    with pytest.raises(games.GameError):
        games.pyr_answer(g, "p1", "red")  # pas son tour
    games.pyr_answer(g, "p0", "red")       # AD rouge : réussi
    assert P["last"]["ok"] and games.view(g, "p1")["me"]["give"] == 0
    games.pyr_answer(g, "p1", "red")       # 2S noir : raté, boit 1
    assert games.view(g, "p1")["me"]["drink"] == 1
    games.pyr_answer(g, "p0", "moins")     # 8H < A (l'As est la plus forte)
    games.pyr_answer(g, "p1", "moins")     # QC > 2 : raté
    games.pyr_answer(g, "p0", "dedans")    # 5C entre 1 et 8
    games.pyr_answer(g, "p1", "dedans")    # 9H entre 2 et 12
    games.pyr_answer(g, "p0", "D")         # KD carreau
    games.pyr_answer(g, "p1", "S")         # 3S pique
    assert g["phase"] == "pyramid"
    v = games.view(g, "p0")["pyr"]
    assert all(c == "??" for s in v["seats"] for c in s["cards"])  # plus personne ne voit ses cartes
    assert v["pyramid"] == ["??"] * 15


def finish_deal(g):
    P = g["pyr"]
    while g["phase"] == "deal":
        games.pyr_answer(g, P["order"][P["turn"]], games.PYR_STEPS[P["step"]][0])


def test_pyramid_claim_accuse_reveal_and_peek():
    g = pyramid()
    finish_deal(g)
    P = g["pyr"]
    games.pyr_flip(g)
    assert P["pyramid"][0] == games.view(g, "p1")["pyr"]["current"]
    games.pyr_claim(g, "p1")
    with pytest.raises(games.GameError):
        games.pyr_claim(g, "p1")
    claim = P["claims"][0]
    games.pyr_judge(g, claim["id"], liar=True)
    P["hands"]["p1"][2] = P["pyramid"][0][0] + "H"  # il avait bien la carte
    games.pyr_reveal(g, "p1", 2)
    v = games.view(g, "p0")["pyr"]
    assert v["reveal"]["truth"] and v["seats"][1]["cards"][2] != "??"  # visible par tous 3 s
    P["reveal"]["at"] -= 4
    assert games.view(g, "p0")["pyr"]["seats"][1]["cards"][2] == "??"
    games.pyr_peek(g, "p0", [0, 3])
    games.pyr_peek_decide(g, P["peeks"][0]["id"], True)
    mine = games.view(g, "p0")["pyr"]["seats"][0]["cards"]
    assert mine[0] != "??" and mine[3] != "??" and mine[1] == "??"
    assert games.view(g, "p1")["pyr"]["seats"][0]["cards"][0] == "??"  # coup d'œil privé
    assert games.view(g, "p0")["me"]["drink"] >= 4  # 2 gorgées par carte


def test_pyramid_top_memory_roulette_and_boat():
    g = pyramid(n=3)
    finish_deal(g)
    P = g["pyr"]
    for _ in range(15):
        games.pyr_flip(g)
    top = P["pyramid"][-1]
    with pytest.raises(games.GameError):
        games.pyr_claim(g, "p0")  # au sommet : pas de bluff
    P["hands"]["p1"][0] = top[0] + "S"
    P["hands"]["p2"] = [c for c in P["hands"]["p2"]]
    P["hands"]["p2"] = ["2S", "2H", "2D", "2C"] if top[0] != "2" else ["3S", "3H", "3D", "3C"]
    games.pyr_top(g, "p1")
    games.pyr_top(g, "p2")
    assert games.view(g, "p1")["pyr"]["top_me"] is True and games.view(g, "p2")["pyr"]["liars"] == ["P2"]
    games.pyr_to_memory(g)
    games.pyr_memory(g, "p0", [c[0] for c in P["hands"]["p0"]])           # 0 erreur
    games.pyr_memory(g, "p1", ["K", "K", "K", "K"] if P["hands"]["p1"][0][0] != "K" else ["Q"] * 4)
    games.pyr_memory(g, "p2", ["10" if c[0] == "T" else c[0] for c in P["hands"]["p2"]])
    assert g["phase"] == "memres"
    assert {c["name"] for c in games.view(g, "p0")["pyr"]["candidates"]} >= {"P2"}  # menteur au sommet
    games.pyr_pick_boat(g, random.Random(1))
    assert g["phase"] == "boatpick"
    games.pyr_boat_start(g)
    boat = P["boat"]
    P["deck"] = ["KS", "3C", "9D", "8S", "2H"]  # 2H rouge ✓, 8S plus ✓, 9D dehors ✓, 3C pas pique ✗
    games.pyr_boat_answer(g, boat, "red")
    games.pyr_boat_answer(g, boat, "plus")
    games.pyr_boat_answer(g, boat, "dehors")
    games.pyr_boat_answer(g, boat, "S")  # 2H : raté → 1 gorgée, retour au début
    b = P["bstate"]
    assert b["step"] == 1 and b["sips"] == 1
    games.pyr_boat_answer(g, boat, "black")  # KS noir ✓ puis paquet vide : fin
    assert g["phase"] == "end" and b["result"] == "deck"


def test_pyramid_soft_mode_no_boat_and_fresh_deck():
    g = games.new_game("pyramid", host="p0", name="P0")
    games.join(g, "p1", "P1")
    g["options"].update(pmode="soft", boat=False)
    games.start(g, random.Random(3))
    finish_deal(g)
    assert all(t["drink"] + t["give"] == 4 for t in g["tally"].values())  # 1 gorgée par carte
    for _ in range(15):
        games.pyr_flip(g)
    games.pyr_to_memory(g)
    games.pyr_memory(g, "p0", ["A"] * 4)
    games.pyr_memory(g, "p1", ["K"] * 4)
    assert g["phase"] == "end"  # pas de bateau
    h = pyramid()
    finish_deal(h)
    for _ in range(15):
        games.pyr_flip(h)
    games.pyr_to_memory(h)
    games.pyr_results(h)
    games.pyr_pick_boat(h, random.Random(0))
    games.pyr_boat_start(h, random.Random(0))
    assert len(h["pyr"]["deck"]) == 52  # paquet neuf pour le bateau


def test_pyramid_ace_is_highest():
    assert games.pyr_value("AS") > games.pyr_value("KS") > games.pyr_value("2S")
    assert games._pyr_check(2, "plus", ["KD"], "AH") and not games._pyr_check(2, "plus", ["AD"], "KH")


def test_pyramid_poteau_everyone_drinks():
    g = pyramid(n=3)
    P = g["pyr"]
    P["deck"] += ["7C", "7H"]  # p0 reçoit 7H puis… on force p0 à retomber sur un 7 au tour suivant
    games.pyr_answer(g, "p0", "red")
    before = {x: g["tally"].get(x, {}).get("drink", 0) for x in P["order"]}
    P["deck"].append("7S")
    games.pyr_answer(g, "p1", "red")  # p1 tire 7S : pas de poteau (sa 1re carte)
    assert not P["last"]["poteau"]
    games.pyr_answer(g, "p2", "red")
    P["deck"].append("7D")
    games.pyr_answer(g, "p0", "plus")  # p0 a déjà un 7 : poteau
    assert P["last"]["poteau"]
    after = {x: g["tally"].get(x, {}).get("drink", 0) for x in P["order"]}
    assert after["p1"] == before["p1"] + 1 or after["p1"] >= 1  # tout le monde boit 1
    assert all(after[x] >= 1 for x in P["order"])


def test_pyramid_late_join_needs_approval_and_plays_own_deal():
    g = pyramid()
    finish_deal(g)
    games.pyr_flip(g)
    games.join(g, "late", "Retard")
    assert games.view(g, "late")["pyr"]["me"]["pending"] and "late" not in g["pyr"]["order"]
    assert games.view(g, "p0")["pyr"]["pending"][0]["name"] == "Retard"
    games.pyr_accept(g, "late")
    v = games.view(g, "p1")["pyr"]
    assert v["late"]["name"] == "Retard" and v["late"]["step"] == 1
    with pytest.raises(games.GameError):
        games.pyr_flip(g)  # la pyramide attend sa distribution
    for step in range(1, 5):
        games.pyr_answer(g, "late", games.PYR_STEPS[step][0])
        if step < 4:
            assert games.view(g, "p0")["pyr"]["seats"][-1]["cards"][-1] != "??"  # visible de tous
    assert g["pyr"]["late"] is None and len(g["pyr"]["hands"]["late"]) == 4
    assert all(c == "??" for c in games.view(g, "late")["pyr"]["seats"][-1]["cards"])  # retournées
    games.pyr_flip(g)


def test_pyramid_refuse_and_kick_anytime():
    g = pyramid(n=3)
    finish_deal(g)
    games.join(g, "x", "Intrus")
    games.pyr_refuse(g, "x")
    assert games.player(g, "x") is None
    games.pyr_flip(g)
    games.pyr_claim(g, "p2")
    games.kick(g, "p2")
    assert "p2" not in g["pyr"]["order"] and not g["pyr"]["claims"]


def test_pyramid_poteau_hard_and_double_floor_sips():
    g = pyramid()
    g["options"].update(poteau="hard", double=True)
    P = g["pyr"]
    P["deck"] += ["5S", "5H"]
    games.pyr_answer(g, "p0", "red")       # 5H
    games.pyr_answer(g, "p1", "black")     # 5S (sa 1re carte : pas de poteau)
    before = g["tally"].get("p1", {}).get("drink", 0)
    P["deck"].append("5D")
    games.pyr_answer(g, "p0", "plus")      # p0 retombe sur un 5 : poteau hard (cul sec, pas de gorgée pour les autres)
    assert P["last"]["poteau"] and g["tally"].get("p1", {}).get("drink", 0) == before
    finish_deal(g)
    games.pyr_flip(g)
    games.pyr_claim(g, "p0")
    assert P["claims"][0]["sips"] == 2  # étage 1 en mode double
    for _ in range(5):
        games.pyr_flip(g)
    games.pyr_claim(g, "p1")
    assert P["claims"][0]["sips"] == 4 and games.view(g, "p0")["pyr"]["floor_sips"] == 4


def test_casino_undo_and_ready_starts_spin():
    g = casino()
    games.casino_bet(g, "a", "color:red", 10)
    games.casino_bet(g, "a", "color:red", 5)
    games.casino_bet(g, "a", "n:7", 5)
    games.casino_undo(g, "a")  # retire le 7
    games.casino_undo(g, "a")  # retire 5 sur Rouge
    assert g["casino"]["bets"]["a"] == [{"kind": "color", "target": "red", "amount": 10}]
    games.casino_ready(g, "a", FixedRng(3))
    assert g["phase"] == "bet"  # Bob n'est pas prêt
    games.casino_bet(g, "a", "n:3", 5)  # changer sa mise annule « prêt »
    assert not g["casino"]["ready"] or "a" not in g["casino"]["ready"]
    games.casino_ready(g, "a", FixedRng(3))
    games.casino_ready(g, "b", FixedRng(3))  # Bob prêt sans miser : tout le monde est prêt → la bille part
    assert g["phase"] == "results" and g["casino"]["spin"]["number"] == 3


def test_admin_summary_has_details_without_secrets():
    g = games.new_game("undercover", host="h", name="Hôte")
    for i in range(3):
        games.join(g, f"p{i}", f"P{i}")
    games.start(g, random.Random(1))
    s = games.summary(g)
    assert s["host"] == "Hôte" and s["created_at"] and len(s["players_detail"]) == 4
    assert "Avec Mr. White" in s["facts"]
    assert g["words"]["civil"] not in str(s) and g["words"]["undercover"] not in str(s)
    c = games.new_game("casino", host="h", name="H")
    assert games.summary(c)["players_detail"][0]["extra"] == "💰 100"


# --- Biskit Royal ---

def biskit(n=3, sips=1):
    g = games.new_game("biskit", host="p0", name="P0", sips=sips)
    for i in range(1, n):
        games.join(g, f"p{i}", f"P{i}")
    games.start(g, random.Random(5))
    return g


def draw(g, card, rng=None):
    g["bk"]["deck"].append(card)
    g["bk"]["ready_at"] = 0  # pas de pause de lecture dans les tests
    cur = g["bk"]["order"][g["bk"]["turn"]]
    games.bk_draw(g, cur, rng or random.Random(0))
    return cur


def test_biskit_simple_cards_and_turns():
    g = biskit(sips=2)
    with pytest.raises(games.GameError):
        games.bk_draw(g, "p1")  # pas son tour
    a = draw(g, "3H")  # 3 rouge : distribue 3 × 2
    assert g["tally"][a]["give"] == 6 and g["bk"]["key"] == "3-red"
    b = draw(g, "2S")  # 2 noir : bois 2 × 2
    assert g["tally"][b]["drink"] == 4 and b != a


def test_biskit_reflex_last_one_drinks():
    g = biskit()
    draw(g, "7H")
    with pytest.raises(games.GameError):
        draw(g, "2S")  # attendre la fin du réflexe
    games.bk_tap(g, "p1"); games.bk_tap(g, "p0"); games.bk_tap(g, "p2")
    assert g["bk"]["reflex"]["losers"] == ["p2"] and g["tally"]["p2"]["drink"] == 1


def test_biskit_await_actions_rules_duel_and_kings():
    g = biskit()
    a = draw(g, "JH")
    with pytest.raises(games.GameError):
        draw(g, "2S")
    games.bk_complete(g, a, text="Interdit de dire « boire »")
    assert g["bk"]["rules"][0]["text"] == "Interdit de dire « boire »"
    b = draw(g, "JS")
    games.bk_complete(g, b, target=g["bk"]["rules"][0]["id"])
    assert g["bk"]["rules"] == []
    c = draw(g, "QS")
    other = next(x for x in g["bk"]["order"] if x != c)
    games.bk_complete(g, c, target=other, rng=random.Random(1))
    assert g["bk"]["duel"] and any("Duel" in o["text"] for o in g["bk"]["outcomes"])
    for _ in range(4):
        draw(g, "KD")
    assert g["phase"] == "end" and g["bk"]["final"]


def test_biskit_dice_double_three_makes_new_biskit():
    g = biskit()

    class R(random.Random):
        def randint(self, a, b):
            return 3
    a = draw(g, "4H", R())
    assert g["bk"]["biskit"] == a and g["bk"]["dice"]["d"] == [3, 3]


def test_admin_has_animator_rights_in_every_game(admin):  # noqa: F811
    """L'admin (cookie) peut faire avancer n'importe quelle partie, comme l'animateur."""
    main._game_creations.clear()
    host = TestClient(main.app)
    g = host.post("/api/games", json={"guest_id": "host-rights-01", "name": "Léa", "type": "never", "plays": True}).json()
    guest = TestClient(main.app)
    guest.post(f"/api/games/{g['code']}", json={"guest_id": "guest-rights-1", "name": "Tom", "action": "join"})
    # Un simple joueur ne peut pas lancer…
    assert guest.post(f"/api/games/{g['code']}", json={"guest_id": "guest-rights-1", "action": "start"}).status_code == 403
    # … l'admin si, même sans être l'animateur, et il voit les commandes.
    view = admin.get(f"/api/games/{g['code']}?guest_id=admin-rights-01").json()
    assert view["is_host"]
    r = admin.post(f"/api/games/{g['code']}", json={"guest_id": "admin-rights-01", "action": "start"})
    assert r.status_code == 200 and r.json()["phase"] == "question"
    assert admin.post(f"/api/games/{g['code']}", json={"guest_id": "admin-rights-01", "action": "next"}).status_code == 200


def test_biskit_pause_before_next_card():
    """5 s pour lire le gage : la carte suivante est refusée avant, le serveur l'impose."""
    g = biskit()
    draw(g, "4S")  # 4 noir : rien de spécial à choisir
    g["bk"]["ready_at"] = games.time.time() + games.BK_PAUSE
    cur = g["bk"]["order"][g["bk"]["turn"]]
    with pytest.raises(games.GameError, match="lire le gage"):
        games.bk_draw(g, cur)
    assert games.view(g, cur)["bk"]["wait"] > 4
    g["bk"]["ready_at"] = 0
    games.bk_draw(g, cur)



def test_game_room_flow():
    """Salle de jeux : un code pour la soirée ; l'animateur lance un jeu, tout le monde y est ; à la fin, retour à la salle."""
    main._game_creations.clear()
    h, o = TestClient(main.app), TestClient(main.app)
    r = h.post("/api/games", json={"guest_id": "room-host-0001", "name": "Ludo", "type": "room", "plays": True}).json()
    code = r["code"]
    assert r["room_info"]["current"] is None and any(c["type"] == "quiz" for c in r["room_info"]["catalog"])
    o.post(f"/api/games/{code}", json={"guest_id": "room-other-001", "name": "Léa", "action": "join"})
    h.post(f"/api/games/{code}", json={"guest_id": "room-host-0001", "action": "addguest", "guess": "Tom"})
    # Un simple joueur ne lance pas de jeu
    assert o.post(f"/api/games/{code}", json={"guest_id": "room-other-001", "action": "launch", "settings": {"type": "quiz"}}).status_code == 403
    v = h.post(f"/api/games/{code}", json={"guest_id": "room-host-0001", "action": "launch", "settings": {"type": "biskit", "sips": 1}}).json()
    cur = v["room_info"]["current"]
    assert cur["type"] == "biskit" and cur["players"] == 3  # Ludo, Léa et Tom (sans téléphone) d'office
    child = o.get(f"/api/games/{cur['code']}?guest_id=room-other-001").json()
    assert child["room"] == code and child["me"] and not child["is_host"]
    assert h.get(f"/api/games/{cur['code']}?guest_id=room-host-0001").json()["is_host"]
    # Un retardataire rejoint la salle : il est aussi inscrit au jeu en cours
    z = TestClient(main.app)
    z.post(f"/api/games/{code}", json={"guest_id": "room-late-0001", "name": "Zoé", "action": "join"})
    assert any(p["name"] == "Zoé" for p in z.get(f"/api/games/{cur['code']}?guest_id=room-late-0001").json()["players"])
    # Fin du jeu : retour à la salle, le jeu figure dans l'historique de la soirée
    main.store.session.games[cur["code"]]["tally"] = {"room-other-001": {"drink": 3, "give": 1}}
    h.post(f"/api/games/{cur['code']}", json={"guest_id": "room-host-0001", "action": "end"})
    back = o.get(f"/api/games/{code}?guest_id=room-other-001").json()["room_info"]
    assert back["current"] is None and back["history"][0]["type"] == "biskit"
    assert next(b for b in back["board"] if b["name"] == "Léa")["drink"] == 3
    # Passer la main dans la salle : le nouvel animateur l'est aussi du jeu suivant
    lea = next(p["pid"] for p in back and o.get(f"/api/games/{code}?guest_id=room-other-001").json()["players"] if p["name"] == "Léa")
    h.post(f"/api/games/{code}", json={"guest_id": "room-host-0001", "action": "handover", "target": lea})
    v = o.post(f"/api/games/{code}", json={"guest_id": "room-other-001", "action": "launch", "settings": {"type": "quiz"}}).json()
    q = o.get(f"/api/games/{v['room_info']['current']['code']}?guest_id=room-other-001").json()
    assert q["is_owner"] and any(p["name"] == "Ludo" for p in q["players"])  # l'ancien animateur joue encore


@pytest.mark.parametrize("n, wanted, white, expected", [(6, 2, False, 2), (6, 3, False, 2), (5, 3, True, 1), (9, 0, False, 2), (4, 1, False, 1)])
def test_undercover_impostor_count_option(n, wanted, white, expected):
    """Nombre d'imposteurs choisi (0 = auto), plafonné pour que les civils restent majoritaires."""
    g = games.new_game("undercover", white=white)
    g["options"]["impostors"] = wanted
    for i in range(n):
        games.join(g, f"p{i}")
    games.start(g, random.Random(3))
    assert len(by_role(g, "undercover")) == expected
    assert len(by_role(g, "civil")) > len(by_role(g, "undercover")) + len(by_role(g, "white"))


def test_undercover_reveal_and_hint_options():
    g = games.new_game("undercover", white=True)
    g["options"].update(reveal=True, hint=True, white_hint=True)
    for i in range(6):
        games.join(g, f"p{i}")
    games.start(g, random.Random(2))
    hint = g["words"]["hint"]
    assert hint
    under, white, civil = by_role(g, "undercover")[0], by_role(g, "white")[0], by_role(g, "civil")[0]
    assert games.view(g, under)["me"]["role"] == "Undercover" and games.view(g, under)["me"]["hint"] == hint
    assert games.view(g, white)["me"]["role"] == "Mr. White" and games.view(g, white)["me"]["hint"] == hint
    assert games.view(g, civil)["me"]["role"] is None and games.view(g, civil)["me"]["hint"] is None
    g["options"].update(reveal=False)  # sans révélation : l'imposteur ne sait rien, et n'a donc pas d'indice
    assert games.view(g, under)["me"]["role"] is None and games.view(g, under)["me"]["hint"] is None
    assert games.view(g, white)["me"]["hint"] == hint  # l'indice de Mr. White est un réglage à part
    g["options"].update(white_hint=False, reveal=True)
    assert games.view(g, white)["me"]["hint"] is None and games.view(g, under)["me"]["hint"] == hint


def test_undercover_options_from_api():
    c = TestClient(main.app)
    r = c.post("/api/games", json={"guest_id": "uc-opts-host-01", "name": "Ludo", "type": "undercover",
                                   "impostors": 9, "reveal": True, "hint": True, "white_hint": True}).json()
    g = main.store.session.games[r["code"]]
    assert g["options"]["impostors"] == 3 and g["options"]["reveal"] and g["options"]["hint"] and g["options"]["white_hint"]


def test_word_pairs_all_have_a_hint():
    assert all(len(t) == 3 and all(x.strip() for x in t) for t in games.WORD_PAIRS)


def test_question_banks_are_large_distinct_and_do_not_repeat():
    """« Qui de nous ? » compare les joueurs, « Je n'ai jamais » parle d'expériences : deux banques distinctes et assez grandes."""
    for kind, (modes, _) in games.QUESTION_GAMES.items():
        for mode, (_, pool) in modes.items():
            assert len(pool) >= 120 and len(set(pool)) == len(pool), (kind, mode)
    whoof = set(games.WHOOF_MODES["mix"][1])
    assert not [q for q in whoof if q.startswith(("a déjà", "s'est déjà", "est déjà"))]
    g = games.new_game("never")
    for i in range(2):
        games.join(g, f"p{i}")
    games.start(g, random.Random(4))
    seen = [g["question"]]
    for _ in range(119):
        games.next_step(g, random.Random(len(seen)))
        seen.append(g["question"])
    assert len(set(seen)) == 120  # pas de répétition sur les 120 premières questions d'une partie
