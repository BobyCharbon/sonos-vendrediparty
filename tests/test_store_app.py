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
    assert set(main.STORE_HIDDEN_GAMES) == {"casino", "blackjack", "beerpong", "biskit", "purity"}  # Pyramide : en points
    for kind in main.STORE_HIDDEN_GAMES:
        r = create(STORE_UA, kind, f"store-{kind}")
        assert r.status_code == 403 and r.json()["detail"] == MESSAGE  # jamais « ouvre-le sur le site »
    assert create(STORE_UA, "whoof", "store-ok").status_code == 200


def test_other_apps_keep_every_game():
    for i, ua in enumerate((BETA_UA, WEB_UA)):
        for kind in ("blackjack", "biskit", "beerpong"):
            assert create(ua, kind, f"guest-{kind}-{i}").status_code == 200


def test_a_game_created_by_the_store_app_counts_points_and_never_has_hot_questions():
    """Décision de l'admin du 25.11 : dans l'app, les « gorgées » sont des ⭐ points (la page les affiche ainsi) ;
    la partie est marquée `store` (questions filtrées) et n'a jamais de mode Hot / Mix."""
    g = create(STORE_UA, "whoof", "store-sips", sips=3, mode="hot").json()
    raw = main.store.session.games[g["code"]]
    assert raw["store"] and raw["options"]["sips"] == 3 and raw["options"]["mode"] == "soft"
    assert client(STORE_UA).get(f"/api/games/{g['code']}?guest_id=store-sips").status_code == 200
    py = create(STORE_UA, "pyramid", "store-pyr1").json()
    assert main.store.session.games[py["code"]]["store"]


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
    started = main.store.session.games[create(WEB_UA, "never", "web-host-a").json()["code"]]
    started["phase"] = "question"
    assert client(STORE_UA).get(f"/api/games/{started['code']}?guest_id=store-p1").status_code == 403
    lobby = main.store.session.games[create(WEB_UA, "never", "web-host-b", mode="awkward").json()["code"]]
    assert client(STORE_UA).get(f"/api/games/{lobby['code']}?guest_id=store-p1").status_code == 200
    assert lobby["store"]  # la suite est tirée sans boisson
    web_pyr = main.store.session.games[create(WEB_UA, "pyramid", "web-host-c").json()["code"]]
    web_pyr["phase"] = "deal"  # Pyramide lancée sur le web : des gorgées, jamais ouverte à l'app
    assert client(STORE_UA).get(f"/api/games/{web_pyr['code']}?guest_id=store-p1").status_code == 403


def test_store_app_cannot_launch_hidden_games_from_a_game_room():
    room = create(STORE_UA, "room", "store-room-1").json()
    for kind in ("blackjack", "biskit", "beerpong"):
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
                                                                "settings": {"type": "never", "sips": 2, "mode": "hot"}})
    assert r.status_code == 200
    child = main.store.session.games[room["current"]]
    assert child["store"] and child["options"]["mode"] == "soft"  # ses 2 « gorgées » : des points dans l'app
    assert client(STORE_UA).get(f"/api/games/{child['code']}?guest_id=store-p").status_code == 200
    main.end_game(child["code"], "host")
    r = client(WEB_UA).post(f"/api/games/{room['code']}", json={"guest_id": "web-room", "action": "launch",
                                                                "settings": {"type": "pyramid"}})
    assert r.status_code == 200 and main.store.session.games[room["current"]]["store"]  # Pyramide en points


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
    likely.configure(lk, {"packs": ["family", "friends"]})
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
        assert create(STORE_UA, "whoof", "store-guest-01").status_code == 200, i
    web = [create(WEB_UA, "whoof", "web-guest-001").status_code for _ in range(3)]
    assert web[:2] == [200, 200] and web[2] == 403
    # Une partie web rejointe depuis l'app : pas de plafond non plus.
    code = create(WEB_UA, "whoof", "web-host-xyz").json()["code"]
    r = client(STORE_UA).post(f"/api/games/{code}", json={"guest_id": "store-guest-01", "action": "join", "name": "Léa"})
    assert r.status_code == 200, r.text
