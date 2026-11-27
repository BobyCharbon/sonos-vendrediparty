"""Contrôle Apple, tour 6 (27.11) : textes des JOUEURS de l'app App Store (« PartyStore »). Une passe bornée qui ferme les
familles PAR CONSTRUCTION, au lieu d'allonger la liste mot par mot (tours 4, 5, 6) :
- alphabet : seulement les lettres que le pli (NFKD sans accents, ı ĸ đ ð ħ ŀ ŋ þ ŧ ł ø æ œ ß ŉ) ramène à a-z, Latin
  étendu additionnel compris (Thị, Đức, Ngọc) ; chaque caractère admis est vérifié ;
- formes dérivées examinées EN PLUS de la forme normale : pli, lettres répétées (3 fois ou plus), « ! » / « + » entre deux
  lettres, lettre doublée en fin de mot, 2 et 3 morceaux recollés (mot entier), mot collé à un article, mots collés des
  réponses (hors mots du dictionnaire) ;
- famille anglais / allemand / italien / espagnol (moderation_terms.STORE_ONLY, textes des joueurs seulement) ;
- joueur de l'app jamais inscrit dans un jeu de salle qu'elle ne voit pas.
Corpus : scripts du contrôleur (c1 à c5, recopiés ici : le dossier de travail est éphémère)."""
import pytest
from fastapi.testclient import TestClient

from app import games, main, moderation, store_app

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
WEB_UA = "Mozilla/5.0 Safari"


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


def name_blocked(text) -> bool:
    try:
        return main.name_refusal(main.clean_name(text), True) != ""
    except Exception:
        return True


def answer_blocked(text) -> bool:
    """Refusée, ou montrée masquée (insulte d'un mot : ••••)."""
    try:
        return games.shown_text(text, "answer", store=True) != text
    except games.GameError:
        return True


C1 = [
    'Vŏdka', 'Hıtler', 'Vodĸa', 'Hĩtler', 'Wĥisky', 'Ŝalope', 'Pastiș', 'Șhot', 'Cŏke', 'Ganĵa', 'Mĕrde', 'Pŭtain',
    'Bĭère', 'Nazĭ', 'Hītler', 'Ƿeed', 'Vođka', 'Coñnard', 'Vooodka', 'Whiiisky', 'Biiière', 'Rhuuum', 'Shooot',
    'Pastiiis', 'Cooke', 'Weeeed', 'Coooke', 'Tequiiila', 'Vo dk a', 'Hi tl er', 'V od ka', 'Pas tis', 'Ri card',
    'Mo jito', 'Co ke', 'Mer de', 'Ga nja', 'Coc aine', 'Jo int', 'Wee d', 'Gor gée', 'Sh ot', 'Cham pagne', 'Ap éro',
    'Vi n', 'Rh um', 'Pas-tis', 'Mer-de', 'Hit-l-er',
]

