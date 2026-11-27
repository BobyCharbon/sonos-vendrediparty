"""Journal des membres après la suppression d'un compte (recette du 27.11, Apple 5.1.1(v) et (i), migration 20261127170000) :
plus d'identifiant, de surnom, de fin de numéro ni d'appareil de la personne, la trace « Compte supprimé » reste ; les
notifications qui pointent vers elle (data.member) partent ; le journal est purgé à 12 mois. Vraie suppression sur la base de
TEST, dans une transaction annulée : rien n'est enregistré."""
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

U = "00000000-0000-4000-8000-000000170001"


def run(jwt: bool) -> dict:
    claims = f"""{{"sub": "{U}", "role": "authenticated"}}""" if jwt else ""
    return sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at)
  values ('{U}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799917001', now(), now());
insert into public.profiles (id) values ('{U}') on conflict (id) do nothing;
update public.profiles set display_name = 'AuditSuppr', first_name = 'Audit', last_name = 'Suppr', status = 'active' where id = '{U}';
insert into auth.sessions (id, user_id, created_at, updated_at, user_agent)
  values (gen_random_uuid(), '{U}', now(), now(), 'iPhone AuditSuppr');
insert into public.member_group_members (group_id, user_id)
  select id, '{U}' from public.member_groups where not coalesce(private_chat, false) order by created_at limit 1;
insert into public.notifications (user_id, kind, title, body, data)
  select id, 'member_signup', 'Nouveau compte', 'AuditSuppr', jsonb_build_object('member', '{U}')
  from public.profiles where id <> '{U}' limit 1;
create temp table _r (before int, ok boolean, err text, ids int, names int, notifs int, deleted jsonb) on commit drop;
insert into _r (before) select count(*) from public.member_audit where actor = '{U}' or target = '{U}';
select set_config('request.jwt.claims', '{claims}', true);
do $s$
begin
  delete from auth.users where id = '{U}';
  update _r set ok = true;
exception when others then update _r set ok = false, err = sqlerrm;
end $s$;
update _r set
  ids = (select count(*) from public.member_audit a where a.actor = '{U}' or a.target = '{U}'
         or row_to_json(a)::text like '%{U}%'),
  names = (select count(*) from public.member_audit a where row_to_json(a)::text ~ '(AuditSuppr|"phone_end")'
           and a.at > now() - interval '1 minute'),
  notifs = (select count(*) from public.notifications n where n.data ->> 'member' = '{U}'),
  deleted = (select to_jsonb(a) from public.member_audit a where a.action = 'account.deleted' order by a.id desc limit 1);
select * from _r;
rollback;
""")[-1]


def test_a_deleted_account_leaves_no_personal_data_in_the_journal():
    for jwt in (True, False):
        r = run(jwt)
        assert r["ok"], r["err"]
        assert r["before"] >= 3, r  # connexion, création, groupe
        assert r["ids"] == 0 and r["names"] == 0, r
        assert r["notifs"] == 0, r
        d = r["deleted"]
        assert d["target"] is None and d["target_name"] == "Compte supprimé", d
        assert d["details"] == {"by": "self" if jwt else "admin"}, d


def test_the_journal_is_purged_after_twelve_months():
    r = sql("""
begin;
insert into public.member_audit (at, action) values (now() - interval '13 months', 'purge.old'), (now() - interval '11 months', 'purge.new');
select private.member_audit_tick();
select count(*) filter (where action = 'purge.old') old, count(*) filter (where action = 'purge.new') new,
       (select count(*) from cron.job where jobname = 'member-audit-tick') job
  from public.member_audit where action like 'purge.%';
rollback;
""")[-1]
    assert r == {"old": 0, "new": 1, "job": 1}, r
