"""Zicou dans l'app (4.11) : pastille (/api/pet/status) et cadeau de bienvenue garanti à la toute première éclosion."""
from app import pet, pet_welcome
from tests.test_pet_api import ALICE, TOK_A, TOK_GONE, act, me, setup  # noqa: F401  (fixture partagée)


def status(c, tok=TOK_A):
    r = c.post("/api/pet/status", json={"token": tok})
    assert r.status_code == 200, r.text
    return r.json()


def test_status_never_lays_an_egg_nor_saves(setup):
    c, base, *_ = setup
    assert status(c) == {"adopted": False}
    assert ALICE not in base.pets and base.saves == []
    assert base.opens == [(ALICE, None)]   # pas une ouverture comptée


def test_status_follows_the_egg_then_the_baby(setup):
    c, base, clock, *_ = setup
    me(c)
    egg = status(c)
    assert egg["adopted"] and egg["stage"] == "egg" and egg["next_stage_in"] == pet.EGG_SECONDS and egg["need"] is None
    saves = len(base.saves)
    clock.go(minutes=4)
    baby = status(c)
    assert baby["stage"] == "baby" and baby["emotion"] and baby["welcome"] is True
    assert len(base.saves) == saves   # relu seulement : l'éclosion est enregistrée à l'ouverture suivante


def test_status_needs(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=4)
    me(c)
    assert status(c)["need"] == "chest"   # coffre du jour prêt : pastille sur l'onglet, pas de point rouge
    assert act(c, "chest").status_code == 200
    assert status(c)["need"] is None
    clock.go(hours=30)
    assert status(c)["need"] == "alert"   # il a faim : point rouge


def test_status_without_account(setup):
    c, *_ = setup
    assert c.post("/api/pet/status", json={"token": TOK_GONE}).status_code == 401
    assert c.post("/api/pet/status", json={"token": "court"}).status_code == 400


def test_first_hatch_brings_a_guaranteed_welcome_gift_once(setup):
    c, base, clock, *_ = setup
    first = me(c)
    coins = first["pet"]["daily"]["coins"]
    clock.go(minutes=4)
    hatched = me(c)
    welcome = [n for n in hatched["news"] if n["kind"] == "welcome"]
    assert welcome == [{"kind": "welcome", "item": "noeud", "coins": pet_welcome.WELCOME_COINS,
                        "text": "🎁 Cadeau de bienvenue : nœud papillon et 50 pièces"}]
    assert hatched["pet"]["daily"]["coins"] == coins + pet_welcome.WELCOME_COINS
    assert hatched["pet"]["coll"]["acc"].get("neck") == "noeud"   # déjà porté
    again = me(c)
    assert not [n for n in again["news"] if n["kind"] == "welcome"]
    assert again["pet"]["daily"]["coins"] == hatched["pet"]["daily"]["coins"]


def test_welcome_only_for_the_very_first_egg():
    life, owner = pet.new_pet(pet.parse("2026-11-04T09:00:00Z"))
    life["gen"] = 2
    s = {"life": life, "owner": owner, "now": pet.parse("2026-11-04T09:05:00Z"), "news": []}
    assert pet_welcome.apply(s, [{"kind": "hatched"}]) is None and "welcome" not in owner
    life["gen"] = 1
    owner["welcome"] = {"item": "noeud"}
    assert pet_welcome.apply(s, [{"kind": "hatched"}]) is None
