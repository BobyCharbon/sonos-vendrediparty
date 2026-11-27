"""Contrôle Apple, tour 8 (27.11), angle jeux, puis tout Party (filtre COMMUN, app/moderation.py et la base) :
- 🔴1 phrases de haine : liste fermée de groupes × tournures hostiles (« Mort aux juifs », « Sales arabes », « Les noirs
  dehors », « Négresse »…), refusées en surnom, nom, message, réponse de jeu, prénom de l'app ;
- 🔴2 incitation au suicide en phrases (« Va te jeter d'un pont », « Tire-toi une balle », « Meurs »…), même chose ;
- sans faux refus : « J'adore la cuisine arabe », « Je meurs de faim », « Va te jeter à l'eau », « Salle noire »…"""
import pytest

from app import games, main, moderation

HATE = [
    "Mort aux juifs", "Sale juive", "Sales juifs", "Sales arabes", "Sales noirs", "Négresse", "Sale négresse",
    "Mort aux arabes", "Mort aux noirs", "Mort aux musulmans", "Mort aux gays", "Gazer les juifs", "Les juifs au four",
    "Les noirs dehors", "Les arabes dehors", "Les étrangers dehors", "Je hais les noirs", "Sale musulman", "Sale gay",
    "Sale lesbienne", "Sale trans", "Sale handicapé", "Sale renoi", "Sale rebeu", "Je déteste les femmes",
    "J'emmerde les musulmans", "À bas les chrétiens", "Exterminer les roms", "Brûler les gitans", "Tuer tous les homos",
    "Sale pédé", "Sales chinois", "Sale feuj", "Juifs dehors", "Les immigrés à la chambre à gaz", "Sale blanche",
    "Mort aux femmes", "A mort les gays", "Sale africain", "Je hais les asiatiques", "Sale migrant", "Crever les noirs",
    "SALE JUIF", "S@le ar@be", "Mort aux juuuifs", "Les blacks dehors", "Sale tsigane",
    # variantes d'un cran (relecture du lot 15)
    "Arabes dehors", "Noirs dehors", "Africains dehors", "Réfugiés dehors", "Femmes dehors", "Trans dehors",
    "Blacks dehors", "Morts aux juifs", "Sale petit juif", "Sale grosse arabe", "Gitans au four",
]
SUICIDE = [
    "Va te jeter d'un pont", "Va te jeter sous un train", "Va te jeter par la fenêtre", "Va te noyer", "Tire-toi une balle",
    "Fous-toi en l'air", "Va te foutre en l'air", "Meurs", "Meurs connard", "Meurs !", "Le monde irait mieux sans toi",
    "Personne ne te regrettera", "Personne te regrettera", "Go die", "Va te pendre", "Va te suicider",
    "Ouvre-toi les veines", "Tue-toi", "Pends-toi", "Va te tuer", "Va te jeter", "Kill yourself",
    "Jette-toi du haut d'un pont", "Allez vous pendre", "Sérieux va te pendre",
    "Meurs donc", "Meurs débile", "Meurs dans d'atroces souffrances", "Tue-toi oui", "Pends-toi et vite",
    "Bon va te pendre", "Non va te noyer", "Bouffon va te suicider", "Va te jeter dans la Seine",
]
# Faux refus vérifiés. Choix : « Va te jeter à l'eau » (= lance-toi) et « Tire-toi une balle dans le pied » passent ;
# « Va te jeter » seul est refusé. « blanc » est aussi une couleur et un blanc d'œuf : « les blancs au four » passe.
FINE = [
    "J'adore la cuisine arabe", "Mon ami est juif", "Les femmes du groupe", "Je hais les lundis", "Mort de rire",
    "Ma grand-mère est morte", "Je meurs de faim", "Va te coucher", "Va te jeter à l'eau",
    "Le monde irait mieux sans pollution", "Rom-com", "Gitan", "Il fait noir dehors", "Salle noire", "Salle blanche",
    "Salle handicapés", "Negresco", "Je déteste les blancs d'oeuf", "Brûler les blancs de poulet", "Je joue les noirs",
    "Les blancs au four", "Pain arabe au four", "Poulet chinois au four", "On mange chinois dehors",
    "Tu vas te tuer à la tâche", "Le loup va te tuer", "Il va te tuer", "Tire-toi une balle dans le pied", "Meursault",
    "Je meurs", "Meurs pas", "Mort aux rats", "Les juifs de Genève", "Les Noirs Désirs", "Mon chat va mourir",
    "Go Die Hard", "Les gays du village", "Fierté gay", "La communauté musulmane", "Les chrétiens d'Orient",
    "Lance-toi dans la vie", "Les enfants dehors", "Sortons dehors les amis", "Qui tue ? Toi ou moi",
    "Tu vas te noyer si tu nages là", "Allez-vous tuer le dragon ?", "Sale temps", "Ma salle de bain est sale",
    "Linge sale", "Les Roms", "Trans Europe Express", "Gay Pride", "Les femmes au pouvoir", "Les étrangers bienvenus",
    "Je déteste les chats", "Il faut tuer les moustiques", "Je vais te jeter à l'eau", "Il meurt de rire",
    "Les femmes à mort de rire", "Pains arabes au four", "Il fait noir dehors ce soir", "On va te noyer sous les cadeaux",
]


