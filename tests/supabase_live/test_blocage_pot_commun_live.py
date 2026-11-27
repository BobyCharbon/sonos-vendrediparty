"""Blocage dans le Pot commun et le résumé des réponses (Apple 1.2, migration 20261127140000), base de TEST, comptes neufs
dans une transaction annulée à la fin, dans les deux sens du blocage :
1. tc_group_json : l'autre s'appelle « Personne bloquée », sans moyens de paiement ; ses dépenses : titre vide, ni note ni
   ticket ; montants, payeur et parts identiques ; un tiers voit tout ; tc_join_info : même nom caché ;
2. tc_save_expense : on ne modifie pas la dépense de l'autre ; RLS de tc_payment : rien de l'autre ;
3. tc_event_sync : un « Présent » en blocage avec le créateur du pot n'est pas ajouté d'office, les autres oui ;
4. flush_rsvp_digests : la réponse de la personne bloquée n'entre pas dans le résumé de l'organisateur ; seule réponse : rien ;
5. la migration, rejouée, ne change plus rien.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_blocage_pot_commun_live.py -q"""
import json
import pathlib

import pytest

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

MIGRATION = (pathlib.Path(__file__).parents[2] / 'supabase/migrations/20261127140000_blocage_pot_commun.sql').read_text()
O, B, C = (f"00000000-0000-4000-8000-00000000060{i}" for i in (1, 2, 3))
E1, E2 = "00000000-0000-4000-8000-000000000691", "00000000-0000-4000-8000-000000000692"
X1, X2 = "00000000-0000-4000-8000-000000000681", "00000000-0000-4000-8000-000000000682"  # dépenses de O et de B


def jwt(uid: str) -> str:
    return f"""select set_config('request.jwt.claims', '{{"sub": "{uid}", "role": "authenticated"}}', true);"""


def attempt(key: str, stmt: str) -> str:
    return f"""do $s$ begin {stmt}; insert into _r values ('{key}', 'ok');
exception when others then insert into _r values ('{key}', sqlerrm); end $s$;"""


def run(direction: str) -> dict:
    blocker, blocked = (B, O) if direction == "b_blocks_o" else (O, B)
    users = ", ".join(f"('{u}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '4179999060{i}', now(), now())"
                      for i, u in enumerate((O, B, C), 1))
    names = {O: 'Orga', B: 'Bloqué', C: 'Tiers'}
    rows = sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at) values {users};
set local session_replication_role = replica;
insert into public.profiles (id) values ('{O}'), ('{B}'), ('{C}') on conflict (id) do nothing;
{''.join(f"update public.profiles set display_name = '{n}', first_name = '{n}', last_name = 'Test', role = 'member', status = 'active' where id = '{u}';" for u, n in names.items())}
insert into public.events (id, title, starts_at, created_by, status, visibility, pot_enabled) values
  ('{E1}', 'Soirée pot', now() + interval '3 days', '{O}', 'published', 'invited', true),
  ('{E2}', 'Soirée seule', now() + interval '3 days', '{O}', 'published', 'invited', false);
insert into public.rsvps (event_id, user_id, status) values ('{E1}', '{B}', 'yes'), ('{E1}', '{C}', 'yes');
insert into public.notification_prefs (user_id, rsvp_mine) values ('{O}', true)
  on conflict (user_id) do update set rsvp_mine = true;
insert into public.tc_payment (user_id, iban, holder) values ('{O}', 'CH9300762011623852957', 'Orga Test'),
  ('{B}', 'CH5604835012345678009', 'Bloqué Test') on conflict (user_id) do nothing;
insert into public.direct_blocks (user_id, blocked_id) values ('{blocker}', '{blocked}');
update private.moderation_settings set terms_enforced = false where id = 1;  -- annulé avec la transaction
set local session_replication_role = origin;
create temp table _r (k text, v text) on commit drop;
grant all on _r to authenticated;

-- 3. Le pot de l'événement : O (créateur) et C ; B, en blocage avec O, n'est pas ajouté d'office.
select private.tc_event_sync('{E1}');
insert into _r select 'synced', string_agg(m.name, ',' order by m.name)
  from public.tc_members m join public.tc_groups g on g.id = m.group_id where g.event_id = '{E1}';
-- B était déjà dans le pot avant le blocage (avec ses moyens de paiement montrés et une dépense).
set local session_replication_role = replica;
insert into public.tc_members (group_id, user_id, name, show_payment)
  select id, '{B}', 'Bloqué', true from public.tc_groups where event_id = '{E1}';
insert into public.tc_expenses (id, group_id, title, amount_cents, paid_by, note, receipt_path, created_by)
  select '{X1}', g.id, 'Courses de O', 3000, (select m.id from public.tc_members m where m.group_id = g.id and m.user_id = '{O}'),
         'note de O', 'ticket-o.jpg', '{O}' from public.tc_groups g where g.event_id = '{E1}';
insert into public.tc_expenses (id, group_id, title, amount_cents, paid_by, note, receipt_path, created_by)
  select '{X2}', g.id, 'Courses de B', 4500, (select m.id from public.tc_members m where m.group_id = g.id and m.user_id = '{B}'),
         'note de B', 'ticket-b.jpg', '{B}' from public.tc_groups g where g.event_id = '{E1}';
insert into public.tc_shares (expense_id, member_id, weight)
  select x.id, m.id, 1 from public.tc_expenses x join public.tc_members m on m.group_id = x.group_id where x.id in ('{X1}', '{X2}');
update public.tc_members set show_payment = true where group_id = (select id from public.tc_groups where event_id = '{E1}');
set local session_replication_role = origin;

