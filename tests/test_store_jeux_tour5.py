"""Contrôle Apple, tour 5 (27.11) : textes des joueurs dans l'app App Store (« PartyStore »). On CHANGE DE MÉTHODE :
- prénoms : NFKC puis liste BLANCHE (lettres latines accentuées, chiffres, espace, trait d'union, apostrophe, 30 signes) ;
  tout le reste (cyrillique, grec, symboles, emoji) est refusé, et un prénom du web hors de cet alphabet devient « Joueur N » ;
- réponses : NFKC, sosies cyrillique / grec → latin avant le filtre, ni emoji ni symbole hors de la ponctuation courante ;
- listes par familles (drogue, ivresse, marques, paris, haine, violence sexuelle, sexuel) : textes des joueurs seulement ;
- corpus de non-régression : chaque prénom et réponse des scripts du contrôleur (tour4-jeux, tour5-jeux) reste REFUSÉ ;
  les témoins de ces scripts (Léa, Tom, Max, Paul, Jean, Lou, Julie, « Une longue balade… », « Le chocolat », « pomme »…)
  et les faux positifs connus restent ACCEPTÉS ;
- trames /neon /island /heist : check_store_access en tête (partie refusée, prénoms réécrits) ;
- filtre commun (app/moderation.py ET la base, migration 20261127130000) : sosies + NFKC."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import games, main, moderation, store_app

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
WEB_UA = "Mozilla/5.0 Safari"
ROOT = Path(main.__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


def client(ua):
    return TestClient(main.app, headers={"User-Agent": ua})


def create(ua, kind, gid, name="Léa"):
    main._game_creations.clear()
    r = client(ua).post("/api/games", json={"guest_id": gid, "name": name, "type": kind, "terms": True})
    assert r.status_code == 200, r.text
    return r.json()["code"]


def act(ua, code, gid, name, action, **kw):
    return client(ua).post(f"/api/games/{code}", json={"guest_id": gid, "name": name, "action": action, "terms": True, **kw})


# Recette iPhone du 28.11 : « Zoépicoler » passait (un mot de la liste collé à un prénom).
# ── Corpus des scripts du contrôleur (recopié ici : le dossier de travail est éphémère) ──

NAMES_TOUR4 = [  # tour4-jeux/names.py, names2.py (hors « Léa », témoin)
    "Hitler", "H1tler", "Hit ler", "HITLER", "Adolf Hitler", "Nazi", "Ganja", "Weeed", "Beuh", "Shit", "Merde", "M3rde",
    "Putain", "Ptn", "Vodka", "V0dka", "Whiskey", "Whisky", "Bière", "Biere", "Rhum", "Pinard", "Picole", "Tise", "Saoul",
    "Bourré", "Shot", "Gorgée", "Cul sec", "Clope", "Pute", "Salope", "Connard", "Enculé", "Fdp", "Ntm", "Bite", "Couille",
    "Chatte", "Nichon", "Sexe", "Porno", "Cocaïne", "Coke", "Heroine", "Weed", "Pétard", "Jäger", "🍺", "🍷Léa", "Casino",
    "Poker", "Pari", "Fuck", "Bitch", "Négro", "Bougnoule", "Pédé", "Terroriste", "Daech", "Ben Laden"]
NAMES_FOLLOWUP = [  # followup.py (les deux tours), partie 1 et 4
    "Merde", "Saoul", "Shot", "Cul sec", "Clope", "Casino", "Pari", "Poker", "Coke", "Weed", "Pétard", "Bière", "Rhum",
    "Gorgée", "🍺", "Chatte", "Couille", "Nazi", "Ganja"]
NAMES_TOUR5 = [  # tour5-jeux/names_view.py
    "Viol", "Violeur", "Pédo", "Inceste", "Nique", "Suce", "Pénis", "Vagin", "Orgie", "KKK", "SS", "88", "Daech", "Feuj",
    "Raton", "Tapette", "Mongol", "Trisomique", "Ketamine", "Meth", "Codéine", "Poppers", "Xtc", "Ivrogne", "Poivrot",
    "Pochtron", "Murge", "Gnôle", "Schnaps", "Smirnoff", "Jack Daniels", "Baileys", "Desperados", "Kronenbourg",
    "Ti punch", "Cuba libre", "Bloody Mary", "Betclic", "Winamax", "Jackpot", "Suicide", "Ben Laden", "Staline"]
NAMES_UI5 = ["Hіtler", "Léa 卐", "Ｖｏｄｋａ", "Smirnoff", "Ketamine", "Pochtron", "Daech", "Max 🚬💊"]  # tour5-jeux/ui5.py
NAMES_TRICKS = [  # mêmes mots, autres écritures : sosies, formes NFKC, symboles
    "Cоnnard", "CОNNARD", "Ηitler", "𝐇𝐢𝐭𝐥𝐞𝐫", "Ⓗⓘⓣⓛⓔⓡ", "Ｍｅｒｄｅ", "Vоdka", "Léa ✨", "Zoé 💊", "Νίκος", "Иван",
    "Tom̶", "Léa #1", "@Léa", "Paul_88", "Kéta", "Héro", "Champi", "Feldschlösschen", "PMU", "Tiercé", "Get 27",
    "Moët", "Ku Klux Klan", "Pique la nique",
    "Zoépicoler", "Zoévodka", "Zoé picoler", "Hitlerine", "Maxsmirnoff", "LéaKétamine", "Tomcasino", "Juliepochtron"]
REFUSED_NAMES = sorted(set(NAMES_TOUR4 + NAMES_FOLLOWUP + NAMES_TOUR5 + NAMES_UI5 + NAMES_TRICKS))

ANSWERS_TOUR5 = [  # tour5-jeux/answers.py (Tu me connais ?)
    "Une bouteille de Smirnoff", "Du Jack Daniels avec du coca", "Prendre une murge", "Finir pochtron", "Un petit schnaps",
    "De la kétamine", "Un rail de meth", "Un poppers", "Parier au PMU", "Jouer sur Winamax", "Le viol", "Les pédos",
    "Ma nique", "Un ti punch", "Un cuba libre", "Une Kronenbourg", "Des Desperados", "Prendre une caisse", "Être ivrogne",
    "Boire un coup", "Une mousse bien fraîche", "Un demi pression", "Une pinte", "Un Baileys", "La gnôle de papi"]
SLANG_DILEMMAS = [  # tour4-jeux/slang.py et tour5-jeux/slang.py (hors « coucher le premier soir », accepté)
    "Faut-il picoler avant chaque soirée ?", "Faut-il trinquer à chaque anniversaire ?",
    "Faut-il finir pompette le samedi soir ?", "Faut-il se mettre une mine tous les week-ends ?",
    "Faut-il boire cul sec quand on perd ?", "Faut-il parier 20 francs sur le match ?", "Faut-il miser son salaire au loto ?",
    "Faut-il fumer un pétard avant de dormir ?", "Faut-il prendre une biture pour fêter ça ?", "Faut-il être saoul pour danser ?",
    "Faut-il ramener du pinard à chaque repas ?", "Faut-il se torcher la gueule au nouvel an ?",
    "Faut-il arroser chaque victoire au champagne ?", "Faut-il tiser avant d'aller en boîte ?",
    "Faut-il être éméché pour chanter au karaoké ?", "Faut-il se défoncer chaque samedi soir ?",
    "Faut-il prendre de la C avant la soirée ?", "Faut-il rouler un pet avant le film ?", "Faut-il faire des paris entre amis ?"]
ANSWERS_TRICKS = [
    "Une Vоdka", "Un Ｗｈｉｓｋｙ", "Du Sмirnoff", "J'adore 🍺", "Un ♥ pour toi", "Le 卐", "Les SS", "J'ai 88 ans",
    "Une 1664", "Un Get 27", "Un Label 5", "Une petite mousse", "Il tient une caisse"]
REFUSED_ANSWERS = sorted(set(ANSWERS_TOUR5 + SLANG_DILEMMAS + ANSWERS_TRICKS))

ACCEPTED_NAMES = [  # faux positifs connus + témoins des scripts
    "Léa", "Paris", "Merdan", "Nazim", "Nazir", "Shitaké", "Chattam", "Hugo", "Chantal", "Zoé", "Anaïs", "O'Neil", "O’Neil",
    "Jean-Pierre", "Dominique", "Tom", "Max", "Paul", "Jean", "Lou", "Julie", "Joueur 1", "Kevin 2", "Marie-Thérèse",
    "Cœur", "Ștefan", "Łukasz", "Ｌéａ", "Violette", "Cuba", "Jess", "Lucas", "Monique", "Hector", "Sacha", "Massimo",
    "Viola", "Champion", "Méthode", "Mona", "Alexe", "Pedro", "Héros", "Loïc", "Ana-Lou", "Ève"]
ACCEPTED_ANSWERS = [
    "Une longue balade au bord du lac", "Le chocolat", "pomme", "Faut-il manger des pâtes chaque jour ?",
    "Faut-il coucher le premier soir ?", "Qu’est-ce que c’est ?", "Je n'ai pas su ce soir", "Un pique-nique",
    "Mon héros", "J'ai 55 ans", "J'ai 30 ans", "Une mousse au chocolat", "Un raton laveur", "Il pleut : 20 % de chances !",
    "« Bonjour » — dit-il…", "La violette et le violon", "Un voyage à Cuba", "Les champions", "5 à 7", "Le 4x4 de papa",
    "Une caisse à outils", "Le demi-frère de Léa"]


@pytest.mark.parametrize("name", REFUSED_NAMES)
def test_every_name_of_the_inspector_stays_refused_in_the_app(name):
    assert main.name_refusal(name, True), name
    assert store_app.name_refused(name)
    with pytest.raises(games.GameError):
        games.shown_text(name, "name", store=True)


@pytest.mark.parametrize("text", REFUSED_ANSWERS)
def test_every_answer_of_the_inspector_stays_refused_in_an_app_game(text):
    with pytest.raises(games.GameError):
        games.shown_text(text, "answer", store=True)


@pytest.mark.parametrize("name", ACCEPTED_NAMES)
def test_ordinary_names_are_still_accepted(name):
    assert main.name_refusal(main.clean_name(name), True) == "", name
    assert not store_app.name_refused(main.clean_name(name))


@pytest.mark.parametrize("text", ACCEPTED_ANSWERS)
def test_ordinary_answers_are_still_accepted(text):
    assert games.shown_text(text, "answer", store=True)


def test_the_web_keeps_its_names_and_answers():
    """Le site et la BETA : ni liste blanche ni familles de l'app (« Νίκος », « Smirnoff » restent possibles)."""
    for text in ("Νίκος", "Léa ✨", "Smirnoff", "Un ti punch"):
        assert main.name_refusal(text, False) == ""
        assert games.shown_text(text, "answer", store=False)
    assert not store_app.drinky("Smirnoff")  # banques et filtre des événements inchangés


