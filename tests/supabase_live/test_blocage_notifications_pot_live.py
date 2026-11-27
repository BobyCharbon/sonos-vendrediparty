"""Blocage et notifications d'un événement, Signaler dans le Pot commun (migration 20261127150000), base de TEST, comptes
neufs dans une transaction annulée à la fin, dans les deux sens du blocage :
1. drop_blocked_notification : sans session (pg_cron), ce qui vient de O ou annonce son événement (nouvel événement,
   rappel, changement, sondage, date, invitation) ne parvient jamais à B, en blocage avec O ; ce qui sert à qui participe
   encore (message d'un autre, verre servi, paiement, souvenirs, modération) arrive ; un tiers reçoit tout ;
2. report_content 'tc_group' (nom du pot, propriétaire = créateur) et 'tc_member' (prénom d'un membre, sans propriétaire :
   tout membre renomme tout membre) : par un membre du pot seulement, jamais par un inconnu ; « Masquer » remplace le nom et le prénom ; les autres types restent permis ;
3. la migration, rejouée, ne change plus rien.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_blocage_notifications_pot_live.py -q"""
import pathlib

import pytest

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

MIGRATION = (pathlib.Path(__file__).parents[2] / 'supabase/migrations/20261127150000_blocage_notifications_pot.sql').read_text()
O, B, C, D = (f"00000000-0000-4000-8000-00000000070{i}" for i in (1, 2, 3, 4))
E1 = "00000000-0000-4000-8000-000000000791"
G = "00000000-0000-4000-8000-000000000781"
MO, MC = "00000000-0000-4000-8000-000000000771", "00000000-0000-4000-8000-000000000773"
DROPPED = ("new_event", "reminder", "event_changed", "poll_new", "date_fixed", "private_invite")
KEPT = ("message", "bar_served", "ticket_pay_confirmed", "souvenirs_revealed", "moderation_notice")
KINDS = DROPPED + KEPT


def jwt(uid: str) -> str:
    return f"""select set_config('request.jwt.claims', '{{"sub": "{uid}", "role": "authenticated"}}', true);"""


def attempt(key: str, stmt: str) -> str:
    return f"""do $s$ begin {stmt}; insert into _r values ('{key}', 'ok');
exception when others then insert into _r values ('{key}', sqlerrm); end $s$;"""


def run(direction: str) -> dict:
    blocker, blocked = (B, O) if direction == "b_blocks_o" else (O, B)
    users = ", ".join(f"('{u}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '4179999070{i}', now(), now())"
                      for i, u in enumerate((O, B, C, D), 1))
    names = {O: 'Orga', B: 'Bloqué', C: 'Tiers', D: 'Inconnu'}
    queue = "".join(f"perform public.queue_notification('{u}', '{k}', '{E1}', 'Titre', 'Texte', null);"
                    for u in (B, C) for k in KINDS)
    rows = sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at) values {users};
set local session_replication_role = replica;
insert into public.profiles (id) values ('{O}'), ('{B}'), ('{C}'), ('{D}') on conflict (id) do nothing;
{''.join(f"update public.profiles set display_name = '{n}', first_name = '{n}', last_name = 'Test', role = 'member', status = 'active' where id = '{u}';" for u, n in names.items())}
insert into public.events (id, title, starts_at, created_by, status, visibility) values
  ('{E1}', 'Soirée de O', now() + interval '3 days', '{O}', 'published', 'invited');
insert into public.direct_blocks (user_id, blocked_id) values ('{blocker}', '{blocked}');
insert into public.tc_groups (id, name, emoji, currency, created_by) values ('{G}', 'Pot de O', '🎉', 'CHF', '{O}');
insert into public.tc_members (id, group_id, user_id, name) values ('{MO}', '{G}', '{O}', 'Orga'), ('{MC}', '{G}', '{C}', 'Tiers');
set local session_replication_role = origin;
create temp table _r (k text, v text) on commit drop;
grant all on _r to authenticated;

