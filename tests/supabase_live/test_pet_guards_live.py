"""Compagnon, failles du playtest « Marc » (4 novembre 2026), reproduites sur la VRAIE base de TEST (jamais la prod) :

  · F1 : un compte connecté appelait pet_save lui-même avec un état forgé (999 999 pièces, série de 365 jours) → refusé
         sans la clé du serveur Party ; et même avec la clé, un état incohérent est refusé ;
  · F4 : cadeaux de comptes secondaires (sans compagnon vivant, compte tout neuf), plus de 3 cadeaux reçus par jour ;
         ajout forcé à un groupe pour devenir « ami » (visite, cadeau) sans que la personne ait rejoint d'elle-même.

Comptes : Testeur 1, 2 et 3. Leur compagnon, cadeaux, journal, groupes de test : effacés avant et après."""
import copy
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import pet
from tests.supabase_live.test_member_admin_live import GUESTS, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_pet_live import sql_test, wipe

GROUP = "6e7a0000-0000-4000-8000-00000000f00d"
FORCED = "6e7a0000-0000-4000-8000-00000000fa11"


def server_key() -> str:
    return sql_test("select decrypted_secret as k from vault.decrypted_secrets where name = 'pet_server_key';")[0]["k"]


@pytest.fixture(scope="module")
def trio():
    a, b, c = Session(GUESTS[0]), Session(GUESTS[1]), Session(GUESTS[2])
    ids = [a.uid, b.uid, c.uid]
    wipe(ids)
    sql_test(f"delete from public.member_groups where id in ('{GROUP}', '{FORCED}');")
    sql_test(f"""insert into public.member_groups (id, name) values ('{GROUP}', 'Test garde-fous');
      insert into public.member_group_members (group_id, user_id) values ('{GROUP}', '{a.uid}'), ('{GROUP}', '{b.uid}');""")
    yield a, b, c
    wipe(ids)
    sql_test(f"delete from public.member_groups where id in ('{GROUP}', '{FORCED}');")


def hatched():
    now = datetime.now(timezone.utc)
    life, owner = pet.new_pet(now - timedelta(minutes=10))
    pet.advance(life, now, owner)
    return life, owner


def save(s: Session, life, owner, version, key=None):
    args = dict(p_life=life, p_owner=owner, p_version=version, p_hungry_at=None, p_dies_at=None)
    return s.rpc("pet_save", **args, **({"p_key": key} if key is not None else {}))


def test_f1_a_member_cannot_write_his_own_state_without_the_server_key(trio):
    a, *_ = trio
    life, owner = hatched()
    forged = copy.deepcopy(owner)
    forged["loop"] = {"coins": 999999, "inv": {"snack:cupcake": 99}}
    forged["streak"].update(count=365, best=365)
    for attempt in (save(a, life, forged, 0), save(a, life, forged, 0, key="x" * 64)):
        assert attempt.status_code == 400 and "server" in attempt.json()["message"], attempt.text
    assert sql_test(f"select count(*)::int as n from public.pets where user_id = '{a.uid}';") == [{"n": 0}]
    loaded = a.rpc("pet_load")   # la lecture directe aussi (elle compte les ouvertures)
    assert loaded.status_code == 400 and "server" in loaded.json()["message"]


def test_f1_even_with_the_key_an_incoherent_state_is_refused(trio):
    a, *_ = trio
    key = server_key()
    life, owner = hatched()
    assert save(a, life, owner, 0, key).status_code == 200
    rich = copy.deepcopy(owner)
    rich["loop"] = {"coins": 999999}
    long = copy.deepcopy(owner)
    long["streak"].update(count=365, best=365)
    stars = copy.deepcopy(owner)
    stars["stats"]["stars"] = 9
    over = copy.deepcopy(life)
    over["g"]["food"] = 250
    for bad_life, bad_owner in ((life, rich), (life, long), (life, stars), (over, owner)):
        r = save(a, bad_life, bad_owner, 1, key)
        assert r.status_code == 400 and "incohérent" in r.json()["message"], r.text
    fine = copy.deepcopy(owner)
    fine["loop"] = {"coins": 40}
    assert save(a, life, fine, 1, key).status_code == 200


