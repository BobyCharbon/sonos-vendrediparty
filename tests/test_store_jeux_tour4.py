"""Contrôle Apple, tour 4 (27.11) : jeux de l'app App Store (« PartyStore »). On change la MÉTHODE, pas seulement la liste :
- prénoms nettoyés À LA SOURCE : dès que l'app touche une partie, puis à chaque écriture de prénom, tout prénom refusé est
  réécrit « Joueur 1 », « Joueur 2 »… DANS la partie (store_app.scrub_names), copies comprises (historiques, auteurs,
  trames 3D) ;
- filtre à chaque entrée de prénom (création, rejoindre, présence, invité ajouté, renommage) pour l'app OU une partie `store` ;
- Pour ou contre avec l'app : la banque seule ; argot des joueurs (store_app.player_offensive) ;
- pages HTML brutes et /admin : 404 pour l'app ; Méninges sans la case ; débuts de mots ; classement du Quiz ; avis IA."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import games, main, quiz, store_app, store_static

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
WEB_UA = "Mozilla/5.0 Safari"
ROOT = Path(main.__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


def client(ua, **headers):
    return TestClient(main.app, headers={"User-Agent": ua, **headers})


def create(ua, kind, gid, name="Léa"):
    main._game_creations.clear()
    r = client(ua).post("/api/games", json={"guest_id": gid, "name": name, "type": kind, "terms": True})
    assert r.status_code == 200, r.text
    return r.json()["code"]


def act(ua, code, gid, name, action, **kw):
    return client(ua).post(f"/api/games/{code}", json={"guest_id": gid, "name": name, "action": action, "terms": True, **kw})


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for x in o.values():
            yield from strings(x)
    elif isinstance(o, (list, tuple)):
        for x in o:
            yield from strings(x)


# ── 3. Argot et contournements (textes de joueurs) ──

SLANG = [  # dilemmes et prénoms du rapport du contrôleur (slang.py, followup.py)
    "Faut-il picoler avant chaque soirée ?", "Faut-il trinquer à chaque anniversaire ?", "Faut-il finir pompette le samedi soir ?",
    "Faut-il se mettre une mine tous les week-ends ?", "Faut-il boire cul sec quand on perd ?",
    "Faut-il parier 20 francs sur le match ?", "Faut-il miser son salaire au loto ?", "Faut-il fumer un pétard avant de dormir ?",
    "Faut-il prendre une biture pour fêter ça ?", "Faut-il être saoul pour danser ?", "Faut-il ramener du pinard à chaque repas ?",
    "Faut-il se torcher la gueule au nouvel an ?", "Faut-il arroser chaque victoire au champagne ?",
    "Faut-il tiser avant d'aller en boîte ?", "Faut-il être éméché pour chanter au karaoké ?",
    "Faut-il se défoncer chaque samedi soir ?", "Faut-il prendre de la C avant la soirée ?", "Faut-il rouler un pet avant le film ?",
    "Faut-il faire des paris entre amis ?", "Il s'est torché", "se mettre une race", "une mise de 10 francs",
    "Saoul", "Soûl", "Shot", "Cul sec", "Clope", "Clopes", "Casino", "Pari", "PARIS", "Poker", "Coke", "Weed", "Pétard", "Bière",
    "Rhum", "Gorgée", "🍺", "Chatte", "Couille", "Nazi", "Ganja", "Whiskey", "v0dka", "V 0 D K A", "v.o.d.k.a", "vod ka", "b1ère",
    "h1tler", "hit ler", "H i t l e r", "Hitler", "Merde"]
ORDINARY = [  # rien d'ordinaire n'est refusé : villes, prénoms, nombres, « mise à jour »
    "Léa", "Paris", "Faut-il vivre à Paris ?", "Faut-il faire une mise à jour chaque soir ?", "Faut-il une mise en place stricte ?",
    "Mise au point", "Chantal", "Hugo", "Merdan", "Nazir", "Matchatte", "Shitaké", "Anna Zimmer", "La lampe torche",
    "Faut-il écouter de la soul ?", "Zoé", "Une longue balade au bord du lac", "Le chocolat", "pomme", "Misère", "Paul Ier",
    "Parisa", "J'ai 30 ans", "5 à 7", "100", "mal à la gorge et au dos", "Il m'a dit mal t'aime", "7153", "Le 4x4 de papa",
    "Faut-il coucher le premier soir ?", "Marie-Thérèse", "Kevin 2", "Bob l'éponge", "Joueur 1"]


@pytest.mark.parametrize("text", SLANG)
def test_slang_and_disguised_words_are_refused_in_an_app_game(text):
    assert store_app.player_offensive(text)
    with pytest.raises(games.GameError):
        games.shown_text(text, "answer", store=True)


@pytest.mark.parametrize("text", ORDINARY)
def test_ordinary_texts_pass(text):
    assert not store_app.player_offensive(text)
    assert games.shown_text(text, "answer", store=True)
    if len(text) <= 30 and store_app.name_chars_ok(text):  # « ? » n'est pas dans l'alphabet des prénoms (tour 5)
        assert not store_app.name_refused(text)


def test_the_slang_filter_is_for_players_only_never_the_events_filter():
    """Le filtre des événements (drinky) n'est pas élargi : « pompette » ou « paris » restent son affaire."""
    assert not store_app.drinky("Faut-il finir pompette ?") and not store_app.drinky("des paris entre amis")