def test_names_are_stored_in_nfkc_and_capped():
    assert main.clean_name("Ｌéａ") == "Léa"
    assert not store_app.name_chars_ok("A" * 31)
    code = create(STORE_UA, "quiz", "store5-h", "Ｍａｘ")
    # Décision du 28.11 : « Max » n'est pas dans la liste de l'app (« Ｓａｍ » → « Sam » l'est).
    assert main.store.session.games[code]["players"][0]["name"] == "Joueur 1"
    code = create(STORE_UA, "quiz", "store5-h3", "Ｓａｍ")
    assert main.store.session.games[code]["players"][0]["name"] == "Sam"


def test_a_store_request_cannot_enter_a_name_outside_the_alphabet():
    code = create(STORE_UA, "room", "store5-h1")
    for bad in ("Hіtler", "Léa 卐", "Max 🚬💊", "Νίκος"):
        assert act(STORE_UA, code, "store5-j" + str(len(bad)), bad, "join").status_code == 400, bad
    assert act(STORE_UA, code, "store5-ok", "Zoé", "join").status_code == 200
    r = client(STORE_UA).post("/api/games", json={"guest_id": "store5-h2", "name": "Ｖｏｄｋａ", "type": "quiz", "terms": True})
    assert r.status_code == 400
    assert client(STORE_UA).post("/api/presence", json={"guest_id": "store5-p", "name": "Léa 卐"}).status_code == 400


