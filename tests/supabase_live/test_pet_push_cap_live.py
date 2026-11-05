"""Plafond des notifications Zicou sur la VRAIE base de test (migration 20261105170000, jamais la prod) : au plus 2 par
jour et par compte, toutes sortes confondues (cadeau d'ami, alertes « très faim », rappel du jour, barre pleine), la
barre jamais après le rappel du jour, priorité cadeau d'ami > très faim > rappel > barre.

Comptes : Testeur 3 (reçoit) et Testeur 1 (offre le cadeau, ligne écrite directement dans pet_gifts). Le compagnon de
Testeur 3, ses cadeaux reçus et ses notifications pet_* sont effacés avant et après : aucun vrai membre n'est notifié."""
import json

import pytest

from tests.supabase_live.test_member_admin_live import GUESTS, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_pet_live import fresh, pet_cron, save, sql_test

NUDGE = {"day": "2026-11-05", "minute": 600, "kind": "pet_daily", "title": "Zicou", "body": "Coucou 🎁",
         "alt_title": "Zicou", "alt_body": "Le coffre du jour brille sous mon lit 🎁"}


def wipe(uid: str) -> None:
    sql_test(f"""delete from public.pets where user_id = '{uid}';
      delete from public.pet_gifts where to_user = '{uid}';
      delete from public.notifications where user_id = '{uid}' and kind like 'pet\\_%';
      update public.notification_prefs set pet_bar = true, pet_daily = true, pet_gifts = true, muted_until = null
       where user_id = '{uid}';""")


@pytest.fixture(scope="module")
def pair():
    c, giver = Session(GUESTS[2]), Session(GUESTS[0])
    wipe(c.uid)
    life, owner = fresh()
    assert save(c, life, owner, 0).status_code == 200
    yield c, giver
    wipe(c.uid)


def reset(c, *, bar_full_at="null", dies_at="null", minute=600):
    nudge = json.dumps({**NUDGE, "minute": minute}, ensure_ascii=False).replace("'", "''")
    sql_test(f"""update public.pets set stage = 'baby', name = 'Zicou', last_seen_at = null, daily_sent_on = null,
                   gifts_noted_at = now(), alerts_sent = '{{}}', nudge = '{nudge}'::jsonb, dies_at = {dies_at},
                   bar_full_at = {bar_full_at}, bar_notified_for = null, bar_sent_on = null, bar_sent_n = 0,
                   push_on = null, push_n = 0
                 where user_id = '{c.uid}';
                 delete from public.pet_gifts where to_user = '{c.uid}';
                 delete from public.notifications where user_id = '{c.uid}' and kind like 'pet\\_%';""")


def kinds(c) -> list[str]:
    return [r["kind"] for r in sql_test(f"""select kind from public.notifications
                                            where user_id = '{c.uid}' and kind like 'pet\\_%' order by created_at, kind;""")]


def run(c, at: str) -> None:
    """Un passage des deux tâches (comme pg_cron toutes les 10 minutes), le rappel d'abord."""
    pet_cron(f"private.pet_notify('2026-11-05 {at}+01')", c.uid)
    pet_cron(f"private.pet_bar_notify('2026-11-05 {at}+01')", c.uid)


def test_the_bar_never_goes_once_the_daily_reminder_went(pair):
    c, _ = pair
    reset(c, bar_full_at="'2026-11-05 10:30+01'")
    pet_cron("private.pet_notify('2026-11-05 10:20+01')", c.uid)   # rappel à 10 h 00 (heure apprise)
    pet_cron("private.pet_bar_notify('2026-11-05 10:40+01')", c.uid)
    assert kinds(c) == ["pet_daily"]


def test_bar_then_reminder_then_nothing_more_that_day(pair):
    c, _ = pair
    reset(c, bar_full_at="'2026-11-05 09:30+01'", minute=1080)
    run(c, "09:40")
    assert kinds(c) == ["pet_bar"]
    sql_test(f"update public.pets set bar_full_at = '2026-11-05 12:10+01' where user_id = '{c.uid}';")
    run(c, "12:20")
    assert kinds(c) == ["pet_bar"]   # une seule barre : elle ne prend jamais la dernière place
    run(c, "18:05")
    assert kinds(c) == ["pet_bar", "pet_daily"]
    # Un repas oublié : l'alerte « très faim » attend le lendemain (plafond atteint).
    sql_test(f"update public.pets set dies_at = '2026-11-07 12:00+01' where user_id = '{c.uid}';")
    run(c, "19:00")
    assert kinds(c) == ["pet_bar", "pet_daily"]
    pet_cron("private.pet_notify('2026-11-06 09:00+01')", c.uid)
    assert kinds(c) == ["pet_bar", "pet_daily", "pet_alert"]


def test_a_friends_gift_and_the_hunger_alert_fill_the_day(pair):
    c, giver = pair
    reset(c, bar_full_at="'2026-11-05 10:30+01'", dies_at="'2026-11-06 20:00+01'", minute=1080)
    sql_test(f"""update public.pets set gifts_noted_at = '2026-11-05 09:00+01' where user_id = '{c.uid}';
      insert into public.pet_gifts (from_user, to_user, kind, day, created_at)
      values ('{giver.uid}', '{c.uid}', 'hug', '2026-11-05', '2026-11-05 09:30+01');""")
    run(c, "10:40")   # même passage : le cadeau d'ami, puis l'alerte « très faim » ; la barre n'a plus de place
    assert sorted(kinds(c)) == ["pet_alert", "pet_gift"]
    run(c, "18:05")
    assert sorted(kinds(c)) == ["pet_alert", "pet_gift"]   # rien de plus aujourd'hui


def test_with_a_hunger_alert_coming_the_reminder_keeps_its_place(pair):
    c, _ = pair
    reset(c, bar_full_at="'2026-11-05 09:30+01'", dies_at="'2026-11-06 07:00+01'", minute=1080)
    sql_test(f"update public.pets set alerts_sent = array[gen || ':48'] where user_id = '{c.uid}';")   # déjà eue hier
    run(c, "09:40")
    assert kinds(c) == ["pet_bar"]
    run(c, "18:05")   # envol dans moins de 48 h : le rappel ne prend pas la dernière place
    assert kinds(c) == ["pet_bar"]
    run(c, "19:05")   # 12 h avant l'envol : l'alerte vitale, elle, l'a
    assert kinds(c) == ["pet_bar", "pet_alert"]


def test_the_vital_alert_always_goes_even_after_two(pair):
    """Seule exception au plafond (décision de l'admin) : « a besoin de toi », 12 h avant l'envol, une fois par envol."""
    c, giver = pair
    reset(c, dies_at="'2026-11-06 06:00+01'", minute=1080)
    sql_test(f"""update public.pets set gifts_noted_at = '2026-11-05 09:00+01' where user_id = '{c.uid}';
      insert into public.pet_gifts (from_user, to_user, kind, day, created_at)
      values ('{giver.uid}', '{c.uid}', 'hug', '2026-11-05', '2026-11-05 09:30+01');""")
    run(c, "10:40")   # le cadeau d'ami et l'alerte « très faim » (48 h) : plafond atteint
    assert sorted(kinds(c)) == ["pet_alert", "pet_gift"]
    run(c, "18:10")   # moins de 12 h avant l'envol : l'alerte vitale passe quand même
    rows = sql_test(f"""select title from public.notifications where user_id = '{c.uid}' and kind = 'pet_alert'
                        order by created_at;""")
    assert [r["title"] for r in rows] == ["Zicou a très faim", "Zicou a besoin de toi"]
    run(c, "18:20")
    assert len(kinds(c)) == 3   # une seule fois par envol
