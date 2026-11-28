"""Décision de l'admin du 28.11 (question 1, choix b) : dans les jeux de l'app App Store (et de la BETA, sa copie), PLUS
AUCUN TEXTE LIBRE écrit par un joueur n'est montré aux autres. Prénom : un de la liste du serveur (store_app.PLAYER_NAMES)
ou « Joueur N » ; réponses : choisies parmi des propositions ; Tu me connais ? et Le Masque (texte écrit) : cachés.

Test discriminant : une chaîne sentinelle (des lettres seulement, acceptée par tous les filtres d'avant) est envoyée dans
CHAQUE champ texte de CHAQUE action de CHAQUE jeu gardé, depuis l'app ET depuis le web dans une partie où l'app est entrée ;
elle n'apparaît dans aucune réponse lue par l'app ni dans l'état de ces parties. Témoin : une partie du web seul la montre."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import games, main, moderation, quiz, store_app, store_static

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
WEB_UA = "Mozilla/5.0 Safari"
SENT = "Zorblax"  # sentinelle : lettres seules, sous 20 signes (roulette), passe le filtre de l'app d'avant le 28.11
KEPT = [k for k in games.GAMES if k not in store_app.HIDDEN_GAMES]
# Toutes les actions des jeux (main.perform_game_action), sauf « end » (qui ferme la partie avant la fin du test).
ACTIONS = ["join", "vote", "guess", "start", "vote_start", "close_vote", "eliminate", "skip_guess", "next", "restart", "up",
           "down", "names", "spin", "dnext", "djoker", "dback", "dheart", "tanswer", "tjudge", "addguest", "mvote", "rvote",
           "pause", "resume", "tq", "treveal", "treport", "finish", "qset", "qans", "qjoker", "qstop", "qpause", "hset",
           "nset", "nteam", "prplay", "prpass", "prexchange", "lkset", "lkvote", "lkskip", "lkswap", "psyans", "psysub",
           "psyreveal", "dbset", "dbvote", "dbskip", "dbswap", "dbrevote", "dbpropose", "dbaccept", "dbrefuse", "dbreport",
           "msset", "mswrite", "msswap", "msshow", "msguess", "mshide", "msreveal", "msreport", "rfset", "rfpick", "rfswap",
           "rfvote", "rfskip", "nreport", "remove", "ban", "handover"]
SETTINGS = {"q": SENT, "a": SENT, "i": SENT, "bet": SENT, "picks": {SENT: SENT}, "unmask": SENT, "team": SENT, "cup": SENT,
            "pid": SENT, "mode": SENT, "themes": [SENT], "packs": [SENT], "cats": [SENT], "public": SENT, "name": SENT,
            "text": SENT, "title": SENT}


def test_the_sentinel_passed_every_filter_before_the_decision():
    assert main.name_refusal(SENT, True) == "" and not store_app.name_refused(SENT)
    assert games.shown_text(SENT, "answer", store=True) == SENT and games.shown_text(SENT, "name", store=True) == SENT
    assert SENT not in store_app.PLAYER_NAMES


def test_the_list_of_names_is_clean_and_unique():
    names = store_app.PLAYER_NAMES
    assert len(names) >= 40
    assert len({store_app._name_key(n) for n in names}) == len(names)  # Léa / Lea : un seul
    for n in names:
        assert main.name_refusal(n, True) == "", n
        assert moderation.check(n, "name").ok and not store_app.drinky(n) and not store_static.CODE_DRINK_RE.search(n), n
        assert store_app.listed_name(n) == n and store_app.listed_name(n.lower()) == n
    assert not store_app.ALIAS_RE.fullmatch(store_app.ALIAS)  # « Joueur » seul : le serveur donne le numéro
    r = TestClient(main.app, headers={"User-Agent": STORE_UA}).get("/api/games/names")
    assert r.json() == {"names": list(names), "anonymous": "Joueur"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    monkeypatch.setattr(main, "notify_admin", lambda *a, **k: None)
    monkeypatch.setattr(main.journal, "record", lambda *a, **k: None)
    monkeypatch.setattr(quiz, "STATS_PATH", tmp_path / "quiz_stats.json")
    main._game_creations.clear()


class Reader:
    """Un téléphone : toutes les réponses lues sont gardées (celles de l'app sont ensuite fouillées)."""

    def __init__(self, ua):
        self.c = TestClient(main.app, headers={"User-Agent": ua}, raise_server_exceptions=False)
        self.read: list[str] = []

    def get(self, path, **params):
        r = self.c.get(path, params=params)
        self.read.append(r.text)
        return r

    def post(self, path, body):
        main._game_creations.clear()
        r = self.c.post(path, json=body)
        self.read.append(r.text)
        return r


def body(gid, action, kind):
    return {"guest_id": gid, "name": SENT, "action": action, "target": SENT, "guess": SENT, "names": [SENT, SENT + "e"],
            "who": SENT, "values": [SENT], "step": "", "terms": True, "amount": 0,
            "settings": {**SETTINGS, "type": "likely" if action == "launch" else SENT}}


def play(code, players, kind, rounds=2):
    """Chaque joueur envoie chaque action avec la sentinelle partout ; « start » / « next » font avancer les phases."""
    for _ in range(rounds):
        for reader, gid in players:
            for action in ACTIONS:
                reader.post(f"/api/games/{code}", body(gid, action, kind))
            reader.get(f"/api/games/{code}", guest_id=gid, name=SENT)


def app_side_text(app: Reader) -> str:
    return "\n".join(app.read)


def store_state() -> str:
    return json.dumps([g for g in main.store.session.games.values() if g.get("store")], ensure_ascii=False)


@pytest.mark.parametrize("kind", KEPT)
def test_no_text_typed_in_the_app_reaches_any_answer_it_reads(kind):
    app = Reader(STORE_UA)
    r = app.post("/api/games", {"guest_id": "zs-host-0001", "name": SENT, "type": kind, "terms": True, "plays": True})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    phones = [(app, "zs-host-0001")] + [(Reader(STORE_UA), f"zs-app-{i:04d}") for i in range(3)]
    play(code, phones, kind)
    if kind == "room":  # un jeu lancé dans la salle, joué à son tour
        app.post(f"/api/games/{code}", {**body("zs-host-0001", "launch", kind), "settings": {"type": "likely"}})
        child = main.room_child(main.store.session.games[code])
        assert child and child.get("store")
        play(child["code"], phones, "likely", rounds=2)
    texts = app_side_text(app) + "".join(app_side_text(r) for r, _ in phones[1:])
    assert SENT not in texts
    assert SENT not in store_state()
    assert SENT not in json.dumps(quiz.leaderboard(store=True))
    names = {p["name"] for g in main.store.session.games.values() for p in g["players"]}
    assert names and all(store_app.name_shown(n) for n in names), names


@pytest.mark.parametrize("kind", KEPT)
def test_no_text_typed_on_the_web_reaches_the_app_once_it_entered_the_game(kind):
    web, app = Reader(WEB_UA), Reader(STORE_UA)
    r = web.post("/api/games", {"guest_id": "zw-host-0001", "name": SENT, "type": kind, "plays": True})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    # Le web écrit d'abord (prénoms, réponses) ; l'app entre ensuite (code ou QR) : tout est déjà réécrit pour elle.
    early = [(web, "zw-host-0001")] + [(Reader(WEB_UA), f"zw-web-{i:04d}") for i in range(2)]
    for reader, gid in early[1:]:
        reader.post(f"/api/games/{code}", body(gid, "join", kind))
    assert app.get(f"/api/games/{code}", guest_id="zw-app-0001").status_code == 200
    app.post(f"/api/games/{code}", {**body("zw-app-0001", "join", kind), "name": "Léa"})
    play(code, early + [(app, "zw-app-0001")], kind)
    if kind == "room":
        web.post(f"/api/games/{code}", {**body("zw-host-0001", "launch", kind), "settings": {"type": "likely"}})
        child = main.room_child(main.store.session.games[code])
        assert child and child.get("store")
        play(child["code"], early + [(app, "zw-app-0001")], "likely", rounds=2)
    assert SENT not in app_side_text(app)
    assert SENT not in store_state()
    # Le web lit la même partie : le prénom tapé y est aussi « Joueur N » (la partie est celle de l'app).
    assert SENT not in web.get(f"/api/games/{code}", guest_id="zw-host-0001").text


@pytest.mark.parametrize("kind", ["likely", "undercover", "room"])
def test_control_a_web_only_game_shows_the_sentinel(kind):
    """Témoin : sans l'app, le web garde le prénom tapé (le test ci-dessus ne passe pas pour rien)."""
    web = Reader(WEB_UA)
    code = web.post("/api/games", {"guest_id": "zc-host-0001", "name": SENT, "type": kind, "plays": True}).json()["code"]
    web.post(f"/api/games/{code}", body("zc-bob-00001", "join", kind))
    assert SENT in web.get(f"/api/games/{code}", guest_id="zc-host-0001").text


def test_the_fantome_picks_one_of_the_proposed_words_in_a_game_of_the_app():
    app = Reader(STORE_UA)
    code = app.post("/api/games", {"guest_id": "zu-host-0001", "name": "Léa", "type": "undercover", "terms": True,
                                   "white": True}).json()["code"]
    for i, n in enumerate(("Tom", "Zoé", "Hugo", "Lina")):
        assert app.post(f"/api/games/{code}", {**body(f"zu-p{i}-00001", "join", "undercover"), "name": n}).status_code == 200
    g = main.store.session.games[code]
    games.start(g)
    white = next(p for p in g["players"] if p["role"] == "white")
    g["phase"] = "vote"
    games.eliminate(g, white["id"])
    choices = g["last"]["choices"]
    assert len(choices) == games.WHITE_CHOICES and g["words"]["civil"] in choices and len(set(choices)) == len(choices)
    assert not [w for w in choices if store_app.drinky(w)]
    view = app.get(f"/api/games/{code}", guest_id=white["id"]).json()
    assert view["last"]["choices"] == choices
    r = app.post(f"/api/games/{code}", {**body(white["id"], "guess", "undercover"), "guess": SENT})
    assert r.status_code == 409 and "proposés" in r.json()["detail"]
    r = app.post(f"/api/games/{code}", {**body(white["id"], "guess", "undercover"), "guess": str(choices.index(g["words"]["civil"]))})
    assert r.status_code == 200 and g["winner"] == "white"


def test_a_name_from_the_list_is_kept_unless_another_player_has_it():
    app = Reader(STORE_UA)
    code = app.post("/api/games", {"guest_id": "zn-host-0001", "name": "lea", "type": "likely", "terms": True}).json()["code"]
    g = main.store.session.games[code]
    assert g["host_name"] == "Léa"  # forme de la liste
    app.post(f"/api/games/{code}", {**body("zn-bob-00001", "join", "likely"), "name": "Léa"})
    app.post(f"/api/games/{code}", {**body("zn-ann-00001", "join", "likely"), "name": "Joueur 7"})  # jamais pris tel quel
    app.post(f"/api/games/{code}", {**body("zn-cid-00001", "join", "likely"), "name": "Joueur"})
    assert [p["name"] for p in g["players"]] == ["Léa", "Joueur 1", "Joueur 2", "Joueur 3"]
    # « Joueur » renvoyé à chaque lecture : jamais de nouveau numéro ; un prénom libre de la liste : pris.
    for _ in range(3):
        app.get(f"/api/games/{code}", guest_id="zn-cid-00001", name="Joueur")
    assert games.player(g, "zn-cid-00001")["name"] == "Joueur 3"
    app.get(f"/api/games/{code}", guest_id="zn-cid-00001", name="Nina")
    assert games.player(g, "zn-cid-00001")["name"] == "Nina"
    # Participant sans téléphone ajouté par l'animateur : la liste, sinon « Joueur N ».
    app.post(f"/api/games/{code}", {**body("zn-host-0001", "addguest", "likely"), "guess": SENT})
    app.post(f"/api/games/{code}", {**body("zn-host-0001", "addguest", "likely"), "guess": "Sam"})
    # « Joueur 3 » reste réservé à sa place (repris si elle redevient « Joueur ») : le suivant est « Joueur 5 ».
    assert [p["name"] for p in g["players"] if p.get("manual")] == ["Joueur 5", "Sam"]


def test_a_party_account_shows_no_photo_nor_profile_in_the_games_of_the_app(monkeypatch):
    monkeypatch.setattr(main.accounts, "photo", lambda gid: "https://example.test/p.jpg")
    monkeypatch.setattr(main.accounts, "is_linked", lambda gid: True)
    app, web = Reader(STORE_UA), Reader(WEB_UA)
    code = app.post("/api/games", {"guest_id": "zp-host-0001", "name": "Léa", "type": "likely", "terms": True}).json()["code"]
    seen = app.get(f"/api/games/{code}", guest_id="zp-host-0001").json()["players"][0]
    assert "photo" not in seen and "account" not in seen
    assert web.get(f"/api/games/{code}", guest_id="zp-host-0001").json()["players"][0]["photo"]


# ── La page de l'app : aucun champ de texte libre dans les jeux ──
STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
GAME_SCRIPTS = ("games.js", "quiz.js", "likely.js", "debate.js", "psy.js", "reflet.js", "president.js", "president-fx.js",
                "neon.js", "island.js", "heist.js", "brain/core.js", "brain/stats.js", "profile-card.js")
TEXT_FIELD = re.compile(r"<textarea\b[^>]*>|<input\b(?![^>]*\btype=\"(?:checkbox|radio|hidden|range|search)\")[^>]*>|(?<!\.)\bprompt\(", re.I)
# Champs gardés : codes à chiffres (jeu, soirée), recherche de titres (Musique), message privé à l'hôte, avis à l'équipe.
ALLOWED = ('id="gCode"', 'id="pinInput"', 'id="msgText"', 'id="fbText"', 'id="fbAiMoreText"', 'class="fb-edit-text"',
           "installEvent.prompt(")


def store_page() -> dict[str, str]:
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    out = {"index.html": c.get("/").text}
    for name in GAME_SCRIPTS:
        r = c.get(f"/static-store/{name}")
        assert r.status_code == 200, name
        out[name] = r.text
    return out


def test_the_store_page_has_no_free_text_field_in_the_games():
    found = {name: [m.group(0)[:90] for m in TEXT_FIELD.finditer(text) if not any(a in text[m.start():m.end() + 30]
                                                                                    for a in ALLOWED)]
             for name, text in store_page().items()}
    assert {k: v for k, v in found.items() if v} == {}
    # Les fichiers du Masque ne sont plus servis à l'app ; le web garde tout.
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    assert c.get("/static-store/masque.js").status_code == 404
    web = TestClient(main.app, headers={"User-Agent": WEB_UA})
    assert 'id="gNameInput" class="grow" type="text"' in web.get("/static/games.js").text


def test_the_store_page_picks_a_name_from_the_list():
    page = store_page()
    js, html = page["games.js"], page["index.html"]
    assert 'data-name-pick="gNameInput"' in js and "/api/games/names" in js and "data-wguess" in js
    assert '<select class="grow" name="manualName"' in js and "namePickOptions()" in js
    assert 'data-name-pick="nameInput"' in html and "pickGameName()" in html
    assert "masque.js" not in html
