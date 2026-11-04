"""Compagnon : retours de la testeuse « Léa » (4 novembre 2026), côté serveur. Horloge simulée, faux Supabase.
L'écran (compte à rebours de l'œuf, messages, mini-jeu, jauges chiffrées…) est testé dans tests/e2e/test_pet_game.py."""
from datetime import timedelta

from app import pet
from tests.test_pet_api import ALICE, BOB, T0, TOK_A, TOK_B, act, me, setup  # noqa: F401 (fixture)


def test_b1_missions_drawn_before_the_name_was_chosen_use_the_current_name(setup):
    c, base, clock, *_ = setup
    first = me(c)   # l'œuf : les missions du jour sont tirées avec « Zicou »
    assert first["pet"]["daily"]["missions"]
    renamed = act(c, "rename", name="Mochi").json()["pet"]["daily"]
    texts = [m["text"] for m in renamed["missions"]] + [renamed["week"]["text"]]
    assert not any("Zicou" in t for t in texts), texts
    clock.go(minutes=5)
    done = [act(c, a) for a in ("feed", "cuddle", "cuddle", "cuddle", "heal", "play")]
    news = [n["text"] for r in done if r.status_code == 200 for n in r.json()["news"] if n["kind"] == "mission"]
    assert news and all("Zicou" not in t for t in news), news


def test_b4_no_evolution_announcement_when_he_flew_away(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    me(c)
    clock.go(days=9)   # Léa l'oublie : il grandit puis s'envole pendant son absence
    news = me(c)["news"]
    assert {"kind": "died", "text": "🕊️ Il s'est envolé…"} in news
    assert not [n for n in news if n["kind"] == "evolved"], news


def test_a_gift_to_a_friend_counts_for_the_day_so_friday_protects_saturday(setup):
    """Léa : vendredi, coffre + visite + goûter offert, sans soigner le sien ; dimanche, 🔥 0. Désormais le cadeau compte."""
    c, base, clock, *_ = setup
    clock.now = T0 + timedelta(days=1)   # jeudi 5.11, 10 h
    me(c)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c, TOK_B)
    assert act(c, "cuddle").status_code == 200   # jeudi : un soin
    clock.go(days=1)                           # vendredi : coffre, visite, cadeau, pas de soin
    me(c)
    me(c, TOK_B)
    act(c, "chest")
    c.post("/api/pet/friends", json={"token": TOK_A})
    assert c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "snack"}).status_code == 200
    friday = base.pets[ALICE]["owner"]["streak"]
    assert friday["count"] == 2 and friday["last"] == pet.day_of(clock.now)
    clock.go(days=2)                           # dimanche : samedi en répit, la série tient
    assert me(c)["pet"]["daily"]["streak"]["count"] == 2


def test_the_rule_for_a_day_to_count_is_shown_until_it_counts(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    d = me(c)["pet"]["daily"]
    assert d["streak"]["today"] is False
    assert act(c, "chest").json()["pet"]["daily"]["streak"]["today"] is False   # le coffre seul ne suffit pas
    assert act(c, "cuddle").json()["pet"]["daily"]["streak"]["today"] is True


def test_a_brand_new_companion_has_one_freeze(setup):
    c, *_ = setup
    assert me(c)["pet"]["daily"]["streak"]["freezes"] == 1


def test_warnings_before_he_flies_away_are_clear_and_early():
    life, owner = pet.new_pet(T0)
    now = T0 + timedelta(minutes=5)
    pet.advance(life, now, owner)
    assert pet.view(life, owner, now)["alert"] is None
    life["g"]["food"] = 20.0
    assert pet.view(life, owner, now)["alert"] == {"kind": "hungry"}
    later = now + timedelta(hours=40)
    pet.advance(life, later, owner)
    alert = pet.view(life, owner, later)["alert"]
    assert alert["kind"] == "starving" and 0 < alert["hours_left"] <= pet.DEATH_STARVING_HOURS
