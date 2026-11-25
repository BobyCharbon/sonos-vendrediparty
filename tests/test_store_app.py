"""App VendrediParty de l'App Store (« PartyStore ») : sans jeux d'argent simulés (Casino, Blackjack, 05.11) et, depuis le
refus Apple 1.4.3 du 25.11, sans jeu à boire, gorgée, boisson, drogue ni mode Hot. C'est le SERVEUR qui le garantit
(app/store_app.py) : création, salle, code / QR, lecture. Le site, l'app BETA et Android gardent tout."""
import random

import pytest
from fastapi.testclient import TestClient

from app import debate, games, likely, main, quiz, store_app

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
BETA_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0"
WEB_UA = "Mozilla/5.0 Safari"
MESSAGE = "Ce jeu n'est pas disponible dans l'app."


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    """Parties des autres tests : le plafond de 30 parties ou de 5 créations par adresse serait atteint."""
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


def client(ua, **headers):
    return TestClient(main.app, headers={"User-Agent": ua, **headers})


def create(ua, kind, gid, **options):
    main._game_creations.clear()
    return client(ua).post("/api/games", json={"guest_id": gid, "name": "Léa", "type": kind, **options})


def test_store_app_cannot_open_the_hidden_games():
    # Décision de l'admin du 25.11 : tous les jeux à boire par leur origine ou leur mécanique sont BLOQUÉS en 1.0.0.
    assert set(main.STORE_HIDDEN_GAMES) == {"casino", "blackjack", "beerpong", "biskit", "purity", "pyramid", "never",
                                            "whoof", "roulette"}
    for kind in main.STORE_HIDDEN_GAMES:
        r = create(STORE_UA, kind, f"store-{kind}")
        assert r.status_code == 403 and r.json()["detail"] == MESSAGE  # jamais « ouvre-le sur le site »
    assert create(STORE_UA, "likely", "store-ok").status_code == 200


def test_other_apps_keep_every_game():
    for i, ua in enumerate((BETA_UA, WEB_UA)):
        for kind in ("blackjack", "biskit", "beerpong", "pyramid", "never", "whoof", "roulette"):
            assert create(ua, kind, f"guest-{kind}-{i}").status_code == 200


def test_a_game_created_by_the_store_app_has_no_drinks_no_points_mode_and_no_hidden_theme():
    """Décision de l'admin du 25.11 : dans l'app, AUCUNE gorgée ni « mode points » qui les remplacerait (sips toujours 0),
    ni thème WTF, ni paquet « Entre amis » ; la partie est marquée `store` (questions filtrées)."""
    g = create(STORE_UA, "likely", "store-sips", sips=3, cats=["family", "friends"]).json()
    raw = main.store.session.games[g["code"]]
    assert raw["store"] and raw["options"]["sips"] == 0 and raw["likely"]["packs"] == ["family"]
    view = client(STORE_UA).get(f"/api/games/{g['code']}?guest_id=store-sips").json()
    assert [p["id"] for p in view["likely"]["pack_list"]] == ["family"] and view["likely"]["max_sips"] == 0
    qz = main.store.session.games[create(STORE_UA, "quiz", "store-qz1", sips=1).json()["code"]]
    assert qz["options"]["sips"] == 0
    db = main.store.session.games[create(STORE_UA, "debate", "store-db1", cats=["light", "wtf"]).json()["code"]]
    assert db["debate"]["themes"] == ["light"]
    themes = client(STORE_UA).get(f"/api/games/{db['code']}?guest_id=store-db1").json()["debate"]["theme_list"]
    assert "wtf" not in {t["id"] for t in themes}
    # Réglages refusés ensuite (403, même message), même par un téléphone du web dans une partie de l'app.
    for code, gid, settings, action in ((g["code"], "store-sips", {"sips": 2}, "lkset"), (g["code"], "store-sips", {"packs": ["friends"]}, "lkset"),
                                        (db["code"], "store-db1", {"themes": ["wtf"]}, "dbset")):
        for ua in (STORE_UA, WEB_UA):
            r = client(ua).post(f"/api/games/{code}", json={"guest_id": gid, "action": action, "settings": settings})
            assert r.status_code == 403 and r.json()["detail"] == MESSAGE, (action, settings, r.text)
    assert raw["options"]["sips"] == 0 and raw["likely"]["packs"] == ["family"]
    # Le web, lui, garde gorgées et thème WTF.
    web = main.store.session.games[create(WEB_UA, "likely", "web-sips", sips=2).json()["code"]]
    assert web["options"]["sips"] == 2 and not web.get("store")