@pytest.mark.parametrize("text", HATE + SUICIDE)
@pytest.mark.parametrize("kind", ["name", "message", "answer"])
def test_hate_and_suicide_phrases_are_refused_by_the_common_filter(text, kind):
    v = moderation.check(text, kind)
    assert not v.ok and v.category == "haine", (text, kind, v)


@pytest.mark.parametrize("text", HATE + SUICIDE)
def test_hate_and_suicide_phrases_are_refused_as_an_app_player_name_and_answer(text):
    assert main.name_refusal(text, True) != ""
    with pytest.raises(games.GameError):
        games.shown_text(text, "answer", store=True)


@pytest.mark.parametrize("text", FINE)
@pytest.mark.parametrize("kind", ["name", "message", "answer"])
def test_ordinary_sentences_are_not_refused(text, kind):
    v = moderation.check(text, kind)
    assert v.ok and v.text == text, (text, kind, v)


def test_the_phrases_need_their_hostile_turn_or_target():
    """Par construction : un groupe seul ou une tournure seule ne suffit pas, les deux ensemble oui."""
    assert moderation.check("Les musulmans", "name").ok and moderation.check("Mort aux", "name").ok
    assert not moderation.check("Mort aux musulmans", "name").ok
    assert moderation.check("Va te", "name").ok and moderation.check("un pont", "name").ok


# ── 🟠 joueurs de l'app seulement (app/store_app.py) ──
def answer_blocked(text) -> bool:
    try:
        return games.shown_text(text, "answer", store=True) != text
    except games.GameError:
        return True


@pytest.mark.parametrize("text", ["V()dka", "C()ke", "Bière sans alcool", "Je bois de la vodka",
                                  "Je bois de l'eau et de la vodka", "Je bois de l'eau-de-vie", "Bois du whisky"])
def test_parentheses_as_o_and_drinks_next_to_a_safe_phrase_stay_refused(text):
    assert answer_blocked(text)


@pytest.mark.parametrize("text", ["Je bois de l'eau", "J'ai bu un café", "Il boit trop de café", "Zéro alcool",
                                  "Une soirée sans alcool", "Non à la drogue", "Le tabac tue", "Je déteste la cigarette",
                                  "Un trou noir dans l'espace", "J'habite à Porto-Novo"])
def test_ordinary_answers_about_water_coffee_or_saying_no_pass(text):
    assert not answer_blocked(text)


@pytest.mark.parametrize("name", ["Bordeaux", "Porto Novo", "Cointreau", "Léa Bordeaux", "Marc Cointreau"])
def test_place_and_family_names_pass_as_app_player_names(name):
    assert main.name_refusal(name, True) == ""


@pytest.mark.parametrize("name", ["Le Bordeaux", "Bordeaux rouge", "Mon Cointreau", "Team Cointreau", "Un rouge de Bordeaux",
                                  "Vodka Bordeaux"])
def test_a_family_name_never_covers_a_drink(name):
    assert main.name_refusal(name, True) != ""


@pytest.mark.parametrize("text", ["Jamais sans alcool", "Pas de soirée sans alcool", "Impossible sans alcool",
                                  "Jamais zéro alcool"])
def test_without_alcohol_only_passes_when_it_says_no(text):
    assert answer_blocked(text)


@pytest.mark.parametrize("card", ["Si votre couple était une boisson, laquelle serait-ce ?",
                                  "Quelle soirée de ton groupe d'amis est devenue légendaire ?",
                                  "Quelle soirée entre amis restera légendaire dans votre histoire ?"])
def test_divan_cards_about_a_drink_or_a_legendary_night_are_left_out_of_the_app(card):
    from app import divan_cards, store_app
    assert card in str(vars(divan_cards)) and store_app.drinky(card)
    assert not store_app.drinky("Si tu étais une créature légendaire, laquelle serais-tu ?")
