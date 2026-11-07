"""Campagne 2 des bots (07.11.2026), corrections de la base « invitations, groupes, cycle de vie » (migration
20261107100000), sur la VRAIE base de TEST, avec les comptes des BOTS seulement (groupes « Bots » / « Bots 2 ») :
- une personne en blocage avec l'organisateur est sautée quand un groupe est invité (création, Inviter, validation par
  l'admin du groupe, ajout d'un membre au groupe), sans faire échouer l'invitation ni révéler qui ;
- un lien « pour plusieurs » ne fait pas entrer une personne en blocage ;
- « Prévenir le groupe » depuis Inviter ne vise que les groupes ajoutés ; couper/rallumer ne redemande pas ;
- « Rouvrir l'événement » prévient « Événement rétabli » ceux qui avaient reçu l'annulation (jamais « Proposition validée ») ;
- l'organisateur qui ouvre / répond à son propre lien ne le consomme pas ;
- co-organisateur sans droit de modifier : ne peut pas annuler ; un co-organisateur ajouté est prévenu ;
- invités sans réponse prévenus d'une annulation (pas d'une modification) ; l'auteur jamais de sa propre modification ;
- « Événement annulé » reste dans l'Activité quand l'événement est supprimé.
Tout se passe dans des transactions ANNULÉES (rien ne reste)."""
import json

from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

BOTS = {"ada": "41790000101", "come": "41790000102", "olga": "41790000103", "oscar": "41790000104",
        "victor": "41790000105", "violette": "41790000108", "marc": "41790000109", "max": "41790000111",
        "gus": "41790000112"}

DECLARE = "e uuid; a uuid; t uuid; n int; m int; r jsonb; msg text; bots uuid; bots2 uuid; " + " ".join(f"{k} uuid;" for k in BOTS)
SETUP = "\n".join(f"select id into {k} from public.profiles where phone = '{p}';" for k, p in BOTS.items()) + """
select id into bots from public.member_groups where name = 'Bots';
select id into bots2 from public.member_groups where name = 'Bots 2';
delete from public.direct_blocks where user_id in (olga, gus, violette) or blocked_id in (olga, gus, violette);
update public.notification_prefs set invites = true, event_changed = true, announce_requests = true, announce_results = true
  where user_id in (ada, come, olga, oscar, victor, violette, marc, max, gus);
update public.member_groups set events_need_approval = false, announce_mode = 'request' where id in (bots, bots2);"""


def as_bot(name: str) -> str:
    return (f"execute 'reset role'; perform set_config('request.jwt.claims', "
            f"json_build_object('sub', {name}, 'role', 'authenticated')::text, true); execute 'set local role authenticated';")


def as_postgres() -> str:
    return "execute 'reset role'; perform set_config('request.jwt.claims', '', true);"


def block(who: str, whom: str) -> str:
    return as_postgres() + f"insert into public.direct_blocks (user_id, blocked_id) values ({who}, {whom});"


def event_by(who: str, group: str | None = "bots", announce: bool = False, publish: bool = True) -> str:
    return as_bot(who) + f"""
      insert into public.events (title, status, visibility, public_link, notify_on_publish, announce_group, starts_at)
        values ('Test C2 invitations', 'draft', 'invited', false, false, {str(announce).lower()}, now() + interval '30 days')
        returning id into e;
      {f"insert into public.event_groups (event_id, group_id) values (e, {group});" if group else ''}
      {"update public.events set status = 'published' where id = e;" if publish else ''}"""


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False)


def invited(who: str) -> str:
    return f"(select count(*) from public.event_invites where event_id = e and user_id = {who})"


def notes(kind: str, who: str, title: str = "") -> str:
    title_filter = f"and title = '{title}'" if title else ""
    return (f"(select count(*) from public.notifications where kind = '{kind}' and user_id = {who} "
            f"and (event_id = e or data->>'target_event' = e::text) {title_filter})")


# --- 1. Blocage : le groupe est invité, la personne en blocage est sautée ------------------------------------------------

def test_a_blocked_member_is_skipped_when_an_event_is_published_for_the_group():
    out = run(block("olga", "gus") + event_by("olga") + as_postgres() + f"""
      raise exception 'résultat: statut=% gus=% victor=%', (select status from public.events where id = e), {invited('gus')}, {invited('victor')};""")
    assert "résultat: statut=published gus=0 victor=1" in out, out