-- 1. Envoi sans session (comme pg_cron) : B ne reçoit rien de l'événement de O, sauf la modération ; C reçoit tout.
select set_config('request.jwt.claims', '', true);
do $q$ begin {queue} end $q$;
insert into _r select 'notif_' || case user_id when '{B}' then 'b' else 'c' end, string_agg(kind, ',' order by kind)
  from public.notifications where event_id = '{E1}' and user_id in ('{B}', '{C}') group by user_id;

-- 2. Signaler le nom du pot et un prénom.
{jwt(C)}
{attempt('c_group', f"perform public.report_content('tc_group', '{G}', 'shocking')")}
{attempt('c_member', f"perform public.report_content('tc_member', '{MO}', 'harassment')")}
{attempt('c_self', f"perform public.report_content('tc_member', '{MC}', 'spam')")}
{jwt(D)}
{attempt('d_group', f"perform public.report_content('tc_group', '{G}', 'spam')")}
{attempt('d_member', f"perform public.report_content('tc_member', '{MO}', 'spam')")}
select set_config('request.jwt.claims', '', true);
insert into _r select 'kinds', string_agg(target_kind || ':' || coalesce(target_user::text, '-'), ',' order by target_kind)
  from public.content_reports where reporter_id = '{C}';
select private.moderation_hide(r), private.notify_content_hidden(r) from public.content_reports r where r.reporter_id = '{C}';
insert into _r select 'pot_name', name from public.tc_groups where id = '{G}';
insert into _r select 'member_name', name from public.tc_members where id = '{MO}';
insert into _r select 'hidden_notice', string_agg(body, ' | ') from public.notifications
  where user_id = '{O}' and kind = 'content_hidden';
insert into _r select 'old_kind', count(*)::text from (select 1) x
  where exists (select 1 from pg_constraint where conname = 'content_reports_target_kind_check'
                and pg_get_constraintdef(oid) like '%''pet_word''%' and pg_get_constraintdef(oid) like '%''tc_member''%');

-- 3. Rejouée : sans effet.
create temp table _d on commit drop as select p.oid, pg_get_functiondef(p.oid) d from pg_proc p
  where p.proname in ('drop_blocked_notification', 'report_snapshot', 'moderation_hide', 'notify_new_report',
                      'notify_content_hidden', 'tc_group_report_snapshot', 'tc_member_report_snapshot');
create temp table _c on commit drop as select pg_get_constraintdef(oid) c from pg_constraint
  where conname = 'content_reports_target_kind_check';
{MIGRATION}
insert into _r select 'replay_changed', count(*)::text from _d where pg_get_functiondef(_d.oid) <> _d.d;
insert into _r select 'replay_constraint', count(*)::text from _c
  where c <> (select pg_get_constraintdef(oid) from pg_constraint where conname = 'content_reports_target_kind_check');
select * from _r;
rollback;
""")
    return {r["k"]: r["v"] for r in rows}


@pytest.mark.parametrize("direction", ["b_blocks_o", "o_blocks_b"])
def test_blocked_person_gets_no_notification_of_the_event_and_pot_names_can_be_reported(direction):
    got = run(direction)
    # 1. Jeté : ce qui vient de O ; gardé : ce qui sert à qui participe (pg_cron compris) ; C reçoit tout.
    assert got.get("notif_b") == ",".join(sorted(KEPT)), got
    assert got["notif_c"] == ",".join(sorted(KINDS)), got
    # 2. Membre du pot : nom du pot et prénom d'un autre ; jamais son propre prénom ; un inconnu : rien.
    assert got["c_group"] == "ok" and got["c_member"] == "ok", got
    assert got["c_self"] == "ok", got  # son prénom, peut-être écrit par un autre
    assert got["d_group"].startswith("not_found:") and got["d_member"].startswith("not_found:"), got
    assert got["kinds"] == f"tc_group:{O},tc_member:-,tc_member:-", got
    assert got["pot_name"] == "Pot renommé par la modération" and got["member_name"] == "Prénom masqué", got
    assert "Pot commun" in got["hidden_notice"] and "prénom" not in got["hidden_notice"], got
    assert got["old_kind"] == "1", got
    # 3. Rejouée : rien ne change.
    assert got["replay_changed"] == "0" and got["replay_constraint"] == "0", got
