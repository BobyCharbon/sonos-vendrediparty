"""Journal des gorgées : chaque gorgée comptée (bue ou distribuée) est notée avec le prénom, pour que la télé annonce
en grand « Léa boit 2 » quel que soit le jeu."""
import random

from app import games


def game_with(kind="never", sips=2):
    g = games.new_game(kind, "host-sips-0001", "Boby", code="1234", sips=sips)
    for gid, name in [("p-sips-0002", "Léa"), ("p-sips-0003", "Tom")]:
        games.join(g, gid, name)
    return g


def test_each_sip_is_logged_with_the_name_and_a_growing_number():
    g = game_with()
    games.add_sips(g, "p-sips-0002", drink=2)
    games.add_sips(g, "p-sips-0003", give=3)
    log = games.view(g, "")["sips_log"]
    assert [(e["name"], e["drink"], e["give"]) for e in log] == [("Léa", 2, 0), ("Tom", 0, 3)]
    assert log[0]["n"] < log[1]["n"] and log[0]["pid"]
    assert 0 <= log[1]["age"] < 5  # secondes depuis la gorgée : la télé regroupe celles d'un même coup


def test_never_results_log_who_drinks():
    g = game_with()
    games.start(g, random.Random(1))
    games.vote(g, "host-sips-0001", "no")
    games.vote(g, "p-sips-0002", "yes")
    games.vote(g, "p-sips-0003", "yes")  # le dernier vote ferme la question
    assert g["phase"] == "results"
    assert {e["name"] for e in games.view(g, "")["sips_log"]} == {"Léa", "Tom"}


def test_the_log_keeps_only_the_latest_entries():
    g = game_with()
    for _ in range(games.SIPS_LOG_SIZE + 10):
        games.add_sips(g, "p-sips-0002", drink=1)
    assert len(games.view(g, "")["sips_log"]) == games.SIPS_LOG_SIZE
