"""Compagnon sur la VRAIE base de test (jamais la prod) : table fermée (aucun accès direct), chacun n'écrit que le sien,
versions (conflit entre appareils), garde-fous de pet_save, amis = groupe en commun (ce qui est montrable seulement),
cadeau un par jour, notifications (rappel du jour, alertes avant l'envol, interrupteurs) et passage par app/pet_store.py.

Comptes : Testeur 1, 2 et 3 (numéros de test à code fixe). Leurs compagnons, cadeaux, journaux, le groupe de test et
les notifications pet_* sont effacés avant et après (outil supabase/tools/sbq.py, base de TEST seulement)."""
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app import accounts as accounts_mod, pet, pet_store
from tests.supabase_live.test_member_admin_live import GUESTS, KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
GROUP = "6e7a0000-0000-4000-8000-00000000c0de"


def sql_test(query: str) -> list:
    out = subprocess.run(["python3", str(ROOT / "supabase/tools/sbq.py"), "test", "rw"], input=query,
                         capture_output=True, text=True, timeout=120, check=True).stdout
    return json.loads(out or "[]")


def wipe(ids: list[str]) -> None:
    users = ",".join(f"'{u}'" for u in ids)
    sql_test(f"""delete from public.pets where user_id in ({users});
      delete from public.pet_gifts where from_user in ({users}) or to_user in ({users});
      delete from public.pet_journal where user_id in ({users});
      delete from public.notifications where user_id in ({users}) and kind in ('pet_daily', 'pet_alert');
      delete from public.member_groups where id = '{GROUP}';""")


@pytest.fixture(scope="module")
def trio():
    a, b, c = Session(GUESTS[0]), Session(GUESTS[1]), Session(GUESTS[2])
    ids = [a.uid, b.uid, c.uid]
    wipe(ids)
    # a et b partagent ce groupe de test ; c n'y est pas (test_friends… vérifie qu'aucun autre groupe ne le relie à b).
    sql_test(f"""insert into public.member_groups (id, name) values ('{GROUP}', 'Test compagnon');
      insert into public.member_group_members (group_id, user_id) values ('{GROUP}', '{a.uid}'), ('{GROUP}', '{b.uid}');""")
    yield a, b, c
    wipe(ids)


def fresh(now=None):
    life, owner = pet.new_pet(now or datetime.now(timezone.utc))
    return life, owner


def save(s: Session, life, owner, version, **kw):
    return s.rpc("pet_save", p_life=life, p_owner=owner, p_version=version, p_hungry_at=kw.get("hungry"),
                 p_dies_at=kw.get("dies"), p_cared=kw.get("cared", False), p_gifts=kw.get("gifts", []),
                 p_journal=kw.get("journal", []))


def test_the_tables_are_closed(trio):
    a, *_ = trio
    for table in ("pets", "pet_gifts", "pet_journal"):
        r = a.get(f"{table}?select=*")
        assert r.status_code in (401, 403) or r.json() == [], (table, r.text)
    anon = httpx.post(f"{TEST_URL}/rest/v1/rpc/pet_load", json={},
                      headers={"apikey": KEY_FILE.read_text().strip(), "Content-Type": "application/json"}, timeout=30)
    assert anon.status_code in (401, 403) or "Connecte-toi" in anon.text


def test_save_load_versions_and_guards(trio):
    a, *_ = trio
    life, owner = fresh()
    assert save(a, life, owner, 1).status_code == 400   # pas encore de compagnon : version 0 attendue
    r = save(a, life, owner, 0, journal=[{"kind": "egg", "detail": {"gen": 1}}], cared=True)
    assert r.status_code == 200 and r.json() == {"version": 1}, r.text
    loaded = a.rpc("pet_load").json()
    assert loaded["pet"]["version"] == 1 and loaded["pet"]["life"]["stage"] == "egg"
    assert loaded["gifts"] == [] and isinstance(loaded["brain"], list) and isinstance(loaded["events"], list)
    conflict = save(a, life, owner, 0)
    assert conflict.status_code == 400 and "conflict" in conflict.json()["message"]
    bad = dict(life, stage="dragon")
    assert "invalid" in save(a, bad, owner, 1).json()["message"]
    assert "invalid" in save(a, dict(life, name=""), owner, 1).json()["message"]
    assert "invalid" in save(a, dict(life, gen="x"), owner, 1).json()["message"]
    assert "invalid" in save(a, life, owner, 1, journal=[{"kind": "x"}] * 13).json()["message"]
    life2 = dict(life, gen=2)
    assert save(a, life2, owner, 1).status_code == 200
    assert "invalid" in save(a, life, owner, 2).json()["message"]   # la génération ne recule jamais
    rows = sql_test(f"select gen, version, stage, last_care_at is not null as cared from public.pets where user_id = '{a.uid}';")
    assert rows == [{"gen": 2, "version": 2, "stage": "egg", "cared": True}]
    assert sql_test(f"select count(*)::int as n from public.pet_journal where user_id = '{a.uid}';")[0]["n"] >= 1


def test_friends_share_a_group_and_see_only_the_creature(trio):
    a, b, c = trio
    life, owner = fresh()
    pet.advance(life, datetime.now(timezone.utc) + timedelta(minutes=5), owner)   # éclos : peut recevoir un cadeau
    owner["memorial"] = [{"gen": 9, "name": "secret"}]
    current = b.rpc("pet_load").json()["pet"]
    assert save(b, life, owner, current["version"] if current else 0).status_code == 200
    friends = a.rpc("pet_friends").json()
    mine = [f for f in friends if f["id"] == b.uid]
    assert len(mine) == 1 and set(mine[0]) == {"id", "name", "avatar_url", "life", "gifted"}
    assert "secret" not in json.dumps(friends)
    assert a.rpc("pet_friend", p_friend=b.uid).status_code == 200
    stranger = c.rpc("pet_friend", p_friend=b.uid)
    assert stranger.status_code == 400 and "forbidden" in stranger.json()["message"]
    assert "forbidden" in c.rpc("pet_gift", p_friend=b.uid, p_kind="hug").json()["message"]


