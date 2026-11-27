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
    return client(ua).post("/api/games", json={"guest_id": gid, "name": "Léa", "type": kind, "terms": True, **options})


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
    assert all("drink" not in r and "give" not in r for r in seen["board"])  # app : aucun compte de gorgées (26.11)
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
    r = client(STORE_UA).post(f"/api/games/{code}", json={"guest_id": "store-guest-01", "action": "join", "name": "Léa", "terms": True})
    assert r.status_code == 200, r.text


def test_the_filter_also_catches_vomit_cheers_beer_and_bottles():
    for text in ("J'ai déjà vomi en soirée", "Tchin-tchin !", "S'Beer", "vomir"):
        assert store_app.drinky(text), text
    assert not store_app.drinky("Soirée jeux de société")


def test_the_filter_catches_everyday_party_drink_and_tobacco_words():
    """Tour 6 : titres d'événement publics qui passaient le filtre (1.4.3 cite aussi le tabac) ; même liste côté écran."""
    for text in ("Happy hour du vendredi", "Afterwork au bureau", "After-work", "Une pinte au pub", "Oktoberfest 2027",
                 "Ti-punch party", "Binouze entre potes", "Pub crawl à Lyon", "Margarita night", "Soirée shooters",
                 "Soirée Ricard", "Soirée Heineken", "Soirée chicha", "Narguilé au parc", "Soirée Jäger", "Pils et IPA",
                 "On vapote ensemble", "Puff party", "Helemaal verknipt", "Een asbak op tafel"):
        assert store_app.drinky(text), text
    for text in ("Soirée jeux de société", "Pique-nique", "Rendez-vous au parc", "Soirée pyjama", "Publication"):
        assert not store_app.drinky(text), text
    ts = (__import__("pathlib").Path(main.__file__).resolve().parents[1] / "web/events/src/lib/storeEvents.ts").read_text()
    for word in ("happy hour", "after-?work", "oktoberfest", "binouze", "chicha", "narguil[ée]", "heineken", r"\\bricard\\b",
                 "verknipt", "asbak"):
        assert f"'{word}'" in ts, word


def test_push_of_the_app_store_app_uses_exactly_the_same_drink_words():
    """Contrôle Apple du 26.11 : send-push neutralise une notification « à boisson » pour l'app App Store, avec
    EXACTEMENT DRINK_RE (copie dans l'Edge Function, Deno)."""
    ts = (__import__("pathlib").Path(main.__file__).resolve().parents[1] / "supabase/functions/send-push/apns.ts").read_text()
    assert "const DRINK_PY = String.raw`" + store_app.DRINK_RE.pattern + "`;" in ts
    index = (__import__("pathlib").Path(main.__file__).resolve().parents[1] / "supabase/functions/send-push/index.ts").read_text()
    assert "storeAppText(apns.topic, row.title, row.body)" in index and "text.title, text.body" in index


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
        assert c.post(f"/api/games/{code}", json={"guest_id": gid, "name": gid, "action": "join", "terms": True}).status_code == 200
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


def test_round_three_no_purify_stats_in_the_app_and_the_web_keeps_them():
    # « Mes stats de jeu » : le Purify Test (alcool, drogue) n'existe pas dans l'app, ni ses routes.
    html = (__import__("pathlib").Path(main.__file__).parent / "static/index.html").read_text(encoding="utf-8")
    assert "if (STORE_APP) document.querySelector('[data-stats-tab=\"purity\"]')?.remove();" in html
    assert 'let statsTab = STORE_APP ? "brain" : "purity";' in html
    assert client(STORE_UA).get("/api/purity/leaderboard").status_code == 404
    assert client(STORE_UA).post("/api/purity/me", json={"token": "x" * 40}).status_code == 404
    assert client(WEB_UA).get("/api/purity/leaderboard").status_code == 200


def test_round_three_a_game_report_reaches_the_admin_at_once(monkeypatch):
    sent = []
    monkeypatch.setattr(main, "notify_admin", lambda payload, kind="messages": sent.append((payload, kind)))
    monkeypatch.setattr(main.journal, "record", lambda *a, **k: None)
    monkeypatch.setattr(main, "client_ip", lambda request: "1.2.3.4")
    g = {"type": "tmc", "code": "4321", "players": [{"id": "a", "name": "Léa"}]}
    main.log_game_report(g, "a", {"text": "Une réponse vexante", "author": "a"}, None)
    assert sent and sent[0][1] == "feedback" and "Signalement" in sent[0][0]["title"]
    assert sent[0][0]["body"] == "Une réponse vexante"


def test_round_three_wallet_ticket_carries_the_issuer_contact(monkeypatch):
    from app import wallet
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://exemple.test")
    back = wallet._fields({"title": "Soirée"}, {"code": "ABCD"}, "Léa")["backFields"]
    contact = next(f for f in back if f["key"] == "contact")
    assert "support@vendrediparty.ch" in contact["value"] and "https://exemple.test/support" in contact["value"]
    assert "Ludovic Trombert" in contact["value"]


def test_round_three_texts_judged_risky_are_gone_from_the_app():
    # Divan : nuit de fête et son lendemain ; L'Intrus : jamais une autre plateforme mobile (2.3.10).
    assert store_app.drinky("Comment as-tu assuré le lendemain d'une fête qui a duré toute la nuit ?")
    assert not any("Android" in w for pair in games.WORD_PAIRS for w in pair)
    from app import assistant
    assert "vin" not in assistant.RECEIPT_SYSTEM.split("summary :", 1)[1].split("\n", 1)[0]


def test_round_three_share_extension_only_creates_an_event_in_the_store_app():
    root = __import__("pathlib").Path(main.__file__).resolve().parents[1] / "ios/PartyShare"
    model = (root / "ShareModel.swift").read_text(encoding="utf-8")
    assert "static var isStoreApp" in model and ".eventOffer" in model
    start = model.split("func start(shared: String) async {", 1)[1].split("func prepareEvent", 1)[0]
    assert start.index("if Self.isStoreApp") < start.index("api.search(query)")  # aucune recherche de titre


# ── Tour 4 (25.11) ──

def _root():
    return __import__("pathlib").Path(main.__file__).resolve().parents[1]