C2 = [
    'Bier', 'Ein Bier bitte', 'Saufen', 'Besoffen', 'Kiffen', 'Wein', 'Birra', 'Ubriaco', 'Sbronza', 'Cerveza',
    'Borracho', 'Chupito', 'Porro', 'Cerveja', 'Booze', 'Drunk', 'Wasted', 'Hammered', 'Tipsy', 'Stoned',
    'Getting high', 'Bong', 'Blunt', 'Dope', 'Molly', 'Acid', 'Shrooms', 'Xanax', 'Lean', 'Purple drank', 'Dronken',
    'Zuipen', 'Biertje', 'Un petit rosé', 'Un Martini', 'Un Malibu', 'Une Suze', 'Un Get', 'Une Jupiler',
    'Une Corona', 'Une Paulaner', 'Une Kwak', 'Une Orval', 'Une Chouffe', 'Un jaja', 'Se murger', 'Se pinter',
    'Se cuiter', 'Déchiré', 'Rond comme une queue de pelle', 'Faire la chouille', 'Un taz', 'Un ecsta', 'De la MD',
    'Un ballon de proto', 'Du proto', 'Gaz hilarant', 'Un buvard', "De l'amphé", 'Sniffer un trait', 'Un bédo',
    'Un gros spliff', 'Du zamal', 'Du teuch', 'Du shit', 'Une Marlboro', 'Des Gitanes', 'Une Elfbar', 'Un Juul',
    'Une IQOS', 'Un Lucky Strike', 'Faites vos Paris', 'Les Paris sportifs', 'Une mise en jeu de 10 francs',
    'Le Quinté', 'Le Tiercé', 'Swisslos', 'La Loterie Romande', 'Bet365', '1xBet', 'Betway', 'Le bandit manchot',
    'Le baccara', 'Texas Holdem', "Jouer de l'argent", 'Une cagnotte', 'Gratter un Millionnaire', 'Un Tribolo',
    'Auschwitz', 'Mein Kampf', 'Pétain', 'Troisième Reich', 'Bin Laden', 'Oussama', 'Dutroux', 'Fourniret', 'Breivik',
    'ISIS', 'Rital', 'Boche', 'Bridé', 'Toubab', 'Pédale', 'Fiotte', 'Tafiole', 'Travelo', 'Triso', 'Mongolien',
    'Attardé', 'Autiste', 'Sale blanc', 'Sale gitan', 'Sale chinois', 'Sale pédé', '14/88', '14-88', 'S S', 'HH',
    'Rudolf Hess', 'Heydrich', 'Eichmann', 'Levrette', 'Plan cul', 'Chaudasse', 'Tchoin', 'Cochonne', 'Turlute',
    'Zob', 'Chibre', 'Braquemart', 'Foufoune', 'Nibards', 'Boobs', 'Bander', 'Orgasme', 'Gangbang', 'BDSM',
    'Onlyfans', 'MILF', 'Hentai', 'Sex', 'Fist', 'Gros cul', 'Pipe', 'Escort', 'Catin', 'Prostituée', 'Une capote',
    'Nympho', '69', 'Sucer', 'Bite', 'Kill yourself', 'Kys', 'Va crever', 'Je vais te tuer', 'Va te pendre',
    'Ta gueule', 'Ftg', 'Va te faire foutre', 'Fils de chien', 'Enculer', 'Nique ta race',
]

C3 = [
    'Margarita', 'Trinquier', 'Brandy', 'Sherry', 'Kirsch', 'Heineken', 'Champagne', 'Bourbon', 'Pinot', 'Merlot',
    'Cognac', 'Porto', 'Torpedo', 'Ginette', 'Gina', 'Vincent', 'Barbara', 'Basile', 'Ambre', 'Tabata', 'Whiskers',
    'Rosé', 'Bacchus', 'Sake', 'Picolo', 'Pinardi', 'Picoli', 'Ganjavi', 'Isis', 'Mise', 'Misa', 'Paris', 'Pâris',
    'Viola', 'Violaine', 'Heroine', 'Sucette', 'Branly', 'Hero', 'Mongo', 'Sexton', 'Anal', 'Analia', 'Annalisa',
    'Cockburn', 'Dick', 'Coco', 'Kiki', 'Pipo', 'Pute', 'Fanny', 'Ass', 'Bassam', 'Hassan', 'Assia', 'Massa',
    'Jasmine', 'Shiva', 'Chicha', 'Bar', 'Barry', 'Tom Bar', 'Abigaïl', 'Mathis', 'Noé', 'Inès', 'Mélissa', 'Yasmine',
    'Ilyès', 'Kenza', 'Soumaya', 'Bilal', 'Rayane', 'Chaïma', 'Wassim', 'Louna', 'Khadija', 'Fatoumata', 'Oumou',
    'Aïssatou', 'Mamadou', 'Moussa', 'Kwame', 'Tiago', 'Joao', 'Ngozi', 'Nguyen', 'Thị', 'Đức', 'Mỹ', 'Ngọc',
    'Siobhán', 'Seán', 'Björn', 'Søren', 'Åsa', 'Zoë', 'Øystein', 'Þór', 'Dóra', 'Ðorđe', 'Ibrahim', 'Gülşen',
    'Çağla', 'Ayşe', 'Oğuz', 'Şükrü', 'İlker', 'Michał', 'Paweł', 'Wojciech', 'Dvořák', 'Jiří', 'Ľubica', 'Miłosz',
    'Emeka', "J'ai arrosé les plantes", 'Une tournée de concerts', "Un verre d'eau", 'Un voyage à Porto',
    "J'habite à Bordeaux", 'Le joint de la salle de bain', 'Un crack en maths', 'Un screenshot', 'Une mise à jour',
    'Un shooting photo', 'La Champagne', 'Le bar à jus', 'Ma tante Ginette', 'Le vin chaud de Noël',
    'Les grands crus', 'Un pot de départ', 'Sexy', 'Le sexe des anges', 'Les huîtres', 'Un mot de passe',
    'Le pari de Pascal', 'Pierre a parié', 'Mon pédiatre', 'Les Pays-Bas', 'La gorge', 'Un doigt de miel', 'La meth',
    'La méthode', 'Le Rhin', 'Bu', 'Ma mère est conne', "C'est le coco", 'Le bourbier', 'Le shotgun', 'Un portrait',
]

