"""Pot commun : chaque dépense dit si elle est À MOI (`mine` = created_by = moi, migration 20261128100000), pour que l'app
iPhone ne propose jamais « Signaler la dépense » sur la sienne (la base refuse « self »). Base de TEST, comptes neufs dans
une transaction annulée : O a créé une dépense payée par B → `mine` vrai pour O, faux pour B ; et la migration rejouée ne
change rien.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_depense_mienne_live.py -q"""
import json
import pathlib

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

MIGRATION = (pathlib.Path(__file__).parents[2] / 'supabase/migrations/20261128100000_depense_mienne.sql').read_text()
O, B = "00000000-0000-4000-8000-000000000611", "00000000-0000-4000-8000-000000000612"
G, X = "00000000-0000-4000-8000-000000000621", "00000000-0000-4000-8000-000000000631"


def jwt(uid: str) -> str:
    return f"""select set_config('request.jwt.claims', '{{"sub": "{uid}", "role": "authenticated"}}', true);"""


def test_each_expense_says_whether_it_is_mine():
    rows = sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at) values
  ('{O}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990611', now(), now()),
  ('{B}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990612', now(), now());
set local session_replication_role = replica;
insert into public.profiles (id) values ('{O}'), ('{B}') on conflict (id) do nothing;
insert into public.tc_groups (id, name, created_by) values ('{G}', 'Pot test', '{O}');
insert into public.tc_members (group_id, user_id, name) values ('{G}', '{O}', 'Orga'), ('{G}', '{B}', 'Payeur');
insert into public.tc_expenses (id, group_id, title, amount_cents, paid_by, created_by)
  select '{X}', '{G}', 'Courses', 3000, m.id, '{O}' from public.tc_members m where m.group_id = '{G}' and m.user_id = '{B}';
set local session_replication_role = origin;
create temp table _r (k text, v text) on commit drop;
{jwt(O)} insert into _r select 'o', private.tc_group_json('{G}')::text;
{jwt(B)} insert into _r select 'b', private.tc_group_json('{G}')::text;
create temp table _d on commit drop as select pg_get_functiondef('private.tc_group_json(uuid)'::regprocedure) d;
{MIGRATION}
insert into _r select 'replay_changed', (pg_get_functiondef('private.tc_group_json(uuid)'::regprocedure) <> d)::text from _d;
select * from _r;
rollback;
""")
    got = {r["k"]: r["v"] for r in rows}
    exp = {k: json.loads(got[k])["expenses"][0] for k in "ob"}
    assert exp["o"]["mine"] is True and exp["b"]["mine"] is False, exp
    assert exp["o"]["paid_by"] == exp["b"]["paid_by"]
    assert got["replay_changed"] == "false", got