def test_a_web_name_outside_the_alphabet_becomes_joueur_n_in_the_app():
    code = create(WEB_UA, "likely", "webxx5-h", "Νίκος")
    g = main.store.session.games[code]
    games.join(g, "webxx5-e", "Max 🚬")
    games.join(g, "webxx5-z", "Zoé")
    v = client(STORE_UA).get(f"/api/games/{code}?guest_id=store5-t&name=Tom").json()
    assert sorted(p["name"] for p in v["players"]) == ["Joueur 1", "Joueur 2", "Zoé"]
    dump = json.dumps(g, ensure_ascii=False)
    assert "Νίκος" not in dump and "🚬" not in dump


@pytest.mark.parametrize("kind", ["neon", "island", "heist"])
def test_3d_frames_check_the_store_access_on_their_own(kind):
    """La trame seule (sans lecture de la partie avant) : prénoms réécrits, partie à gorgées refusée."""
    code = create(WEB_UA, kind, "webxx5-h3", "Léa")
    g = main.store.session.games[code]
    games.join(g, "webxx5-m3", "Hitler")
    games.join(g, "webxx5-n3", "Νίκος")
    act(WEB_UA, code, "webxx5-h3", "Léa", "start")
    frame = client(STORE_UA).post(f"/api/games/{code}/{kind}", json={"guest_id": "store5-3d"})
    assert frame.status_code == 200, frame.text
    dump = json.dumps(frame.json(), ensure_ascii=False) + json.dumps(g, ensure_ascii=False)
    assert "Hitler" not in dump and "Νίκος" not in dump and g.get("store")
    g["options"]["sips"] = 2  # partie du web à gorgées : jamais dans l'app
    assert client(STORE_UA).post(f"/api/games/{code}/{kind}", json={"guest_id": "store5-3d"}).status_code == 403
    assert client(WEB_UA).post(f"/api/games/{code}/{kind}", json={"guest_id": "webxx5-h3"}).status_code == 200


