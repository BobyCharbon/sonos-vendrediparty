"""Blocage, suite (Apple 1.2, migration 20261127120000), base de TEST, comptes neufs dans une transaction annulée à la fin :
1. un co-organisateur tiers ne peut pas ajouter une personne en blocage avec le CRÉATEUR (service : inchangé) ;
2. bloquer retire chacun des co-organisateurs des événements créés par l'autre (créateur et événements tiers intacts) ;
3. join_group_by_link refusé en blocage avec le créateur du groupe ou l'auteur du lien (lien jamais consommé) ;
4. join_event_by_link refusé en blocage avec l'organisateur ou l'auteur du lien (ni invitation ni lien consommé) ;
5. « prénom, surnom et photo) » disparaît des messages (la migration, rejouée, le retire d'une fonction qui l'a encore)."""
import pathlib

import pytest

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

MIGRATION = (pathlib.Path(__file__).parents[2] / 'supabase/migrations/20261127120000_blocage_suite.sql').read_text()
O, B, C, D = (f"00000000-0000-4000-8000-00000000050{i}" for i in (1, 2, 3, 4))
E1, E2, E3, E4 = (f"00000000-0000-4000-8000-00000000059{i}" for i in (1, 2, 3, 4))
G1, G2 = "00000000-0000-4000-8000-000000000581", "00000000-0000-4000-8000-000000000582"
T1, T2 = "00000000-0000-4000-8000-000000000571", "00000000-0000-4000-8000-000000000572"  # liens des groupes
L1, L2, L3 = (f"00000000-0000-4000-8000-00000000056{i}" for i in (1, 2, 3))  # liens uniques


def jwt(uid: str) -> str:
    return f"""select set_config('request.jwt.claims', '{{"sub": "{uid}", "role": "authenticated"}}', true);"""


def attempt(key: str, stmt: str) -> str:
    return f"""do $s$ begin {stmt}; insert into _r values ('{key}', 'ok');
exception when others then insert into _r values ('{key}', sqlerrm); end $s$;"""


def run(direction: str) -> dict:
    """direction : « B a bloqué O » (b_blocks_o) ou « O a bloqué B » (o_blocks_b)."""
    blocker, blocked = (B, O) if direction == "b_blocks_o" else (O, B)
    users = ", ".join(f"('{u}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '4179999050{i}', now(), now())"
                      for i, u in enumerate((O, B, C, D), 1))
    rows = sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at) values {users};
set local session_replication_role = replica;
insert into public.profiles (id) values ('{O}'), ('{B}'), ('{C}'), ('{D}') on conflict (id) do nothing;
update public.profiles set display_name = 'Suite' || right(id::text, 1), first_name = 'Suite', last_name = 'Test',
  role = 'member', status = 'active' where id in ('{O}', '{B}', '{C}', '{D}');
insert into public.events (id, title, starts_at, created_by, status, visibility) values
  ('{E1}', 'Soirée de O', now() + interval '3 days', '{O}', 'published', 'invited'),
  ('{E2}', 'Soirée de B', now() + interval '3 days', '{B}', 'published', 'invited'),
  ('{E3}', 'Soirée de C', now() + interval '3 days', '{C}', 'published', 'invited'),
  ('{E4}', 'Autre soirée de C', now() + interval '3 days', '{C}', 'published', 'invited');
insert into public.event_organizers (event_id, user_id) values ('{E1}', '{B}'), ('{E1}', '{C}'), ('{E2}', '{O}'),
  ('{E3}', '{B}'), ('{E3}', '{O}');
insert into public.member_groups (id, name, created_by, invite_token, invite_token_by) values
  ('{G1}', 'Groupe de O', '{O}', '{T1}', '{O}'), ('{G2}', 'Groupe de C', '{C}', '{T2}', '{O}');
insert into public.member_group_members (group_id, user_id) values ('{G1}', '{O}'), ('{G2}', '{C}'), ('{G2}', '{O}');
insert into private.invite_links (token, kind, target, created_by) values
  ('{L1}', 'event', '{E1}', '{C}'), ('{L2}', 'group', '{G1}', '{C}'), ('{L3}', 'event', '{E4}', '{O}');
set local session_replication_role = origin;
create temp table _r (k text, v text) on commit drop;