C4 = [
    'VivaHitler', 'AdolfHitler', 'Unevodka', 'Unshot', 'Monjoint', 'Lamerde', 'Cettemerde', 'Grosnazi', 'Unebière',
    'Duwhisky', 'H!tler', 'V*dka', 'Sh!t', 'Pu+ain', 'Wh!sky', 'C0ke', 'Vodk@', 'Hitl3r', 'M€rde', 'Hi.tler',
    "Hit'ler", 'Merdeee', 'Faites vos PARIS', 'Paris sur le match', 'Ganjaaa', 'Ganja', 'Ga-nja', 'Ri-card', 'Ricard',
    'Ricaaard', 'Pastis', 'Pastisss', 'Champagneee', 'Moooojito', 'Rhuum', 'Bièèère', 'Shoot', 'Shots', 'Shotss',
    'Picoleee', 'Pompettte', 'Coc4ïne', 'Cocaiiine', 'Kokain', 'Cocaína', 'Heroin', 'Marihuana', 'Cannabiss', 'Nazzi',
    'Nazii', 'Hiiitler', 'Hitleeer', 'Saloppe',
]

C5 = [
    'Wine', 'Liquor', 'Keg', 'Chug', 'Chug it', 'Drinking game', 'Hangover', 'Smoke weed', '420', 'Get high',
    'Get lit', 'Jello shots', 'Shots shots shots', 'Beer', 'Beers', 'Drink', 'Drinks', 'Drinking', "Let's drink",
    "Let's get drunk", 'Tipsy Tom', 'Alcohol', 'Whiskey sour', 'Rum', 'Lager', 'Ale', 'Stout', 'Cider',
    'Booze cruise', 'Pothead', 'Stoner', 'Crackhead', 'Junkie', 'Cocaine', 'Coke', 'Meth head', 'Lines', 'Snort',
    'Pills', 'Cigarette', 'Cig', 'Smoke', 'Vape', 'Juul', 'Bet', 'Betting', 'Gamble', 'Gambling', 'Wager', 'Odds',
    'Penis', 'Dick', 'Cock', 'Tits', 'Boobs', 'Ass', 'Butt', 'Nude', 'Naked', 'Horny', 'Sexy', 'Sex', 'Fuck', 'Shit',
    'Bitch', 'Slut', 'Whore', 'Retard', 'Nigger', 'Nazi', 'Hitler', 'Kill yourself', 'KYS', 'Die', 'Suicide', 'Rape',
    'Rapist', 'Pedo', 'Pedophile', 'Terrorist', 'Isis', 'Allah akbar',
]


# Ce qui passe ENCORE, exprès (rapport du tour 6) : mots rares isolés ou à double sens, dont le refus coûterait des
# prénoms ou des phrases ordinaires. « Shoot » DOIT passer (faux refus à éviter).
STILL_PASSING = {
    "Cooke", "Rhuum",  # lettre doublée au milieu d'un mot (Shoot ; Cooke : nom de famille)
    "Porro", "Bong", "Blunt", "Dope", "Molly", "Acid", "Lean", "Un Malibu", "Une Suze", "Un Get", "Une Corona",
    "Une Orval", "Déchiré", "Un taz", "Un buvard", "Des Gitanes", "Une mise en jeu de 10 francs", "Une cagnotte",
    "Gratter un Millionnaire", "Oussama", "ISIS", "Isis", "Bridé", "Toubab", "Pédale", "Mongolien", "Attardé", "Autiste",
    "Turlute", "Bander", "Fist", "Pipe", "Escort", "Une capote", "69", "420", "Paris sur le match", "Shoot", "Ale",
    "Stout", "Lines", "Pills", "Smoke", "Odds", "Butt", "Retard", "Die", "Allah akbar",
    "Lager", "Un jaja",  # allemand : « Lager » (camp), « ja ja »
}
NAME_ONLY = {"Le Tiercé"}  # « tierce » refusé dans un prénom seulement (« la tierce personne » passe)
REFUSED = sorted(set(C1 + C2 + C4 + C5) - STILL_PASSING)