@pytest.mark.parametrize("options", [{"type": "never", "sips": 1}, {"type": "whoof", "sips": 2}, {"type": "quiz", "sips": 1},
                                     {"type": "whoof", "mode": "hot"}, {"type": "never", "mode": "mix"},
                                     {"type": "likely", "sips": 1}])
def test_store_app_cannot_see_or_join_a_drinking_or_hot_game_opened_on_the_web(options):
    g = create(WEB_UA, options.pop("type"), "web-host", **options).json()
    code = g["code"]
    r = client(STORE_UA).get(f"/api/games/{code}?guest_id=store-p1")
    assert r.status_code == 403 and r.json()["detail"] == MESSAGE
    r = client(STORE_UA).post(f"/api/games/{code}", json={"guest_id": "store-p1", "action": "join", "name": "Léa"})
    assert r.status_code == 403
    assert client(WEB_UA).get(f"/api/games/{code}?guest_id=web-host").status_code == 200  # le web, lui, la garde


def test_store_app_cannot_view_or_join_a_casino_opened_elsewhere():
    g = create(BETA_UA, "casino", "web-host-1").json()
    assert client(STORE_UA).get(f"/api/games/{g['code']}?guest_id=store-p1").status_code == 403
    r = client(STORE_UA).post(f"/api/games/{g['code']}", json={"guest_id": "store-p1", "action": "join", "name": "Léa"})
    assert r.status_code == 403


def test_a_web_game_already_running_without_the_filter_is_refused_but_a_lobby_is_cleaned():
    started = main.store.session.games[create(WEB_UA, "likely", "web-host-a").json()["code"]]
    started["phase"] = "ask"
    assert client(STORE_UA).get(f"/api/games/{started['code']}?guest_id=store-p1").status_code == 403
    lobby = main.store.session.games[create(WEB_UA, "likely", "web-host-b", cats=["family", "friends"]).json()["code"]]
    assert client(STORE_UA).get(f"/api/games/{lobby['code']}?guest_id=store-p1").status_code == 200
    assert lobby["store"] and lobby["likely"]["packs"] == ["family"]  # la suite est tirée sans boisson
    masque_game = main.store.session.games[create(WEB_UA, "masque", "web-host-m").json()["code"]]
    assert client(STORE_UA).get(f"/api/games/{masque_game['code']}?guest_id=store-p1").status_code == 200
    assert masque_game["store"]  # textes écrits filtrés pour la suite
    # Pyramide créée sur le web (des gorgées) : jamais ouverte à l'app, même en salle d'attente (contrôle final du 25.11).
    web_pyr = main.store.session.games[create(WEB_UA, "pyramid", "web-host-c").json()["code"]]
    assert web_pyr["phase"] == "lobby"
    assert client(STORE_UA).get(f"/api/games/{web_pyr['code']}?guest_id=store-p1").status_code == 403
    r = client(STORE_UA).post(f"/api/games/{web_pyr['code']}", json={"guest_id": "store-p1", "action": "join", "name": "Léa"})
    assert r.status_code == 403 and not web_pyr.get("store")


def test_store_app_cannot_launch_hidden_games_from_a_game_room():
    room = create(STORE_UA, "room", "store-room-1").json()
    for kind in ("blackjack", "biskit", "beerpong", "pyramid", "never", "whoof", "roulette"):
        r = client(STORE_UA).post(f"/api/games/{room['code']}", json={"guest_id": "store-room-1", "action": "launch",
                                                                      "settings": {"type": kind}})
        assert r.status_code == 403