-- 2. Le blocage, par la fonction de l'app.
{jwt(blocker)}
select public.set_direct_block('{blocked}', true);
insert into _r select 'orgs', string_agg(right(event_id::text, 1) || ':' || right(user_id::text, 1), ',' order by 1)
  from public.event_organizers where event_id in ('{E1}', '{E2}', '{E3}');

-- 1. C, co-organisateur de E1, ne peut pas y ajouter B (en blocage avec O, le créateur) ; D, oui.
{jwt(C)}
{attempt('coorg_blocked', f"insert into public.event_organizers (event_id, user_id) values ('{E1}', '{B}')")}
{attempt('coorg_free', f"insert into public.event_organizers (event_id, user_id) values ('{E1}', '{D}')")}

-- 3. Groupes : B ne rejoint ni le groupe de O (lien du groupe ou lien unique de C), ni celui de C par le lien de O.
{jwt(B)}
{attempt('group_token', f"perform public.join_group_by_link('{T1}')")}
{attempt('group_single', f"perform public.join_group_by_link('{L2}')")}
{attempt('group_author', f"perform public.join_group_by_link('{T2}')")}
-- 4. Événements : ni E1 (organisateur O) par le lien de C, ni E4 (de C) par le lien de O.
{attempt('event_creator', f"perform public.join_event_by_link('{L1}')")}
{attempt('event_author', f"perform public.join_event_by_link('{L3}')")}
insert into _r select 'b_left', count(*)::text from public.event_invites where user_id = '{B}';
insert into _r select 'b_groups', count(*)::text from public.member_group_members where user_id = '{B}';
insert into _r select 'links_used', count(*)::text from private.invite_links where token in ('{L1}', '{L2}', '{L3}') and used_by is not null;
-- Sans blocage : D entre.
{jwt(D)}
{attempt('group_free', f"perform public.join_group_by_link('{T1}')")}
{attempt('event_free', f"perform public.join_event_by_link('{L1}')")}

-- Service (séries récurrentes) : pas de jeton, pas de refus.
select set_config('request.jwt.claims', '', true);
{attempt('coorg_service', f"insert into public.event_organizers (event_id, user_id) values ('{E1}', '{B}')")}

-- 5. Une fonction qui cite encore la photo : la migration, rejouée, la corrige (et ne casse rien de déjà fait).
create function public._t_photo_msg() returns text language sql
  as $f$ select 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) avant de rejoindre'::text $f$;
{MIGRATION}
insert into _r select 'photo_fixed', public._t_photo_msg();
insert into _r select 'photo_left', count(*)::text from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname in ('public', 'private') and p.prosrc like '%surnom et photo%';
select * from _r;
rollback;
""")
    return {r["k"]: r["v"] for r in rows}


@pytest.mark.parametrize("direction", ["b_blocks_o", "o_blocks_b"])
def test_blocking_follows_coorganizers_group_and_event_links(direction):
    got = run(direction)
    # 2. B quitte E1 (créé par O), O quitte E2 (créé par B) ; C reste sur E1 ; E3 (de C) garde B et O.
    assert sorted(got["orgs"].split(",")) == ["1:3", "3:1", "3:2"], got
    # 1. Co-organisateur tiers : refusé pour B, permis pour D ; service : inchangé.
    assert got["coorg_blocked"].startswith("blocked:"), got
    assert got["coorg_free"] == "ok" and got["coorg_service"] == "ok", got
    # 3 et 4. Refus neutres (jamais qui a bloqué), rien d'enregistré ni de consommé.
    for k in ("group_token", "group_single", "group_author"):
        assert got[k] == "Tu ne peux pas rejoindre ce groupe.", (k, got)
    for k in ("event_creator", "event_author"):
        assert got[k] == "Tu ne peux pas répondre à cette invitation.", (k, got)
    assert got["b_left"] == "0" and got["b_groups"] == "0" and got["links_used"] == "0", got
    assert got["group_free"] == "ok" and got["event_free"] == "ok", got
    # 5. La photo n'est plus demandée nulle part.
    assert got["photo_fixed"] == "profile_incomplete: complète ton profil (nom, prénom et surnom) avant de rejoindre", got
    assert got["photo_left"] == "0", got
