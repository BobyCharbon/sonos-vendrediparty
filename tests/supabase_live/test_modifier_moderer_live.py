"""Modifier son événement, droits de l'équipe et rôle Modérateur (décisions de l'admin du 22.11.2026, migration
20261122160000), sur la VRAIE base de TEST (jamais la prod), comptes des BOTS, validation du site allumée comme en prod :
- le créateur d'un événement PUBLIC sans « modifier un publié » (Guest) le modifie : il repasse en attente ; un Membre
  VIP (edit_own_published) ou un Organisateur (publish_direct) : il reste publié ; created_by / approved_by intacts ;
- événement de GROUPE : simple membre d'un groupe « Événements à valider » → le groupe repasse en attente ; qui gère le
  groupe → libre ; réenregistrer sans changement → rien ;
- events.edit_others / events.remove_others : sans eux, un Organisateur ne touche pas l'événement d'un autre ; avec,
  il le modifie (statut inchangé, jamais un brouillon) ou l'annule ;
- rôle Modérateur : droits attendus, valide un événement public, masque un message signalé, accepte un compte, ne bannit
  pas, ne change pas de rôle, n'est ni admin du site ni « tous les groupes ».
Tout se passe dans des transactions ANNULÉES : rien ne reste."""
import json

from tests.supabase_live.test_groupes_libres_live import as_bot
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

BOTS = {"ada": "41790000101", "olga": "41790000103", "oscar": "41790000104", "victor": "41790000105",
        "marc": "41790000109", "gus": "41790000112", "gina": "41790000113"}

DECLARE = "e uuid; e2 uuid; g uuid; m uuid; rep uuid; r jsonb; n int; st text; t text; " + " ".join(f"{k} uuid;" for k in BOTS)
SETUP = "\n".join(f"select id into {k} from public.profiles where phone = '{p}';" for k, p in BOTS.items()) + """
update public.group_settings set require_approval = true;
update public.profiles set role = 'guest' where id in (gus, gina);
update public.profiles set role = 'member' where id = victor;
update public.profiles set role = 'organizer' where id = olga;
-- Droits de la prod (22.11) : un Guest crée des événements.
insert into public.role_permissions (role, perm) values ('guest', 'events.create') on conflict do nothing;
insert into public.terms_acceptances (user_id, version)
  select p.id, (select terms_version from private.moderation_settings where id = 1) from public.profiles p
  where p.phone in (""" + ", ".join(f"'{p}'" for p in BOTS.values()) + """) on conflict do nothing;"""


def as_postgres() -> str:
    # « set local role postgres » plutôt que « reset role » : après un bloc exception, reset role restait authenticated.
    return "execute 'set local role postgres'; perform set_config('request.jwt.claims', '', true);"


def claims_of(name: str) -> str:
    """Fonctions privées (non appelables par authenticated) évaluées pour ce compte."""
    return as_postgres() + f"perform set_config('request.jwt.claims', json_build_object('sub', {name}, 'role', 'authenticated')::text, true);"


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False)


def published_event(who: str, var: str = "e", public: bool = True, group: bool = False) -> str:
    """Brouillon puis « Publier » ; un événement public en attente est validé par Ada (admin)."""
    return as_bot(who) + f"""
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test modifier', 'draft', '{'all' if public else 'invited'}', {str(public).lower()}, false,
                now() + interval '30 days') returning id into {var};
      {f"insert into public.event_groups (event_id, group_id) values ({var}, g);" if group else ''}
      update public.events set status = 'published' where id = {var};""" + as_bot("ada") + f"""
      if (select status from public.events where id = {var}) = 'pending' then perform public.approve_event({var}); end if;"""


def test_the_creator_edits_his_public_event_and_it_waits_again_unless_he_may_edit_published():
    out = run(published_event("gus") + as_bot("gus") + """
      update public.events set title = 'Test modifier (corrigé)', created_by = victor, approved_by = gus where id = e;"""
              + published_event("victor", "e2") + as_bot("victor") + """
      update public.events set title = 'Test modifier VIP' where id = e2;""" + as_postgres() + """
      st := (select status || '/' || (created_by = gus) || '/' || (approved_by = ada) from public.events where id = e);
      t := (select status::text from public.events where id = e2);""" + published_event("olga", "e2") + as_bot("olga") + """
      update public.events set title = 'Test modifier orga' where id = e2;""" + as_postgres() + """
      raise exception 'résultat: guest=% membre_vip=% organisateur=% propositions=%', st, t,
        (select status from public.events where id = e2),
        (select count(*) from public.notifications where kind = 'proposal' and event_id = e);""")
    assert "résultat: guest=pending/true/true membre_vip=published organisateur=published propositions=" in out, out
    assert "propositions=0" not in out, out  # les valideurs du site sont prévenus de la nouvelle proposition