def test_a_room_joined_by_the_store_app_never_shows_a_hidden_game():
    """Salle ouverte sur le web, Biskit lancé, puis l'app App Store entre : ni « en cours », ni « déjà joué », ni
    catalogue, ni votes, ni gorgées ; et le web ne peut plus y lancer un jeu caché."""
    room = main.store.session.games[create(WEB_UA, "room", "web-room").json()["code"]]
    games.join(room, "voter", "Tom")
    games.room_vote(room, "voter", "biskit")
    room["rhistory"].append({"type": "beerpong", "name": "Beer pong", "at": 0, "players": 2, "winner": None})
    room["rtally"]["web-room"] = {"drink": 4, "give": 2}
    r = client(WEB_UA).post(f"/api/games/{room['code']}", json={"guest_id": "web-room", "action": "launch",
                                                                "settings": {"type": "biskit"}})
    assert r.status_code == 200
    seen = client(STORE_UA).get(f"/api/games/{room['code']}?guest_id=store-p").json()["room_info"]
    assert seen["current"] is None and not seen["history"] and "biskit" not in seen["votes"] and not seen["top"]
    assert not {c["type"] for c in seen["catalog"]} & set(store_app.HIDDEN_GAMES)
    assert all(not r["drink"] and not r["give"] for r in seen["board"])
    assert client(STORE_UA).get(f"/api/games/{room['current']}?guest_id=store-p").status_code == 403
    main.end_game(room["current"], "host")
    r = client(WEB_UA).post(f"/api/games/{room['code']}", json={"guest_id": "web-room", "action": "launch",
                                                                "settings": {"type": "beerpong"}})
    assert r.status_code == 403
    r = client(WEB_UA).post(f"/api/games/{room['code']}", json={"guest_id": "web-room", "action": "launch",
                                                                "settings": {"type": "likely", "sips": 2, "cats": ["family", "friends"]}})
    assert r.status_code == 200
    child = main.store.session.games[room["current"]]
    assert child["store"] and child["options"]["sips"] == 0 and child["likely"]["packs"] == ["family"]  # aucune gorgée
    assert client(STORE_UA).get(f"/api/games/{child['code']}?guest_id=store-p").status_code == 200
    main.end_game(child["code"], "host")
    for kind in ("pyramid", "never", "whoof", "roulette"):
        r = client(WEB_UA).post(f"/api/games/{room['code']}", json={"guest_id": "web-room", "action": "launch",
                                                                    "settings": {"type": kind}})
        assert r.status_code == 403, kind


# ── Textes tirés dans une partie de l'app App Store : jamais une boisson, une ivresse ni une drogue ──

def store_game(kind, **opts):
    g = games.new_game(kind, "h", "Hôte", **opts)
    for i in range(6):
        games.join(g, f"p{i}", f"Joueur {i}")
    store_app.flag(g)
    return g


def test_store_questions_of_never_and_whoof_never_talk_about_drinking():
    for kind in ("never", "whoof"):
        g = store_game(kind, mode="awkward")
        seen = set()
        for _ in range(400):
            games._next_question(g, random)
            seen.add(g["question"])
        assert seen and not [q for q in seen if store_app.drinky(q)]
    web = games.new_game("never", "h", "Hôte", mode="awkward")
    assert any(store_app.drinky(q) for q in games.NEVER_AWKWARD)  # le web garde ses phrases
    assert web["options"]["mode"] == "awkward"


def test_store_undercover_words_likely_tmc_divan_debate_quiz_are_clean():
    rng = random.Random(1)
    g = store_game("undercover")
    for _ in range(200):
        games.start(g, rng)
        assert not store_app.drinky(" ".join(g["words"].values()))
    lk = store_game("likely")
    likely.configure(lk, {"packs": ["family"]})
    assert not [q for q in likely._pool(lk["likely"]) if store_app.drinky(q)]
    tm = store_game("tmc")
    assert not [q for q in (games._tmc_question(tm, rng) for _ in range(400)) if store_app.drinky(q)]
    dv = store_game("divan")
    for _ in range(300):
        games._divan_draw(dv, rng)
        assert not store_app.drinky(dv["divan"]["card"]["text"])
    db = store_game("debate")
    debate.configure(db, {"themes": list(debate.THEMES)})
    db["debate"]["store"] = True
    for _ in range(300):
        assert not store_app.drinky(debate._draw(db["debate"], rng, bank_only=True)["text"])
    qz = store_game("quiz")
    assert not [q for q in quiz._pool(qz, "") if store_app.drinky(" ".join([q["q"], q["a"], *q["w"]]))]


