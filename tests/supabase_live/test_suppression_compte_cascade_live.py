"""Suppression du compte (Apple 5.1.1(v)) : chaque colonne « qui a fait quoi » (`*_by`, `user_id`) en `on delete set null`
passe par les gardes BEFORE UPDATE de sa table quand la base efface le compte. Bug du 27.11 : la garde des présences sans
compte refusait cette cascade (20261127090000) ; 20261127110000 corrige guard_event (approved_by), guard_bring_item,
guard_event_group_status et group_photo_guard. Ici, pour CHAQUE colonne, une VRAIE suppression sur la base de TEST, dans
une transaction annulée à la fin : un compte neuf (rôle choisi), posé comme auteur de vraies lignes de la base de TEST, puis
`delete from auth.users` avec SON jeton (comme `delete_my_account`). La suppression doit réussir ET ne laisser aucune trace
de l'identifiant effacé. Lignes posées dans la même transaction : une garde qui remet l'identifiant effacé y fait échouer la
clé étrangère (en prod, sur une ligne ancienne, la base ne revérifie pas : l'identifiant mort reste). Rien n'est enregistré."""
import json

import pytest

from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

# (table, colonne, rôle du compte supprimé, filtre des lignes choisies). TOUTES les lignes de la base de TEST qui passent
# le filtre (états variés : publié, brouillon, payé…), sauf conflit d'unicité.
CASES = [
    ("public.events", "approved_by", "admin", "true"),
    ("public.events", "approved_by", "moderator", "true"),
    ("public.events", "approved_by", "coadmin", "true"),
    ("public.events", "approved_by", "organizer", "true"),
    ("public.bring_items", "added_by", "member", "true"),
    ("public.bring_items", "claimed_by", "member", "true"),
    ("public.date_options", "proposed_by", "member", "true"),
    ("public.event_bar_log", "actor", "member", "true"),
    ("public.event_bar_log", "user_id", "member", "true"),
    ("public.event_bar_units", "served_by", "member", "true"),
    ("public.event_bar_units", "cancelled_by", "member", "true"),
    ("public.event_bar_units", "corrected_by", "member", "true"),
    ("public.event_bars", "created_by", "member", "true"),
    ("public.event_bars", "payee_id", "member", "true"),
    ("public.event_groups", "answered_by", "member", "true"),
    ("public.event_groups", "requested_by", "member", "true"),
    ("public.event_tickets", "issued_by", "member", "true"),
    ("public.event_tickets", "paid_by", "member", "true"),
    ("public.event_tickets", "checked_in_by", "member", "true"),
    ("public.member_groups", "created_by", "member", "true"),
    ("public.member_groups", "invite_token_by", "member", "true"),
    ("public.member_groups", "photo_by", "member", "true"),
    ("public.polls", "created_by", "member", "true"),
    ("public.poll_options", "created_by", "member", "true"),
    ("private.invite_links", "created_by", "member", "true"),
    ("private.invite_links", "used_by", "member", "true"),
    ("public.rsvps", "set_by", "member", "true"),
    ("public.tc_groups", "created_by", "member", "true"),
    ("public.tc_expenses", "created_by", "member", "true"),
    ("public.tc_members", "user_id", "member", "true"),
    ("public.event_manual_guests", "added_by", "member", "true"),
]


def uid(n: int) -> str:
    return f"00000000-0000-4000-8000-0000000{n:05d}"


def delete_case(cols: list[tuple[str, str, str]], role: str, n: int, limit: int | None = None, jwt: bool = True) -> dict:
    """Une vraie suppression, annulée à la fin : le compte neuf n° n est posé dans cols (table, colonne, filtre), puis
    effacé avec son jeton (`delete_my_account`) ou sans (jwt=False : console, service). Rend {"ok", "err", "rows", "trace"}."""
    u = uid(n)
    claims = json.dumps({"sub": u, "role": "authenticated"}) if jwt else ""
    lim = f"limit {limit}" if limit else ""
    put = "\n".join(f"""
  for r in select ctid from {t} where {c} is distinct from '{u}' and ({w}) order by ctid {lim} loop
    begin
      update {t} set {c} = '{u}' where ctid = r.ctid;
      update _r set rows = rows + 1;
    exception when others then null; -- contrainte d'unicité : ligne suivante
    end;
  end loop;""" for t, c, w in cols)
    trace = " + ".join(f"(select count(*) from {t} where {c} = '{u}')" for t, c, _ in cols)
    # Lignes posées en mode « replica » (déclencheurs coupés) : seule la suppression passe par les gardes.
    return sql(f"""
begin;
insert into auth.users (id, instance_id, aud, role, phone, created_at, updated_at)
  values ('{u}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '41799990{n % 1000:03d}', now(), now());
set local session_replication_role = replica;
insert into public.profiles (id) values ('{u}') on conflict (id) do nothing;
update public.profiles set display_name = 'Suppr{n}', first_name = 'Suppr', last_name = 'Test', role = '{role}', status = 'active'
  where id = '{u}';
create temp table _r (ok boolean, err text, rows int, trace int) on commit drop;
insert into _r (rows) values (0);
-- Présences sans compte : aucune sur la base de TEST, deux posées (événements publiés et annulés).
insert into public.event_manual_guests (event_id, name)
  select id, 'Invité sans compte' from public.events where status in ('published', 'cancelled') order by created_at desc limit 3;
do $s$
declare r record;
begin{put}
end $s$;
set local session_replication_role = origin;
select set_config('request.jwt.claims', '{claims}', true);
do $s$
begin
  delete from auth.users where id = '{u}';
  update _r set ok = true;
exception when others then
  update _r set ok = false, err = sqlerrm;
end $s$;
update _r set trace = {trace};
select * from _r;
rollback;
""")[-1]