def test_round_four_quiz_of_the_app_names_no_other_phone_platform_and_the_web_keeps_it():
    """Apple 2.3.10 : dans l'app, le Quiz ne tire jamais une question qui cite Android ou un .apk ; le web garde tout."""
    text = lambda q: " ".join([q["q"], q["a"], *q["w"]])
    qz = store_game("quiz")
    shown = quiz._pool(qz, "")
    assert shown and not [q for q in shown if store_app.OTHER_PLATFORM_RE.search(text(q))]
    assert not [q for q in shown if store_app.drinky(text(q))]  # toujours sans alcool
    web = games.new_game("quiz", "h", "Hôte")
    assert any(store_app.OTHER_PLATFORM_RE.search(text(q)) for q in quiz._pool(web, ""))


def test_round_four_privacy_names_processor_guarantees_shared_expenses_and_what_stays_after_deletion():
    """Apple 5.1.1(i) et 5.1.1(v) : web et iPhone (prochain build) disent la même chose."""
    web = (_root() / "web/events/src/app/privacy.tsx").read_text(encoding="utf-8").replace("’", "'")
    ios = (_root() / "ios/Party/Settings/Account/SignInView.swift").read_text(encoding="utf-8")
    for text in (web, ios):
        assert "protection au moins égale à celle décrite dans cette politique" in text
        assert "Pot commun : les dépenses, les membres du pot" in text and "Party ne touche jamais l'argent" in text
        assert "Pot commun (dépenses, membres, photos de tickets) : jusqu'à la suppression de la dépense ou du pot" in text
        assert "Restent pour les autres, sans lien avec toi" in text and "les groupes que tu as créés" in text


def test_round_four_review_notes_present_an_app_for_everyone_and_nothing_dormant():
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    assert len(notes) <= 4000 and notes in guide
    assert "for anyone organising real-world events, chats and party games" in notes and "with friends" not in notes
    assert "group of friends" not in guide and "for friends:" not in notes
    assert "wait for our approval" not in notes and 'tick group "Démo Apple" > Publish: live at once' in notes
    assert "off for this app on our server" not in notes and "switched off for this app on our server" not in guide
    assert "would need a new review" in notes.split("Not in this version", 1)[1].split("\n", 1)[0]
    assert "see attached video" not in notes and "video" not in guide.split("PART B", 1)[1].lower()  # 26.11 : aucune vidéo
    assert "grouped as Général, Musique" not in guide
    checklist = (_root() / "docs/app-store/checklist-envoi.md").read_text(encoding="utf-8")
    assert "le bar « Soirée démo »" not in checklist


def test_round_four_age_rating_declares_every_answer_of_the_checklist():
    import json
    rating = json.loads((_root() / "ios/appstore/metadata-fr.json").read_text(encoding="utf-8"))["ageRating"]
    for key in ("profanityOrCrudeHumor", "sexualContentOrNudity", "violenceCartoonOrFantasy"):
        assert rating[key] == "INFREQUENT_OR_MILD", key
    assert rating["ageRatingOverrideV2"] == "EIGHTEEN_PLUS" and rating["gamblingSimulated"] == "NONE"


def test_round_four_nickname_prod_file_also_cleans_notifications_already_sent():
    apply = (_root() / "supabase/prod/2026-11-25-surnom-sans-logo-apply.sql").read_text(encoding="utf-8")
    rollback = (_root() / "supabase/prod/2026-11-25-surnom-sans-logo-rollback.sql").read_text(encoding="utf-8")
    body = apply.split("begin;", 1)[1]
    assert body.index("update public.notifications") < body.index("raise exception")
    assert "from public.notifications" in body.split("do $$", 1)[1]
    # Le retour arrière ne recopie JAMAIS le texte d'une notification (extraits de messages privés, dépôt public).
    assert "public.notifications" not in rollback and "efa3bf" in rollback
    # Pot commun : le nom d'un membre est une copie du surnom (pot « Cobalt Project Paintball » d'Apple-test).
    assert body.index("update public.tc_members") < body.index("raise exception")
    assert "from public.tc_members" in body.split("do $$", 1)[1] and "update public.tc_members" in rollback


def test_round_five_native_app_keeps_pronos_agenda_zicou_and_bar_off_whatever_the_server_says():
    store = (_root() / "ios/Party/Settings/SettingsStore.swift").read_text(encoding="utf-8")
    for flag in ("compagnon = !store &&", "bar = !store &&", "agendaOn = !store &&", "pronosOn = !store &&"):
        assert flag in store, flag
    assert "let store = AppConfig.storeLocked" in store
    config = (_root() / "ios/Party/AppConfig.swift").read_text(encoding="utf-8")
    assert "#if E2E_HOOKS\n        return false\n        #else\n        return isStoreApp" in config
    pot = (_root() / "ios/Party/Tricount/TricountGroupView.swift").read_text(encoding="utf-8")
    assert 'Label("Rembourser", systemImage: "arrow.uturn.left")' in pot and '"creditcard"' not in pot
    # Apple TV (même fiche) : aucune ligne « Boit » / « Distribue » / gorgées dans l'app App Store.
    tv = (_root() / "ios/PartyTV/Outcome.swift").read_text(encoding="utf-8")
    assert "$0.kind != .drink && $0.kind != .give" in tv
    cards = (_root() / "ios/PartyTV/CardGames.swift").read_text(encoding="utf-8")
    assert '!StoreGames.isStoreApp, let sips = P["step_sips"]' in cards and 'drink > 0 && !StoreGames.isStoreApp' in cards


def test_round_five_group_pronos_page_is_guarded_privacy_and_consent_are_exact():
    layout = (_root() / "web/events/src/app/_layout.tsx").read_text(encoding="utf-8")
    assert r"/^\/(?:prono|group\/[^/]+\/pronos)/" in layout
    import re
    guard = re.compile(r"^\/(?:prono|group\/[^/]+\/pronos)")
    assert guard.match("/group/ab637a9d-0000-0000-0000-000000000000/pronos") and guard.match("/prono/new")
    assert not guard.match("/group/ab637a9d-0000-0000-0000-000000000000/settings")
    for path in ("web/events/src/app/privacy.tsx", "ios/Party/Settings/Account/SignInView.swift"):
        text = (_root() / path).read_text(encoding="utf-8")
        assert "hébergé en Suisse" not in text and "hébergé en France" in text, path
        assert "où sont hébergés le serveur de Party" not in text, path
    for path in ("app/static/index.html", "web/events/src/lib/aiConsent.ts", "ios/Party/Feedback/FeedbackAI.swift"):
        assert "publié sur GitHub, où tout le monde peut le lire, puis lu par Claude, sans ton prénom ni ton numéro" in (_root() / path).read_text(encoding="utf-8"), path
    # Le texte a changé (GitHub public dit en clair) : un accord d'avant ne vaut plus (5.1.2(ii)).
    from app import ai_feedback
    assert ai_feedback.CONSENT_VERSION >= 4
    assert "static let consentVersion = 4" in (_root() / "ios/Party/Feedback/FeedbackAI.swift").read_text(encoding="utf-8")