def test_undercover_is_now_the_intruder_with_a_ghost():
    assert games.GAMES["undercover"] == "L'Intrus"
    assert games.ROLE_LABELS == {"civil": "Civil", "undercover": "Intrus", "white": "Fantôme"}


# ── Bar et écrans natifs ──

def test_bar_is_off_for_the_store_app_and_native_calls_in_production(monkeypatch):
    monkeypatch.setenv("BAR_ENABLED", "1")
    monkeypatch.delenv("PARTY_PUBLIC_URL", raising=False)
    assert client(WEB_UA).get("/api/features").json()["bar"] is True
    assert client(STORE_UA).get("/api/features").json()["bar"] is False
    # Écrans natifs de l'app (PartyAPI.swift : seulement « X-Party-Native: ios ») : en production, c'est l'app App Store.
    assert client("Party/1 CFNetwork", **{"X-Party-Native": "ios"}).get("/api/features").json()["bar"] is False
    assert 'data-bar="off"' in client(STORE_UA).get("/").text
    assert 'data-bar="off"' not in client(WEB_UA).get("/").text
    # Site de test : la BETA garde tout (elle ne parle jamais à la prod).
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://partytest.bobycharbon.ch")
    assert client("Party/1 CFNetwork", **{"X-Party-Native": "ios"}).get("/api/features").json()["bar"] is True


def test_events_module_page_has_no_bar_for_the_store_app(monkeypatch, tmp_path):
    monkeypatch.setenv("BAR_ENABLED", "1")
    (tmp_path / "index.html").write_text("<!doctype html><html lang=fr><head></head><body></body></html>")
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path)
    store_page, web_page = client(STORE_UA).get("/events/").text, client(WEB_UA).get("/events/").text
    assert 'data-bar="off"' in store_page and 'data-store="1"' in store_page  # data-store : emojis 🍻 🍷 des groupes cachés
    assert 'data-bar="off"' not in web_page and "data-store" not in web_page


def test_native_chats_show_no_drink_emoji_to_the_store_app():
    data = {"chats": [{"kind": "group", "emoji": "🍻"}, {"kind": "group", "emoji": "⚽"}], "group": {"emoji": "🍷"}}
    assert store_app.neutral_emojis(data) == {"chats": [{"kind": "group", "emoji": "🎉"}, {"kind": "group", "emoji": "⚽"}],
                                              "group": {"emoji": "🎉"}}


def test_store_app_guests_play_without_limit_while_the_web_keeps_its_cap(monkeypatch, tmp_path):
    """Décision de l'admin du 25.11 : dans l'app App Store, les jeux restent illimités en invité ; le web garde le plafond
    (ici 2 parties) ; le compte reste exigé ailleurs (événements, groupes, discussions)."""
    from app.guest_gate import GuestGate
    gate = GuestGate(tmp_path / "g.json")
    gate.set_settings(games=2)
    monkeypatch.setattr(main, "guest_gate", gate)
    monkeypatch.setattr(main, "_store_guests", set())
    for i in range(4):
        assert create(STORE_UA, "likely", "store-guest-01").status_code == 200, i
    web = [create(WEB_UA, "likely", "web-guest-001").status_code for _ in range(3)]
    assert web[:2] == [200, 200] and web[2] == 403
    # Une partie web rejointe depuis l'app : pas de plafond non plus.
    code = create(WEB_UA, "likely", "web-host-xyz").json()["code"]
    r = client(STORE_UA).post(f"/api/games/{code}", json={"guest_id": "store-guest-01", "action": "join", "name": "Léa"})
    assert r.status_code == 200, r.text


def test_the_filter_also_catches_vomit_cheers_beer_and_bottles():
    for text in ("J'ai déjà vomi en soirée", "Tchin-tchin !", "S'Beer", "vomir"):
        assert store_app.drinky(text), text
    assert not store_app.drinky("Soirée jeux de société")


