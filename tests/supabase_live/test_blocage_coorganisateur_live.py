"""Blocage contourné (Apple 1.2, migration 20261127110000) : un organisateur ne peut ni ajouter comme co-organisateur
(event_organizers) ni noter présent (set_rsvp_for) une personne qui l'a bloqué ou qu'il a bloquée, et les notifications
« coorganizer_added » / « rsvp_set » entre personnes bloquées sont jetées. Sans blocage : inchangé. Service (séries
récurrentes, auth.uid() null) : inchangé. Base de TEST, comptes neufs dans une transaction annulée à la fin."""
import pytest

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

O, B, C = (f"00000000-0000-4000-8000-00000000040{i}" for i in (1, 2, 3))


def run(direction: str) -> dict:
    """direction : « B a bloqué O » (b_blocks_o) ou « O a bloqué B » (o_blocks_b). Rend {étape: résultat}."""
    blocker, blocked = (B, O) if direction == "b_blocks_o" else (O, B)
    rows = sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at) values
  ('{O}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990401', now(), now()),
  ('{B}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990402', now(), now()),
  ('{C}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990403', now(), now());
set local session_replication_role = replica;
insert into public.profiles (id) values ('{O}'), ('{B}'), ('{C}') on conflict (id) do nothing;
update public.profiles set display_name = 'Bloc' || right(id::text, 1), first_name = 'Bloc', last_name = 'Test',
  role = 'member', status = 'active' where id in ('{O}', '{B}', '{C}');
insert into public.notification_prefs (user_id) values ('{O}'), ('{B}'), ('{C}') on conflict (user_id) do nothing;
update public.notification_prefs set invites = true where user_id in ('{O}', '{B}', '{C}');
insert into public.events (id, title, starts_at, created_by, status, visibility)
  values ('00000000-0000-4000-8000-000000000499', 'Soirée blocage', now() + interval '3 days', '{O}', 'published', 'all');
insert into public.direct_blocks (user_id, blocked_id) values ('{blocker}', '{blocked}');
set local session_replication_role = origin;
create temp table _r (k text, v text) on commit drop;
select set_config('request.jwt.claims', '{{"sub": "{O}", "role": "authenticated"}}', true);
do $s$
declare ev uuid := '00000000-0000-4000-8000-000000000499';
begin
  begin insert into public.event_organizers (event_id, user_id) values (ev, '{B}'); insert into _r values ('coorg_blocked', 'ok');
  exception when others then insert into _r values ('coorg_blocked', sqlerrm); end;
  begin perform public.set_rsvp_for(ev, '{B}', 'yes'); insert into _r values ('rsvp_blocked', 'ok');
  exception when others then insert into _r values ('rsvp_blocked', sqlerrm); end;
  begin insert into public.event_organizers (event_id, user_id) values (ev, '{C}'); insert into _r values ('coorg_free', 'ok');
  exception when others then insert into _r values ('coorg_free', sqlerrm); end;
  begin perform public.set_rsvp_for(ev, '{C}', 'yes'); insert into _r values ('rsvp_free', 'ok');
  exception when others then insert into _r values ('rsvp_free', sqlerrm); end;
  -- Notifications directes (autre chemin qui les créerait) : jetées entre personnes bloquées.
  perform public.queue_notification('{B}', 'coorganizer_added', ev, 'Co-organisateur', 'test');
  perform public.queue_notification('{B}', 'rsvp_set', ev, 'Soirée', 'test');
end $s$;
insert into _r select 'notif_B', coalesce(string_agg(kind, ',' order by kind), '') from public.notifications where user_id = '{B}';
insert into _r select 'notif_C', coalesce(string_agg(kind, ',' order by kind), '') from public.notifications where user_id = '{C}';
insert into _r select 'rsvp_B', coalesce((select status::text from public.rsvps where user_id = '{B}'), 'aucune');
select set_config('request.jwt.claims', '', true);
do $s$
begin
  insert into public.event_organizers (event_id, user_id) values ('00000000-0000-4000-8000-000000000499', '{B}');
  insert into _r values ('coorg_service', 'ok');
exception when others then insert into _r values ('coorg_service', sqlerrm);
end $s$;
select * from _r;
rollback;
""")
    return {r["k"]: r["v"] for r in rows}


@pytest.mark.parametrize("direction", ["b_blocks_o", "o_blocks_b"])
def test_a_blocked_person_is_never_made_coorganizer_nor_noted_present(direction):
    got = run(direction)
    assert got["coorg_blocked"].startswith("blocked:"), got
    assert got["rsvp_blocked"].startswith("blocked:"), got
    assert got["rsvp_B"] == "aucune", got
    assert got["notif_B"] == "", f"notification envoyée malgré le blocage : {got['notif_B']}"
    # Sans blocage : inchangé (ajout, présence notée, notifications).
    assert got["coorg_free"] == "ok" and got["rsvp_free"] == "ok", got
    assert "coorganizer_added" in got["notif_C"] and "rsvp_set" in got["notif_C"], got
    # Service (séries récurrentes, console) : pas de jeton, pas de refus.
    assert got["coorg_service"] == "ok", got