def test_round_five_listing_notes_and_checklist():
    import json
    meta = json.loads((_root() / "ios/appstore/metadata-fr.json").read_text(encoding="utf-8"))
    assert "pour une bande d'amis" not in meta["description"] and "toutes tes soirées entre amis" in meta["description"]
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8")
    assert "Absent from this app" not in notes and "never opened by this build" in notes
    assert '"Rembourser" shows' in notes and '"Payer" shows' not in notes
    checklist = (_root() / "docs/app-store/checklist-envoi.md").read_text(encoding="utf-8")
    assert "- [x] Captures iPhone Duo" not in checklist and "AUCUNE version tvOS" in checklist


def test_round_seven_shared_expenses_are_filtered_and_the_listing_names_both_extensions():
    mig = (_root() / "supabase/migrations/20261125110000_pot_commun_filtre.sql").read_text(encoding="utf-8")
    prod = (_root() / "supabase/prod/2026-11-25-pot-commun-filtre-apply.sql").read_text(encoding="utf-8")
    for table in ("tc_groups", "tc_members", "tc_expenses"):
        trigger = f"create trigger {table}_moderation before insert or update of"
        assert trigger in mig and trigger in prod, table
    assert "private.item_text_verdict(new.note, 'Note')" in mig and "'20261125110000'" in prod
    import json
    desc = json.loads((_root() / "ios/appstore/metadata-fr.json").read_text(encoding="utf-8"))["description"]
    assert "Partager › Party" in desc and "Activité en direct" not in desc and len(desc) <= 4000  # 26.11 : plus de Musique
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    assert "names, titles and notes pass the app's word filter" in guide


def test_store_app_never_opens_the_test_site_nor_any_supabase_project_and_has_no_agenda_pronos_bridge():
    """Contrôle du 26.11 (2.2, 2.5.19) : le site de test ne s'ouvre DANS l'app que dans la BETA ; seule la base Supabase
    exacte est interne ; ponts Agenda, Pronos et cartes secrètes à null, sans gestionnaire, dans l'app App Store."""
    config = (_root() / "ios/Party/AppConfig.swift").read_text(encoding="utf-8")
    assert '[".supabase.co"]' not in config and "hasSuffix($0)" not in config
    assert 'isStoreApp ? ["party.bobycharbon.ch", "accounts.spotify.com"]' in config  # pas de site de test
    assert 'isStoreApp ? ["gsuetixzobooggeaubvb.supabase.co"]' in config
    bridge = (_root() / "ios/Party/NativeBridge.swift").read_text(encoding="utf-8")
    for name in ("pronosScript", "agendaScript", "secretScript"):
        assert f'private static let {name} = AppConfig.storeLocked ? "null"' in bridge, name
    for handler in ("PronosHandler(model: model)", "AgendaBridge(model: model)", "SecretCardsHandler(model: model)"):
        line = next(l for l in bridge.splitlines() if handler in l and "controller.add" in l)
        before = bridge[: bridge.index(line)].splitlines()[-1]
        assert "if !AppConfig.storeLocked" in line or "if !AppConfig.storeLocked" in before, handler


def test_store_app_notification_settings_hide_music_and_groups_never_promise_pronos():
    notif = (_root() / "ios/Party/Settings/NotificationSettingsView.swift").read_text(encoding="utf-8")
    assert "if !AppConfig.isStoreApp || store.hostMode { music }" in notif
    groups = (_root() / "ios/Party/Chats/Groups/GroupsListView.swift").read_text(encoding="utf-8")
    assert "pronos" not in groups.lower().split("emptyhero")[1][:1500]


def test_round_eight_texts_match_what_the_reviewer_can_try():
    """Contrôle de la prod du 26.11 : aucune promesse que l'app App Store ne tient pas (2.1, 2.3.1(a), 5.1.2)."""
    import json
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    desc = json.loads((_root() / "ios/appstore/metadata-fr.json").read_text(encoding="utf-8"))["description"]
    fiche = (_root() / "docs/app-store/fiche-app-store.md").read_text(encoding="utf-8")
    assert len(notes) <= 4000 and notes in guide
    for gone in ("attached video", "Paying unlocks nothing", "quick action", "joined only by link", "**✨ IA** (top right)",
                 "to the organisers"):
        assert gone not in guide, gone
    assert "nothing digital is sold or unlocked" in notes and "photos and voice messages can be sent" in guide
    assert '"Présent" at an event with a pot (or marked so) adds you' in notes
    assert "everyone who answers **Présent** is added" in guide and "anyone the organiser marks **Présent**" in guide
    # « Pas présent » ne retire PAS du pot (tc_rsvp_changed ajoute seulement) : on le quitte soi-même dans Réglages.
    assert "removes you" not in notes and "**Absent** removes" not in guide and "Quitter ce pot commun" in guide
    assert desc in fiche  # la fiche recopie la description envoyée
    assert "mini-sondages" not in desc and "Soirée Musique" not in desc
    assert "modération par notre équipe" not in desc and "aux organisateurs" not in desc
    assert "signalements lus et traités par l'éditeur sous 24 heures" in desc and "à l'équipe de Party" in desc
    for path in ("web/events/src/app/privacy.tsx", "ios/Party/Settings/Account/SignInView.swift"):
        text = (_root() / path).read_text(encoding="utf-8").replace("’", "'")
        assert "Supabase (société américaine)" in text and "dont on ne peut pas retrouver le numéro" not in text, path
        assert "répondre « Présent » à cet événement, ou être noté « Présent » par l'organisateur, t'ajoute d'office à ce pot" in text, path
        assert "l'en fait sortir" not in text and "« Quitter ce pot commun »" in text, path
        # Contrôle Apple, tour 2 : l'IA reçoit des alias à la place des surnoms ; pot : paiement montré seulement si choisi.
        # Tour 3 : seules les personnes déjà choisies partent, sous alias ; la liste des membres n'est jamais envoyée.
        assert "les personnes déjà choisies, sous un alias ; la liste des membres n'est jamais envoyée" in text, path
        assert "les surnoms des membres de Party que tu peux inviter" not in text, path
        # 27.11 : comme la base (20261126140000, show_payment) : montrés si on a créé le pot ou l'a rejoint par son lien ;
        # ajouté d'office : cachés tant qu'on ne choisit pas « Montrer mes moyens de paiement dans ce pot ».
        assert "si tu as créé le pot ou si tu l'as rejoint toi-même par son lien" in text, path
        assert "ils restent cachés tant que tu ne choisis pas « Montrer mes moyens de paiement dans ce pot »" in text, path
        assert "Une recherche par numéro exact révèle qu'une personne qui a ce numéro est sur Party" in text, path
        assert "empreinte chiffrée" not in text, path
        assert "Journal des connexions et des actions d'administration : 12 mois. Journal des appels à l'IA : 12 mois. Recherches de personnes : 1 heure." in text, path