# ── Test anti-alcool de TOUS les jeux (décision de l'admin du 25.11) : l'app n'en montre aucun mot ; le web garde tout ──

def _texts(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _texts(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _texts(v)


def test_every_game_of_the_app_draws_nothing_about_drinking_and_the_web_keeps_its_games():
    from app import divan_cards, psy, tmc_questions
    from app.masque_cards import MASQUE_CARDS, REFLET_CARDS
    from app.quizbank import BANK, THEMES
    kept = [t for t in games.GAMES if t not in store_app.HIDDEN_GAMES]
    assert set(kept) >= {"likely", "quiz", "undercover", "president", "debate", "divan", "tmc", "masque", "reflet", "psy",
                         "neon", "island", "heist", "room"}
    assert not [games.GAMES[t] for t in kept if store_app.drinky(games.GAMES[t])]
    # Banques filtrées dans une partie de l'app (store_app.clean) : la version de l'app ne garde aucune phrase « à boire ».
    banks = {
        "likely": [q for p, (_, qs) in likely.PACKS.items() if p not in store_app.HIDDEN_PACKS for q in qs],
        "debate": [q for t, (_, qs) in debate.THEMES.items() if t not in store_app.HIDDEN_THEMES for q in qs],
        "divan": [q for qs in divan_cards.DIVAN_CARDS.values() for q in qs],
        "tmc": list(tmc_questions.TMC_QUESTIONS),
        "undercover": [" ".join(p) for p in games.WORD_PAIRS],
        "quiz": [" ".join([q["q"], q["a"], *q["w"]]) for t in THEMES for q in BANK.get(t, [])],
    }
    banks["masque"] = [c[2] for c in MASQUE_CARDS]  # tour 2 : « si c'était une boisson ? » (deck filtré dans l'app)
    for kind, bank in banks.items():
        shown = store_app.clean(bank)
        assert len(shown) > len(bank) // 2, kind  # le filtre n'a pas vidé la banque (sinon clean rendrait tout)
        assert not [t for t in shown if store_app.drinky(t)], kind
    # Banques non filtrées (Reflet, Qui es-tu vraiment ?) : propres telles quelles.
    for kind, bank in (("reflet", REFLET_CARDS),
                       ("psy", [getattr(psy, a) for a in dir(psy) if a.isupper()])):
        assert not [t for t in _texts(bank) if store_app.drinky(t)], kind
    # Le web garde ses jeux à boire et leurs textes (rien n'a changé pour lui).
    assert {"pyramid", "never", "whoof", "roulette", "beerpong", "biskit", "purity"} <= set(games.GAMES)
    assert any(store_app.drinky(q) for q in games.NEVER_AWKWARD) and any(store_app.drinky(q) for q in debate.THEMES["wtf"][1] + debate.THEMES["light"][1])


def test_phrases_found_by_the_judges_are_never_drawn_in_the_app():
    """Relu le 25.11 : apéritif, soirée arrosée, vin, tabac, casino, drogue dans les titres d'œuvres, ivresse sans le mot."""
    for text in ("Quel apéritif improvisé est devenu une soirée légendaire ?", "…après une soirée arrosée ?",
                 "vigneron ou vigneronne, ta cuvée ?", "les vendanges", "Poker / Blackjack, un jeu de cartes de casino",
                 "Faut-il taxer la viande comme le tabac ?", "De quel pays vient le cognac ?", "De quel pays vient la Guinness ?",
                 "Quel fruit rouge sert à faire le kir ?", "Comment appelle-t-on le chasselas en Valais ?",
                 "Dans quel pays se trouve la région viticole : Lavaux ?", "la damassine (eau-de-vie)",
                 "Dans quelle série un professeur de chimie devient trafiquant ?", "Breaking Bad", "Pablo Escobar",
                 "Je n'ai jamais été réveillé chez quelqu'un sans savoir comment j'y étais arrivé",
                 "Je n'ai jamais dormi dans ma voiture après une soirée", "Qui est le plus susceptible d'oublier comment il est rentré ?",
                 "le pot de départ", "la buvette", "à quelle heure la boirait-on ?"):
        assert store_app.drinky(text), text
    for name in ("Marc", "Léa", "Mirabelle", "Jean-Marc", "Ginette", "contournées"):
        assert not store_app.drinky(name), name


def test_texts_typed_by_players_in_an_app_game_never_mention_drinking():
    g = store_game("likely")
    with pytest.raises(games.GameError, match="pas accepté"):
        games.add_guest(g, "Vodka")
    games.add_guest(g, "Marc")
    web = games.new_game("likely", "h", "Hôte")
    games.add_guest(web, "Vodka")  # le web garde son filtre habituel seulement
    db = store_game("debate")
    with pytest.raises(debate.DebateError, match="pas accepté"):
        debate.propose(db, "p0", "Faut-il offrir des shots à tout le monde ce soir ?")


def test_new_music_party_codes_have_six_digits_and_old_four_digit_codes_still_work(monkeypatch):
    monkeypatch.setattr(main.store, "save", lambda *a, **k: None)
    old = main.store.session.guest_pin
    try:
        pin = main.store.regenerate_pin()
        assert len(pin) == 6 and pin.isdigit()
        main.store.regenerate_pin("4321")  # ancien code choisi par l'hôte : accepté (web)
        assert client(WEB_UA).post("/api/join", json={"pin": "4321"}).status_code == 200
    finally:
        main.store.session.guest_pin = old


def test_shared_expenses_never_show_a_drink_emoji_in_the_app():
    from app import tricount_logic as tc
    assert tc.CATEGORIES["drinks"][1] == "🥤" and tc.CATEGORIES["health"][1] == "🩺"
    assert main.store_emoji("🍻", type("R", (), {"headers": {"user-agent": STORE_UA}})()) == "🎉"
    assert main.store_emoji("🍻", type("R", (), {"headers": {"user-agent": WEB_UA}})()) == "🍻"


def test_every_game_the_app_can_open_shows_no_drink_word_in_its_view():
    """Tour 2 : chaque jeu gardé dans l'app, créé par l'app, puis lu par l'app (vue JSON complète, lobby) : aucun mot de
    boisson, de gorgée ni de drogue. Le web garde les mêmes jeux avec leurs gorgées."""
    for kind in [t for t in games.GAMES if t not in store_app.HIDDEN_GAMES and t != "room"]:
        gid = f"store-all-{kind}"
        r = create(STORE_UA, kind, gid)
        assert r.status_code == 200, (kind, r.text)
        view = client(STORE_UA).get(f"/api/games/{r.json()['code']}?guest_id={gid}").json()
        assert not [t for t in _texts(view) if store_app.drinky(t)], kind


def test_questions_asking_to_be_a_drink_are_never_drawn_in_the_app():
    from app import masque
    from app.masque_cards import MASQUE_CARDS
    for text in ("Si tu étais une boisson, laquelle serais-tu ?", "Ton état d'esprit de ce soir, si c'était une boisson ?"):
        assert store_app.drinky(text)
    g = store_game("masque")
    S = masque.state(g)
    S.update(cats=sorted({c[0] for c in MASQUE_CARDS}), levels=sorted({c[1] for c in MASQUE_CARDS}))
    assert not [i for i in masque.deck(S, True) if store_app.drinky(MASQUE_CARDS[i][2])]
    assert any(store_app.drinky(MASQUE_CARDS[i][2]) for i in masque.deck(S))  # le web garde sa carte
    assert "masque" in store_app.BANK_GAMES


def test_a_tmc_answer_can_be_reported_and_disappears_for_the_table(monkeypatch):
    logged = []
    monkeypatch.setattr(main, "log_game_report", lambda g, me, res, req: logged.append(res))
    code = create(STORE_UA, "tmc", "store-tmc-host").json()["code"]
    c = client(STORE_UA)
    for gid in ("store-tmc-b", "store-tmc-c"):
        assert c.post(f"/api/games/{code}", json={"guest_id": gid, "name": gid, "action": "join"}).status_code == 200
    g = main.store.session.games[code]
    games.tmc_next(g, random.Random(1))
    d = g["tmc"]["duo"]
    games.tmc_answer(g, d["subject"], "Une réponse vexante")
    games.tmc_reveal(g, d["subject"])
    other = next(p["id"] for p in g["players"] if p["id"] != d["subject"])
    view = c.get(f"/api/games/{code}?guest_id={other}").json()["tmc"]["duo"]
    assert view["can_report"] and view["answer"] == "Une réponse vexante"
    assert not c.get(f"/api/games/{code}?guest_id={d['subject']}").json()["tmc"]["duo"]["can_report"]
    r = c.post(f"/api/games/{code}", json={"guest_id": other, "action": "treport"})
    assert r.status_code == 200, r.text
    view = c.get(f"/api/games/{code}?guest_id={other}").json()["tmc"]["duo"]
    assert view["reported"] and view["answer"] is None and not view["can_report"]
    assert logged == [{"text": "Une réponse vexante", "author": d["subject"]}]
    with pytest.raises(games.GameError):
        games.tmc_report(g, d["subject"])


def test_pronos_agenda_and_drink_tags_stay_off_for_the_store_app(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "pronos_enabled", lambda: True)
    monkeypatch.setattr(main, "agenda_enabled", lambda: True)
    monkeypatch.setattr(main, "patates_enabled", lambda: True)
    store = client(STORE_UA).get("/api/features").json()
    assert (store["pronos"], store["agenda"], store["patates"]) == (False, False, False)
    web = client(WEB_UA).get("/api/features").json()
    assert (web["pronos"], web["agenda"], web["patates"]) == (True, True, True)
    assert client(STORE_UA).post("/api/account/pronos/rpc", json={}).status_code == 404
    assert client(STORE_UA).post("/api/account/agenda/rpc", json={}).status_code == 404
    html = main.features_page("<html><body></body></html>", True)
    assert 'data-pronos="off"' in html and 'data-agenda="off"' in html
    rows = {"categories": [{"name": "Soirées"}, {"name": "Apéro"}], "tags": [{"name": "bar"}, {"name": "sport"}],
            "category_ids": [], "tag_ids": []}
    monkeypatch.setattr(main.accounts, "subscriptions", lambda token: {k: list(v) for k, v in rows.items()})
    out = client(STORE_UA).post("/api/account/subscriptions", json={"token": "t"}).json()
    assert [t["name"] for t in out["tags"]] == ["sport"] and [c["name"] for c in out["categories"]] == ["Soirées"]
    assert len(client(WEB_UA).post("/api/account/subscriptions", json={"token": "t"}).json()["tags"]) == 2


def test_music_songs_never_need_an_account_in_the_store_app(monkeypatch):
    monkeypatch.setattr(main.guest_gate, "settings", lambda: {"tracks": 0, "games": 3})
    store_req = type("R", (), {"headers": {"user-agent": STORE_UA}})()
    web_req = type("R", (), {"headers": {"user-agent": WEB_UA}})()
    monkeypatch.setattr(main, "is_admin", lambda r: False)
    assert main.guest_tracks("guest-x", store_req) is None
    assert main.guest_tracks("guest-x", web_req)["left"] == 0


def test_support_page_and_app_versions_of_terms_and_privacy_for_the_store_listing(monkeypatch, tmp_path):
    r = client(WEB_UA).get("/support")
    assert r.status_code == 200 and "support@vendrediparty.ch" in r.text and "établi en France" in r.text
    assert "http" not in r.text.split("<body>")[1].replace("mailto:", "")  # aucune ressource ni lien externe
    assert not store_app.drinky(r.text) and "Pronos" not in r.text and "suisse" not in r.text.lower()
    (tmp_path / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path)
    for path in ("terms?app=ios", "privacy?app=ios"):
        assert 'data-store="1"' in client(WEB_UA).get(f"/events/{path}").text
    assert 'data-store="1"' not in client(WEB_UA).get("/events/terms").text
    assert 'data-store="1"' not in client(WEB_UA).get("/events/groups?app=ios").text
    import json
    from pathlib import Path
    meta = json.loads((Path(__file__).resolve().parents[1] / "ios/appstore/metadata-fr.json").read_text(encoding="utf-8"))
    assert meta["supportUrl"].endswith("/support") and meta["privacyPolicyUrl"].endswith("/events/privacy?app=ios")