# ── 1. Prénoms réécrits dans la partie ──

def test_scrub_rewrites_every_copy_and_keeps_twins_apart():
    g = {"host": "h", "host_name": "Merde", "store": True,
         "players": [{"id": "h", "pid": "p1", "name": "Merde"}, {"id": "a", "pid": "p2", "name": "Merde"},
                     {"id": "b", "pid": "p3", "name": "Pari"}, {"id": "c", "pid": "p4", "name": "Léa"}],
         "likely": {"history": [{"winners": ["Merde", "Léa"]}]}, "masque": {"result": [{"author": "Pari", "text": "x"}]},
         "log": ["Merde a gagné la manche", "Une question à Paris ?"]}
    assert store_app.scrub_names(g)
    assert [p["name"] for p in g["players"]] == ["Joueur 1", "Joueur 2", "Joueur 3", "Léa"]
    assert g["host_name"] == "Joueur 1" and g["store_alias"] == {"h": "Joueur 1", "a": "Joueur 2", "b": "Joueur 3"}
    assert g["likely"]["history"][0]["winners"] == ["Joueur 1", "Léa"] and g["masque"]["result"][0]["author"] == "Joueur 3"
    assert g["log"] == ["Joueur 1 a gagné la manche", "Une question à Paris ?"]  # mot entier : « Paris » reste
    assert [p["id"] for p in g["players"]] == ["h", "a", "b", "c"]  # jamais un identifiant
    assert not store_app.scrub_names(g)  # stable : rien ne change ensuite


def test_the_host_who_does_not_play_is_renamed_too():
    g = {"host": "h", "host_name": "Hitler", "players": [{"id": "x", "pid": "p", "name": "Joueur 1"}]}
    store_app.scrub_names(g)
    assert g["host_name"] == "Joueur 2"  # « Joueur 1 » est déjà pris par un vrai prénom


def test_a_web_game_with_bad_names_is_rewritten_when_the_app_arrives_and_the_web_sees_it_too():
    code = create(WEB_UA, "likely", "webxx0-h", "Putain")  # « Hitler » : refusé partout depuis le lot 15b
    g = main.store.session.games[code]
    games.join(g, "webxx0-v", "Vodka")
    games.join(g, "webxx0-z", "Zoé")
    v = client(STORE_UA).get(f"/api/games/{code}?guest_id=store0-t&name=Tom").json()
    assert sorted(p["name"] for p in v["players"]) == ["Joueur 1", "Joueur 2", "Zoé"]
    assert not any(store_app.name_refused(s) for s in strings(g) if s in ("Putain", "Vodka"))
    # Le joueur du web revient avec son ancien prénom : il garde « Joueur N » (même filtre pour la partie de l'app).
    web = client(WEB_UA).get(f"/api/games/{code}?guest_id=webxx0-v&name=Vodka").json()
    assert "Vodka" not in json.dumps(web, ensure_ascii=False) and "Putain" not in json.dumps(web, ensure_ascii=False)


@pytest.mark.parametrize("kind", ["neon", "island", "heist"])
def test_3d_frames_lose_the_bad_names_when_the_app_arrives_after_the_start(kind):
    """Ordre difficile : le web crée, « Vodka » et « Hitler » entrent, la manche part, PUIS l'app arrive."""
    code = create(WEB_UA, kind, "webxx0-h3", "Léa")
    g = main.store.session.games[code]
    games.join(g, "webxx0-v3", "Vodka")
    games.join(g, "webxx0-m3", "Hitler")
    act(WEB_UA, code, "webxx0-h3", "Léa", "start")
    assert "Vodka" in json.dumps(g, ensure_ascii=False)
    client(STORE_UA).get(f"/api/games/{code}?guest_id=store0-3d&name=Tom")
    frame = client(STORE_UA).post(f"/api/games/{code}/{kind}", json={"guest_id": "store0-3d"}).json()
    names = [f.get("name") for f in frame.get("fighters", [])]
    assert "Vodka" not in names and "Hitler" not in names and {"Joueur 1", "Joueur 2"} <= set(names)
    assert "Vodka" not in json.dumps(g, ensure_ascii=False) and "Hitler" not in json.dumps(g, ensure_ascii=False)


