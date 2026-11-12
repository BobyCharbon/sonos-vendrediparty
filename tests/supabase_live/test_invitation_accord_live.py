"""Accord de l'organisateur (décision de l'admin du 12.11.2026), sur la base de TEST, bots seulement, tout annulé :
sur un événement sans lien public (sur invitation, groupe, Membres Vendredi Party), une personne arrivée par le lien d'un
INVITÉ attend l'accord de l'organisateur avant de voir l'événement ; les liens de l'organisateur et des co-organisateurs
font entrer directement ; un événement public ne change pas.
Événement de Bot Olga réservé au groupe « Bots » (Ada, Côme, Victor, Valentin) ; Bot Violette n'en fait pas partie."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

VICTOR_LINK = olga_event(announce=False) + as_bot("victor") + """
  r := public.create_event_invite(e, 0, null, 'Collègues');
  a := (r->>'token')::uuid;"""


def test_someone_invited_by_a_guest_waits_for_the_organizer():
    out = run(VICTOR_LINK + as_bot("violette") + """
      r := public.invite_preview(a);
      m := case when (r->>'approval')::boolean then 1 else 0 end;
      r := public.accept_invite(a, 'yes');
      raise exception 'résultat: accord_annonce=% en_attente=% voit=% carte=%', m, r->>'pending', public.can_see_event(e),
        public.invite_preview(a)->>'state';""")
    assert "résultat: accord_annonce=1 en_attente=true voit=f carte=waiting" in out, out


def test_the_organizer_sees_the_request_and_is_notified():
    out = run(VICTOR_LINK + as_bot("violette") + """
      perform public.accept_invite(a, 'maybe');""" + as_bot("olga") + """
      r := public.event_guest_list(e);""" + as_postgres() + """
      raise exception 'résultat: demandes=% par=% reponse=% liste=% notif=%', jsonb_array_length(r->'requests'),
        r->'requests'->0->>'invited_by', r->'requests'->0->>'answer',
        (select count(*) from jsonb_array_elements(r->'people') p where p->>'id' = violette::text),
        (select count(*) from public.notifications x where x.user_id = olga and x.event_id = e and x.kind = 'join_request'
           and x.body like '%aimerait venir%' and private.web_push_allowed(x));""")
    assert "résultat: demandes=1 par=Bot Victor reponse=maybe liste=0 notif=1" in out, out


def test_accepted_the_person_sees_the_event_with_her_answer_and_one_notification():
    out = run(VICTOR_LINK + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("olga") + """
      r := public.decide_join_request(e, violette, true);""" + as_bot("violette") + """
      m := case when public.can_see_event(e) then 1 else 0 end;""" + as_postgres() + """
      raise exception 'résultat: voit=% vient=% demandes=% notifs=%', m,
        (select status from public.rsvps where event_id = e and user_id = violette), jsonb_array_length(r->'requests'),
        (select count(*) from public.notifications where user_id = violette and event_id = e and kind = 'private_invite');""")
    assert "résultat: voit=1 vient=yes demandes=0 notifs=1" in out, out


def test_refused_the_person_never_sees_the_event_and_cannot_retry():
    out = run(VICTOR_LINK + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("olga") + """
      perform public.decide_join_request(e, violette, false);""" + as_bot("valentin") + """
      r := public.create_event_invite(e, 1);""" + as_bot("violette") + """
      begin perform public.accept_invite((r->>'token')::uuid, 'yes'); m := 1; exception when others then m := 0; end;
      raise exception 'résultat: voit=% nouvel_essai=% carte=%', public.can_see_event(e), m, public.invite_preview(a)->>'state';""")
    assert "résultat: voit=f nouvel_essai=0 carte=refused" in out, out


def test_only_organizers_decide():
    out = run(VICTOR_LINK + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("victor") + """
      begin perform public.decide_join_request(e, violette, true); m := 1; exception when others then m := 0; end;
      raise exception 'résultat: victor=%', m;""")
    assert "résultat: victor=0" in out, out


def test_the_guest_sees_a_waiting_arrival_without_a_name():
    out = run(VICTOR_LINK + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("victor") + """
      r := public.event_guest_list(e);
      raise exception 'résultat: arrivee=% nom=% viennent=%', r->'links'->0->'arrivals'->0->>'request',
        coalesce(r->'links'->0->'arrivals'->0->>'name', 'aucun'), r->'counts'->>'yes';""")
    assert "résultat: arrivee=pending nom=aucun viennent=0" in out, out


def test_links_of_the_organizer_and_co_organizers_let_people_in_directly():
    out = run(olga_event(announce=False) + as_bot("olga") + """
      insert into public.event_organizers (event_id, user_id) values (e, valentin);
      r := public.create_event_invite(e, 1);
      a := (r->>'token')::uuid;""" + as_bot("valentin") + """
      r := public.create_event_invite(e, 1);""" + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');
      m := case when public.can_see_event(e) then 1 else 0 end;""" + as_postgres() + """
      delete from public.event_invites where event_id = e and user_id = violette;
      delete from public.rsvps where event_id = e and user_id = violette;""" + as_bot("violette") + """
      perform public.accept_invite((r->>'token')::uuid, 'yes');
      n := case when public.can_see_event(e) then 1 else 0 end;""" + as_postgres() + """
      raise exception 'résultat: lien_olga=% lien_coorga=% demandes=%', m, n,
        (select count(*) from public.event_join_requests where event_id = e);""")
    assert "résultat: lien_olga=1 lien_coorga=1 demandes=0" in out, out


def test_a_public_event_does_not_ask_for_approval():
    out = run(olga_event(announce=False, public=True) + as_bot("victor") + """
      r := public.create_event_invite(e, 1);""" + as_bot("violette") + """
      r := public.accept_invite((r->>'token')::uuid, 'yes');
      raise exception 'résultat: en_attente=% vient=%', coalesce(r->>'pending', 'non'), r->>'status';""")
    assert "résultat: en_attente=non vient=yes" in out, out


def test_a_co_organizer_sees_the_request_in_activity_and_accepts_it():
    out = run(VICTOR_LINK + as_bot("olga") + """
      insert into public.event_organizers (event_id, user_id) values (e, ada);""" + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("ada") + """
      r := public.my_join_requests();
      m := jsonb_array_length(r);
      perform public.decide_join_request(e, violette, true);""" + as_bot("valentin") + """
      n := jsonb_array_length(public.my_join_requests());""" + as_bot("violette") + """
      raise exception 'résultat: ada_voit=% titre=% valentin_voit=% violette_voit=%', m, r->0->>'title', n, public.can_see_event(e);""")
    assert "résultat: ada_voit=1 titre=Test annonce bots valentin_voit=0 violette_voit=t" in out, out
