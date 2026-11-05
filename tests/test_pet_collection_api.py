"""Collection du Compagnon câblée au serveur (/api/pet/*), faux Supabase (FakeBase, mêmes règles que la migration
20261104210000) : coffre → Légendaire frappé et certifié (vérifiable en public), Mythique numéroté, Zicoudex masqué,
boutique, atelier, porter, vitrine et nom filtrés par la modération, cadeaux d'événement rangés une fois, Zicou shiny."""
import pytest

from app import pet, pet_catalog, pet_chest, pet_collection, pet_store
from tests.test_pet_api import ALICE, BOB, TOK_A, TOK_B, act, me, setup  # noqa: F401


def hatch(c, clock):
    me(c)
    clock.go(minutes=5)
    return me(c)


def only(monkeypatch, rarity):
    """Table du coffre réduite à une rareté (pour tester la suite : frappe, révélation)."""
    monkeypatch.setattr(pet_chest, "CHEST_TABLE", ({"cat": rarity, "weight": 1},))


def coll(c, tok=TOK_A):
    r = c.post("/api/pet/collection", json={"token": tok})
    assert r.status_code == 200, r.text
    return r.json()["collection"]


def do(c, tok=TOK_A, **body):
    return c.post("/api/pet/coll", json={"token": tok, **body})


def test_a_legendary_from_the_chest_is_minted_numbered_and_its_certificate_verifies(setup, monkeypatch):
    c, base, clock, *_ = setup
    hatch(c, clock)
    only(monkeypatch, "legendary")
    found = act(c, "chest").json()["effect"]["found"]
    assert found["kind"] == "item" and found["rarity"] == "legendary" and found["serial"] == 1 and found["code"]
    inst = base.items[0]
    assert inst["owner"] == ALICE and inst["ref"] == f"chest:{pet.day_of(clock.now)}" and inst["sig"]
    key = c.get("/api/pet/certificats/cle").json()
    assert key["alg"] == "Ed25519" and len(key["fingerprint"]) == 16
    shown = c.get("/api/pet/verifier", params={"code": found["code"].lower()}).json()
    assert shown["found"] and shown["authentic"] and shown["serial"] == 1 and shown["item"]["id"] == found["item"]
    inst["payload"] = inst["payload"].replace("|1|", "|7|")   # certificat retouché en base : la signature ne tient plus
    assert c.get("/api/pet/verifier", params={"code": found["code"]}).json()["authentic"] is False
    assert c.get("/api/pet/verifier", params={"code": "ZC-2222-3333-4444"}).json() == {"code": "ZC-2222-3333-4444", "found": False}
    assert c.get("/api/pet/verifier", params={"code": "n'importe quoi"}).status_code == 400
    assert c.get("/zicou/certificat").status_code == 200


def test_the_same_chest_never_mints_twice_even_after_a_conflict(setup, monkeypatch):
    c, base, clock, *_ = setup
    hatch(c, clock)
    only(monkeypatch, "legendary")
    base.race = 1   # un autre appareil enregistre juste avant : le serveur relit et rejoue
    r = act(c, "chest")
    assert r.status_code == 200, r.text
    assert len(base.items) == 1 and r.json()["effect"]["found"]["serial"] == 1


def test_a_mythic_is_numbered_out_of_its_edition_and_revealed(setup, monkeypatch):
    c, base, clock, *_ = setup
    hatch(c, clock)
    before = coll(c)
    assert all(x.get("masked") for s in before["dex"] for x in s["items"] if x["rarity"] == "mythic")
    only(monkeypatch, "mythic")
    body = act(c, "chest").json()
    found = body["effect"]["found"]
    assert found["rarity"] == "mythic" and found["of"] == 8 and found["serial"] == 1 and found["mint"]
    assert any(n["kind"] == "mythic" and "n° 1/8" in n["text"] for n in body["news"])
    after = coll(c)
    mine = [x for s in after["dex"] for x in s["items"] if x.get("id") == found["item"]]
    assert mine and mine[0]["serial"] == 1 and mine[0]["owned"]
    assert sum(1 for s in after["dex"] for x in s["items"] if x.get("masked")) == len(pet_catalog.mythics()) - 1


def test_all_copies_gone_gives_dust_instead(setup, monkeypatch):
    c, base, clock, *_ = setup
    hatch(c, clock)
    only(monkeypatch, "mythic")
    for m in pet_catalog.mythics("chest")[1:]:
        for n in range(pet_catalog.item(m)["edition"]):
            base.mint_for(BOB, m, "chest", f"chest:x{n}")
    first = pet_catalog.mythics("chest")[0]
    for n in range(pet_catalog.item(first)["edition"] - 1):
        base.mint_for(BOB, first, "chest", f"chest:y{n}")
    base.minted_at = "2026-11-04T09:00:00Z"
    # Un dernier exemplaire part pendant le tirage (autre joueur) : poussière, jamais un objet en trop.
    real = base.pet_mint

    def race(uid, b):
        base.mint_for(BOB, first, "chest", "chest:last")
        return real(uid, b)
    monkeypatch.setattr(base, "pet_mint", race)
    found = act(c, "chest").json()["effect"]["found"]
    assert found["dup"] and found["dust"] == 400 and "partis" in found["label"]
    assert not [i for i in base.items if i["owner"] == ALICE]