def test_room_and_its_game_give_the_same_number_to_the_same_player():
    room = create(WEB_UA, "room", "webxx0-rh", "Léa")
    act(WEB_UA, room, "webxx0-rm", "Merde", "join")
    assert act(WEB_UA, room, "webxx0-rh", "Léa", "launch", settings={"type": "neon"}).status_code == 200
    child = main.store.session.games[room]["current"]
    v = client(STORE_UA).get(f"/api/games/{room}?guest_id=store0-r&name=Tom").json()
    assert "Joueur 1" in [p["name"] for p in v["players"]]
    c = client(STORE_UA).get(f"/api/games/{child}?guest_id=store0-r&name=Tom").json()
    assert "Joueur 1" in [p["name"] for p in c["players"]] and "Merde" not in json.dumps(c, ensure_ascii=False)


# ── 2. Filtre à chaque entrée de prénom : App Store, web, partie mixte ──

@pytest.mark.parametrize("bad", ["Merde", "Vodka", "Hitler", "Pompette", "v0dka"])
def test_every_name_entry_is_filtered(bad):
    # Création par l'app.
    r = client(STORE_UA).post("/api/games", json={"guest_id": "store0-c", "name": bad, "type": "quiz", "terms": True})
    assert r.status_code == 400
    # Partie de l'app : rejoindre depuis l'app ET depuis le web (partie mixte).
    code = create(STORE_UA, "room", "store0-h")
    assert act(STORE_UA, code, "store0-j", bad, "join").status_code == 400
    assert act(WEB_UA, code, "webxx0-j", bad, "join").status_code == 400
    assert act(WEB_UA, code, "webxx0-ok", "Zoé", "join").status_code == 200
    # Partie du web : l'app y entre avec un mauvais prénom → refusé.
    web = create(WEB_UA, "quiz", "webxx0-h")
    assert act(STORE_UA, web, "store0-k", bad, "join").status_code == 400
    # Présence : l'app, et le web dans une partie de l'app (champ `game`) ; le web seul garde ses règles.
    assert client(STORE_UA).post("/api/presence", json={"guest_id": "store0-p", "name": bad}).status_code == 400
    assert client(WEB_UA).post("/api/presence", json={"guest_id": "webxx0-p", "name": bad, "game": code}).status_code == 400
    # Invité ajouté par l'animateur dans la salle de l'app.
    assert act(STORE_UA, code, "store0-h", "Léa", "addguest", guess=bad).status_code == 400
    # Renommage par la lecture (prénom en haut à droite) : l'ancien reste.
    v = client(WEB_UA).get(f"/api/games/{code}?guest_id=webxx0-ok&name={bad}").json()
    assert "Zoé" in [p["name"] for p in v["players"]] and bad not in json.dumps(v, ensure_ascii=False)


def test_the_web_alone_keeps_its_own_rules():
    """Le web, hors partie de l'app : « Merde » et « Vodka » restent permis (liste commune inchangée)."""
    code = create(WEB_UA, "quiz", "webxx0-h2", "Merde")
    assert act(WEB_UA, code, "webxx0-j2", "Vodka", "join").status_code == 200
    assert client(WEB_UA).post("/api/presence", json={"guest_id": "webxx0-p2", "name": "Pompette"}).status_code == 200


# ── 3. Pour ou contre : la banque seule avec l'app ──

def test_no_player_dilemma_in_a_game_with_the_app():
    code = create(STORE_UA, "debate", "store0-db")
    act(WEB_UA, code, "webxx0-db", "Max", "join")
    for ua, gid, name in ((WEB_UA, "webxx0-db", "Max"), (STORE_UA, "store0-db", "Léa")):
        r = act(ua, code, gid, name, "dbpropose", guess="Faut-il toujours dire la vérité à ses amis ?")
        assert r.status_code == 409
    v = client(STORE_UA).get(f"/api/games/{code}?guest_id=store0-db").json()
    assert v["debate"]["propose"] is False
    web = create(WEB_UA, "debate", "webxx0-db2")
    assert act(WEB_UA, web, "webxx0-db2", "Léa", "dbpropose", guess="Faut-il toujours dire la vérité à ses amis ?").status_code == 200
    assert client(WEB_UA).get(f"/api/games/{web}?guest_id=webxx0-db2").json()["debate"]["propose"] is True