def test_a_simple_member_edit_goes_back_to_a_group_that_validates_and_the_group_manager_edits_freely():
    out = run(as_bot("gus") + """
      insert into public.member_groups (name, emoji, color, created_by) values ('Test modifier groupe', '⚽', 'mint', gus)
        returning id into g;
      update public.member_groups set events_need_approval = true where id = g;""" + as_postgres() + """
      insert into public.member_group_members (group_id, user_id) values (g, gus), (g, gina) on conflict do nothing;"""
              + published_event("gina", public=False, group=True) + as_bot("gus") + """
      r := public.answer_group_event(e, g, true);""" + as_bot("gina") + """
      update public.events set title = 'Test modifier groupe' where id = e;  -- modifié par un simple membre : le groupe revalide
      """ + as_postgres() + """
      update public.event_groups set status = 'approved' where event_id = e;
      st := (select status::text from public.events where id = e);""" + as_bot("gina") + """
      update public.events set description = 'Rien n''a changé' where id = e;
      update public.events set description = 'Rien n''a changé' where id = e;""" + as_postgres() + """
      t := (select ev.status || '/' || eg.status from public.events ev join public.event_groups eg on eg.event_id = ev.id where ev.id = e);
      update public.event_groups set status = 'approved' where event_id = e;""" + as_bot("gina") + """
      update public.events set description = 'Rien n''a changé' where id = e;  -- même texte : aucune nouvelle validation
      """ + as_postgres() + """
      st := st || ' ' || (select status from public.event_groups where event_id = e);""" + published_event("gus", "e2", public=False, group=True) + as_bot("gus") + """
      update public.events set title = 'Test modifier par le créateur du groupe' where id = e2;""" + as_postgres() + """
      raise exception 'résultat: membre=% sans_changement=% gerant=%/%', t, st,
        (select status from public.events where id = e2), (select status from public.event_groups where event_id = e2);""")
    assert "résultat: membre=published/pending sans_changement=published approved gerant=published/approved" in out, out


def test_events_of_others_need_the_new_rights():
    out = run(published_event("gus") + as_bot("gus") + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test brouillon de Gus', 'draft', 'all', true, false, now() + interval '30 days') returning id into e2;"""
              + as_bot("olga") + """
      update public.events set title = 'Pas à toi' where id = e;
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + """
      st := (select title || '/' || status from public.events where id = e);
      insert into public.role_permissions (role, perm) values ('organizer', 'events.edit_others') on conflict do nothing;"""
              + as_bot("olga") + """
      update public.events set title = 'Corrigé par Olga' where id = e;
      begin update public.events set status = 'cancelled' where id = e; t := 'annulé';
        exception when others then t := 'refusé'; end;
      select count(*) into n from public.events where id = e2;  -- jamais le brouillon d'un autre
      """ + as_postgres() + """
      st := st || ' ' || (select title || '/' || status from public.events where id = e) || ' annuler_sans_droit=' || t || ' brouillon=' || n;
      delete from public.role_permissions where role = 'organizer' and perm = 'events.edit_others';
      insert into public.role_permissions (role, perm) values ('organizer', 'events.remove_others') on conflict do nothing;"""
              + as_bot("olga") + """
      begin update public.events set title = 'Encore' where id = e; t := 'modifié';
        exception when others then t := 'refusé'; end;
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + """
      raise exception 'résultat: % modifier_avec_retirer=% retiré=% admin=% coadmin=% organisateur=%', st, t,
        (select status from public.events where id = e),
        (select count(*) from public.role_permissions where role = 'admin' and perm in ('events.edit_others', 'events.remove_others')),
        (select count(*) from public.role_permissions where role = 'coadmin' and perm in ('events.edit_others', 'events.remove_others')),
        (select count(*) from public.role_permissions where role = 'organizer' and perm = 'events.edit_others');""")
    assert ("résultat: Test modifier/published Corrigé par Olga/published annuler_sans_droit=refusé brouillon=0 "
            "modifier_avec_retirer=refusé retiré=cancelled admin=2 coadmin=2 organisateur=0") in out, out


def test_the_moderator_role():
    out = run("""
      update public.profiles set role = 'moderator' where id = oscar;
      st := (select string_agg(k || '=' || private.user_has(oscar, k), ' ' order by k) from unnest(array[
        'events.approve', 'members.approve', 'moderation.reports', 'chat.moderate', 'events.publish_direct',
        'members.ban', 'members.roles', 'events.manage_all', 'events.edit_others', 'events.remove_others']) k);
      t := (select string_agg(key, '<' order by rank) from public.roles where key in ('organizer', 'moderator', 'coadmin'));"""
              + claims_of("oscar") + """
      st := st || ' admin_site=' || private.is_member_admin() || ' tous_groupes=' || private.sees_all_groups();"""
              + as_bot("gus") + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test modérateur', 'draft', 'all', true, false, now() + interval '30 days') returning id into e;
      update public.events set status = 'published' where id = e;
      insert into public.member_groups (name, emoji, color, created_by) values ('Test modérateur groupe', '⚽', 'mint', gus)
        returning id into g;""" + as_postgres() + """
      insert into public.member_group_members (group_id, user_id) values (g, gus) on conflict do nothing;
      insert into public.group_messages (group_id, user_id, body) values (g, gus, 'Message à masquer') returning id into m;
      insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason)
        values (gina, 'group_message', m::text, gus, 'spam') returning id into rep;
      insert into public.join_requests (user_id, status) values (marc, 'pending')
        on conflict (user_id) do update set status = 'pending';
      update public.profiles set role = 'basic' where id = marc;""" + as_bot("oscar") + """
      perform public.approve_event(e);
      r := public.moderation_act(rep, 'hide', null, null);
      perform public.decide_join_request(marc, true);
      begin r := public.moderation_act(rep, 'ban', null, null); t := t || ' bannir=oui';
        exception when others then t := t || ' bannir=non'; end;
      begin update public.profiles set role = 'organizer' where id = victor; t := t || ' role=oui';
        exception when others then t := t || ' role=non'; end;""" + as_postgres() + """
      raise exception 'résultat: % rangs=% evenement=% masque=% compte=%', st, t,
        (select status from public.events where id = e),
        (select deleted_by_admin from public.group_messages where id = m), (select role from public.profiles where id = marc);""")
    assert ("chat.moderate=true events.approve=true events.edit_others=false events.manage_all=false "
            "events.publish_direct=true events.remove_others=false members.approve=true members.ban=false "
            "members.roles=false moderation.reports=true admin_site=false tous_groupes=false") in out, out
    assert "rangs=organizer<moderator<coadmin bannir=non role=non evenement=published masque=t compte=member" in out, out