def test_a_member_who_blocked_the_organizer_is_skipped_too():
    out = run(block("gus", "olga") + event_by("olga") + as_postgres() + f"""
      raise exception 'résultat: statut=% gus=% victor=%', (select status from public.events where id = e), {invited('gus')}, {invited('victor')};""")
    assert "résultat: statut=published gus=0 victor=1" in out, out


def test_invite_sheet_with_a_group_and_people_skips_only_the_blocked_one():
    out = run(block("olga", "gus") + event_by("olga", group=None) + """
      r := public.invite_people(e, array[max, gus], array[bots]);""" + as_postgres() + f"""
      raise exception 'résultat: gus=% max=% victor=% groupes=%', {invited('gus')}, {invited('max')}, {invited('victor')},
        (select count(*) from public.event_groups where event_id = e);""")
    assert "résultat: gus=0 max=1 victor=1 groupes=1" in out, out


def test_a_single_blocked_invitation_is_refused_in_clean_french():
    out = run(block("olga", "gus") + event_by("olga", group=None) + """
      begin insert into public.event_invites (event_id, user_id) values (e, gus); msg := 'passé';
        exception when others then msg := sqlerrm; end;
      raise exception 'résultat: %', msg;""")
    assert "résultat: blocked: Tu ne peux pas inviter cette personne." in out, out


def test_the_group_admin_accepting_a_group_event_skips_the_blocked_member():
    out = run(as_bot("ada") + """
      perform public.set_group_event_rules(bots2, true, 'request');""" + block("violette", "olga")
              + event_by("olga", group="bots2", announce=True) + as_bot("ada") + """
      r := public.answer_group_event(e, bots2, true);""" + as_postgres() + f"""
      raise exception 'résultat: lien=% violette=% olga=% invitation_violette=%', (select status from public.event_groups where event_id = e),
        {invited('violette')}, {invited('olga')}, {notes('private_invite', 'violette')};""")
    assert "résultat: lien=approved violette=0 olga=1 invitation_violette=0" in out, out


def test_an_accepted_announcement_never_reaches_a_blocked_member():
    out = run(block("gus", "olga") + event_by("olga", announce=True) + as_postgres() + """
      select id into a from public.event_announcements where event_id = e;""" + as_bot("ada") + """
      r := public.answer_announcement(a, true);""" + as_postgres() + f"""
      raise exception 'résultat: statut=% gus=% victor=%', (select status from public.event_announcements where id = a),
        {notes('private_invite', 'gus')}, {notes('private_invite', 'victor')};""")
    assert "résultat: statut=accepted gus=0 victor=1" in out, out


def test_adding_a_blocked_person_to_the_group_does_not_fail_and_does_not_invite_him():
    out = run(block("olga", "gus") + event_by("olga", group="bots2") + as_postgres() + """
      begin insert into public.member_group_members (group_id, user_id) values (bots2, gus); msg := 'ajouté';
        exception when others then msg := sqlerrm; end;""" + f"""
      raise exception 'résultat: ajout=% gus=% violette=%', msg, {invited('gus')}, {invited('violette')};""")
    assert "résultat: ajout=ajouté gus=0 violette=1" in out, out


def test_a_blocked_person_cannot_enter_by_a_link_for_several():
    out = run(event_by("olga", group=None) + """
      r := public.create_event_invite(e, 5);
      t := (r->>'token')::uuid;""" + block("olga", "gus") + as_bot("gus") + """
      begin perform public.accept_invite(t, 'yes'); msg := 'entré'; exception when others then msg := sqlerrm; end;""" + as_postgres() + f"""
      raise exception 'résultat: %| gus=% places=%', msg, {invited('gus')},
        (select uses from private.invite_links where token = t);""")
    assert "résultat: Tu ne peux pas répondre à cette invitation.| gus=0 places=0" in out, out


# --- 2 et 3. « Prévenir le groupe » ------------------------------------------------------------------------------------------

def test_announce_from_the_invite_sheet_only_tells_the_added_group():
    out = run(event_by("ada") + """
      r := public.invite_people(e, '{}', array[bots2], true);""" + as_postgres() + f"""
      raise exception 'résultat: annonces=% annonce_evenement=% victor=% violette=%',
        (select string_agg(g.name || ' ' || x.status, ', ' order by g.name) from public.event_announcements x
           join public.member_groups g on g.id = x.group_id where x.event_id = e),
        (select announce_group from public.events where id = e), {notes('private_invite', 'victor')}, {notes('private_invite', 'violette')};""")
    assert "résultat: annonces=Bots 2 direct annonce_evenement=f victor=0 violette=1" in out, out