def test_player_dilemmas_proposed_on_the_web_are_dropped_when_the_app_arrives():
    code = create(WEB_UA, "debate", "webxx0-db3")
    g = main.store.session.games[code]
    games.join(g, "webxx0-db4", "Max")
    act(WEB_UA, code, "webxx0-db4", "Max", "dbpropose", guess="Faut-il toujours dire la vérité à ses amis ?")
    client(STORE_UA).get(f"/api/games/{code}?guest_id=store0-db3")
    assert g["debate"]["proposals"] == [] and g["debate"]["queue"] == []


# ── 4. Pages HTML brutes et /admin ──

@pytest.mark.parametrize("path", ["/static/index.html", "/static/admin.html", "/static/tv.html", "/static-store/index.html",
                                  "/static-store/x.html", "/static/%2e%2e/static/admin.html", "/static/pet/verify.html",
                                  "/admin", "/admin/", "/ADMIN", "/admin.html"])
@pytest.mark.parametrize("headers", [{"User-Agent": STORE_UA}, {"User-Agent": WEB_UA, "x-party-native": "ios"}])
def test_raw_html_pages_and_admin_are_404_for_the_app(path, headers, monkeypatch):
    monkeypatch.setattr(store_app, "is_test_site", lambda: False)
    assert TestClient(main.app, headers=headers).get(path).status_code == 404


def test_the_web_still_reads_admin():
    assert client(WEB_UA).get("/admin").status_code == 200


# ── 5. « Plus tard » visible d'office ; Méninges sans la case ──

def test_later_button_is_shown_by_default_and_opens_meninges_alone():
    js = (ROOT / "app/static/games.js").read_text(encoding="utf-8")
    assert 'class="secondary g-terms-later" id="gTermsLater"' in js  # plus de « hidden »
    assert 'classList.toggle("hidden", !guestName)' not in js
    assert "if (STORE && gTermsLater && (!guestName || !gamesTermsOk())) return renderSoloHome();" in js
    css = (ROOT / "app/static/games.css").read_text(encoding="utf-8")
    assert "#gHome.g-solo > :not(.g-solo-back):not(.g-cat[data-cat=brain])" in css
    # Méninges n'envoie aucun prénom ni texte lu par d'autres : ses routes ne prennent pas de prénom.
    for model in ("BrainResult", "BrainLocal", "BrainGameLocal"):
        assert "name" not in getattr(main, model).model_fields


def test_the_name_form_waits_for_the_server():
    js = (ROOT / "app/static/games.js").read_text(encoding="utf-8")
    form = js[js.index('$("gNameForm").addEventListener'):]
    form = form[:form.index("\n});")]
    assert "await gapi(\"/api/presence\", { guest_id: guestId, name, game: myGame" in form
    assert form.index("await gapi") < form.index("guestName = name")
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert "game: typeof myGame" in html


# ── 6. Débuts de mots et classement du Quiz ──

def test_meninges_never_starts_with_a_forbidden_beginning():
    index = json.loads((ROOT / "app/static/brain/mots/index.json").read_text(encoding="utf-8"))["prefixes"]
    for stem in "vod alc ivr naz hit whi teq pok rhu cig gin vin".split():
        assert index[stem].get("start") is False, stem
    for abc, entry in index.items():
        if store_app.name_refused(abc):
            assert entry.get("start") is False, abc
    tool = (ROOT / "tools/build_mots_fr.py").read_text(encoding="utf-8")
    assert all(s in tool for s in ("vod", "naz", "hit", "kir"))


def test_quiz_leaderboard_gives_each_hidden_player_a_number(monkeypatch):
    stats = {"players": {k: {"name": n, "pts": p, "games": 1, "wins": 0, "ok": 1, "n": 2, "best_streak": 1,
                             "records": {"classic": p}} for k, n, p in
                         (("a", "Merde", 300), ("b", "Vodka", 200), ("c", "Léa", 100), ("d", "Joueur 1", 50))}}
    monkeypatch.setattr(quiz, "_load_stats", lambda: stats)
    names = [r["name"] for r in quiz.leaderboard(store=True)["top"]]
    assert names == ["Joueur 1", "Joueur 2", "Léa", "Joueur 3"]
    assert quiz.leaderboard(store=True)["records"]["classic"]["name"] == "Joueur 1"
    assert [r["name"] for r in quiz.leaderboard()["top"]] == ["Merde", "Vodka", "Léa", "Joueur 1"]


# ── 7. Avis IA : jamais « Zicou » dans l'app ──

def test_feedback_ai_never_labels_zicou_in_the_app():
    shown = store_static.render(ROOT / "app/static/feedback-ai.js")
    assert "Zicou" not in shown and 'pet: "🌐 Général"' in shown
    assert "🐾 Zicou" in (ROOT / "app/static/feedback-ai.js").read_text(encoding="utf-8")  # le site garde son étiquette