def test_apple_check_round_one_texts_promise_only_what_the_reviewer_can_try():
    """Contrôle Apple du 26.11, tour 1 (2.1, 2.3.1(a), 1.2) : notes et guide = ce que l'app App Store fait vraiment."""
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    part_b = guide.split("## PART B", 1)[1]
    assert len(notes) <= 4000 and notes in guide
    assert '"+ Proposer" > "Sur invitation" > tick group "Démo Apple" > Publish' in notes
    assert 'tap **Sur invitation**, then tick **Démo Apple · 2**, then **Publier**' in part_b
    assert "J'ai 18 ans ou plus et j'accepte les conditions" in notes and "server-checked" in notes
    assert "names and answers filtered" in notes and "a first name changed during a game" in part_b
    assert "messages from a blocked person disappear at once" in notes and "Joindre les 10 messages précédents" in part_b
    assert "photo/voice copied" not in notes  # la copie des photos signalées : guide seulement
    for text in (notes, guide):
        assert "cover" not in text.lower()
    # Tour 2 : l'Activité en direct est dans le build (décrite, facultative) ; Souvenirs : « Not in this version ».
    assert "optional Live Activity for your song" in notes and "it ends by itself once the song has played" in part_b
    assert "Souvenirs" in notes.split("Not in this version", 1)[1].split("\n", 1)[0]
    assert "needs the host's Sonos" in notes  # Musique décrite, jamais cachée (2.3.1)
    titles = [l.split(" ", 2)[1] for l in part_b.splitlines() if l.startswith("#### B4.")]
    assert titles == [f"B4.{n}" for n in range(1, len(titles) + 1)], titles  # numérotation continue



def test_round_one_native_app_souvenirs_bridge_terms_and_shared_expense_reports():
    """Contrôle Apple du 26.11, tour 1 (app iPhone) : Souvenirs absents de l'app App Store, pont natif réservé au site
    de l'app (jamais accounts.spotify.com), CGU et « Signaler » du Pot commun, IBAN déclaré au manifeste."""
    import plistlib
    ios = _root() / "ios/Party"
    bridge = (ios / "NativeBridge.swift").read_text(encoding="utf-8")
    assert 'private static let souvenirsScript = AppConfig.storeLocked ? "null"' in bridge
    line = next(l for l in bridge.splitlines() if "SouvenirsBridge(model: model)" in l)
    assert "if !AppConfig.storeLocked" in bridge[: bridge.index(line)].splitlines()[-1]
    web = (ios / "WebModel.swift").read_text(encoding="utf-8")
    assert "souvenirs = AppConfig.storeLocked ? nil : SouvenirsStore(" in web
    assert "func openSouvenirs(_ route: SouvenirRoute) {\n        if AppConfig.storeLocked { return }" in web
    conv = (ios / "Chats/ConversationView.swift").read_text(encoding="utf-8")
    assert "if chat.isEvent, !AppConfig.storeLocked { SouvenirChatBanner(" in conv
    # Pont : seulement l'hôte du site (et TEST dans la BETA) ; le script ne pose rien ailleurs, les gestionnaires refusent.
    config = (ios / "AppConfig.swift").read_text(encoding="utf-8")
    hosts = config.split("static var bridgeHosts")[1].split("}")[0]
    assert "spotify" not in hosts and "supabase" not in hosts
    assert "indexOf(String(location.hostname).toLowerCase()) < 0) return;" in bridge
    swift = "\n".join(p.read_text(encoding="utf-8") for p in ios.rglob("*.swift"))
    assert "AppConfig.isInternal(message.frameInfo" not in swift and "AppConfig.isInternal(page)" not in swift
    # Bloquer depuis une conversation : le fil se relit aussitôt.
    assert "publisher(for: .partyBlockChanged)) { _ in Task { await store.open(group) } }" in conv
    # Conditions en grand et « Ton avis ».
    sheets = (ios / "Settings/Moderation/ModerationSheets.swift").read_text(encoding="utf-8")
    assert "Tolérance zéro : un contenu choquant est retiré et son auteur peut être banni." in sheets
    assert "Les points des jeux n'ont aucune valeur en argent." in sheets and "objets du jeu" not in sheets
    assert ("Sans elles, tu gardes les jeux. Écrire, publier, choisir ton surnom ou "
            "répondre à un événement te les redemanderont.") in sheets
    assert "Écris à l'équipe de Party" in (ios / "Settings/SettingsView.swift").read_text(encoding="utf-8")
    # Pot commun : Signaler (dépense, ticket) et CGU avant d'enregistrer.
    editor = (ios / "Tricount/ExpenseEditor.swift").read_text(encoding="utf-8")
    assert "kind: .tcExpense" in editor and "tc_receipt" not in editor and ".tcTermsGate(store) { await save() }" in editor
    assert "TermsAcceptSheet(store: store.moderation" in (ios / "Tricount/TricountStore.swift").read_text(encoding="utf-8")
    tc_store = (ios / "Tricount/TricountStore.swift").read_text(encoding="utf-8")
    assert "catch PartyAPIError.termsRequired {\n            needsTerms = true" in tc_store
    assert "Signaler la photo du ticket" in (ios / "Tricount/TricountGroupView.swift").read_text(encoding="utf-8")
    with open(ios / "PrivacyInfo.xcprivacy", "rb") as f:
        types = {e["NSPrivacyCollectedDataType"] for e in plistlib.load(f)["NSPrivacyCollectedDataTypes"]}
    assert {"NSPrivacyCollectedDataTypePaymentInfo", "NSPrivacyCollectedDataTypeOtherFinancialInfo"} <= types


