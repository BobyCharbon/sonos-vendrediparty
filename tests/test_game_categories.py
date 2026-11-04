"""Catégories de l'écran Jeux et de la salle de jeux (définies dans games.js) : chaque jeu du serveur est rangé dans
exactement une catégorie, pour qu'un nouveau jeu ne disparaisse pas de l'accueil."""
import json
import re
from pathlib import Path

from app import games

JS = (Path(__file__).resolve().parent.parent / "app" / "static" / "games.js").read_text(encoding="utf-8")


def categories() -> list[tuple[str, str, list[str]]]:
    block = re.search(r"const GAME_CATEGORIES = (\[.*?\]);\n", JS, re.S).group(1)
    return [tuple(c) for c in json.loads(block)]


# Rangés dans une catégorie sans être une partie du serveur : Méninges (entraînement solo, app/static/brain/) et
# Compagnon (personnage à entretenir, app/static/pet/).
CLIENT_ONLY = {"brain", "pet"}


def test_every_game_is_in_exactly_one_category():
    listed = [t for _, _, types in categories() for t in types if t not in CLIENT_ONLY]
    assert sorted(listed) == sorted(t for t in games.GAMES if t != "room")
    assert not CLIENT_ONLY & set(games.GAMES)


def test_categories_in_the_chosen_order():
    # Compagnon et Méninges en tête (demandes de l'admin, 03.11 et 04.11.2026).
    assert [label for _, label, _ in categories()] == ["✨ Chaque jour", "🍻 Alcool", "🎮 Jeux 3D", "💞 Parler vrai", "🃏 Jeux de cartes",
                                                     "🎉 Ambiance"]
    cats = {cid: types for cid, _, types in categories()}
    assert set(cats["talk"]) == {"masque", "reflet", "psy", "divan", "debate", "tmc"}
    assert set(cats["cards"]) == {"pyramid", "blackjack", "president"}
    assert set(cats["three"]) == {"neon", "island", "heist"}
    assert set(cats["mood"]) == {"quiz", "undercover", "likely"}
    assert cats["brain"] == ["pet", "brain"]


def test_brain_card_opens_the_training_panel_not_a_game():
    """La carte Méninges ouvre le panneau d'entraînement (data-brain-open), sans créer de partie (data-create)."""
    assert 'data-brain-open="brain"' in JS and 'data-create="brain"' not in JS
    html = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("/static/games.js") < html.index("/static/brain/core.js")
    assert "/static/brain/brain.css" in html


def test_drink_tag_only_outside_the_alcohol_category():
    tagged = json.loads(re.search(r"const DRINK_TAG_GAMES = (\[.*?\]);", JS).group(1))
    alcohol = next(types for cid, _, types in categories() if cid == "drinks")
    assert set(tagged) == {"pyramid", "blackjack", "quiz", "likely"} and not set(tagged) & set(alcohol)


def test_pet_card_opens_the_companion_panel():
    """La carte Compagnon ouvre le panneau du personnage (data-pet-open), le skin est chargé avant le moteur."""
    assert 'data-pet-open="pet"' in JS and 'data-create="pet"' not in JS
    html = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("/static/pet/skin.js") < html.index("/static/pet/pet.js")
    assert "/static/pet/pet.css" in html
