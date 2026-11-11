"""Invitations : corrections de la recette réelle du 10.11.2026 (migration 20261110100100_invitations_recette), sur la
VRAIE base de TEST, comptes des bots seulement, dans des transactions ANNULÉES (rien ne reste) :
- un lien « Après l'événement » d'un sondage suit la date fixée ; une durée choisie (3 jours) ne bouge pas ;
- supprimer l'événement supprime ses liens ;
- un membre retiré du groupe garde le sondage où il a voté ;
- un membre quitte lui-même un groupe, jamais le groupe Membres Vendredi Party.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_invitations_recette_live.py -q"""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

POLL = as_bot("olga") + """
  insert into public.events (title, status, visibility, notify_on_publish, date_mode, starts_at)
    values ('[Recette] Sondage lien', 'published', 'invited', false, 'poll', null) returning id into e;"""


def test_a_default_link_follows_the_fixed_date_and_a_chosen_duration_does_not_move():
    out = run(POLL + """
      r := public.create_event_invite(e, 5);
      r := r || jsonb_build_object('short', public.create_event_invite(e, 5, now() + interval '3 days'));""" + as_postgres() + """
      update public.events set starts_at = now() + interval '40 days' where id = e;
      raise exception 'résultat: suit=% fixe=%',
        (select round(extract(epoch from expires_at - (now() + interval '41 days')) / 3600)
           from private.invite_links where token = (r->>'token')::uuid),
        (select round(extract(epoch from expires_at - (now() + interval '3 days')) / 3600)
           from private.invite_links where token = (r->'short'->>'token')::uuid);""")
    assert "résultat: suit=0 fixe=0" in out, out


def test_deleting_the_event_deletes_its_links():
    out = run(POLL + """
      r := public.create_event_invite(e, 5);""" + as_postgres() + """
      delete from public.events where id = e;
      raise exception 'résultat: liens=%', (select count(*) from private.invite_links where target = e);""")
    assert "résultat: liens=0" in out, out


def test_a_member_removed_from_the_group_keeps_the_poll_he_voted_on():
    out = run(as_bot("olga") + """
      insert into public.events (title, status, visibility, notify_on_publish, date_mode, starts_at)
        values ('[Recette] Sondage groupe', 'draft', 'invited', false, 'poll', null) returning id into e;
      insert into public.event_groups (event_id, group_id) values (e, bots);
      insert into public.date_options (event_id, starts_at) values (e, now() + interval '20 days') returning id into a;
      update public.events set status = 'published' where id = e;""" + as_bot("victor") + """
      insert into public.date_votes (option_id, user_id, vote) values (a, victor, 'yes');""" + as_postgres() + """
      delete from public.member_group_members where group_id = bots and user_id in (victor, valentin);""" + as_bot("victor") + """
      select count(*) into n from public.events where id = e;""" + as_bot("valentin") + """
      select count(*) into m from public.events where id = e;""" + as_postgres() + """
      raise exception 'résultat: votant_voit=% non_votant_voit=%', n, m;""")
    assert "résultat: votant_voit=1 non_votant_voit=0" in out, out


def test_a_member_leaves_a_group_himself_but_never_the_members_group():
    out = run(as_postgres() + """
      select count(*) into m from public.member_group_members mm join public.member_groups g on g.id = mm.group_id
        where g.system_key is not null and mm.user_id = victor;""" + as_bot("victor") + """
      delete from public.member_group_members where group_id = bots and user_id = victor;
      delete from public.member_group_members mm using public.member_groups g
        where g.id = mm.group_id and g.system_key is not null and mm.user_id = victor;""" + as_postgres() + """
      raise exception 'résultat: victor_bots=% systeme_garde=% systeme=%',
        (select count(*) from public.member_group_members where group_id = bots and user_id = victor),
        (select count(*) from public.member_group_members mm join public.member_groups g on g.id = mm.group_id
          where g.system_key is not null and mm.user_id = victor) = m, m;""")
    assert "résultat: victor_bots=0 systeme_garde=t" in out, out


INVITED = as_bot("olga") + """
  insert into public.events (title, status, visibility, notify_on_publish, starts_at)
    values ('[Recette] Détails liens', 'published', 'invited', false, now() + interval '20 days') returning id into e;"""


def test_a_removed_guest_sees_it_on_the_card_and_his_place_goes_back_to_the_link():
    out = run(INVITED + """
      r := public.create_event_invite(e, 5);""" + as_bot("violette") + """
      perform public.accept_invite((r->>'token')::uuid, 'yes');""" + as_postgres() + """
      select uses into n from private.invite_links where token = (r->>'token')::uuid;""" + as_bot("olga") + """
      perform public.remove_invitee(e, violette);""" + as_bot("violette") + """
      r := r || jsonb_build_object('card', public.invite_preview((r->>'token')::uuid));""" + as_postgres() + """
      raise exception 'résultat: avant=% apres=% etat=% evenement=% places=%', n,
        (select uses from private.invite_links where token = (r->>'token')::uuid),
        r->'card'->>'state', coalesce(r->'card'->>'event_id', 'aucun'), r->'card'->>'places_left';""")
    assert "résultat: avant=1 apres=0 etat=removed evenement=aucun places=5" in out, out


def test_someone_already_invited_opening_a_used_link_is_led_to_the_event():
    out = run(INVITED + """
      insert into public.event_invites (event_id, user_id) values (e, valentin);
      r := public.create_event_invite(e, 1);""" + as_bot("victor") + """
      perform public.accept_invite((r->>'token')::uuid, 'yes');""" + as_bot("valentin") + """
      r := public.invite_preview((r->>'token')::uuid);""" + as_postgres() + """
      raise exception 'résultat: etat=% deja=% evenement=% places=% multi=%', r->>'state', r->>'already',
        (r->>'event_id')::uuid = e, coalesce(r->>'places_left', 'aucune'), r->>'multi';""")
    assert "résultat: etat=full deja=true evenement=t places=aucune multi=false" in out, out


def test_a_guest_sees_the_nickname_of_the_members_of_his_group():
    out = run("""
      select id into a from public.profiles where phone = '41790000006';  -- Guest de test (sans droit de voir les membres)
      insert into public.member_group_members (group_id, user_id) values (bots, a);""" + as_bot("a") + """
      select count(*) into n from public.profiles where id = ada;          -- Ada : même groupe
      select count(*) into m from public.profiles where id = violette;     -- Violette : aucun groupe en commun""" + as_postgres() + """
      raise exception 'résultat: voit_tout=% meme_groupe=% autre=%',
        (select public.has_perm('events.view') from (select set_config('request.jwt.claims', json_build_object('sub', a)::text, true)) x),
        n, m;""")
    assert "meme_groupe=1 autre=0" in out, out