def test_announce_from_the_invite_sheet_waits_for_the_group_admin_and_only_for_that_group():
    out = run(event_by("olga", group="bots2") + """
      r := public.invite_people(e, '{}', array[bots], true);""" + as_postgres() + f"""
      raise exception 'résultat: annonces=% demandes_ada=%',
        (select string_agg(g.name || ' ' || x.status, ', ' order by g.name) from public.event_announcements x
           join public.member_groups g on g.id = x.group_id where x.event_id = e), {notes('announce_request', 'ada')};""")
    assert "résultat: annonces=Bots pending demandes_ada=1" in out, out


def test_switching_announce_off_and_on_asks_the_group_admins_only_once():
    out = run(event_by("olga", announce=True) + """
      update public.events set announce_group = false where id = e;
      update public.events set announce_group = true where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: statut=% demandes_ada=%', (select string_agg(status, ',') from public.event_announcements where event_id = e),
        {notes('announce_request', 'ada')};""")
    assert "résultat: statut=pending demandes_ada=1" in out, out


def test_editing_the_event_keeps_an_announcement_asked_from_the_invite_sheet():
    out = run(event_by("olga", group="bots2") + """
      r := public.invite_people(e, '{}', array[bots], true);
      update public.events set title = 'Test C2 invitations (modifié)', visibility = 'invited', announce_group = false where id = e;""" + as_postgres() + """
      raise exception 'résultat: annonces=%', (select string_agg(status, ',') from public.event_announcements where event_id = e);""")
    assert "résultat: annonces=pending" in out, out


# --- 4 et 6. Cycle de vie ---------------------------------------------------------------------------------------------------

def test_reopening_tells_those_told_of_the_cancellation_never_proposal_validated():
    out = run(event_by("olga") + as_bot("victor") + """
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes');""" + as_bot("olga") + """
      update public.events set status = 'cancelled' where id = e;""" + as_bot("ada") + """
      update public.events set status = 'published' where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: statut=% annule_victor=% retabli_victor=% valide_olga=% retabli_ada=%', (select status from public.events where id = e),
        {notes('event_changed', 'victor', 'Événement annulé')}, {notes('event_changed', 'victor', 'Événement rétabli')},
        {notes('approved', 'olga')}, {notes('event_changed', 'ada', 'Événement rétabli')};""")
    assert "résultat: statut=published annule_victor=1 retabli_victor=1 valide_olga=0 retabli_ada=0" in out, out