# c3 : faux refus à éviter (prénoms du monde, phrases ordinaires) mêlés de cas refusés exprès.
C3_REFUSED = {  # refusés exprès (vérifiés)
    "Margarita", "Kirsch", "Heineken", "Champagne", "Bourbon", "Pinot", "Merlot", "Cognac", "Porto", "Sake", "Mise",
    "Heroine", "Hero", "Anal", "Dick", "Pute", "Ass", "Chicha", "Bar", "Tom Bar", "Le vin chaud de Noël",
    "Un pot de départ", "Sexy", "Le sexe des anges", "Le pari de Pascal", "Pierre a parié", "La meth", "Bu",
    "Ma mère est conne",
}
# Refusés À TORT, qui restent (rapport du tour 6, jamais vérifiés ici pour qu'une correction ne casse rien) : un mot de
# DRINK_RE dans une phrase ordinaire (banques et événements gardent DRINK_RE), noms de famille qui contiennent un mot collé.
C3_WRONGLY_REFUSED = {
    "J'ai arrosé les plantes", "Une tournée de concerts", "Un voyage à Porto", "Le joint de la salle de bain",
    "La Champagne", "Le bar à jus", "Trinquier", "Branly", "Picolo", "Picoli", "Pinardi", "Ganjavi", "Whiskers", "Torpedo",
}
C3_ACCEPTED = [x for x in C3 if x not in C3_REFUSED | C3_WRONGLY_REFUSED]
FALSE_REFUSALS = ["Un verre d'eau", "La mer de glace", "Shoot", "Un crack en maths", "J'habite à Bordeaux"]
ORDINARY_ANSWERS = FALSE_REFUSALS + [
    "la tierce personne", "Torpedo", "Je n'ai pas su ce soir", "Il a pu te voir", "Le chat te regarde",
    "Du fromage râpé",
    "Une râpe à fromage", "Les députés à Paris", "La Tamise", "Décider seulement par 1 et par 2", "Un épinard",
    "Ça me terrorisait", "Mon héros", "Bonjour !", "Il pleut : 20 % de chances !", "J'ai 69 ans", "Un shooting photo",
    "Une mise à jour", "Les grands crus", "Ana l'a dit", "Vi n'a rien dit", "Le noyau du proton", "Snif !", "Ja ja",
    "Je viens de Bordeaux", "La mer des Sargasses"]
# Prénom + initiale (deux Léa à la table) : jamais recollés (« Ana L » ≠ « anal », « Vi N » ≠ « vin », « Martin I »).
INITIALS = ["Ana L", "Vio L", "Vi N", "Martin I", "Gi N", "Léa B", "Sho T"]
# Contournements de PLAYER_SAFE : refusés comme avant.
SAFE_BYPASSES = ["Un verre d'eau-de-vie", "Un verre d'eau de vie", "Du crack en soirée", "Un grand cru de Bordeaux",
                 "Un rouge de Bordeaux", "Vi n"]
VIETNAMESE = ["Thị", "Đức", "Ngọc", "Mỹ", "Nguyễn Văn", "Trần Thị Ánh", "Huỳnh", "Phạm"]


@pytest.mark.parametrize("text", REFUSED)
def test_every_text_of_the_inspector_is_refused_as_a_name(text):
    assert name_blocked(text), text


@pytest.mark.parametrize("text", sorted(set(REFUSED) - NAME_ONLY))
def test_every_text_of_the_inspector_is_refused_or_masked_as_an_answer(text):
    assert answer_blocked(text), text


@pytest.mark.parametrize("text", sorted(C3_REFUSED))
def test_the_refused_probes_of_c3_stay_refused(text):
    assert name_blocked(text) and answer_blocked(text), text


@pytest.mark.parametrize("text", C3_ACCEPTED + VIETNAMESE + FALSE_REFUSALS)
def test_names_and_sentences_of_the_world_still_pass(text):
    assert not name_blocked(text), text
    assert not answer_blocked(text), text


@pytest.mark.parametrize("text", INITIALS)
def test_a_name_with_an_initial_is_never_glued(text):
    assert not name_blocked(text), text