def test_round_one_store_permission_texts_never_name_souvenirs_nor_the_agenda():
    from tests.test_compliance_1411 import targets, usage_texts
    party = targets()["Party"]
    store, beta = usage_texts(party), usage_texts(party, "STORE_beta")
    for key, text in store.items():
        assert "Souvenirs" not in text and "Agenda" not in text and "chiffrée" not in text, key
    assert store["NSCalendarsFullAccessUsageDescription"] == store["NSCalendarsUsageDescription"] == (
        "Pour mettre les dates d'un sondage dans ton calendrier, puis retirer celles qui ne sont pas retenues. "
        "Party ne garde ni n'envoie rien d'autre ; rien ne quitte ton iPhone.")
    assert "Agenda" in beta["NSCalendarsFullAccessUsageDescription"] and "Souvenirs" in beta["NSCameraUsageDescription"]
    assert 'PARTY_VARIANT: "STORE$(PARTY_BUNDLE_SUFFIX:c99extidentifier)"' in party["text"]


def test_apple_check_round_two_texts_say_what_the_build_really_does():
    """Contrôle Apple du 26.11, tour 2 (2.1, 2.3.1, 5.1.1, 1.2) : notes, guide et dossier App Store Connect."""
    import plistlib
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    part_b = guide.split("## PART B", 1)[1]
    flat = " ".join(guide.split("## PART B", 1)[1].split())
    assert len(notes) <= 4000 and notes in guide
    assert '"Mes amis dans Party"' in notes  # l'invitation par SMS : partie B (B8, ci-dessous)
    assert "No select-all; Party sends nothing." in flat and '"Mes amis dans Party": numbers are hashed' in flat
    assert "Live Activity" in part_b.split("#### B4.15", 1)[1].split("#### B4.16", 1)[0]
    assert "Pronos, Agenda, companion, Souvenirs." in notes
    assert '"Montrer mes moyens de paiement dans ce pot"' in notes and '"Signaler" on expenses and receipts' in notes
    assert "**Montrer mes moyens de paiement dans ce pot**" in part_b
    assert "**Signaler le groupe**" in part_b.split("#### B4.13", 1)[1].split("#### B4.14", 1)[0]
    assert "**Signaler le groupe**" in part_b.split("### B6.", 1)[1].split("### B7.", 1)[0]
    assert "aliases P1, P2…" in flat.split("### B7.", 1)[1]
    assert "Why a last name" in flat and "Afficher mon nom et prénom" in flat
    # B4.4 : aucune sous-liste (le script du PDF la numérotait comme une étape).
    b44 = part_b.split("#### B4.4", 1)[1].split("#### B4.5", 1)[0]
    assert not any(l.startswith(" ") and l.lstrip().startswith("- ") for l in b44.splitlines())
    for words in ("alcohol", "wine", " bet ", "wager", "drunk"):
        assert words not in notes.lower(), words
    # App Store Connect § 5 : les types du manifeste, Payment Info compris.
    asc = (_root() / "ios/appstore/app-store-connect.md").read_text(encoding="utf-8")
    with open(_root() / "ios/Party/PrivacyInfo.xcprivacy", "rb") as f:
        types = [e["NSPrivacyCollectedDataType"] for e in plistlib.load(f)["NSPrivacyCollectedDataTypes"]]
    # 27.11 : Search History (recherches de personnes 1 h, lieux chez Google) : textes ici, manifeste par le lot 6 iPhone.
    types = sorted(set(types) | {"NSPrivacyCollectedDataTypeSearchHistory"})
    assert "NSPrivacyCollectedDataTypeSearchHistory" in asc and "Search History" in asc
    assert f"exactement **{len(types)} types**" in asc and "à ajouter** au manifeste" not in asc
    assert "**à ajouter** au manifeste" not in asc
    assert "ses événements partent « pour validation »" not in asc
    tuto = (_root() / "docs/app-store/tutoriel-reviewer-fr.md").read_text(encoding="utf-8")
    assert "section bar / paiements" not in tuto
    checklist = (_root() / "docs/app-store/checklist-envoi.md").read_text(encoding="utf-8")
    for words in ("Apple-test 2", "12.12", "20.12", "PRIVÉ", f"**{len(types)} types**", "storage_secret_key",
                  "20261126100000", "20261126120000", "20261126130000", "20261126140000", "send-web-push", "xcodegen",
                  "nettoyage de la démo appliqué"):
        assert words in checklist, words


def test_round_two_beta_features_are_not_compiled_into_the_app_store_binary():
    # Contrôle Apple du 26.11, tour 2 : Souvenirs, Pronos, Agenda et l'écran du Purify Test ne sont compilés que dans la
    # BETA (PARTY_SWIFT_CONDITIONS=BETA) et les recettes E2E_HOOKS ; le binaire de l'App Store n'en contient rien.
    ios = _root() / "ios" / "Party"
    for folder in ("Souvenirs", "Pronos", "Agenda"):
        for f in (ios / folder).glob("*.swift"):
            lines = f.read_text(encoding="utf-8").splitlines()
            assert lines[1] == "#if BETA || E2E_HOOKS" and lines[-1] == "#endif", f
    # Jetons partagés (Discussions, Groupes, modération) sortis de Pronos/ : compilés partout.
    shared = (ios / "Chats/Neon/NeonShared.swift").read_text(encoding="utf-8")
    for name in ("enum PronoTheme", "struct PronoFace", "struct PronoAvatar:", "struct PronoAvatarStack", "struct PronoKitPressStyle"):
        assert name in shared and "#if BETA" not in shared, name
    stats = (ios / "Settings/Account/AnnouncementsView.swift").read_text(encoding="utf-8")
    purify = stats.index("@ViewBuilder private var purify")
    assert stats.rfind("#if BETA", 0, purify) > stats.rfind("#endif", 0, purify)
    assert "#else\n            BrainStatsSections(store: store, openGames: openGames)" in stats


