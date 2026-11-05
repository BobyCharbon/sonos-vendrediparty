"""Nouvelle économie de Zicou câblée au serveur (/api/pet/*), faux Supabase et horloge simulée : festins achetés,
niveau, festin offert à un ami (payé par celui qui offre, pièces rendues si la base refuse), chambre et teintures,
caisse commune (sans classement, rejeu compté une fois, pièces rendues si refus), Zicou en vedette à l'Apple TV."""
import httpx
import pytest

from app import main, tv_star
from tests.test_pet_api import ALICE, BOB, TOK_A, TOK_B, me, setup  # noqa: F401
from tests.test_pet_collection_api import coll, do, hatch


def coins(base, uid=ALICE):
    return base.pets[uid]["owner"]["loop"]["coins"]


def rich(base, uid=ALICE, n=1000):
    base.pets[uid]["owner"].setdefault("loop", {})["coins"] = n


def test_buying_a_feast_debits_coins_and_shows_it(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    rich(base)
    r = do(c, action="feast", item="pizza")
    assert r.status_code == 200, r.text
    body = r.json()
    assert coins(base) == 880 and body["pet"]["feast"]["active"]["kind"] == "pizza" and body["pet"]["xp"]["boost"]
    assert any(n["kind"] == "feast" for n in body["news"])
    again = do(c, action="feast", item="fondue")
    assert again.status_code == 400 and "Un festin à la fois" in again.json()["detail"]
    assert do(c, action="feast", item="caviar").status_code == 400
    assert coins(base) == 880


def test_care_gives_xp_and_the_level_is_shown(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    before = me(c)["pet"]["xp"]
    assert before["level"] == 1 and before["caps"] == {"care": 20, "game": 10, "social": 10}
    r = c.post("/api/pet/act", json={"token": TOK_A, "action": "cuddle"})
    assert r.status_code == 200 and r.json()["pet"]["xp"]["total"] == before["total"] + 4
    assert base.pets[ALICE]["life"]["lvl"] == {"level": 1, "stars": 0}


def friends_ready(c, base, clock):
    hatch(c, clock)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c, TOK_B)


def test_a_gifted_feast_is_paid_by_the_giver_and_lands_on_the_friend(setup):
    c, base, clock, *_ = setup
    friends_ready(c, base, clock)
    rich(base, ALICE, 100)
    poor = c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "feast_pizza"})
    assert poor.status_code == 400 and "manque 20" in poor.json()["detail"] and not base.gifts   # rien envoyé
    rich(base, ALICE, 500)
    r = c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "feast_pizza"})
    assert r.status_code == 200, r.text
    assert coins(base) == 380 and base.gifts[-1]["kind"] == "feast_pizza"
    bob_coins = coins(base, BOB)
    bob = me(c, TOK_B)
    assert bob["pet"]["feast"]["active"]["kind"] == "pizza" and coins(base, BOB) == bob_coins   # un effet, pas des pièces
    assert any("Pizza dorée" in n["text"] for n in bob["news"])
    again = c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "feast_fondue"})
    assert again.status_code == 400 and coins(base) == 380   # déjà un cadeau aujourd'hui : rien débité
    assert c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "feast_raclette"}).status_code == 422


def test_coins_come_back_when_the_base_refuses_a_gifted_feast(setup, monkeypatch):
    c, base, clock, *_ = setup
    friends_ready(c, base, clock)
    rich(base, ALICE, 500)
    monkeypatch.setattr(base, "pet_gift", lambda uid, b: base.err("limit: Son Zicou a déjà reçu plein de cadeaux aujourd'hui."))
    r = c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "feast_fondue"})
    assert r.status_code == 400 and coins(base) == 500
    kinds = [j["kind"] for _, j in base.journal]
    assert "feast_gift" in kinds and "feast_refund" in kinds


