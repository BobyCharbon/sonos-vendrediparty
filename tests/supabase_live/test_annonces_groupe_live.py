"""Annonces d'événement aux groupes (décision de l'admin du 06.11.2026, migration 20261106220000), sur la VRAIE base de
TEST (jamais la prod), avec les comptes des BOTS seulement (groupes « Bots » / « Bots 2 », jamais Vendredi Party) :
- Bot Olga (organisatrice, simple membre du groupe Bots) demande « Prévenir le groupe » : demande en attente, valideurs
  (Bot Ada, créatrice ; Bot Côme, Co-admin dans le groupe) prévenus, aucun membre prévenu ;
- acceptée : le groupe est prévenu, Olga aussi ; la seconde réponse est refusée (première réponse gagne) ;
- refusée : rien n'est envoyé, l'événement reste publié et visible par le groupe ;
- 48 h simulées (date de la demande reculée) : acceptée et envoyée d'office par la tâche planifiée ;
- Bot Ada (créatrice du groupe) : envoi direct ; un événement public : jamais rien ;
- groupe « avec validation » : un événement proposé par un simple membre attend, invisible du groupe, puis validé ;
- interrupteurs respectés, statuts et réponses impossibles à contourner.
Tout se passe dans des transactions ANNULÉES (rien ne reste), sauf le test de concurrence (événement supprimé ensuite)."""
import json
import threading
import time

from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

BOTS = {"ada": "41790000101", "come": "41790000102", "olga": "41790000103", "victor": "41790000105",
        "valentin": "41790000107", "violette": "41790000108"}

DECLARE = "e uuid; a uuid; n int; m int; r jsonb; bots uuid; bots2 uuid; " + " ".join(f"{k} uuid;" for k in BOTS)
SETUP = "\n".join(f"select id into {k} from public.profiles where phone = '{p}';" for k, p in BOTS.items()) + """
select id into bots from public.member_groups where name = 'Bots';
select id into bots2 from public.member_groups where name = 'Bots 2';"""


def as_bot(name: str) -> str:
    """Change d'utilisateur au milieu du bloc (session authenticated, règles de la base)."""
    return (f"execute 'reset role'; perform set_config('request.jwt.claims', "
            f"json_build_object('sub', {name}, 'role', 'authenticated')::text, true); execute 'set local role authenticated';")


def as_postgres() -> str:
    return "execute 'reset role'; perform set_config('request.jwt.claims', '', true);"


def olga_event(announce: bool = True, group: str = "bots", public: bool = False) -> str:
    return as_bot("olga") + f"""
      insert into public.events (title, status, visibility, public_link, notify_on_publish, announce_group, starts_at)
        values ('Test annonce bots', 'draft', '{'all' if public else 'invited'}', {str(public).lower()}, false,
                {str(announce).lower()}, now() + interval '30 days') returning id into e;
      {'' if public else f"insert into public.event_groups (event_id, group_id) values (e, {group});"}
      update public.events set status = 'published' where id = e;"""


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False)


def count(kind: str, who: str = "") -> str:
    return f"(select count(*) from public.notifications where kind = '{kind}' {f'and user_id = {who}' if who else ''} and (event_id = e or data->>'target_event' = e::text))"


def test_a_member_asks_and_the_group_admins_are_asked_nobody_else_is_told():
    out = run(olga_event() + as_postgres() + f"""
      raise exception 'résultat: statut=% demandes_ada=% demandes_come=% demandes_olga=% invitations=%',
        (select status from public.event_announcements where event_id = e and group_id = bots),
        {count('announce_request', 'ada')}, {count('announce_request', 'come')}, {count('announce_request', 'olga')},
        {count('private_invite')};""")
    assert "résultat: statut=pending demandes_ada=1 demandes_come=1 demandes_olga=0 invitations=0" in out, out


def test_accepted_the_group_is_told_and_the_second_answer_loses():
    out = run(olga_event() + as_postgres() + """
      select id into a from public.event_announcements where event_id = e;""" + as_bot("ada") + """
      r := public.answer_announcement(a, true);""" + as_bot("come") + """
      r := r || jsonb_build_object('second', public.answer_announcement(a, false));""" + as_postgres() + f"""
      raise exception 'résultat: statut=% second=% invitations_victor=% acceptee_olga=%',
        (select status from public.event_announcements where id = a), r->'second'->>'already',
        {count('private_invite', 'victor')}, {count('announce_accepted', 'olga')};""")
    assert "résultat: statut=accepted second=true invitations_victor=1 acceptee_olga=1" in out, out