def test_reopening_respects_the_event_changed_switch():
    out = run(event_by("olga") + as_bot("victor") + """
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes');""" + as_bot("olga") + """
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + """
      update public.notification_prefs set event_changed = false where user_id = victor;""" + as_bot("ada") + """
      update public.events set status = 'published' where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: retabli_victor=%', {notes('event_changed', 'victor', 'Événement rétabli')};""")
    assert "résultat: retabli_victor=0" in out, out


def test_invitees_without_answer_hear_of_a_cancellation_not_of_a_change_and_the_author_never():
    out = run(event_by("olga", group=None) + """
      r := public.invite_people(e, array[max], '{}');
      update public.events set location_name = 'Ailleurs' where id = e;""" + as_postgres() + f"""
      m := {notes('event_changed', 'max')} + {notes('event_changed', 'olga')};""" + as_bot("olga") + """
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: modif=% annule_max=% olga=%', m, {notes('event_changed', 'max', 'Événement annulé')},
        {notes('event_changed', 'olga')};""")
    assert "résultat: modif=0 annule_max=1 olga=0" in out, out


def test_group_members_never_told_of_the_event_are_not_told_of_its_cancellation():
    out = run(event_by("olga") + """
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: victor=%', {notes('event_changed', 'victor')};""")
    assert "résultat: victor=0" in out, out


def test_the_cancellation_notice_stays_when_the_event_is_deleted():
    out = run(event_by("olga") + as_bot("victor") + """
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes');""" + as_bot("olga") + """
      update public.events set status = 'cancelled' where id = e;
      delete from public.events where id = e;""" + as_postgres() + """
      raise exception 'résultat: supprime=% notification=% lien=%', (select count(*) = 0 from public.events where id = e),
        (select count(*) from public.notifications where user_id = victor and title = 'Événement annulé'
           and body = '« Test C2 invitations » est annulé.' and created_at > now() - interval '1 minute'),
        (select count(*) from public.notifications where user_id = victor and title = 'Événement annulé'
           and created_at > now() - interval '1 minute' and (event_id is not null or data ? 'event_id'));""")
    assert "résultat: supprime=t notification=1 lien=0" in out, out


def test_a_coorganizer_without_the_edit_right_cannot_cancel_but_one_with_it_can():
    """Rôle sans events.edit_own_published (retiré ici au rôle de Bot Victor, dans la transaction annulée) : il ne modifie
    pas, il n'annule pas non plus ; Bot Oscar (Organisateur) si. Un « Membre » simple (Bot Marc) est déjà arrêté par la
    règle de la base (is_active) : sa demande ne change rien."""
    out = run(event_by("olga") + as_postgres() + """
      delete from public.role_permissions where role = 'member' and perm = 'events.edit_own_published';""" + as_bot("olga") + """
      insert into public.event_organizers (event_id, user_id) values (e, victor), (e, oscar);""" + as_bot("victor") + """
      begin update public.events set status = 'cancelled' where id = e; msg := 'annulé'; exception when others then msg := sqlerrm; end;""" + as_postgres() + """
      r := jsonb_build_object('victor', msg, 'statut', (select status from public.events where id = e));""" + as_bot("oscar") + """
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + """
      raise exception 'résultat: victor=% apres_victor=% apres_oscar=%', r->>'victor', r->>'statut', (select status from public.events where id = e);""")
    assert "apres_victor=published apres_oscar=cancelled" in out, out
    assert "victor=forbidden: " in out, out


def test_the_creator_without_the_edit_right_can_still_cancel():
    """Sans events.edit_own_published : on annule toujours l'événement qu'on a créé, comme avant."""
    out = run(as_postgres() + """
      delete from public.role_permissions where role = 'member' and perm = 'events.edit_own_published';
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at, created_by)
        values ('Test C2 invitations', 'published', 'invited', false, false, now() + interval '30 days', victor) returning id into e;""" + as_bot("victor") + """
      update public.events set status = 'cancelled' where id = e;""" + as_postgres() + """
      raise exception 'résultat: statut=%', (select status from public.events where id = e);""")
    assert "résultat: statut=cancelled" in out, out


def test_an_added_coorganizer_is_told_with_his_switch():
    out = run(event_by("olga") + """
      insert into public.event_organizers (event_id, user_id) values (e, oscar);""" + as_postgres() + f"""
      m := {notes('coorganizer_added', 'oscar')};
      update public.notification_prefs set invites = false where user_id = marc;""" + as_bot("olga") + """
      insert into public.event_organizers (event_id, user_id) values (e, marc);""" + as_postgres() + f"""
      raise exception 'résultat: oscar=% marc=% envoi_oscar=%', m, {notes('coorganizer_added', 'marc')},
        (select private.web_push_allowed(x) from public.notifications x where x.kind = 'coorganizer_added' and x.user_id = oscar and x.event_id = e);""")
    assert "résultat: oscar=1 marc=0 envoi_oscar=t" in out, out


# --- 5. L'organisateur et son propre lien -----------------------------------------------------------------------------------

def test_the_organizer_opening_and_answering_his_own_link_does_not_use_it():
    out = run(event_by("olga", group=None) + """
      insert into public.event_organizers (event_id, user_id) values (e, oscar);
      r := public.create_event_invite(e, 1);
      t := (r->>'token')::uuid;
      r := public.invite_preview(t, true);
      r := r || jsonb_build_object('reponse', public.accept_invite(t, 'yes'));""" + as_bot("oscar") + """
      perform public.invite_preview(t, true);
      perform public.accept_invite(t, 'yes');""" + as_postgres() + """
      raise exception 'résultat: organisateur=% places=% pris_par=% ouvert=% arrivees=%', r->>'organizer',
        (select uses from private.invite_links where token = t), (select count(used_by) from private.invite_links where token = t),
        (select count(opened_at) from private.invite_links where token = t),
        (select count(*) from private.invite_link_arrivals where token = t);""")
    assert "résultat: organisateur=true places=0 pris_par=0 ouvert=0 arrivees=0" in out, out