# ── Filtre commun : sosies et NFKC, côté serveur ET côté base ──

MIGRATION = ROOT / "supabase/migrations/20261127130000_filtre_sosies.sql"


@pytest.mark.parametrize("text", ["Cоnnard", "CОNNARD", "Ｃｏｎｎａｒｄ", "𝐒𝐚𝐥𝐨𝐩𝐞", "Sаlope", "Еnculé"])
def test_the_common_filter_sees_lookalikes_and_wide_forms(text):
    assert not moderation.check(text, "name").ok


def test_the_common_filter_keeps_ordinary_and_foreign_names():
    for text in ("Léa", "Anaïs", "Paris", "Νίκος", "Иван", "Merdan"):
        assert moderation.check(text, "name").ok, text


def test_the_migration_normalizes_exactly_like_the_server():
    sql = MIGRATION.read_text()
    m = re.search(r"translate\(lower\(translate\(coalesce\(t, ''\),\s*'([^']*)',\s*'([^']*)'\)\),\s*'([^']*)',\s*'([^']*)'\)", sql)
    assert m.group(1) == moderation.SOSIES_FROM and m.group(2) == moderation.SOSIES_TO
    assert m.group(3) == moderation.ACCENTS_FROM + moderation.LEET_FROM + moderation.SOSIES_FROM
    assert m.group(4) == moderation.ACCENTS_TO + moderation.LEET_TO + moderation.SOSIES_TO
    assert "normalize(coalesce(t, ''), NFKC)" in sql
    prod = ROOT / "supabase/prod/2026-11-27-filtre-sosies-apply.sql"
    assert sql in prod.read_text() and "'20261127130000'" in prod.read_text()
    assert "where version = '20261127130000'" in (ROOT / "supabase/prod/2026-11-27-filtre-sosies-rollback.sql").read_text()
