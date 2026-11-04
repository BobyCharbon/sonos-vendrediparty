"""Compagnon sur la VRAIE base de test (jamais la prod) : table fermée (aucun accès direct), chacun n'écrit que le sien,
versions (conflit entre appareils), garde-fous de pet_save, amis = groupe en commun (ce qui est montrable seulement),
cadeau un par jour, notifications (rappel du jour, alertes avant l'envol, interrupteurs) et passage par app/pet_store.py.
Lot 1 « revenir tous les jours » (migration 20261104150000) : ouvertures comptées (pet_opens), rappel à l'heure apprise
(au plus un par jour, jamais la nuit ni en soirée, ni si on est déjà passé), cadeau d'un ami, palier de série, chaque type
avec son interrupteur, tuile admin réservée aux admins.

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
EVENT = "6e7a0000-0000-4000-8000-0000000e7e47"


def sql_test(query: str) -> list:
    out = subprocess.run(["python3", str(ROOT / "supabase/tools/sbq.py"), "test", "rw"], input=query,
                         capture_output=True, text=True, timeout=120, check=True).stdout
    return json.loads(out or "[]")


def KEY() -> str:  # noqa: N802 — clé du serveur Party (coffre de la base de TEST), comme PET_SECRET sur le serveur
    global _KEY
    if not _KEY:
        _KEY = sql_test("select decrypted_secret as k from vault.decrypted_secrets where name = 'pet_server_key';")[0]["k"]
    return _KEY


_KEY = ""


def wipe(ids: list[str]) -> None:
    users = ",".join(f"'{u}'" for u in ids)
    sql_test(f"""delete from public.pets where user_id in ({users});
      delete from public.pet_gifts where from_user in ({users}) or to_user in ({users});
      delete from public.pet_journal where user_id in ({users});
      delete from public.pet_opens where user_id in ({users});
      delete from public.notifications where user_id in ({users}) and kind like 'pet\\_%';
      delete from public.rsvps where event_id = '{EVENT}';
      delete from public.events where id = '{EVENT}';
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
    return s.rpc("pet_save", p_key=KEY(), p_life=life, p_owner=owner, p_version=version, p_hungry_at=kw.get("hungry"),
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
    loaded = a.rpc("pet_load", p_key=KEY()).json()
    assert loaded["pet"]["version"] == 1 and loaded["pet"]["life"]["stage"] == "egg"
    assert loaded["gifts"] == [] and isinstance(loaded["brain"], list) and isinstance(loaded["coins"], list)
    assert "events" not in loaded and "answers" not in loaded   # présence et réponses : plus rien (04.11.2026)
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
    current = b.rpc("pet_load", p_key=KEY()).json()["pet"]
    assert save(b, life, owner, current["version"] if current else 0).status_code == 200
    friends = a.rpc("pet_friends").json()
    mine = [f for f in friends if f["id"] == b.uid]
    assert len(mine) == 1 and set(mine[0]) == {"id", "name", "avatar_url", "life", "gifted"}
    assert "secret" not in json.dumps(friends)
    assert a.rpc("pet_friend", p_friend=b.uid).status_code == 200
    stranger = c.rpc("pet_friend", p_friend=b.uid)
    assert stranger.status_code == 400 and "forbidden" in stranger.json()["message"]
    assert "forbidden" in c.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="hug").json()["message"]


def test_one_gift_per_friend_per_day_applied_by_the_owner(trio):
    a, b, _ = trio
    sql_test(f"update public.pets set stage = 'baby' where user_id = '{a.uid}';")   # offrir : son compagnon doit être là
    assert a.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="hug").status_code == 200
    second = a.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="snack")
    assert second.status_code == 400 and "limit" in second.json()["message"]
    assert "invalid" in a.rpc("pet_gift", p_key=KEY(), p_friend=b.uid, p_kind="bomb").json()["message"]
    assert a.rpc("pet_friend", p_friend=b.uid).json()["gifted"] is True
    gifts = b.rpc("pet_load", p_key=KEY()).json()["gifts"]
    assert len(gifts) == 1 and gifts[0]["kind"] == "hug"
    # a ne peut pas marquer « ouvert » le cadeau de b à sa place
    cur = a.rpc("pet_load", p_key=KEY()).json()["pet"]
    save(a, cur["life"], cur["owner"], cur["version"], gifts=[gifts[0]["id"]])
    assert len(b.rpc("pet_load", p_key=KEY()).json()["gifts"]) == 1


