"""Nouvelle économie de Zicou sur la VRAIE base de TEST (migration 20261105120000, jamais la prod) : catalogue recopié
(Mythiques des coffres à 8 exemplaires), cadeaux d'événement réservés aux admins et co-admins, festins offerts (Pizza
dorée, Fondue ; jamais la Raclette), caisse commune (clé du serveur, référence unique, bornes, 500 par jour, totaux sans
nom pour l'Apple TV, prénoms des amis seulement). Comptes Testeur 1, 2 et 3 ; tout est effacé avant et après."""
import httpx
import pytest

from app import pet_catalog
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, pytestmark  # noqa: F401
from tests.supabase_live.test_pet_live import KEY, fresh, save, sql_test, trio  # noqa: F401


@pytest.fixture
def pets(trio):
    a, b, c = trio
    users = ",".join(f"'{s.uid}'" for s in (a, b, c))
    sql_test(f"delete from public.pet_pot_gifts where user_id in ({users}); delete from public.pet_gifts where from_user in ({users});")
    for s in (a, b):
        life, owner = fresh()
        save(s, life, owner, 0)
    sql_test(f"update public.pets set stage = 'adult' where user_id in ('{a.uid}', '{b.uid}');")
    yield a, b, c
    sql_test(f"delete from public.pet_pot_gifts where user_id in ({users}); delete from public.pet_gifts where from_user in ({users});")


def test_catalog_editions_and_event_gift_bounds():
    rows = sql_test("select id, edition from public.pet_catalog where rarity = 'mythic' order by id;")
    assert {r["id"]: r["edition"] for r in rows} == {m: pet_catalog.item(m)["edition"] for m in pet_catalog.mythics()}
    assert all(r["edition"] == 8 for r in rows if r["id"] != "m-soirees")
    bounds = sql_test("select organizers, max_pct from private.pet_drop_bounds where id = 1;")[0]
    assert bounds["organizers"] is False and bounds["max_pct"]["legendary"] == 1 and bounds["max_pct"]["common"] == 25


def test_feasts_can_be_gifted_but_never_a_raclette(pets):
    a, b, _ = pets
    assert a.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="feast_raclette").status_code == 400
    r = a.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="feast_pizza")
    assert r.status_code == 200, r.text
    assert [g["kind"] for g in b.rpc("pet_load", p_key=KEY()).json()["gifts"]] == ["feast_pizza"]
    again = a.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="feast_fondue")
    assert again.status_code == 400 and "limit" in again.json()["message"]   # un cadeau par ami et par jour


def test_the_common_pot_counts_once_has_bounds_and_shows_no_ranking(pets):
    a, b, c = pets
    assert a.rpc("pet_pot_give", p_goal="boule-disco", p_coins=100, p_ref="pot-test-a-0001").status_code == 400   # sans clé
    before = a.rpc("pet_pot_get", p_key=KEY()).json()
    total0 = next(g["total"] for g in before["goals"] if g["id"] == "boule-disco")
    first = a.rpc("pet_pot_give", p_key=KEY(), p_goal="boule-disco", p_coins=100, p_ref="pot-test-a-0001")
    assert first.status_code == 200, first.text
    replay = a.rpc("pet_pot_give", p_key=KEY(), p_goal="boule-disco", p_coins=100, p_ref="pot-test-a-0001").json()
    assert next(g["total"] for g in replay["goals"] if g["id"] == "boule-disco") == total0 + 100   # compté une fois
    assert replay["mine"] == 100 and replay["mine_today"] == 100
    for bad, why in ((5, "invalid"), (300, "invalid")):
        assert why in a.rpc("pet_pot_give", p_key=KEY(), p_goal="boule-disco", p_coins=bad, p_ref=f"pot-test-bad-{bad}").json()["message"]
    assert "invalid" in a.rpc("pet_pot_give", p_key=KEY(), p_goal="inconnu", p_coins=10, p_ref="pot-test-a-0009").json()["message"]
    for i in range(1, 3):
        assert a.rpc("pet_pot_give", p_key=KEY(), p_goal="boule-disco", p_coins=200, p_ref=f"pot-test-a-100{i}").status_code in (200, 400)
    capped = a.rpc("pet_pot_give", p_key=KEY(), p_goal="boule-disco", p_coins=250, p_ref="pot-test-a-2000")
    assert capped.status_code == 400 and "500" in capped.json()["message"]
    assert "Zicou" in c.rpc("pet_pot_give", p_key=KEY(), p_goal="boule-disco", p_coins=10, p_ref="pot-test-c-0001").json()["message"]
    seen_by_b = b.rpc("pet_pot_get", p_key=KEY()).json()
    assert set(seen_by_b) == {"goals", "donors", "friends", "mine", "mine_today"} and seen_by_b["mine"] == 0
    assert all(set(g) == {"id", "label", "emoji", "target", "total"} for g in seen_by_b["goals"])   # aucun montant par personne
    anon = httpx.post(f"{TEST_URL}/rest/v1/rpc/pet_pot_public", json={}, timeout=30,
                      headers={"apikey": KEY_FILE.read_text().strip(), "Content-Type": "application/json"})
    assert anon.status_code == 200 and "user" not in anon.text and a.uid not in anon.text
    assert a.get("pet_pot_gifts?select=*").status_code in (401, 403, 404) or a.get("pet_pot_gifts?select=*").json() == []
