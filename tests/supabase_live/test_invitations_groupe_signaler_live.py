"""Invitations de groupe reçues (migration 20261128110000, contrôle Apple 1.2) : une invitation d'une personne en blocage
avec moi (qui invite ou créateur du groupe) n'est jamais affichée ; l'invité peut « Signaler » le groupe (report_content
type `group`), un inconnu non. Retour arrière essayé (définitions d'origine), puis migration rejouée. Base de TEST, comptes
neufs dans une transaction annulée.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_invitations_groupe_signaler_live.py -q"""
import json
import pathlib
import re

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

ROOT = pathlib.Path(__file__).parents[2]
MIGRATION = (ROOT / 'supabase/migrations/20261128110000_invitations_groupe_signaler.sql').read_text()
ROLLBACK = re.sub(r'(?m)^(begin|commit);$', '', (ROOT / 'supabase/prod/2026-11-28-invitations-groupe-signaler-rollback.sql').read_text())
O, B, C, D = (f"00000000-0000-4000-8000-0000000007{n}" for n in ("11", "12", "13", "14"))
G, H = "00000000-0000-4000-8000-000000000721", "00000000-0000-4000-8000-000000000722"
FUNCS = "pg_get_functiondef('public.my_group_invitations()'::regprocedure) || pg_get_functiondef('private.group_report_snapshot(uuid,uuid)'::regprocedure)"


def jwt(uid: str) -> str:
    return f"""select set_config('request.jwt.claims', '{{"sub": "{uid}", "role": "authenticated"}}', true);"""


def report(uid: str, key: str) -> str:
    return f"""{jwt(uid)}
do $t$ begin
  perform public.report_content('group', '{G}', 'spam');
  insert into _r values ('{key}', 'ok');
exception when others then insert into _r values ('{key}', sqlerrm);
end $t$;"""


def test_blocked_invitation_hidden_and_invitee_may_report_the_group():
    rows = sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at) values
  ('{O}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990711', now(), now()),
  ('{B}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990712', now(), now()),
  ('{C}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990713', now(), now()),
  ('{D}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990714', now(), now());
set local session_replication_role = replica;
insert into public.profiles (id, display_name, status) values ('{O}', 'Orga', 'active'), ('{B}', 'Invité', 'active'),
  ('{C}', 'Inconnu', 'active'), ('{D}', 'Autre', 'active')
  on conflict (id) do update set display_name = excluded.display_name, status = 'active';
insert into public.member_groups (id, name, created_by) values ('{G}', 'Groupe test', '{O}'), ('{H}', 'Groupe de D', '{D}');
insert into private.group_invitations (group_id, user_id, invited_by) values ('{G}', '{B}', '{O}'), ('{H}', '{B}', '{C}');
set local session_replication_role = origin;
create temp table _r (k text, v text) on commit drop;
create temp table _d on commit drop as select {FUNCS} d;
{jwt(B)} insert into _r select 'before', public.my_group_invitations()::text;
{report(B, 'invitee')}
{report(C, 'stranger')}
insert into public.direct_blocks (user_id, blocked_id) values ('{O}', '{B}');
{jwt(B)} insert into _r select 'blocked_inviter', public.my_group_invitations()::text;
insert into public.direct_blocks (user_id, blocked_id) values ('{B}', '{D}');
{jwt(B)} insert into _r select 'blocked', public.my_group_invitations()::text;
{ROLLBACK}
insert into _r select 'rollback_restores', (position('20261128110000' in {FUNCS}) = 0)::text;
{jwt(B)} insert into _r select 'blocked_after_rollback', public.my_group_invitations()::text;
{MIGRATION}
{MIGRATION}
insert into _r select 'replay_same', ({FUNCS} = d)::text from _d;
select * from _r;
rollback;
""")
    got = {r["k"]: r["v"] for r in rows}
    assert {i["group_id"] for i in json.loads(got["before"])} == {G, H}, got
    assert got["invitee"] == "ok", got
    assert "not_found" in got["stranger"], got
    # O (qui invite, créateur de G) me bloque : plus l'invitation à G ; je bloque D (créateur de H, invitation de C) : plus rien.
    assert [i["group_id"] for i in json.loads(got["blocked_inviter"])] == [H], got
    assert json.loads(got["blocked"]) == [], got
    assert got["rollback_restores"] == "true", got
    assert len(json.loads(got["blocked_after_rollback"])) == 2, got
    assert got["replay_same"] == "true", got