def test_one_gift_per_friend_per_day_applied_by_the_owner(trio):
    a, b, _ = trio
    assert a.rpc("pet_gift", p_friend=b.uid, p_kind="hug").status_code == 200
    second = a.rpc("pet_gift", p_friend=b.uid, p_kind="snack")
    assert second.status_code == 400 and "limit" in second.json()["message"]
    assert "invalid" in a.rpc("pet_gift", p_friend=b.uid, p_kind="bomb").json()["message"]
    assert a.rpc("pet_friend", p_friend=b.uid).json()["gifted"] is True
    gifts = b.rpc("pet_load").json()["gifts"]
    assert len(gifts) == 1 and gifts[0]["kind"] == "hug"
    # a ne peut pas marquer « ouvert » le cadeau de b à sa place
    cur = a.rpc("pet_load").json()["pet"]
    save(a, cur["life"], cur["owner"], cur["version"], gifts=[gifts[0]["id"]])
    assert len(b.rpc("pet_load").json()["gifts"]) == 1


def test_the_python_layer_against_the_real_base(trio, monkeypatch):
    _, b, _ = trio
    monkeypatch.setattr(accounts_mod, "SUPABASE_URL", TEST_URL)
    monkeypatch.setattr(accounts_mod, "SUPABASE_ANON_KEY", KEY_FILE.read_text().strip())
    store = pet_store.PetStore(accounts_mod.Accounts(b"secret", httpx.Client(timeout=30)), pet_store.PartyLog(None))
    token = b.headers["Authorization"].removeprefix("Bearer ")
    first = store.me(token)
    assert first["pet"]["stage"] == "baby"
    assert any(n["kind"] == "gift" for n in first["news"])   # le câlin de a, ouvert
    assert b.rpc("pet_load").json()["gifts"] == []
    fed = store.act(token, "cuddle")
    assert fed["pet"]["left"]["cuddle"] == pet.DAILY_LIMITS["cuddle"] - 1
    row = sql_test(f"select hungry_at is not null as h, dies_at is not null as d from public.pets where user_id = '{b.uid}';")
    assert row == [{"h": True, "d": True}]


def test_notifications_daily_reminder_and_alerts(trio):
    a, b, _ = trio
    evening = "2026-11-05 18:30:00+01"   # 18 h 30 à Zurich
    sql_test(f"""update public.pets set stage = 'baby', hungry_at = '2026-11-05 10:00+01', last_care_at = null,
                   daily_sent_on = null, dies_at = '2026-11-06 12:00+01', alerts_sent = '{{}}'
                 where user_id = '{b.uid}';
                 delete from public.notifications where user_id = '{b.uid}' and kind like 'pet_%';""")
    assert sql_test(f"select private.pet_notify('{evening}') as n;")[0]["n"] >= 2
    rows = sql_test(f"select kind, title, data->>'url' as url from public.notifications where user_id = '{b.uid}' and kind like 'pet_%' order by kind;")
    kinds = [r["kind"] for r in rows]
    assert kinds == ["pet_alert", "pet_daily"], rows
    assert all(r["url"] == "/?tab=games&pet=1" for r in rows)
    assert not any(w in r["title"].lower() for r in rows for w in ("faute", "oubli", "mort"))
    # Une seule fois : ni deuxième rappel le même jour, ni deuxième alerte des 48 h.
    sql_test(f"select private.pet_notify('{evening}');")
    assert sql_test(f"select count(*)::int as n from public.notifications where user_id = '{b.uid}' and kind like 'pet_%';")[0]["n"] == 2
    # 12 h avant : la seconde alerte.
    sql_test("select private.pet_notify('2026-11-06 02:00+01');")
    assert sql_test(f"select count(*)::int as n from public.notifications where user_id = '{b.uid}' and kind = 'pet_alert';")[0]["n"] == 2
    # Le matin : jamais de rappel du jour (17 h – 20 h seulement).
    sql_test(f"update public.pets set daily_sent_on = null where user_id = '{b.uid}';")
    sql_test("select private.pet_notify('2026-11-06 09:00+01');")
    assert sql_test(f"select count(*)::int as n from public.notifications where user_id = '{b.uid}' and kind = 'pet_daily';")[0]["n"] == 1


def test_each_notification_has_its_own_switch(trio):
    _, b, _ = trio
    rows = sql_test(f"""select private.web_push_allowed(n) as ok, n.kind from public.notifications n
                        where n.user_id = '{b.uid}' and n.kind like 'pet_%' limit 2;""")
    assert rows
    sql_test(f"update public.notification_prefs set pet_daily = false, pet_alerts = false where user_id = '{b.uid}';")
    try:
        off = sql_test(f"""select bool_or(private.web_push_allowed(n)) as ok from public.notifications n
                           where n.user_id = '{b.uid}' and n.kind like 'pet_%';""")
        assert off == [{"ok": False}]
        r = b.get(f"notification_prefs?select=pet_daily,pet_alerts&user_id=eq.{b.uid}")
        assert r.json() == [{"pet_daily": False, "pet_alerts": False}]
    finally:
        sql_test(f"update public.notification_prefs set pet_daily = true, pet_alerts = true where user_id = '{b.uid}';")
    assert sql_test(f"select private.may_receive_push('{b.uid}', 'pet_daily') as ok;") == [{"ok": True}]