def test_refused_nothing_is_sent_and_the_event_stays_visible_to_the_group():
    out = run(olga_event() + as_postgres() + """
      select id into a from public.event_announcements where event_id = e;""" + as_bot("come") + """
      r := public.answer_announcement(a, false);""" + as_bot("victor") + """
      select count(*) into n from public.events where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: statut=% invitations=% refusee_olga=% victor_voit=% publie=%',
        (select status from public.event_announcements where id = a), {count('private_invite')},
        {count('announce_refused', 'olga')}, n, (select status from public.events where id = e);""")
    assert "résultat: statut=refused invitations=0 refusee_olga=1 victor_voit=1 publie=published" in out, out


def test_without_answer_for_48_hours_it_is_accepted_and_sent():
    out = run(olga_event() + as_postgres() + f"""
      update public.event_announcements set requested_at = now() - interval '47 hours' where event_id = e;
      n := private.auto_accept_announcements();
      m := {count('private_invite')};
      update public.event_announcements set requested_at = now() - interval '49 hours' where event_id = e;
      perform private.auto_accept_announcements();
      raise exception 'résultat: avant_48h=% statut=% invitations=% partie_olga=%', m,
        (select status from public.event_announcements where event_id = e), {count('private_invite', 'victor')},
        {count('announce_accepted', 'olga')};""")
    assert "résultat: avant_48h=0 statut=auto invitations=1 partie_olga=1" in out, out