def test_round_two_pot_payment_toggle_and_group_report():
    ios = _root() / "ios" / "Party"
    view = (ios / "Tricount/TricountGroupView.swift").read_text(encoding="utf-8")
    assert "Montrer mes moyens de paiement dans ce pot" in view and "ton IBAN et tes liens" in view
    store = (ios / "Tricount/TricountStore.swift").read_text(encoding="utf-8")
    assert "showPaymentMissing = true" in store  # fonction absente : caché, sans message
    assert '"/api/account/tricount/show-payment"' in (ios / "Tricount/TricountModels.swift").read_text(encoding="utf-8")
    page = (ios / "Chats/Groups/GroupPageView.swift").read_text(encoding="utf-8")
    assert "ReportTarget(kind: .group, id: page.group.id" in page and "Signaler le groupe" in page
    assert 'case group\n' in (ios / "Settings/Moderation/ModerationModels.swift").read_text(encoding="utf-8")
    profile = (ios / "Settings/ProfileView.swift").read_text(encoding="utf-8")
    assert "ProfileRules.missingText" in profile and "les autres à te reconnaître" in profile
    for f in ("Contacts/ContactsViews.swift", "Contacts/FriendsView.swift"):
        assert "empreinte chiffrée" not in (ios / f).read_text(encoding="utf-8"), f


def test_apple_check_round_three_demo_ticket_groups_music_camera_and_ai():
    """Contrôle Apple du 26.11, tour 3 (2.1, 2.3.1(a), 5.1.2) : le nettoyage de la démo allume les billets QR sans en
    remettre ; Apple se remet son billet (« Remettre à tous les présents », libellé de TicketsManager.tsx)."""
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    part_b = guide.split("## PART B", 1)[1]
    flat = " ".join(part_b.split())
    assert len(notes) <= 4000 and notes in guide
    label = "Remettre à tous les présents"
    assert "Remettre à tous les présents (${waiting.length})" in (_root() / "web/events/src/components/TicketsManager.tsx").read_text(encoding="utf-8")
    assert "Ajouter à l’app Cartes Apple" in (_root() / "web/events/src/components/WalletButton.tsx").read_text(encoding="utf-8")
    assert f'event chat, then "{label}": your QR ticket.' in notes
    assert "account's ticket is handed" not in guide and "already handed" not in guide
    assert f"tap **{label}** (you are co-organiser)" in flat.split("### B2.", 1)[1].split("### B3.", 1)[0]
    b410 = flat.split("#### B4.10", 1)[1].split("#### B4.11", 1)[0]
    assert label in b410 and "Ajouter à l'app Cartes Apple" in b410
    b413 = flat.split("#### B4.13", 1)[1].split("#### B4.14", 1)[0]
    assert "Group admins can set roles (co-admin, organiser) and who may invite, create events, write or pin; optional approval of new members." in b413
    music = "Music notification settings appear only for the host of a music party"
    assert music in flat.split("#### B4.18", 1)[1].split("#### B4.19", 1)[0] and music in flat.split("### B7.", 1)[1]
    assert ('| Camera | Scanning a QR code (party, game, ticket) or a "Pot commun" receipt, or taking a profile, event, '
            'group or chat photo |') in part_b
    assert "AI screen, event chat, announcement" in flat
    for text in (flat.split("#### B4.4", 1)[1].split("#### B4.5", 1)[0], flat.split("### B7.", 1)[1]):
        assert "never the list of members" in text and "categories and tags" in text
    assert "never by their nicknames" not in guide
    checklist = (_root() / "docs/app-store/checklist-envoi.md").read_text(encoding="utf-8")
    assert "PARTY_SWIFT_CONDITIONS= PARTY_BUNDLE_SUFFIX=" in checklist and "carte du bar" not in checklist
    assert "same fixed code as the first demo account" in checklist
    asc = (_root() / "ios/appstore/app-store-connect.md").read_text(encoding="utf-8")
    gameplay = next(l for l in asc.splitlines() if "**Gameplay Content**" in l)
    assert "Purify" not in gameplay and "Pronos" not in gameplay


def _outside_beta(text):
    """Le texte compilé dans le binaire de l'App Store : sans les blocs `#if BETA || E2E_HOOKS` … `#else`/`#endif`."""
    out, skip, depth = [], False, 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#if"):
            depth += 1
            if s == "#if BETA || E2E_HOOKS":
                skip, at = True, depth
            continue
        if s == "#else" and skip and depth == at:
            skip = False
            continue
        if s == "#endif":
            if skip and depth == at:
                skip = False
            depth -= 1
            continue
        if not skip:
            out.append(line)
    return "\n".join(out)


def test_round_three_store_app_never_shows_souvenirs_agenda_or_pronos_in_its_notification_settings():
    # Contrôle Apple, tour 3 : « 📸 Souvenirs » s'affichait dans l'app App Store (colonne absente en prod → erreur).
    notif = (_root() / "ios/Party/Settings/NotificationSettingsView.swift").read_text(encoding="utf-8")
    assert "Souvenirs" not in _outside_beta(notif)
    beta = notif[notif.index("#if BETA || E2E_HOOKS\n        // Souvenirs"):]
    assert 'Section("📸 Souvenirs")' in beta[: beta.index("#endif")]
    for gated in ('if store.agendaOn {\n            Section("📅 Agenda")', 'if store.pronosOn {\n            Section("🔮 Pronos")'):
        assert gated in notif, gated


def test_round_three_injected_bridge_script_names_no_beta_feature():
    bridge = (_root() / "ios/Party/NativeBridge.swift").read_text(encoding="utf-8")
    script = bridge[bridge.index('private static let script = """'):]
    script = script[: script.index('\n    """\n')]
    comments = "\n".join(l for l in script.splitlines() if l.strip().startswith("//"))
    for word in ("Agenda", "Souvenirs", "Pyramide", "Zicou", "Pronos"):
        assert word not in comments, word


def test_round_three_blocking_anywhere_refreshes_the_chats_at_once_and_later_is_never_silent():
    ios = _root() / "ios" / "Party"
    for f in ("Settings/Account/MemberCardView.swift", "Chats/EventChatInfoView.swift", "Chats/People/MiniProfileSheet.swift"):
        assert "NotificationCenter.default.post(name: .partyBlockChanged" in (ios / f).read_text(encoding="utf-8"), f
    later = (ios / "Settings/Moderation/ModerationSheets.swift").read_text(encoding="utf-8")
    assert "accepte d’abord les conditions d’utilisation de Party : touche" in later
    for f in ("Settings/ProfileView.swift", "Chats/People/MiniProfileSheet.swift", "Chats/People/NewMessageView.swift",
              "Chats/Groups/NewGroupView.swift", "Chats/People/NewChatGroupView.swift", "Settings/GroupsView.swift",
              "Settings/Account/MemberCardView.swift", "Chats/Groups/GroupSettingsView.swift", "Chats/ConversationView.swift",
              "Tricount/TricountStore.swift"):
        assert "TermsLater.message(" in (ios / f).read_text(encoding="utf-8"), f
    conv = (ios / "Chats/ConversationView.swift").read_text(encoding="utf-8")
    voice = conv[conv.index("private func sendVoice"):conv.index("struct PendingVoice")]
    assert "removeItem(at: file)" not in voice and "pendingVoice = PendingVoice(" in voice