def test_room_and_dyes_through_the_api(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    rich(base, ALICE, 1000)
    view = coll(c)
    assert view["room"] == {"level": 0, "price": 400, "max": 60} and [d["id"] for d in view["dyes"]["colors"]][:2] == ["rose", "or"]
    assert do(c, action="room").json()["collection"]["room"]["level"] == 1 and coins(base) == 600
    assert do(c, action="dye", item="noeud", slot="or").status_code == 200 and coins(base) == 540
    assert base.pets[ALICE]["life"]["dye"] == {"noeud": "or"}
    assert do(c, action="dye_wear", item="noeud", slot="").status_code == 200 and base.pets[ALICE]["life"]["dye"] == {}
    assert do(c, action="dye", item="cape", slot="or").status_code == 400


class Pot:
    """Faux pet_pot_get / pet_pot_give (mêmes règles que la migration 20261105120000)."""

    def __init__(self, base):
        self.base, self.gifts = base, []
        self.goals = [{"id": "boule-disco", "label": "Boule disco géante", "emoji": "🪩", "target": 5000},
                      {"id": "neons", "label": "Néons", "emoji": "🌈", "target": 5000}]
        self.refuse = False

    def state(self, uid):
        return {"goals": [g | {"total": sum(x["coins"] for x in self.gifts if x["goal"] == g["id"])} for g in self.goals],
                "donors": len({x["user"] for x in self.gifts}), "friends": ["Alice"] if any(x["user"] == ALICE for x in self.gifts) else [],
                "mine": sum(x["coins"] for x in self.gifts if x["user"] == uid),
                "mine_today": sum(x["coins"] for x in self.gifts if x["user"] == uid)}

    def get(self, uid, b):
        return httpx.Response(200, json=self.state(uid))

    def give(self, uid, b):
        if self.refuse:
            return self.base.err("invalid: Cet objectif est déjà atteint 🎉")
        if not any(x["ref"] == b["p_ref"] for x in self.gifts):
            self.gifts.append({"ref": b["p_ref"], "goal": b["p_goal"], "user": uid, "coins": b["p_coins"]})
        return httpx.Response(200, json=self.state(uid))


@pytest.fixture
def pot(setup):
    c, base, *_ = setup
    p = Pot(base)
    base.pet_pot_get, base.pet_pot_give = p.get, p.give
    return p


def test_the_common_pot_takes_earned_coins_without_any_ranking(setup, pot):
    c, base, clock, *_ = setup
    hatch(c, clock)
    rich(base, ALICE, 400)
    view = c.post("/api/pet/pot", json={"token": TOK_A}).json()
    assert view["current"]["id"] == "boule-disco" and view["steps"] == [10, 50, 100, 250] and view["left_today"] == 500
    r = c.post("/api/pet/pot/give", json={"token": TOK_A, "coins": 250})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["given"] == 250 and coins(base) == 150 and out["current"]["total"] == 250 and out["mine"] == 250
    assert out["friends"] == ["Alice"] and "rank" not in r.text and "top" not in r.text
    assert c.post("/api/pet/pot/give", json={"token": TOK_A, "coins": 250}).status_code == 400   # 150 pièces
    assert c.post("/api/pet/pot/give", json={"token": TOK_A, "coins": 5}).status_code == 422
    assert coins(base) == 150


def test_pot_never_takes_more_than_what_is_missing_and_refunds_if_refused(setup, pot):
    c, base, clock, *_ = setup
    hatch(c, clock)
    rich(base, ALICE, 1000)
    pot.gifts.append({"ref": "x" * 10, "goal": "boule-disco", "user": BOB, "coins": 4970})
    r = c.post("/api/pet/pot/give", json={"token": TOK_A, "coins": 100}).json()
    assert r["given"] == 30 and r["just_reached"] and coins(base) == 970 and r["current"]["id"] == "neons"
    pot.refuse = True
    bad = c.post("/api/pet/pot/give", json={"token": TOK_A, "coins": 50})
    assert bad.status_code == 400 and coins(base) == 970


@pytest.fixture
def soiree(setup, monkeypatch):
    stars = tv_star.TvStars()
    monkeypatch.setattr(main, "tv_stars", stars)
    monkeypatch.setattr(main, "soiree_key", lambda: "1700000000")
    present = {ALICE}
    monkeypatch.setattr(main, "star_present", lambda uid: uid in present)
    return stars, present


def test_a_present_member_books_a_tv_star_once_per_soiree(setup, soiree):
    c, base, clock, *_ = setup
    stars, present = soiree
    hatch(c, clock)
    rich(base, ALICE, 200)
    assert c.post("/api/pet/star", json={"token": TOK_A}).json() == {"open": True, "price": 150, "booked": None, "seconds": 30}
    r = c.post("/api/pet/star/book", json={"token": TOK_A})
    assert r.status_code == 200, r.text
    assert r.json()["booked"]["starts_in"] == 0 and coins(base) == 50
    live, waiting = stars.on_air("1700000000")
    assert live["stage"] in ("baby", "teen", "adult") and ALICE not in repr(live) and waiting == 0
    again = c.post("/api/pet/star/book", json={"token": TOK_A})
    assert again.status_code == 400 and coins(base) == 50
    stars.slots.clear()   # (redémarrage du serveur : la file est perdue, la soirée reste notée dans son Zicou)
    assert c.post("/api/pet/star/book", json={"token": TOK_A}).status_code == 400 and coins(base) == 50


def test_no_tv_star_without_being_present_or_without_coins(setup, soiree):
    c, base, clock, *_ = setup
    stars, present = soiree
    hatch(c, clock)
    rich(base, ALICE, 100)
    r = c.post("/api/pet/star/book", json={"token": TOK_A})
    assert r.status_code == 400 and "manque 50" in r.json()["detail"] and not stars.slots and coins(base) == 100
    present.clear()
    r = c.post("/api/pet/star/book", json={"token": TOK_A})
    assert r.status_code == 400 and "présents" in r.json()["detail"]