def test_the_python_layer_against_the_real_base(trio, monkeypatch):
    _, b, _ = trio
    monkeypatch.setattr(accounts_mod, "SUPABASE_URL", TEST_URL)
    monkeypatch.setattr(accounts_mod, "SUPABASE_ANON_KEY", KEY_FILE.read_text().strip())
    store = pet_store.PetStore(accounts_mod.Accounts(b"secret", httpx.Client(timeout=30)), pet_store.PartyLog(None),
                               secret=KEY())
    token = b.headers["Authorization"].removeprefix("Bearer ")
    first = store.me(token, "notif")
    assert first["pet"]["stage"] == "baby" and first["pet"]["daily"]["chest"]["state"] in ("ready", "opened")
    assert any(n["kind"] == "gift" for n in first["news"])   # le câlin de a, ouvert
    assert b.rpc("pet_load", p_key=KEY()).json()["gifts"] == []
    fed = store.act(token, "cuddle")
    assert fed["pet"]["left"]["cuddle"] == pet.DAILY_LIMITS["cuddle"] - 1
    row = sql_test(f"select hungry_at is not null as h, dies_at is not null as d from public.pets where user_id = '{b.uid}';")
    assert row == [{"h": True, "d": True}]
    if fed["pet"]["daily"]["chest"]["state"] == "ready":
        opened = store.act(token, "chest")
        assert opened["effect"]["found"]["kind"] in ("coins", "snack", "sticker", "item")
    nudge = sql_test(f"select nudge from public.pets where user_id = '{b.uid}';")[0]["nudge"]
    assert nudge and nudge["kind"] in ("pet_daily", "pet_streak") and 480 <= nudge["minute"] <= 1365


def reset_b(b, **cols):
    """Compagnon de b remis comme il faut pour un test de notification (le 5 novembre, pas encore passé)."""
    nudge = cols.pop("nudge", {"day": "2026-11-05", "minute": 1080, "kind": "pet_daily", "title": "Zicou",
                               "body": "Le coffre du jour brille sous mon lit. On l'ouvre ensemble ? 🎁",
                               "alt_title": "Zicou", "alt_body": "Le coffre du jour brille sous mon lit. On l'ouvre ensemble ? 🎁"})
    sets = ", ".join(f"{k} = {v}" for k, v in {"dies_at": "null", **cols}.items())
    sql_test(f"""update public.pets set stage = 'baby', name = 'Zicou', daily_sent_on = null, last_seen_at = null,
                   gifts_noted_at = now(), alerts_sent = '{{}}',
                   nudge = '{json.dumps(nudge, ensure_ascii=False).replace("'", "''")}'::jsonb, {sets}
                 where user_id = '{b.uid}';
                 delete from public.notifications where user_id = '{b.uid}' and kind like 'pet\\_%';""")


def pet_notes(b) -> list[dict]:
    return sql_test(f"""select kind, title, body, data->>'url' as url from public.notifications
                        where user_id = '{b.uid}' and kind like 'pet\\_%' order by created_at, kind;""")


def test_notifications_daily_reminder_at_the_learned_hour_and_alerts(trio):
    a, b, _ = trio
    reset_b(b, dies_at="'2026-11-06 12:00+01'")
    assert sql_test("select private.pet_notify('2026-11-05 17:50+01') as n;")[0]["n"] == 1   # l'alerte des 48 h seulement
    assert [r["kind"] for r in pet_notes(b)] == ["pet_alert"]
    sql_test("select private.pet_notify('2026-11-05 18:05+01');")   # 18 h 05 : l'heure apprise (18 h 00) est passée
    rows = pet_notes(b)
    assert [r["kind"] for r in rows] == ["pet_alert", "pet_daily"], rows
    assert rows[1]["title"] == "Zicou" and "coffre" in rows[1]["body"]
    assert all(r["url"] == "/?tab=games&pet=1&src=notif" for r in rows)
    assert not any(w in (r["title"] + r["body"]).lower() for r in rows for w in ("faute", "oubli", "mort"))
    sql_test("select private.pet_notify('2026-11-05 21:00+01');")   # au plus une par jour (hors alertes vitales)
    assert len(pet_notes(b)) == 2
    sql_test("select private.pet_notify('2026-11-06 02:00+01');")   # 12 h avant : la seconde alerte vitale
    assert [r["kind"] for r in pet_notes(b)].count("pet_alert") == 2