# ── Contrôle Apple, tour 3 (jeux) : prénoms et textes de l'app, dilemmes proposés sur le web ──

STORE_ONLY_WORDS = ("Hitler", "Nazi", "néo-nazis", "Ganja", "Weed", "Beuh", "Pétard", "Marijuana", "Haschich", "Hasch",
                    "Shit", "Chatte", "Zizi", "Trou du cul", "Merde", "Putain", "PUTAINS", "M3rde", "z i z i")


@pytest.mark.parametrize("word", STORE_ONLY_WORDS)
def test_round_three_store_app_refuses_hate_drug_and_crude_names_and_shows_them_as_joueur(word):
    main._game_creations.clear()
    r = client(STORE_UA).post("/api/games", json={"guest_id": "store-nm", "name": word, "type": "likely", "terms": True})
    assert r.status_code == 400
    with pytest.raises(games.GameError):
        games.shown_text(word, "name", store=True)
    assert quiz.store_name(word) == "Joueur"
    assert store_app.offensive(f"Le joueur {word.lower()} !")


@pytest.mark.parametrize("name", ["Léa", "Chantal", "Hugo", "Merdan", "Nazir", "Nazim", "Matchatte", "Shitaké",
                                  "Wedding", "Heidi", "Chattam", "Pétra", "Wed", "Bedos", "Weedy"])
def test_round_three_ordinary_names_are_never_caught(name):
    assert not store_app.offensive(name) and quiz.store_name(name) == name
    assert games.shown_text(name, "name", store=True) == name


def test_round_three_the_web_keeps_its_rules_for_these_words_and_the_app_sees_joueur():
    """Hors app, rien ne change : la base et le web gardent leurs listes (moderation_terms.CATEGORIES)."""
    main._game_creations.clear()
    r = client(WEB_UA).post("/api/games", json={"guest_id": "web-host-nm", "name": "Merde", "type": "likely", "terms": True})
    assert r.status_code == 200
    code = r.json()["code"]
    assert client(WEB_UA).get(f"/api/games/{code}?guest_id=web-host-nm").json()["host_name"] == "Merde"
    # Contrôle Apple, tour 4 : l'app arrive, le prénom est réécrit DANS la partie (« Joueur 1 », pour tous).
    assert client(STORE_UA).get(f"/api/games/{code}?guest_id=store-p9").json()["host_name"] == "Joueur 1"
    assert client(WEB_UA).get(f"/api/games/{code}?guest_id=web-host-nm&name=Merde").json()["host_name"] == "Joueur 1"


def test_round_three_a_drinking_dilemma_proposed_on_the_web_never_reaches_the_app():
    main._game_creations.clear()
    g = main.store.session.games[create(WEB_UA, "debate", "web-host-db").json()["code"]]
    for i in range(3):
        games.join(g, f"w{i}", f"Ami {i}")
    debate.propose(g, "w0", "Faut-il boire une vodka à chaque manche ?")
    debate.propose(g, "w1", "Faut-il toujours dire la vérité à ses amis ?")
    debate.accept(g, debate.propose(g, "w2", "Faut-il fumer de la beuh avant un examen ?"))
    assert g["phase"] == "lobby"
    view = client(STORE_UA).get(f"/api/games/{g['code']}?guest_id=store-db").json()
    assert g["store"]
    left = [p["text"] for p in g["debate"]["proposals"]] + [q["text"] for q in g["debate"]["queue"]]
    assert left == []  # contrôle Apple, tour 4 : avec l'app, la banque de Party seule
    assert "vodka" not in str(view) and "beuh" not in str(view)


def test_round_three_by_is_a_name_shown_as_joueur_to_the_app():
    assert "by" in games.STORE_NAMES
    assert games.store_view({"q": {"text": "x", "by": "Hitler"}}) == {"q": {"text": "x", "by": "Joueur"}}


def test_round_four_terms_sheet_shows_only_the_store_filtered_terms():
    """Contrôle Apple, tour 4 (27.11) : la feuille « J'accepte les conditions » de l'iPhone affichait les conditions sans le
    filtre de l'app App Store (sections bar et Pronos). Elle doit utiliser TermsView.shown, comme Réglages › Conditions."""
    sheet = (_root() / "ios/Party/Settings/Moderation/ModerationSheets.swift").read_text(encoding="utf-8")
    assert "TermsView.sections" not in sheet and "TermsView.shown" in sheet


def test_policy_and_terms_have_no_broken_accents():
    """Contrôle Apple, tour 5 (27.11) : « montrÃ© » dans la politique (web et iPhone). Aucun texte cassé à l'écran."""
    for path in ("web/events/src/app/privacy.tsx", "ios/Party/Settings/Account/SignInView.swift",
                 "web/events/src/lib/terms.ts", "ios/Party/Settings/Moderation/TermsView.swift"):
        assert "Ã" not in (_root() / path).read_text(encoding="utf-8"), path


def test_every_store_report_sheet_promises_24_hours_and_the_contact():
    """Recette iPhone du 28.11 : la feuille « Signaler » d'un message (MessageReportSheet) n'affichait ni le délai ni le
    contact, contrairement à la feuille commune. Toutes les feuilles de l'app App Store les montrent."""
    for path in ("ios/Party/Settings/Moderation/ModerationSheets.swift", "ios/Party/Chats/Conversation/ConversationNeon.swift"):
        text = (_root() / path).read_text(encoding="utf-8")
        assert "Traité sous 24 h · \\(TermsView.supportEmail)" in text, path


