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


def test_every_game_is_in_exactly_one_category():
    listed = [t for _, _, types in categories() for t in types]
    assert sorted(listed) == sorted(t for t in games.GAMES if t != "room")


def test_categories_in_the_chosen_order():
    assert [label for _, label, _ in categories()] == ["🍻 Alcool", "🎮 Jeux 3D", "💞 Parler vrai", "🃏 Jeux de cartes", "🎉 Ambiance"]
    cats = {cid: types for cid, _, types in categories()}
    assert set(cats["talk"]) == {"divan", "debate", "tmc"}
    assert set(cats["cards"]) == {"pyramid", "blackjack", "president"}
    assert set(cats["three"]) == {"neon", "island", "heist"}
    assert set(cats["mood"]) == {"quiz", "undercover", "likely"}


def test_drink_tag_only_outside_the_alcohol_category():
    tagged = json.loads(re.search(r"const DRINK_TAG_GAMES = (\[.*?\]);", JS).group(1))
    alcohol = next(types for cid, _, types in categories() if cid == "drinks")
    assert set(tagged) == {"pyramid", "blackjack", "quiz", "likely"} and not set(tagged) & set(alcohol)