def test_never_at_night_never_once_visited_today_and_a_generic_text_otherwise(trio):
    _, b, _ = trio
    reset_b(b)
    for night in ("2026-11-05 23:10+01", "2026-11-06 07:50+01", "2026-11-06 03:00+01"):
        sql_test(f"select private.pet_notify('{night}');")
    assert pet_notes(b) == []
    sql_test(f"update public.pets set last_seen_at = '2026-11-06 09:00+01' where user_id = '{b.uid}';")
    sql_test("select private.pet_notify('2026-11-06 19:00+01');")   # déjà passé aujourd'hui : rien
    assert pet_notes(b) == []
    sql_test("select private.pet_notify('2026-11-07 19:00+01');")   # le 7 : texte du 5 périmé → texte générique
    rows = pet_notes(b)
    assert [r["kind"] for r in rows] == ["pet_daily"] and "🎁" in rows[0]["body"]


def test_never_during_a_soiree_where_you_are_present(trio):
    _, b, _ = trio
    reset_b(b)
    sql_test(f"""begin; set local session_replication_role = replica;
      insert into public.events (id, title, created_by, status, starts_at, ends_at)
      values ('{EVENT}', 'Test compagnon', '{b.uid}', 'published', '2026-11-05 17:30+01', '2026-11-05 23:30+01');
      insert into public.rsvps (event_id, user_id, status) values ('{EVENT}', '{b.uid}', 'yes'); commit;""")
    try:
        sql_test("select private.pet_notify('2026-11-05 19:00+01');")
        assert pet_notes(b) == []
        assert sql_test(f"select private.pet_at_soiree('{b.uid}', '2026-11-05 17:10+01') as ok;") == [{"ok": True}]
        assert sql_test(f"select private.pet_at_soiree('{b.uid}', '2026-11-06 00:10+01') as ok;") == [{"ok": False}]
    finally:
        sql_test(f"delete from public.rsvps where event_id = '{EVENT}'; delete from public.events where id = '{EVENT}';")


def test_a_gift_from_a_friend_then_nothing_else_that_day(trio):
    a, b, _ = trio
    reset_b(b)
    sql_test(f"""delete from public.pet_gifts where to_user = '{b.uid}';
      insert into public.pet_gifts (from_user, to_user, kind, day) values ('{a.uid}', '{b.uid}', 'hug', '2026-11-05');""")
    sql_test("select private.pet_notify('2026-11-05 10:00+01');")   # avant l'heure apprise : le cadeau, tout de suite
    rows = pet_notes(b)
    assert [r["kind"] for r in rows] == ["pet_gift"] and "câlin" in rows[0]["body"] and rows[0]["title"] == "Zicou"
    sql_test("select private.pet_notify('2026-11-05 18:30+01');")
    assert len(pet_notes(b)) == 1
    # Le lendemain, le même cadeau (toujours pas ouvert) n'est pas renvoyé : le rappel du jour à la place.
    sql_test(f"update public.pets set nudge = null where user_id = '{b.uid}';")
    sql_test("select private.pet_notify('2026-11-06 20:30+01');")
    assert [r["kind"] for r in pet_notes(b)] == ["pet_gift", "pet_daily"]
    sql_test(f"delete from public.pet_gifts where to_user = '{b.uid}';")


def test_streak_milestone_with_its_own_switch_and_the_daily_text_as_fallback(trio):
    _, b, _ = trio
    nudge = {"day": "2026-11-05", "minute": 600, "kind": "pet_streak", "title": "Zicou",
             "body": "Aujourd'hui, ça fera 7 jours qu'on se voit 🔥", "alt_title": "Zicou", "alt_body": "Repli du jour 🎁"}
    reset_b(b, nudge=nudge)
    sql_test("select private.pet_notify('2026-11-05 10:05+01');")
    assert [(r["kind"], r["body"]) for r in pet_notes(b)] == [("pet_streak", nudge["body"])]
    reset_b(b, nudge=nudge)
    sql_test(f"update public.notification_prefs set pet_streaks = false where user_id = '{b.uid}';")
    try:
        sql_test("select private.pet_notify('2026-11-05 10:05+01');")
        assert [(r["kind"], r["body"]) for r in pet_notes(b)] == [("pet_daily", "Repli du jour 🎁")]
        reset_b(b, nudge=nudge)
        sql_test(f"update public.notification_prefs set pet_daily = false where user_id = '{b.uid}';")
        sql_test("select private.pet_notify('2026-11-05 10:05+01');")
        assert pet_notes(b) == []   # les deux coupés : rien
    finally:
        sql_test(f"update public.notification_prefs set pet_streaks = true, pet_daily = true where user_id = '{b.uid}';")