def test_apple_check_round_five_texts_match_the_app_store_build():
    """Contrôle Apple du 27.11, tour 5 : Méninges seul après « Plus tard », dilemmes de Party seulement, « Rembourser »
    quand on doit à un membre, pas de sondages pour un Guest+, et pas de bouton vers /admin (404) dans l'app App Store."""
    notes = (_root() / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    part_b = guide.split("## PART B", 1)[1]
    tuto = (_root() / "docs/app-store/tutoriel-reviewer-fr.md").read_text(encoding="utf-8")
    assert len(notes) <= 4000 and notes in guide
    for words in ('"Plus tard": Méninges only', "Pour ou contre: our dilemmas only",
                  "auto-added members' payment details stay hidden", '"Apple-test 2" (+41 79 000 00 01, same code)'):
        assert words in notes, words
    assert "dilemmas proposed in Pour ou contre" not in guide
    assert "Plus tard · jouer seul à Méninges" in part_b and "Jouer avec les autres" in part_b
    assert "Pour ou contre only uses Party's own dilemmas" in part_b
    assert "Plus tard · jouer seul à Méninges" in tuto and "dilemmes de Party" in tuto
    assert "when you owe another member" in part_b and "quand tu dois de l'argent à un autre membre" in tuto
    avance = part_b.split("#### B4.3", 1)[1].split("**Avancé**", 1)[1].split("\n", 1)[0]
    assert "polls" not in avance.replace("date poll", "")
    games_js = (_root() / "app/static/games.js").read_text(encoding="utf-8")
    assert "Plus tard · jouer seul à Méninges" in games_js and "👥 Jouer avec les autres" in games_js
    host = (_root() / "ios/Party/HostMusic/HostPeopleView.swift").read_text(encoding="utf-8")
    assert 'if !AppConfig.isStoreApp {\n                    Section {\n                        Button("Ouvrir l\'admin du site (secours)"' in host


def test_apple_check_round_six_group_link_and_texts_match_the_app_store_build():
    """Contrôle Apple du 27.11, tour 6 : le libellé réel du lien de groupe (GroupPageView « Inviter » › GroupInviteView
    « Le lien du groupe », WhatsApp / Copier / Autre, QR ; « Inviter le numéro … »), site public seul « à part »,
    aucun libellé anglais inventé pour Spotify, lignes internes périmées retirées."""
    root = _root()
    notes = (root / "ios/appstore/review-notes.txt").read_text(encoding="utf-8").strip()
    guide = (root / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8")
    part_b = guide.split("## PART B", 1)[1]
    tuto = (root / "docs/app-store/tutoriel-reviewer-fr.md").read_text(encoding="utf-8")
    fiche = (root / "docs/app-store/fiche-app-store.md").read_text(encoding="utf-8")
    invite = (root / "ios/Party/Chats/Groups/GroupInviteView.swift").read_text(encoding="utf-8")
    page = (root / "ios/Party/Chats/Groups/GroupPageView.swift").read_text(encoding="utf-8")
    assert 'GroupActionLabel(title: "Inviter"' in page and 'Label("Le lien du groupe"' in invite
    for word in ('"WhatsApp"', '"Copier"', '"Autre"', 'Inviter le numéro'):
        assert word in invite, word
    assert len(notes) <= 4000 and notes in guide
    assert '"Inviter" > "Le lien du groupe" (WhatsApp, Copier, Autre, QR)' in notes
    for text in (guide, tuto):
        assert "Inviter avec un lien" not in text
    assert part_b.count("**Inviter** › **Le lien du groupe**") == 2 and tuto.count("**Inviter** › **Le lien du groupe**") == 2
    assert '"Inviter le numéro …"' in part_b
    assert "other\nplatforms are separate" not in guide and "other platforms are separate" not in guide
    assert "Open in Spotify" not in guide and "each song opens in Spotify" in part_b
    assert "Pour une bande d'amis" not in fiche and "À VÉRIFIER)" not in fiche
    assert "`https://party.bobycharbon.ch/events/privacy?app=ios`" in fiche and "09-musique.png" in fiche
    assert "un bar payant n'existe que" not in guide
    checklist = (root / "docs/app-store/checklist-envoi.md").read_text(encoding="utf-8")
    assert ('Captures 6,9" et Duo refaites avec le binaire App Store (4 onglets, sans Musique ; la 09 remplacée par '
            "Méninges ou la Salle de jeux), envoyées par `tools/appstore_submit.py screens`, vidéo d'aperçu supprimée") in checklist


def test_b5_names_every_feature_the_app_store_build_switches_off_by_itself():
    """Contrôle final (2.5.19) : chaque porte de l'app App Store dans le code iPhone a sa ligne dans B5 ; une porte ajoutée
    sans la dire dans les notes fait échouer ce test."""
    b5 = (_root() / "docs/app-store/notes-for-review.md").read_text(encoding="utf-8").split("Documented here, not hidden", 1)[1]
    b5 = b5.split("### B6", 1)[0]
    gates = {  # fichier → ce que B5 doit en dire
        "ios/Party/NativeBridge.swift": "Pyramide",
        "ios/Party/Settings/NotificationSettingsView.swift": "Music notification switches",
        "ios/Party/QuickActions.swift": "Ajouter un titre",
        "ios/PartyShare/ShareModel.swift": "Share extension",
        "ios/Party/Settings/Account/AnnouncementsView.swift": "Purify Test",
        "ios/Party/HostMusic/HostPeopleView.swift": "Ouvrir l'admin du site (secours)",
        "ios/Party/Settings/Account/MemberCardView.swift": "companion",
    }
    for path, said in gates.items():
        assert said in b5, (path, said)
    assert "bar, Agenda" in b5 and "Pronos, in Settings › Notifications" in b5
    import re
    seen = set()
    for f in (_root() / "ios").rglob("*.swift"):
        if "Tests" in str(f):
            continue
        text = f.read_text(encoding="utf-8")
        if re.search(r"if !?AppConfig\.(isStoreApp|storeLocked|zicouBuild)\b|if store\.bar\b|isStoreApp \?|Self\.isStoreApp", text):
            seen.add(str(f.relative_to(_root())))
    # Portes qui ne cachent rien (textes, adresses, réglages internes) : listées ici exprès.
    harmless = {"ios/Party/AppConfig.swift", "ios/Party/Settings/SettingsView.swift", "ios/Party/Settings/SettingsStore.swift",
                "ios/Party/Tricount/TricountListView.swift", "ios/Party/Settings/Account/AccountStore.swift",
                "ios/Party/Settings/Moderation/TermsView.swift", "ios/Party/Settings/Account/SignInView.swift",
                "ios/Party/WebModel.swift", "ios/Party/PartyApp.swift", "ios/Party/Chats/ConversationView.swift",
                "ios/Party/Chats/People/NewChatGroupView.swift",  # liste d'emojis sans 🍻 🍷
                "ios/PartyTV/CardGames.swift"}  # app Apple TV : pas dans cette version (aucun tvOS joint)
    assert seen - harmless <= set(gates), sorted(seen - harmless - set(gates))