@pytest.mark.parametrize("text", SAFE_BYPASSES)
def test_the_ordinary_phrases_open_no_way_around_the_filter(text):
    assert name_blocked(text) and answer_blocked(text), text


@pytest.mark.parametrize("text", ORDINARY_ANSWERS)
def test_ordinary_answers_still_pass(text):
    assert not answer_blocked(text), text


def test_every_admitted_letter_folds_to_plain_latin():
    """L'alphabet des prénoms et réponses : AUCUNE lettre que le pli ne ramène pas à a-z (sinon elle contourne la liste)."""
    admitted = [c for c in map(chr, range(0x3000)) if c.isalpha() and store_app.NAME_CHARS.fullmatch(c)]
    assert len(admitted) > 400
    for c in admitted:
        assert store_app.ANSWER_CHARS.fullmatch(c), c
        folded = moderation.normalize(store_app.fold(c).lower())
        assert folded.isascii() and folded.isalpha() and folded.islower(), (c, hex(ord(c)), folded)
    for c in "ẜẝẟỺỻỼỽỾỿẚ×÷ʼ":  # sans pli vers a-z : refusées
        assert not store_app.NAME_CHARS.fullmatch(c), c
    assert store_app.fold("Vŏdka Hıtler Vođka Þór Łukasz Œuvre ŀ ŉ ŧ") == "Vodka Hitler Vodka Thor Lukasz Oeuvre l n t"


def test_derived_forms_are_read_in_addition_to_the_normal_form():
    for bad in ("Vooodka", "Biiière", "Pompettte", "Shotss", "Vo dk a", "Hi tl er", "Pas tis", "Hit-l-er", "H!tler",
                "Pu+ain", "VivaHitler", "Lamerde", "Unshot", "Monjoint", "Ŝalope", "Mĕrde"):
        assert store_app.player_offensive(bad) or store_app.glued_hit(bad, store_app.GLUED_ANSWER), bad
    for ok in ("Shoot", "La mer de glace", "par !", "Barr", "Ginn", "Desbois", "Levin", "Leverrier"):
        assert not store_app.player_offensive(ok), ok


def test_the_new_family_is_for_players_only():
    """Banques et filtre des événements (drinky, DRINK_RE) inchangés ; le web garde ces textes."""
    for word in ("Alcohol", "Drunk", "Wine", "Bier", "Saufen", "Birra", "Cerveza", "Borracho", "Bet", "Gambling", "Sex",
                 "Kill yourself", "KYS", "Rape", "Stoned"):
        assert store_app.player_offensive(word), word
        assert not store_app.drinky(word), word
        assert main.name_refusal(word, False) == "", word
    assert not store_app.player_offensive("Une râpe à fromage")


def client(ua):
    return TestClient(main.app, headers={"User-Agent": ua})


def act(ua, code, gid, name, action, **kw):
    return client(ua).post(f"/api/games/{code}", json={"guest_id": gid, "name": name, "action": action, "terms": True, **kw})


@pytest.mark.parametrize("kind,settings", [(k, {}) for k in ("pyramid", "never", "roulette", "casino")]
                         + [("quiz", {"sips": 2}), ("likely", {"mode": "hot"})])
def test_an_app_player_never_enters_a_room_game_the_app_cannot_see(kind, settings):
    r = client(WEB_UA).post("/api/games", json={"guest_id": "web6tour-h1", "name": "Léa", "type": "room", "terms": True})
    room = r.json()["code"]
    assert act(WEB_UA, room, "web6tour-p2", "Max", "join").status_code == 200
    assert act(WEB_UA, room, "web6tour-h1", "Léa", "launch", settings={"type": kind, **settings}).status_code == 200
    child = main.store.session.games[room]["current"]
    assert act(STORE_UA, room, "store6tour-a1", "Tom", "join").status_code == 200  # la salle, oui
    assert not any(p["id"] == "store6tour-a1" for p in main.store.session.games[child]["players"])  # le jeu caché, non
    assert client(STORE_UA).get(f"/api/games/{child}?guest_id=store6tour-a1&name=Tom").status_code == 403
    assert act(WEB_UA, room, "web6tour-p3", "Zoé", "join").status_code == 200  # le web, lui, entre toujours
    assert any(p["id"] == "web6tour-p3" for p in main.store.session.games[child]["players"])
