"""Catégorie Drapeaux du Quiz (avis 544a8fd8b5bd) : contrôle de la banque (second passage automatique) et partie.

Chaque question est relue ici indépendamment du générateur : le drapeau affiché correspond bien à la bonne réponse,
les 4 propositions sont distinctes, jamais deux drapeaux identiques en emoji ensemble, des sosies plausibles,
les trois niveaux, pas de doublon ; l'animateur peut choisir le thème seul et la question montre le drapeau."""
import random
import re

import pytest

from app import games, quiz
from app import quizbank as qb
from app.quizbank import gen_drapeaux as gd
from app.quizbank.fr import bare, flag

FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


def iso_of(emoji: str) -> str:
    return "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in emoji)


@pytest.fixture(autouse=True)
def stats(tmp_path):
    quiz.STATS_PATH = tmp_path / "quiz_stats.json"
    yield


@pytest.fixture(scope="module")
def bank():
    return qb.BANK["drapeaux"]


@pytest.fixture(scope="module")
def names():
    """Nom affiché (sans article) → code ISO, pour relire les questions sans passer par le générateur."""
    table = {bare(name): iso for iso, name, _, _ in gd.countries()}
    assert len(table) == len(gd.countries())  # deux pays n'ont jamais le même nom
    return table


def test_flags_is_a_theme_offered_to_the_host():
    assert qb.THEMES["drapeaux"] == ("Drapeaux", "🚩")
    g = games.new_game("quiz", host="p0", name="P0")
    view = games.view(g, "p0")["quiz"]
    theme = next(t for t in view["catalog"]["themes"] if t["id"] == "drapeaux")
    assert theme["count"] >= 120
    quiz.configure(g, {"themes": ["drapeaux"]})
    assert games.view(g, "p0")["quiz"]["theme_labels"] == ["🚩 Drapeaux"]


def test_bank_has_enough_well_formed_unique_questions(bank):
    assert len(bank) >= 120
    assert len({q["id"] for q in bank}) == len(bank)
    assert len({(q["q"], q["a"]) for q in bank}) == len(bank)  # pas deux fois la même question
    by_level = {d: sum(q["d"] == d for q in bank) for d in (1, 2, 3)}
    assert all(n >= 40 for n in by_level.values()), by_level  # du connu au difficile
    for q in bank:
        assert q["t"] == "drapeaux" and len({q["a"], *q["w"]}) == 4, q


def test_the_flag_shown_belongs_to_the_right_answer(bank, names):
    which = [q for q in bank if q["q"].startswith("À quel pays appartient ce drapeau ?")]
    assert len(which) == len(gd.countries())
    for q in which:
        shown = FLAG_RE.findall(q["q"])
        assert len(shown) == 1, q
        assert iso_of(shown[0]) == names[q["a"]], q
        assert all(w in names for w in q["w"]), q


def test_reverse_questions_offer_the_right_flag(bank, names):
    reverse = [q for q in bank if q["q"].startswith("Quel est le drapeau")]
    assert len(reverse) == len(gd.countries())
    for q in reverse:
        assert all(FLAG_RE.fullmatch(x) for x in [q["a"], *q["w"]]), q
        iso = iso_of(q["a"])
        country = next(c for c in gd.countries() if c[0] == iso)
        assert q["q"].endswith(f"{bare(country[1])} ?") or bare(country[1]).lower() in q["q"].lower(), q


def test_identical_emoji_flags_are_never_offered_together(bank, names):
    for q in bank:
        codes = {iso_of(x) for x in [q["a"], *q["w"]]} if FLAG_RE.fullmatch(q["a"]) else {names[x] for x in [q["a"], *q["w"]]}
        for twin in gd.TWINS:
            assert not twin <= codes, q


def test_lookalikes_are_used_as_wrong_answers(bank):
    def question_for(iso):
        return next(q for q in bank if q["q"] == f"À quel pays appartient ce drapeau ? {flag(iso)}")
    assert {"Côte d'Ivoire", "Italie"} <= set(question_for("IE")["w"])
    assert {"Moldavie", "Andorre"} <= set(question_for("TD")["w"]) and "Roumanie" not in question_for("TD")["w"]
    assert "Pologne" in question_for("MC")["w"] and "Indonésie" not in question_for("MC")["w"]
    assert {"Norvège", "Danemark", "Finlande"} <= set(question_for("IS")["w"])
    assert {"Nouvelle-Zélande", "Fidji"} <= set(question_for("AU")["w"])
    # Les familles de sosies ne citent que des pays connus de la banque.
    known = {c[0] for c in gd.countries()}
    assert all(code in known for family in gd.LOOKALIKES for code in family.split())


def test_well_known_flags_are_easy_and_rare_ones_hard(bank):
    level = {q["a"]: q["d"] for q in bank if q["q"].startswith("À quel pays")}
    assert level["France"] == level["Japon"] == level["Brésil"] == 1
    assert level["Kiribati"] == level["Comores"] == level["Turkménistan"] == 3
    assert level["Italie"] == 2  # trois sosies (Irlande, Côte d'Ivoire, Mexique) : un cran plus dur


def test_geography_no_longer_asks_flags():
    assert not any("drapeau" in q["q"] for q in qb.BANK["geo"])
    assert len(qb.BANK["geo"]) >= 1000


def test_a_flags_game_shows_the_flag_in_the_question():
    g = games.new_game("quiz", host="p0", name="P0")
    games.join(g, "p1", "P1")
    quiz.configure(g, {"themes": ["drapeaux"], "diff": "1"})
    games.start(g, random.Random(5))
    q = games.view(g, "p1")["quiz"]["q"]
    assert q["theme"] == "Drapeaux" and q["icon"] == "🚩" and q["d"] == 1
    assert FLAG_RE.search(q["text"]) or all(FLAG_RE.fullmatch(c) for c in q["choices"])
    assert "correct" not in q  # la bonne réponse reste cachée jusqu'à la révélation