def check(res: dict, what: str):
    assert res["ok"], f"suppression refusée ({what}) : {res['err']}"
    assert res["trace"] == 0, f"identifiant effacé remis ({what}) : {res['trace']} lignes"


@pytest.mark.parametrize("table,col,role,where", CASES, ids=[f"{t}.{c}-{r}" for t, c, r, _ in CASES])
def test_deleting_the_account_clears_who_did_what(table, col, role, where):
    n = 100 + CASES.index((table, col, role, where))
    res = delete_case([(table, col, where)], role, n)
    if not res.get("rows"):
        pytest.skip(f"aucune ligne de {table} sur la base de TEST")
    check(res, f"{table}.{col}, {role}")


@pytest.mark.parametrize("jwt", [True, False], ids=["delete_my_account", "console"])
def test_an_account_that_did_everything_is_deleted_at_once(jwt):
    """Un seul compte sur TOUTES les colonnes à la fois (5 lignes chacune) : la vraie suppression les vide toutes ensemble."""
    res = delete_case([(t, c, w) for t, c, _, w in CASES], "admin", 300 + jwt, limit=5, jwt=jwt)
    assert res["rows"] > 20
    check(res, "toutes les colonnes")


def test_an_admin_who_published_his_own_events_is_deleted():
    """Publié directement (approved_by = lui-même, comme un admin en prod) : ses événements partent avec lui (cascade)."""
    mine = "created_by in (select id from auth.users where phone like '41799990%')"
    res = delete_case([("public.events", "created_by", "status = 'published'"), ("public.events", "approved_by", mine)],
                      "admin", 310, limit=5)
    assert res["rows"] >= 2
    check(res, "événements publiés par lui-même")


def test_a_living_approver_is_never_erased_by_hand():
    """Le passage « compte supprimé » ne vaut que pour un compte qui n'existe plus : un simple membre qui vide approved_by
    de l'événement d'un autre (ou requested_by d'un groupe), compte vivant, est refusé ou remis comme avant."""
    rows = sql("""
begin;
create temp table _r (k text, v text) on commit drop;
do $s$
declare e public.events; m uuid; g public.event_groups;
begin
  select * into e from public.events where approved_by is not null and status = 'published' order by created_at desc limit 1;
  select p.id into m from public.profiles p where p.status = 'active' and p.role = 'member'
    and p.id is distinct from e.created_by
    and not exists (select 1 from public.event_organizers o where o.event_id = e.id and o.user_id = p.id)
    limit 1;
  perform set_config('request.jwt.claims', json_build_object('sub', m, 'role', 'authenticated')::text, true);
  begin
    update public.events set approved_by = null where id = e.id;
    insert into _r values ('event', (select coalesce(approved_by::text, 'null') from public.events where id = e.id));
  exception when others then insert into _r values ('event', 'refusé');
  end;
  select * into g from public.event_groups where requested_by is not null limit 1;
  if g.event_id is not null then
    begin
      update public.event_groups set requested_by = null where event_id = g.event_id and group_id = g.group_id;
      insert into _r values ('group', (select coalesce(requested_by::text, 'null') from public.event_groups
                                        where event_id = g.event_id and group_id = g.group_id));
    exception when others then insert into _r values ('group', 'refusé');
    end;
  end if;
end $s$;
select * from _r;
rollback;
""")
    got = {r["k"]: r["v"] for r in rows}
    assert got["event"] != "null", "un membre a vidé approved_by de l'événement d'un autre"
    assert got.get("group") != "null", "requested_by vidé à la main"
