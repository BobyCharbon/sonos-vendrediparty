"""Pièces Zicou d'un événement sur la VRAIE base de TEST (jamais la prod), migration 20261105090000 :

  · droit « zicou.event_coins » donné à Admin et Co-admin seulement ; sans lui, rien n'est visible ni réglable ;
  · montant borné (5 à 100) ; versé à la fin de l'événement, UNE fois, aux PRÉSENTS seulement (billet scanné ou noté
    « Présent » par un organisateur / un admin), jamais selon un paiement ; journal pet_event_coin_grants ;
  · une fois versé, le montant ne change plus ; pet_load renvoie les pièces (plus « events » ni « answers »), le serveur
    les marque rangées une fois.
Comptes : Admin de test et Testeurs 1, 2 (événement de test sans notification : effacé avant et après)."""
import pytest

from tests.supabase_live.test_member_admin_live import ADMIN_PHONE, GUESTS, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_pet_live import KEY, sql_test

EVENT = "6e7a0000-0000-4000-8000-0000000c0175"


def clean():
    sql_test(f"""delete from public.pet_event_coin_grants where event_id = '{EVENT}';
      delete from public.pet_event_coins where event_id = '{EVENT}';
      delete from public.event_tickets where event_id = '{EVENT}';
      delete from public.rsvps where event_id = '{EVENT}';
      delete from public.events where id = '{EVENT}';""")


@pytest.fixture(scope="module")
def people():
    admin, a, b = Session(ADMIN_PHONE), Session(GUESTS[0]), Session(GUESTS[1])
    clean()
    sql_test(f"""insert into public.events (id, title, created_by, status, starts_at, ends_at, public_link, notify_on_publish, reminders)
      values ('{EVENT}', 'Soirée test pièces', '{admin.uid}', 'published', now() + interval '2 hours', now() + interval '6 hours',
              true, false, '{{}}');""")
    yield admin, a, b
    clean()


def test_the_right_exists_and_is_given_to_admin_and_coadmin_only(people):
    rows = sql_test("select role from public.role_permissions where perm = 'zicou.event_coins' order by role;")
    assert [r["role"] for r in rows] == ["admin", "coadmin"]
    perm = sql_test("select label, grp from public.permissions where key = 'zicou.event_coins';")
    assert perm == [{"label": "Donner des pièces Zicou pour un événement", "grp": "Zicou"}]
    _, a, _ = people
    for table in ("pet_event_coins", "pet_event_coin_grants"):
        r = a.get(f"{table}?select=*")
        assert r.status_code in (401, 403) or r.json() == [], (table, r.text)


def test_without_the_right_nothing_is_visible_nor_settable(people):
    _, a, _ = people
    seen = a.rpc("pet_event_coins_get", p_event=EVENT).json()
    assert seen == {"allowed": False, "mine": None, "setting": None}
    r = a.rpc("pet_event_coins_set", p_event=EVENT, p_coins=20)
    assert r.status_code in (400, 403) and r.json()["message"].startswith("forbidden"), r.text


def test_coins_are_bounded_paid_once_to_present_people_only_and_then_frozen(people):
    admin, a, b = people
    for bad in (4, 101):
        r = admin.rpc("pet_event_coins_set", p_event=EVENT, p_coins=bad)
        assert r.status_code == 400 and "De 5 à 100" in r.json()["message"], r.text
    got = admin.rpc("pet_event_coins_set", p_event=EVENT, p_coins=20)
    assert got.status_code == 200, got.text
    setting = got.json()["setting"]
    assert setting["coins"] == 20 and setting["given"] == 0 and setting["late"] is False
    assert sql_test(f"select count(*)::int as n from public.member_audit where action = 'pet.event_coins' and details ->> 'event' = '{EVENT}';")[0]["n"] >= 1
    # Présents : b (billet scanné, n'a PAS payé), a (noté « Présent » par l'admin). L'admin : inscrit, a PAYÉ, pas arrivé.
    sql_test(f"""insert into public.rsvps (event_id, user_id, status) values ('{EVENT}', '{b.uid}', 'yes'), ('{EVENT}', '{admin.uid}', 'yes');
      update public.rsvps set waitlisted = false where event_id = '{EVENT}';
      insert into public.event_tickets (event_id, user_id, token, code, checked_in_at, paid)
      values ('{EVENT}', '{b.uid}', encode(extensions.gen_random_bytes(32), 'hex'), 'BBBBBC', now(), false),
             ('{EVENT}', '{admin.uid}', encode(extensions.gen_random_bytes(32), 'hex'), 'CCCCCD', null, true);""")
    assert admin.rpc("set_rsvp_for", event=EVENT, member=a.uid, answer="yes").status_code == 204   # noté « Présent »
    assert sql_test(f"select private.pet_event_coins_grant('{EVENT}') as n;")[0]["n"] == 0   # pas encore fini : rien
    sql_test(f"update public.events set starts_at = now() - interval '5 hours', ends_at = now() - interval '1 hour' where id = '{EVENT}';")
    assert sql_test("select private.pet_event_draw_due() >= 2 as ok;")[0]["ok"]          # le cron les verse
    assert sql_test(f"select private.pet_event_coins_grant('{EVENT}') as n;")[0]["n"] == 0   # une seule fois
    grants = sql_test(f"select user_id::text as u, coins from public.pet_event_coin_grants where event_id = '{EVENT}' order by u;")
    assert {g["u"] for g in grants} == {a.uid, b.uid} and all(g["coins"] == 20 for g in grants)   # jamais l'admin (payé)
    frozen = admin.rpc("pet_event_coins_set", p_event=EVENT, p_coins=50)
    assert frozen.status_code == 400 and frozen.json()["message"].startswith("frozen"), frozen.text
    assert admin.rpc("pet_event_coins_get", p_event=EVENT).json()["setting"]["given"] == 2
    assert b.rpc("pet_event_coins_get", p_event=EVENT).json() == {"allowed": False, "mine": 20, "setting": None}


def test_the_server_loads_them_once_and_marks_them(people):
    _, _, b = people
    loaded = b.rpc("pet_load", p_key=KEY()).json()
    assert "events" not in loaded and "answers" not in loaded
    mine = [x for x in loaded["coins"] if x["event_id"] == EVENT]
    assert len(mine) == 1 and mine[0]["coins"] == 20 and mine[0]["event"] == "Soirée test pièces"
    assert b.rpc("pet_event_coins_claim", p_ids=[mine[0]["id"]], p_key=KEY()).json() == 1
    assert b.rpc("pet_event_coins_claim", p_ids=[mine[0]["id"]], p_key=KEY()).json() == 0
    assert not [x for x in b.rpc("pet_load", p_key=KEY()).json()["coins"] if x["event_id"] == EVENT]
    no_key = b.rpc("pet_event_coins_claim", p_ids=[mine[0]["id"]])
    assert no_key.status_code >= 400   # seul le serveur Party (sa clé) marque les pièces rangées