def test_opens_are_counted_by_source(trio):
    _, b, _ = trio
    sql_test(f"delete from public.pet_opens where user_id = '{b.uid}';")
    for src in ("notification", "notification", "tab", None, "bidon"):
        assert b.rpc("pet_load", p_key=KEY(), p_src=src).status_code == 200
    rows = sql_test(f"select n, src from public.pet_opens where user_id = '{b.uid}';")
    assert rows == [{"n": 3, "src": {"notification": 2, "tab": 1}}]
    assert sql_test(f"select last_seen_at > now() - interval '1 minute' as ok from public.pets where user_id = '{b.uid}';") == [{"ok": True}]
    r = b.get("pet_opens?select=*")
    assert r.status_code in (401, 403) or r.json() == []


def test_admin_stats_for_admins_only(trio):
    _, b, _ = trio
    refused = b.rpc("pet_admin_stats")
    assert refused.status_code in (400, 403) and "admin" in refused.text.lower()
    stats = sql_test("select to_jsonb(e) as s from private.pet_engagement e;")[0]["s"]
    assert {"pets", "alive", "players", "active_7d", "active_days_per_7", "opens_per_day", "cohorts", "sources_7d",
            "switches_off"} <= set(stats)
    assert stats["players"] >= 1 and stats["sources_7d"].get("notification", 0) >= 2


def test_save_keeps_a_valid_nudge_and_drops_a_bad_one(trio):
    _, b, _ = trio
    cur = b.rpc("pet_load", p_key=KEY()).json()["pet"]
    good = {"day": "2026-11-06", "minute": 1100, "kind": "pet_daily", "title": "Zicou", "body": "x", "alt_title": "Zicou",
            "alt_body": "x"}
    r = b.rpc("pet_save", p_key=KEY(), p_life=cur["life"], p_owner=cur["owner"], p_version=cur["version"], p_hungry_at=None,
              p_dies_at=None, p_nudge=good)
    assert r.status_code == 200, r.text
    assert sql_test(f"select nudge->>'minute' as m from public.pets where user_id = '{b.uid}';") == [{"m": "1100"}]
    for bad in ({**good, "minute": 120}, {**good, "kind": "spam"}, {**good, "day": "demain"}):
        cur = b.rpc("pet_load", p_key=KEY()).json()["pet"]
        b.rpc("pet_save", p_key=KEY(), p_life=cur["life"], p_owner=cur["owner"], p_version=cur["version"], p_hungry_at=None,
              p_dies_at=None, p_nudge=bad)
        assert sql_test(f"select nudge is null as ok from public.pets where user_id = '{b.uid}';") == [{"ok": True}], bad


def test_each_notification_has_its_own_switch(trio):
    _, b, _ = trio
    sql_test(f"""delete from public.notifications where user_id = '{b.uid}' and kind like 'pet\\_%';
                 insert into public.notifications (user_id, kind, title, body, data)
                 values ('{b.uid}', 'pet_daily', 'Zicou', 'x', '{{}}'), ('{b.uid}', 'pet_alert', 'Zicou', 'x', '{{}}');""")
    rows = sql_test(f"""select private.web_push_allowed(n) as ok, n.kind from public.notifications n
                        where n.user_id = '{b.uid}' and n.kind like 'pet_%' limit 2;""")
    assert rows
    sql_test(f"""update public.notification_prefs set pet_daily = false, pet_alerts = false, pet_gifts = false,
                   pet_streaks = false where user_id = '{b.uid}';
                 insert into public.notifications (user_id, kind, title, body, data)
                 values ('{b.uid}', 'pet_gift', 'Zicou', 'x', '{{}}'), ('{b.uid}', 'pet_streak', 'Zicou', 'x', '{{}}');""")
    try:
        off = sql_test(f"""select bool_or(private.web_push_allowed(n)) as ok from public.notifications n
                           where n.user_id = '{b.uid}' and n.kind like 'pet_%';""")
        assert off == [{"ok": False}]
        r = b.get(f"notification_prefs?select=pet_daily,pet_alerts,pet_gifts,pet_streaks&user_id=eq.{b.uid}")
        assert r.json() == [{"pet_daily": False, "pet_alerts": False, "pet_gifts": False, "pet_streaks": False}]
    finally:
        sql_test(f"""update public.notification_prefs set pet_daily = true, pet_alerts = true, pet_gifts = true,
                       pet_streaks = true where user_id = '{b.uid}';""")
    on = sql_test(f"""select n.kind, private.web_push_allowed(n) as ok from public.notifications n
                      where n.user_id = '{b.uid}' and n.kind in ('pet_gift', 'pet_streak') order by n.kind;""")
    assert on == [{"kind": "pet_gift", "ok": True}, {"kind": "pet_streak", "ok": True}]
    for kind in ("pet_daily", "pet_gift", "pet_streak"):
        assert sql_test(f"select private.may_receive_push('{b.uid}', '{kind}') as ok;") == [{"ok": True}]