def test_shop_workshop_wearing_and_showcase(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    row = base.pets[ALICE]
    row["owner"].setdefault("loop", {})["coins"] = 500
    row["owner"]["coll"] = pet_collection.new_coll() | {"dust": 650, "upgraded": True}
    view = coll(c)
    assert len(view["shop"]) == (3 if view["shop_rule"]["rare_today"] else 2) and view["coins"] == 500 and view["dust"] == 650
    item = view["shop"][0]
    r = do(c, action="buy", item=item["id"])
    assert r.status_code == 200, r.text
    after = r.json()["collection"]
    assert after["coins"] == 500 - item["price"] and next(x for x in after["shop"] if x["id"] == item["id"])["owned"]
    assert do(c, action="buy", item="decor-chalet").status_code == 400   # 3 200 pièces : il en manque
    assert do(c, action="buy", item="lumi").status_code == 400            # souvenir de soirée : jamais en boutique
    r = do(c, action="craft", item="cor-alpes")
    assert r.status_code == 200 and r.json()["collection"]["dust"] == 50
    assert do(c, action="craft", item="m-disco").status_code == 400
    r = do(c, action="equip", item="cor-alpes")
    assert r.status_code == 200 and r.json()["pet"]["coll"]["acc"]["hand"] == "cor-alpes"
    assert base.pets[ALICE]["life"]["acc"]["hand"] == "cor-alpes"
    assert do(c, action="equip", item="cape").status_code == 400
    r = do(c, action="showcase", items=["cor-alpes", "noeud"], title="Ma fanfare")
    assert r.status_code == 200 and r.json()["collection"]["showcase"]["title"] == "Ma fanfare"
    friend = c.post("/api/pet/friend", json={"token": TOK_B, "friend": ALICE})
    assert friend.status_code == 200 and friend.json()["pet"]["showcase"]["items"][0]["label"] == "Cor des Alpes"
    assert friend.json()["pet"]["acc"]["hand"] == "cor-alpes"


def test_names_and_showcase_titles_go_through_the_content_filter(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    r = act(c, "rename", name="connard")
    assert r.status_code == 400 and "pas accepté" in r.json()["detail"]
    assert base.pets[ALICE]["life"]["name"] == pet.DEFAULT_NAME
    r = do(c, action="showcase", items=["noeud"], title="www.vends-mes-objets.ch")
    assert r.status_code == 400 and "lien" in r.json()["detail"]
    assert act(c, "rename", name="Mochi").json()["pet"]["name"] == "Mochi"


def test_the_old_outfit_action_wears_the_item_on_its_slot(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    body = act(c, "outfit", outfit="noeud").json()
    assert body["pet"]["coll"]["acc"] == {"neck": "noeud"}
    assert act(c, "outfit", outfit="").json()["pet"]["coll"]["acc"] == {}


def test_event_gifts_are_shelved_once_and_revealed(setup):
    c, base, clock, *_ = setup
    hatch(c, clock)
    base.awards.append({"id": "aw1", "user": ALICE, "event_id": "ev1", "event": "Soirée disco", "item": "lumi", "prize": 0,
                        "roll": 4.2, "instance": None})
    inst = base.mint_for(ALICE, "projecteurs", "event", "event:ev1:1", "ev1")
    base.awards.append({"id": "aw2", "user": ALICE, "event_id": "ev1", "event": "Soirée disco", "item": "projecteurs",
                        "prize": 1, "roll": 1.5, "instance": inst["id"]})
    body = me(c)
    reveals = body["pet"]["coll"]["reveals"]
    assert [r["item"]["id"] for r in reveals] == ["lumi", "projecteurs"] and reveals[1]["serial"] == 1
    assert all(a["claimed"] for a in base.awards) and inst["sig"]   # rangés, marqués ; certificat signé au passage
    assert base.pets[ALICE]["owner"]["coll"]["inv"]["lumi"] == 1
    assert me(c)["pet"]["coll"]["reveals"] == []
    base.awards.append({"id": "aw3", "user": ALICE, "event_id": "ev2", "event": "Encore", "item": "lumi", "prize": 0,
                        "roll": 2, "instance": None})
    again = me(c)["pet"]["coll"]["reveals"]
    assert again[0]["dup"] and again[0]["dust"] == 100


def test_a_shiny_zicou_hatches_with_its_odds_shown(setup, monkeypatch):
    c, base, clock, *_ = setup
    monkeypatch.setattr(pet_collection, "roll_shiny", lambda rng: True)
    body = hatch(c, clock)
    assert body["pet"]["coll"]["shiny"] and base.pets[ALICE]["life"]["shiny"] is True
    assert any(n["kind"] == "shiny" for n in body["news"])
    assert coll(c)["shiny_odds"] == "1 chance sur 64 à l'éclosion"


def test_collection_requires_a_valid_token_and_known_actions(setup):
    c, *_ = setup
    assert c.post("/api/pet/collection", json={"token": "z" * 40}).status_code == 401
    assert do(c, action="steal", item="lumi").status_code == 422
    assert do(c, action="buy", item="../x").status_code == 422


def test_odds_in_the_daily_view_include_the_mystery_object_and_the_pity_counter(setup):
    c, base, clock, *_ = setup
    daily = hatch(c, clock)["pet"]["daily"]
    assert {"kind": "mythic", "label": "Objet mystère", "pct": 0.001, "text": "1 chance sur 100\u202f000"} in daily["odds"]
    assert {o["kind"] for o in daily["bonus_odds"] if o["pct"] > 0} == {"coins", "object", "common", "rare"}
    assert daily["pity_left"] == pet_chest.PITY and daily["pity"] == pet_chest.PITY
    assert {"pet_mint", "pet_cert_set", "pet_awards_claim", "pet_event_coins_claim"} <= set(pet_store.KEYED_RPC)
