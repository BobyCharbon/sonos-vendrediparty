"""Menu de partage commun (avis 83ebee37aa0f de l'admin, 11.11.2026), sur la base de TEST, bots seulement, tout annulé :
un invité voit les CHIFFRES de l'événement (jamais un nom), crée ses propres liens nommés, les arrête ; une personne qui
ne voit pas l'événement n'a rien ; l'organisatrice garde la liste complète et voit les liens de ses invités.
Événement de Bot Olga réservé au groupe « Bots » (Ada, Côme, Victor, Valentin) ; Bot Violette n'en fait pas partie."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

ANSWERS = olga_event(announce=False) + as_bot("ada") + """
  insert into public.rsvps (event_id, user_id, status) values (e, ada, 'yes');""" + as_bot("come") + """
  insert into public.rsvps (event_id, user_id, status) values (e, come, 'maybe');"""


def test_a_guest_sees_the_numbers_never_the_names():
    out = run(ANSWERS + as_bot("victor") + """
      r := public.event_guest_list(e);
      raise exception 'résultat: invite=% viennent=% peut_etre=% personnes=% noms=%', r->>'guest', r->'counts'->>'yes',
        r->'counts'->>'maybe', jsonb_array_length(r->'people'), r::text like '%Bot Ada%' or r::text like '%Bot Côme%';""")
    assert "résultat: invite=true viennent=1 peut_etre=1 personnes=0 noms=f" in out, out


def test_the_organizer_still_sees_everyone():
    out = run(ANSWERS + as_bot("olga") + """
      r := public.event_guest_list(e);
      raise exception 'résultat: invite=% ada=%', coalesce(r->>'guest', 'non'), r::text like '%Bot Ada%';""")
    assert "résultat: invite=non ada=t" in out, out


def test_someone_who_does_not_see_the_event_gets_nothing():
    out = run(ANSWERS + as_bot("violette") + """
      begin perform public.event_guest_list(e); m := 1; exception when others then m := 0; end;
      begin perform public.create_event_invite(e, 0, null, 'Pirate'); n := 1; exception when others then n := 0; end;
      raise exception 'résultat: liste=% lien=%', m, n;""")
    assert "résultat: liste=0 lien=0" in out, out


def test_a_guest_creates_a_named_link_sees_it_and_the_organizer_too():
    out = run(ANSWERS + as_bot("victor") + """
      r := public.create_event_invite(e, 0, null, 'Groupe foot');
      a := (r->>'token')::uuid;
      r := public.event_guest_list(e);""" + as_bot("olga") + """
      raise exception 'résultat: mes_liens=% nom=% chez_olga=%', jsonb_array_length(r->'links'), r->'links'->0->>'label',
        (select count(*) from jsonb_array_elements(public.event_guest_list(e)->'links') l
          where l->>'token' = a::text and l->>'created_by_id' = victor::text);""")
    assert "résultat: mes_liens=1 nom=Groupe foot chez_olga=1" in out, out


def test_a_guest_only_sees_his_own_links_and_never_who_came_by_name():
    out = run(ANSWERS + as_bot("olga") + """
      perform public.create_event_invite(e, 1, null, 'Pour Léa');""" + as_bot("victor") + """
      r := public.create_event_invite(e, 0, null, 'Collègues');
      a := (r->>'token')::uuid;""" + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("victor") + """
      r := public.event_guest_list(e);
      raise exception 'résultat: liens=% reponses=% nom=% viennent=%', jsonb_array_length(r->'links'),
        jsonb_array_length(r->'links'->0->'arrivals'), coalesce(r->'links'->0->'arrivals'->0->>'name', 'aucun'),
        r->'counts'->>'yes';""")
    # Violette arrive par le lien d'un invité : elle attend l'accord de l'organisatrice (12.11), elle ne compte pas encore.
    assert "résultat: liens=1 reponses=1 nom=aucun viennent=1" in out, out


def test_a_guest_stops_his_own_link_but_another_guest_cannot():
    out = run(ANSWERS + as_bot("victor") + """
      r := public.create_event_invite(e, 0, null, 'Collègues');
      a := (r->>'token')::uuid;""" + as_bot("valentin") + """
      begin perform public.revoke_invite_link(a); m := 1; exception when others then m := 0; end;""" + as_bot("victor") + """
      perform public.revoke_invite_link(a);""" + as_postgres() + """
      raise exception 'résultat: valentin=% arrete=%', m, (select revoked_at is not null from private.invite_links where token = a);""")
    assert "résultat: valentin=0 arrete=t" in out, out


def test_a_guest_has_at_most_twenty_waiting_links():
    out = run(ANSWERS + as_bot("victor") + """
      for n in 1..20 loop perform public.create_event_invite(e, 1); end loop;
      begin perform public.create_event_invite(e, 1); m := 1; exception when others then m := 0; end;
      raise exception 'résultat: vingt_et_unieme=%', m;""")
    assert "résultat: vingt_et_unieme=0" in out, out