def test_the_group_creator_announces_directly():
    out = run(as_bot("ada") + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, announce_group, starts_at)
        values ('Test annonce directe', 'draft', 'invited', false, false, true, now() + interval '30 days') returning id into e;
      insert into public.event_groups (event_id, group_id) values (e, bots);
      update public.events set status = 'published' where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: statut=% invitations_victor=% demandes=%',
        (select status from public.event_announcements where event_id = e), {count('private_invite', 'victor')},
        {count('announce_request')};""")
    assert "résultat: statut=direct invitations_victor=1 demandes=0" in out, out


def test_switched_off_or_public_nothing_is_ever_announced():
    off = run(olga_event(announce=False) + as_postgres() + f"""
      raise exception 'résultat: annonces=% notifications=%',
        (select count(*) from public.event_announcements where event_id = e), {count('private_invite')} + {count('announce_request')};""")
    assert "résultat: annonces=0 notifications=0" in off, off
    public = run(olga_event(public=True) + as_postgres() + """
      raise exception 'résultat: annonces=% notifications=%',
        (select count(*) from public.event_announcements where event_id = e),
        (select count(*) from public.notifications where event_id = e or data->>'target_event' = e::text);""")
    assert "résultat: annonces=0 notifications=0" in public, public


def test_free_mode_lets_members_announce_without_asking():
    out = run(as_bot("ada") + """
      perform public.set_group_event_rules(bots, false, 'free');""" + olga_event() + as_postgres() + f"""
      raise exception 'résultat: statut=% invitations_victor=%',
        (select status from public.event_announcements where event_id = e), {count('private_invite', 'victor')};""")
    assert "résultat: statut=direct invitations_victor=1" in out, out


def test_a_group_with_approval_hides_the_event_until_an_admin_accepts_it():
    out = run(as_bot("ada") + """
      perform public.set_group_event_rules(bots2, true, 'request');""" + olga_event(announce=False, group="bots2") + as_bot("violette") + """
      select count(*) into n from public.events where id = e;""" + as_postgres() + f"""
      r := jsonb_build_object('lien', (select status from public.event_groups where event_id = e), 'violette_avant', n,
        'demande_ada', {count('group_event_request', 'ada')});""" + as_bot("ada") + """
      perform public.answer_group_event(e, bots2, true);""" + as_bot("violette") + """
      select count(*) into n from public.events where id = e;""" + as_postgres() + f"""
      raise exception 'résultat: lien=% violette_avant=% demande_ada=% violette_apres=% acceptee_olga=%',
        r->>'lien', r->>'violette_avant', r->>'demande_ada', n, {count('group_event_accepted', 'olga')};""")
    assert "résultat: lien=pending violette_avant=0 demande_ada=1 violette_apres=1 acceptee_olga=1" in out, out


def test_switches_are_respected_at_queueing_and_at_sending():
    out = run(as_postgres() + """
      update public.notification_prefs set announce_requests = false where user_id = ada;
      update public.notification_prefs set announce_results = false where user_id = olga;""" + olga_event() + as_postgres() + """
      select id into a from public.event_announcements where event_id = e;""" + as_bot("come") + """
      perform public.answer_announcement(a, true);""" + as_postgres() + f"""
      update public.notification_prefs set announce_requests = true where user_id = ada;
      update public.notification_prefs set announce_requests = false where user_id = come;
      raise exception 'résultat: ada=% olga=% envoi_come=%', {count('announce_request', 'ada')}, {count('announce_accepted', 'olga')},
        (select private.web_push_allowed(x) from public.notifications x where x.kind = 'announce_request' and x.user_id = come
           and x.data->>'target_event' = e::text);""")
    assert "résultat: ada=0 olga=0 envoi_come=f\\" in out, out


def test_nobody_gets_around_the_validation():
    out = run(as_bot("ada") + """
      perform public.set_group_event_rules(bots2, true, 'request');""" + olga_event(group="bots2") + as_postgres() + """
      r := '{}';""" + as_bot("olga") + """
      update public.event_groups set status = 'approved' where event_id = e;
      begin insert into public.event_announcements (event_id, group_id, status) values (e, bots2, 'accepted');
        r := r || '{"insertion": "passée"}'; exception when others then r := r || '{"insertion": "refusée"}'; end;
      begin perform public.answer_group_event(e, bots2, true); r := r || '{"reponse": "passée"}';
        exception when others then r := r || '{"reponse": "refusée"}'; end;
      begin perform public.set_group_event_rules(bots2, false, 'free'); r := r || '{"reglages": "passés"}';
        exception when others then r := r || '{"reglages": "refusés"}'; end;
      update public.member_groups set announce_mode = 'free' where id = bots2;""" + as_postgres() + """
      raise exception 'résultat: lien=% insertion=% reponse=% reglages=% mode=%',
        (select status from public.event_groups where event_id = e), r->>'insertion', r->>'reponse', r->>'reglages',
        (select announce_mode from public.member_groups where id = bots2);""")
    assert "résultat: lien=pending insertion=refusée reponse=refusée reglages=refusés mode=request" in out, out


def test_the_ai_writes_with_the_same_rules_announce_group_is_never_set_for_it():
    """L'assistant IA crée avec le jeton de la personne : un événement sans announce_group ne prévient pas le groupe,
    même avec notify_on_publish (l'ancien « prévenir à la publication »)."""
    out = run(as_bot("olga") + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test IA', 'published', 'invited', false, true, now() + interval '30 days') returning id into e;
      insert into public.event_groups (event_id, group_id) values (e, bots);""" + as_postgres() + f"""
      raise exception 'résultat: annonces=% invitations=%',
        (select count(*) from public.event_announcements where event_id = e), {count('private_invite')};""")
    assert "résultat: annonces=0 invitations=0" in out, out


def _answer_in_parallel(announcement: str, who: str, accept: bool, results: dict) -> None:
    claims = json.dumps({"sub": who, "role": "authenticated"})
    results[who] = sql_test(f"""
      begin;
      set local role authenticated;
      set local request.jwt.claims = '{claims}';
      select public.answer_announcement('{announcement}', {str(accept).lower()}) r, pg_sleep(2);
      commit;""")


def test_two_admins_answering_at_the_same_time_only_the_first_wins():
    made = sql_test(f"""
      do $$ declare olga uuid; bots uuid; e uuid; begin
        select id into olga from public.profiles where phone = '{BOTS['olga']}';
        select id into bots from public.member_groups where name = 'Bots';
        perform set_config('request.jwt.claims', json_build_object('sub', olga, 'role', 'authenticated')::text, true);
        insert into public.events (title, status, visibility, public_link, notify_on_publish, announce_group, starts_at)
          values ('Test annonce concurrence (bots)', 'draft', 'invited', false, false, true, now() + interval '30 days') returning id into e;
        insert into public.event_groups (event_id, group_id) values (e, bots);
        update public.events set status = 'published' where id = e;
      end $$;
      select a.id, a.event_id, (select id from public.profiles where phone = '{BOTS['ada']}') ada,
             (select id from public.profiles where phone = '{BOTS['come']}') come
      from public.event_announcements a join public.events ev on ev.id = a.event_id
      where ev.title = 'Test annonce concurrence (bots)' order by a.requested_at desc limit 1;""")
    row = made[-1]
    try:
        results: dict = {}
        threads = [threading.Thread(target=_answer_in_parallel, args=(row["id"], row["ada"], True, results)),
                   threading.Thread(target=_answer_in_parallel, args=(row["id"], row["come"], False, results))]
        for t in threads:
            t.start()
            time.sleep(0.3)
        for t in threads:
            t.join()
        answers = [r[0]["r"] for r in results.values()]
        assert sorted(a["already"] for a in answers) == [False, True], results
        final = sql_test(f"select status, (select count(*) from public.notifications where kind in ('announce_accepted', 'announce_refused') and event_id = '{row['event_id']}') told from public.event_announcements where id = '{row['id']}'")
        assert final[0]["status"] in ("accepted", "refused") and final[0]["told"] == 1, final
    finally:
        sql_test(f"delete from public.notifications where event_id = '{row['event_id']}' or data->>'target_event' = '{row['event_id']}';"
                 f"delete from public.events where id = '{row['event_id']}'")


def test_the_organizer_turns_the_announcement_on_after_publishing_without_edit_rights():
    """Feuille « Inviter » / fiche : seul « Prévenir le groupe » change, même sans « modifier un événement publié »."""
    out = run(as_postgres() + """
      delete from public.role_permissions where role = 'organizer' and perm = 'events.edit_own_published';""" + olga_event(announce=False) + """
      update public.events set announce_group = true where id = e;
      begin update public.events set title = 'Titre changé' where id = e; r := '{"titre": "changé"}';
        exception when others then r := '{"titre": "refusé"}'; end;""" + as_postgres() + """
      raise exception 'résultat: annonce=% titre=%', (select status from public.event_announcements where event_id = e), r->>'titre';""")
    assert "résultat: annonce=pending titre=refusé" in out, out


def test_the_screen_knows_whether_the_announcement_goes_directly():
    out = run(as_bot("olga") + """
      r := public.my_announce_modes(array[bots]);""" + as_bot("ada") + """
      r := jsonb_build_object('olga', r->>bots::text, 'ada', public.my_announce_modes(array[bots])->>bots::text);
      raise exception 'résultat: olga=% ada=%', r->>'olga', r->>'ada';""")
    assert "résultat: olga=request ada=direct" in out, out


def test_accepting_a_proposed_group_event_also_sends_the_requested_announcement():
    """Décision du 06.11 (Q3) : groupe « avec validation » + « Prévenir le groupe » → une seule décision. Accepter
    l'événement envoie aussi l'annonce (sans seconde demande) ; refuser l'événement : rien."""
    out = run(as_bot("ada") + """
      perform public.set_group_event_rules(bots2, true, 'request');""" + olga_event(announce=True, group="bots2") + as_bot("ada") + """
      perform public.answer_group_event(e, bots2, true);""" + as_postgres() + f"""
      raise exception 'résultat: annonce=% par_ada=% violette=% demandes=%',
        (select status from public.event_announcements where event_id = e),
        (select answered_by = ada from public.event_announcements where event_id = e),
        {count('private_invite', 'violette')}, {count('announce_request')};""")
    assert "résultat: annonce=accepted par_ada=t violette=1 demandes=0" in out, out
    refused = run(as_bot("ada") + """
      perform public.set_group_event_rules(bots2, true, 'request');""" + olga_event(announce=True, group="bots2") + as_bot("ada") + """
      perform public.answer_group_event(e, bots2, false);""" + as_postgres() + f"""
      raise exception 'résultat: annonces=% notifications=%', (select count(*) from public.event_announcements where event_id = e),
        {count('private_invite')} + {count('announce_request')};""")
    assert "résultat: annonces=0 notifications=0" in refused, refused
