"""Lot 15b (27.11) : le filtre COMMUN (app/moderation.py et la base : surnoms, noms, messages de tout Party) ne refuse
aucune phrase ordinaire. Les tournures du tour 8 qui en refusaient (« dehors », « au four », « je déteste les », « tuer
les », impératifs du suicide…) ne valent plus que pour les joueurs de l'app (STORE_ONLY, tests/test_store_jeux_tour8.py)."""
import pytest

from app import moderation

# Faux refus du lot 15 (relevés par l'admin), puis les phrases sûres du lot 15.
ACCEPTED = [
    "Va te tuer à la tâche", "Va te tuer au travail", "Lance-toi dans le vide", "Jette toi dans le lac",
    "Tue-toi à la tâche", "Tue toi pas trop", "Noie-toi dans le travail", "Pends-toi à mon cou",
    "Va te noyer dans tes larmes", "Va te pendre au cou de ta mère", "Je déteste les noirs et les gris en déco",
    "Je déteste les chinois de la rue d'à côté, ils ferment tôt", "Il faut tuer les noirs aux échecs",
    "Les noires au four", "Les femmes dehors au soleil", "Personne ne te regrettera ton gâteau", "Daniel va te noyer",
    "Les gays dehors ce soir pour la pride", "Les arabes dehors sur la terrasse avec nous",
    "J'adore la cuisine arabe", "Mon ami est juif", "Je meurs de faim", "Va te coucher", "Va te jeter à l'eau",
    "Le monde irait mieux sans pollution", "Mort de rire", "Mort aux rats", "Salle noire", "Il fait noir dehors",
    "Je déteste les blancs d'oeuf", "Les blancs au four", "Pain arabe au four", "Gay Pride", "Les Roms", "Mort au chinois",
]
NAMES = ["Nazim", "Nazir", "Reichenbach", "Negresco", "Salle noire", "Gay Pride", "Mort de rire", "Daniel", "Kkkk",
         "Les Roms", "Meursault"]
REFUSED = ["Sale juif", "Mort aux arabes", "Gazer les juifs", "Hitler", "Vive Daech", "KKK", "Négresse", "Sales arabes",
           "À mort les gays", "Exterminer les roms", "Les juifs à la chambre à gaz", "Néo-nazi", "Nazis", "Nazisme",
           "Gestapo", "Ku Klux Klan", "Daesh", "Swastika", "Croix gammée", "Heil Hitler", "Sieg Heil", "S@le ar@be"]


@pytest.mark.parametrize("text", ACCEPTED)
def test_ordinary_sentences_pass_the_common_filter_as_a_message(text):
    v = moderation.check(text, "message")
    assert v.ok and v.text == text, (text, v)


@pytest.mark.parametrize("text", NAMES)
def test_plausible_names_pass_the_common_filter(text):
    v = moderation.check(text, "name")
    assert v.ok and v.text == text, (text, v)


@pytest.mark.parametrize("text", REFUSED)
@pytest.mark.parametrize("kind", ["name", "message"])
def test_hate_without_double_meaning_stays_refused_everywhere(text, kind):
    v = moderation.check(text, kind)
    assert not v.ok and v.category == "haine", (text, kind, v)