def test_f4_gifts_need_a_living_companion_an_old_account_and_at_most_3_a_day(trio):
    a, b, c = trio
    key = server_key()
    life, owner = hatched()
    cur = b.rpc("pet_load", p_key=key).json()["pet"]
    assert save(b, life, owner, cur["version"] if cur else 0, key).status_code == 200
    # a : compagnon envolé → ne peut pas offrir
    sql_test(f"update public.pets set stage = 'dead' where user_id = '{a.uid}';")
    r = a.rpc("pet_gift", p_friend=b.uid, p_kind="hug", p_key=key)
    assert r.status_code == 400 and "compagnon à compagnon" in r.json()["message"], r.text
    sql_test(f"update public.pets set stage = 'baby' where user_id = '{a.uid}';")
    # a : compte tout neuf → pas encore
    old = sql_test(f"select created_at from public.profiles where id = '{a.uid}';")[0]["created_at"]
    sql_test(f"update public.profiles set created_at = now() - interval '1 day' where id = '{a.uid}';")
    try:
        r = a.rpc("pet_gift", p_friend=b.uid, p_kind="hug", p_key=key)
        assert r.status_code == 400 and "3 premiers jours" in r.json()["message"], r.text
    finally:
        sql_test(f"update public.profiles set created_at = '{old}' where id = '{a.uid}';")
    # Sans la clé du serveur : refusé
    assert "server" in a.rpc("pet_gift", p_friend=b.uid, p_kind="hug").json()["message"]
    # b a déjà reçu 3 cadeaux aujourd'hui (d'autres amis) : le 4e est refusé
    today = sql_test("select (now() at time zone 'Europe/Zurich')::date as d;")[0]["d"]
    others = [r["id"] for r in sql_test(f"""select id from public.profiles where id not in ('{a.uid}', '{b.uid}', '{c.uid}')
                                             and status = 'active' order by created_at limit 3;""")]
    sql_test("insert into public.pet_gifts (from_user, to_user, kind, day) values "
             + ", ".join(f"('{o}', '{b.uid}', 'hug', '{today}')" for o in others) + ";")
    r = a.rpc("pet_gift", p_friend=b.uid, p_kind="snack", p_key=key)
    assert r.status_code == 400 and "plein de cadeaux" in r.json()["message"], r.text
    sql_test(f"delete from public.pet_gifts where to_user = '{b.uid}';")
    assert a.rpc("pet_gift", p_friend=b.uid, p_kind="snack", p_key=key).status_code == 200


def test_f4_a_forced_group_add_does_not_make_a_friend_before_3_days(trio):
    a, _, c = trio
    key = server_key()
    life, owner = hatched()
    cur = c.rpc("pet_load", p_key=key).json()["pet"]
    assert save(c, life, owner, cur["version"] if cur else 0, key).status_code == 200
    # a crée un groupe et y ajoute c, sans que c ait rien demandé (permis par la politique des groupes)
    made = a.rpc("pet_friends")   # (lecture de contrôle : c n'est pas son ami)
    assert all(f["id"] != c.uid for f in made.json())
    sql_test(f"""insert into public.member_groups (id, name, created_by) values ('{FORCED}', 'Forcé', '{a.uid}');""")
    added = httpx.post(f"{TEST_URL}/rest/v1/member_group_members", headers=a.headers, timeout=30,
                       json=[{"group_id": FORCED, "user_id": c.uid}])   # (le créateur y est mis d'office)
    assert added.status_code in (200, 201), added.text
    rows = sql_test(f"select added_by::text as by from public.member_group_members where group_id = '{FORCED}' and user_id = '{c.uid}';")
    assert rows == [{"by": a.uid}]
    r = a.rpc("pet_friend", p_friend=c.uid)
    assert r.status_code == 400 and "forbidden" in r.json()["message"], r.text
    assert "forbidden" in a.rpc("pet_gift", p_friend=c.uid, p_kind="hug", p_key=key).json()["message"]
    # 3 jours plus tard (c ne l'a pas quitté) : ami
    sql_test(f"update public.member_group_members set added_at = now() - interval '4 days' where group_id = '{FORCED}';")
    assert a.rpc("pet_friend", p_friend=c.uid).status_code == 200


def test_without_pet_secret_a_server_key_is_enrolled_once(trio):
    """Sans PET_SECRET, le serveur crée sa propre clé et l'enrôle : acceptée UNE fois (premier arrivé), puis plus rien."""
    a, b, _ = trio
    taken = sql_test("select count(*)::int as n from private.pet_server_keys;")[0]["n"]
    if taken:
        pytest.skip("une clé de serveur est déjà enrôlée sur la base de TEST (serveur de test) : on n'y touche pas")
    mine, other = "cle-propre-au-serveur-de-test-" + "1" * 40, "cle-arrivee-trop-tard-" + "2" * 40
    try:
        assert a.rpc("pet_server_enroll", p_key="trop-courte").json() is False
        assert a.rpc("pet_server_enroll", p_key=mine).json() is True
        assert a.rpc("pet_load", p_key=mine).status_code == 200
        assert b.rpc("pet_server_enroll", p_key=other).json() is False
        assert "server" in b.rpc("pet_load", p_key=other).json()["message"]
        assert a.rpc("pet_server_enroll", p_key=server_key()).json() is True   # la clé du coffre reste valable
        assert a.get("pet_server_keys?select=*").status_code in (401, 403, 404)
    finally:
        sql_test("delete from private.pet_server_keys;")