-- 1. Ce que chacun voit du pot.
{''.join(f"{jwt(u)} insert into _r select 'pot_{k}', private.tc_group_json((select id from public.tc_groups where event_id = '{E1}'))::text;"
         f" insert into _r select 'join_{k}', public.tc_join_info((select join_token from public.tc_groups where event_id = '{E1}'))::text;"
         for k, u in (('o', O), ('b', B), ('c', C)))}

-- 2. O ne modifie pas la dépense de B (ni B celle de O) ; C, oui. Lecture directe des moyens de paiement.
{jwt(O)}
{attempt('save_o', f"perform public.tc_save_expense((select group_id from public.tc_expenses where id = '{X2}'), jsonb_build_object('id', '{X2}', 'title', 'Écrasé', 'amount_cents', 4500, 'paid_by', (select paid_by from public.tc_expenses where id = '{X2}'), 'shares', jsonb_build_array(jsonb_build_object('member_id', (select paid_by from public.tc_expenses where id = '{X2}')))))")}
set local role authenticated;
insert into _r select 'rls_o', count(*)::text from public.tc_payment where user_id = '{B}';
reset role;
{jwt(C)}
set local role authenticated;
insert into _r select 'rls_c', count(*)::text from public.tc_payment where user_id = '{B}';
reset role;
insert into _r select 'title_x2', title from public.tc_expenses where id = '{X2}';

-- 4. Résumé des réponses : B et C sur E1, B seul sur E2.
select set_config('request.jwt.claims', '', true);
delete from private.rsvp_digest where event_id in ('{E1}', '{E2}');
insert into private.rsvp_digest (event_id, user_id, status, first_at, updated_at) values
  ('{E1}', '{B}', 'yes', now() - interval '10 minutes', now() - interval '10 minutes'),
  ('{E1}', '{C}', 'yes', now() - interval '9 minutes', now() - interval '9 minutes'),
  ('{E2}', '{B}', 'yes', now() - interval '10 minutes', now() - interval '10 minutes');
select private.flush_rsvp_digests();
insert into _r select 'digest_' || right(event_id::text, 1), body from public.notifications
  where user_id = '{O}' and kind = 'rsvp' and event_id in ('{E1}', '{E2}');

-- 5. Rejouée : sans effet.
create temp table _d on commit drop as select p.oid, pg_get_functiondef(p.oid) d from pg_proc p
  where p.proname in ('tc_group_json', 'tc_join_info', 'tc_save_expense', 'tc_event_sync', 'flush_rsvp_digests');
{MIGRATION}
insert into _r select 'replay_changed', count(*)::text from _d where pg_get_functiondef(_d.oid) <> _d.d;
select * from _r;
rollback;
""")
    return {r["k"]: r["v"] for r in rows}


def members(pot: dict) -> dict:
    return {m["name"]: m for m in pot["members"]}


@pytest.mark.parametrize("direction", ["b_blocks_o", "o_blocks_b"])
def test_blocking_hides_each_other_in_the_pot_and_the_rsvp_digest(direction):
    got = run(direction)
    assert got["synced"] == "Orga,Tiers", got  # 3. B pas ajouté d'office
    pot_o, pot_b, pot_c = (json.loads(got[f"pot_{k}"]) for k in "obc")
    # 1. O ne voit de B ni le nom ni les moyens de paiement ; B pareil pour O ; C voit tout.
    mo = members(pot_o)
    assert "Bloqué" not in mo and mo["Personne bloquée"]["payment"] is None, mo
    assert mo["Orga"]["payment"]["holder"] == "Orga Test"
    mb = members(pot_b)
    assert "Orga" not in mb and mb["Personne bloquée"]["payment"] is None, mb
    mc = members(pot_c)
    assert mc["Bloqué"]["payment"]["holder"] == "Bloqué Test" and mc["Orga"]["payment"]["holder"] == "Orga Test", mc
    exp = {k: {e["id"]: e for e in p["expenses"]} for k, p in (("o", pot_o), ("b", pot_b), ("c", pot_c))}
    assert (exp["o"][X2]["title"], exp["o"][X2]["note"], exp["o"][X2]["receipt_path"]) == ("", None, None)
    assert (exp["o"][X1]["title"], exp["o"][X1]["note"]) == ("Courses de O", "note de O")
    assert (exp["b"][X1]["title"], exp["b"][X1]["note"], exp["b"][X1]["receipt_path"]) == ("", None, None)
    assert exp["b"][X2]["title"] == "Courses de B"
    assert exp["c"][X1]["title"] == "Courses de O" and exp["c"][X2]["receipt_path"] == "ticket-b.jpg"
    for k in "ob":  # les comptes restent justes : montants, payeur et parts identiques
        for x in (X1, X2):
            for f in ("amount_cents", "paid_by", "shares"):
                assert exp[k][x][f] == exp["c"][x][f], (k, x, f)
    assert "Bloqué" not in got["join_o"] and "Personne bloquée" in got["join_o"]
    assert "Orga" not in got["join_b"] and "Bloqué" in got["join_c"]
    # 2. Pas de modification de la dépense de l'autre ; moyens de paiement en lecture directe : rien pour O, tout pour C.
    assert got["save_o"] == "forbidden: dépense introuvable" and got["title_x2"] == "Courses de B", got
    assert got["rls_o"] == "0" and got["rls_c"] == "1", got
    # 4. Résumé : la réponse de C, jamais celle de B ; E2 (B seul) : aucune notification.
    assert "Tiers" in got["digest_1"] and "Bloqué" not in got["digest_1"], got
    assert "digest_2" not in got, got
    # 5. Rejouée : rien ne change.
    assert got["replay_changed"] == "0", got
