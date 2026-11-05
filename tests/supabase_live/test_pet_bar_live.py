"""Barre « petit cadeau » de Zicou sur la VRAIE base de test (migration 20261105160000, jamais la prod) : l'heure
« pleine » recopiée de owner -> 'bar' à l'enregistrement, notification « pet_bar » une fois par barre, 2 par jour au plus,
jamais la nuit, ni en pause, ni déjà passé, ni sans l'interrupteur ; l'interrupteur respecté par l'envoi (web_push_allowed).

Compte : Testeur 3 (numéro de test à code fixe) ; son compagnon et ses notifications pet_* sont effacés avant et après."""
import pytest

from tests.supabase_live.test_member_admin_live import GUESTS, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_pet_live import KEY, fresh, save, sql_test


def wipe(uid: str) -> None:
    sql_test(f"""delete from public.pets where user_id = '{uid}';
      delete from public.notifications where user_id = '{uid}' and kind like 'pet\\_%';
      update public.notification_prefs set pet_bar = true, muted_until = null where user_id = '{uid}';""")


@pytest.fixture(scope="module")
def c():
    s = Session(GUESTS[2])
    wipe(s.uid)
    life, owner = fresh()
    owner["bar"] = {"from": "2026-11-05T08:00:00+00:00", "full_at": "2026-11-05T09:30:00+00:00", "day": "", "n": 0,
                    "last": None}
    assert save(s, life, owner, 0).status_code == 200
    yield s
    wipe(s.uid)


def reset(c, full_at="2026-11-05 10:30+01"):
    sql_test(f"""update public.pets set stage = 'baby', name = 'Zicou', last_seen_at = null, bar_full_at = '{full_at}',
                   bar_notified_for = null, bar_sent_on = null, bar_sent_n = 0 where user_id = '{c.uid}';
                 delete from public.notifications where user_id = '{c.uid}' and kind like 'pet\\_%';""")


def notes(c) -> list[dict]:
    return sql_test(f"""select kind, title, body, data->>'url' as url from public.notifications
                        where user_id = '{c.uid}' and kind = 'pet_bar' order by created_at;""")


def test_full_at_is_copied_from_the_saved_owner(c):
    rows = sql_test(f"select bar_full_at = '2026-11-05T09:30:00+00:00'::timestamptz as ok from public.pets where user_id = '{c.uid}';")
    assert rows == [{"ok": True}]
    loaded = c.rpc("pet_load", p_key=KEY()).json()["pet"]
    life, owner = loaded["life"], loaded["owner"]
    owner["bar"]["full_at"] = "pas une date"   # illisible : rien, jamais d'erreur à l'enregistrement
    assert save(c, life, owner, loaded["version"]).status_code == 200
    assert sql_test(f"select bar_full_at from public.pets where user_id = '{c.uid}';") == [{"bar_full_at": None}]


def test_one_notification_per_full_bar_never_at_night_never_once_visited(c):
    reset(c)
    assert sql_test("select private.pet_bar_notify('2026-11-05 10:20+01') as n;")[0]["n"] == 0   # pas encore pleine
    sql_test("select private.pet_bar_notify('2026-11-05 10:40+01');")
    rows = notes(c)
    assert len(rows) == 1 and rows[0]["title"] == "Zicou" and "barre Zicou est pleine" in rows[0]["body"]
    assert rows[0]["url"] == "/?tab=games&pet=1&src=notif"
    assert not any(w in rows[0]["body"].lower() for w in ("raté", "vite", "dernière", "plus que"))   # ton neutre
    sql_test("select private.pet_bar_notify('2026-11-05 11:00+01');")
    assert len(notes(c)) == 1   # une fois par barre
    reset(c, "2026-11-05 22:50+01")
    for night in ("2026-11-05 23:10+01", "2026-11-06 03:00+01", "2026-11-06 07:50+01"):
        sql_test(f"select private.pet_bar_notify('{night}');")
    assert notes(c) == []
    reset(c)
    sql_test(f"update public.pets set last_seen_at = '2026-11-05 10:35+01' where user_id = '{c.uid}';")
    sql_test("select private.pet_bar_notify('2026-11-05 10:40+01');")
    assert notes(c) == []   # déjà passé depuis qu'elle est pleine


def test_at_most_two_a_day(c):
    reset(c)
    for full, run in (("10:30", "10:40"), ("13:10", "13:20"), ("15:50", "16:00")):
        sql_test(f"update public.pets set bar_full_at = '2026-11-05 {full}+01' where user_id = '{c.uid}';")
        sql_test(f"select private.pet_bar_notify('2026-11-05 {run}+01');")
    assert len(notes(c)) == 2
    sql_test(f"update public.pets set bar_full_at = '2026-11-06 10:30+01' where user_id = '{c.uid}';")
    sql_test("select private.pet_bar_notify('2026-11-06 10:40+01');")
    assert len(notes(c)) == 3   # le lendemain, ça repart


def test_its_own_switch_and_the_pause_are_respected(c):
    reset(c)
    sql_test(f"update public.notification_prefs set pet_bar = false where user_id = '{c.uid}';")
    try:
        sql_test("select private.pet_bar_notify('2026-11-05 10:40+01');")
        assert notes(c) == []
        sql_test(f"update public.notification_prefs set pet_bar = true, muted_until = now() + interval '1 hour' where user_id = '{c.uid}';")
        sql_test("select private.pet_bar_notify('2026-11-05 10:40+01');")
        assert notes(c) == []   # pause des notifications : rien
    finally:
        sql_test(f"update public.notification_prefs set pet_bar = true, muted_until = null where user_id = '{c.uid}';")
    sql_test("select private.pet_bar_notify('2026-11-05 10:40+01');")
    assert len(notes(c)) == 1


def test_the_push_gates_know_the_switch(c):
    reset(c)
    sql_test("select private.pet_bar_notify('2026-11-05 10:40+01');")
    gate = f"""select private.may_receive_push('{c.uid}', 'pet_bar') as may,
                      position('prefs.pet_bar' in pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure)) > 0 as web"""
    assert sql_test(gate + ";") == [{"may": True, "web": True}]
    sql_test(f"update public.notification_prefs set push_enabled = true, pet_bar = false where user_id = '{c.uid}';")
    try:
        allowed = sql_test(f"""select private.web_push_allowed(n) as ok from public.notifications n
                               where n.user_id = '{c.uid}' and n.kind = 'pet_bar';""")
        assert allowed == [{"ok": False}]
    finally:
        sql_test(f"update public.notification_prefs set pet_bar = true where user_id = '{c.uid}';")
