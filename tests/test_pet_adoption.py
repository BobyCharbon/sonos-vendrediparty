"""Zicou n'est pondu que par une adoption explicite (bug de l'admin du 5.11 : feuille d'accueil fermée d'un geste,
et pourtant l'œuf était pondu puis éclosait). /api/pet/me, /api/pet/status et toutes les autres lectures ou actions
sans Zicou ne créent rien ; seule l'action « adopt » (choix du nom → « Faire éclore ») pond l'œuf."""
from pathlib import Path

from app import pet
from tests.test_pet_api import ALICE, TOK_A, act, setup  # noqa: F401  (fixture du Compagnon câblé)

BRIDGE = (Path(__file__).resolve().parents[1] / "ios/Party/Pet/PetWidgetBridge.swift").read_text(encoding="utf-8")


def nothing_created(base):
    return ALICE not in base.pets and base.saves == [] and base.journal == []


def test_me_without_adoption_creates_nothing(setup):
    c, base, clock, *_ = setup
    for src in ("tab", "link", "widget", "notif", "none"):
        r = c.post("/api/pet/me", json={"token": TOK_A, "src": src})
        assert r.status_code == 200, r.text
        assert r.json() == {"adopted": False, "pet": None, "news": [], "effect": None}
    clock.go(minutes=10)
    assert c.post("/api/pet/me", json={"token": TOK_A}).json()["adopted"] is False   # pas d'œuf qui « éclot » en douce
    assert c.post("/api/pet/status", json={"token": TOK_A}).json() == {"adopted": False}
    assert nothing_created(base)


def test_actions_and_screens_without_adoption_create_nothing(setup):
    c, base, *_ = setup
    for action in ("feed", "cuddle", "rename", "chest", "new_egg"):
        r = act(c, action, name="Bobby")
        assert r.status_code == 400 and "adopt" in r.json()["detail"].lower(), (action, r.text)
    assert c.post("/api/pet/collection", json={"token": TOK_A}).status_code == 400
    assert c.post("/api/pet/friends", json={"token": TOK_A}).status_code == 200   # la liste d'amis reste lisible
    assert nothing_created(base)


def test_adopt_lays_the_egg_with_its_name_once(setup):
    c, base, clock, *_ = setup
    r = act(c, "adopt", name="Bobby")
    assert r.status_code == 200, r.text
    first = r.json()
    assert first["adopted"] is True and first["pet"]["stage"] == "egg" and first["pet"]["name"] == "Bobby"
    assert first["pet"]["next_stage_in"] == pet.EGG_SECONDS
    assert base.pets[ALICE]["life"]["name"] == "Bobby" and len(base.saves) == 1
    clock.go(minutes=1)
    again = act(c, "adopt", name="Autre").json()   # deuxième toucher, autre appareil : même œuf, même compte à rebours
    assert again["pet"]["name"] == "Bobby" and again["pet"]["next_stage_in"] == pet.EGG_SECONDS - 60
    assert len(base.saves) == 1
    me = c.post("/api/pet/me", json={"token": TOK_A}).json()
    assert me["adopted"] is True and me["pet"]["name"] == "Bobby"


def test_adopt_refuses_a_bad_name_and_creates_nothing(setup):
    c, base, *_ = setup
    r = act(c, "adopt", name="connard")
    assert r.status_code == 400
    assert nothing_created(base)


def test_the_ios_bridge_ignores_an_answer_without_zicou():
    """Widgets et Live Activity de l'éclosion : rien tant qu'aucun Zicou n'est pondu (réponse « pet »: null)."""
    assert "data && data.pet && typeof data.pet.stage === \"string\"" in BRIDGE
