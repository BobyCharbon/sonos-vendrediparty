"""« Réunir les invités dans un groupe » (décision de l'admin du 17.11.2026, migration 20261117110000), sur la VRAIE base
de TEST, bots seulement, tout annulé (transactions rollback) :
- l'option se règle par l'organisatrice sur un groupe qu'elle gère ET dont elle fait partie, jamais Membres Vendredi Party ;
- la case est DÉCOCHÉE par défaut : l'écran envoie join_group true/false ; cochée, l'invitée entre pour chacune des trois
  réponses ; décochée ou sans paramètre, jamais ;
- jamais en blocage (organisatrice ou créateur du groupe), jamais partie du groupe, jamais avec un profil incomplet ;
- notification personnelle « group_added », aucune aux membres (le créateur garde « X a rejoint ton groupe ») ;
- bandeau une seule fois, « Rejoindre le groupe » pour qui avait répondu avant, accord de l'organisatrice ;
- « Garder cette bande ? » : invitations à accepter, une seule fois, jamais ceux qui ont décoché ;
- invite_to_group refuse une personne en blocage avec le créateur du groupe.
Bot Ada a créé le groupe « Bots » (Côme, Olga, Victor, Valentin) ; Bot Violette n'en fait pas partie."""
import json

from tests.supabase_live.test_annonces_groupe_live import BOTS, SETUP, as_bot, as_postgres
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

DECLARE = "e uuid; e2 uuid; a uuid; g uuid; n int; m int; r jsonb; s text; bots uuid; bots2 uuid; " + " ".join(f"{k} uuid;" for k in BOTS)


def run(body: str) -> str:
    rows = sql_test(f"""
    begin;
    do $$ declare {DECLARE} begin
      {SETUP}
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False)


def ada_event(var: str = "e", days: str = "30 days", group: bool = True) -> str:
    """Événement « sur invitation » de Bot Ada (créatrice du groupe Bots), groupe des invités = Bots, lien d'Ada dans a."""
    return as_bot("ada") + f"""
      insert into public.events (title, status, visibility, public_link, notify_on_publish, announce_group, starts_at)
        values ('Test raclette bots', 'draft', 'invited', false, false, false, now() + interval '{days}') returning id into {var};
      update public.events set status = 'published' where id = {var};
      {f"perform public.set_event_guest_group({var}, bots);" if group else ""}
      r := public.create_event_invite({var}, 0, null, 'Tout le monde');
      a := (r->>'token')::uuid;"""


IN_GROUP = "(select count(*) from public.member_group_members where group_id = bots and user_id = violette)"


def test_ticked_she_joins_whatever_her_answer():
    for answer in ("yes", "maybe", "no"):
        out = run(ada_event() + as_bot("violette") + f"""
          r := public.accept_invite_group(a, '{answer}', true);""" + as_postgres() + f"""
          raise exception 'résultat: statut=% groupe=% reponse=%', r->'guest_group'->>'status', {IN_GROUP},
            (select status from public.rsvps where event_id = e and user_id = violette);""")
        assert f"résultat: statut=joined groupe=1 reponse={answer}" in out, (answer, out)


def test_unticked_or_without_the_parameter_she_never_joins():
    out = run(ada_event() + as_bot("violette") + """
      r := public.accept_invite_group(a, 'yes', false);""" + as_postgres() + f"""
      m := {IN_GROUP};
      delete from public.rsvps where event_id = e and user_id = violette;
      delete from private.guest_group_choices where event_id = e;
      delete from private.invite_link_arrivals where token = a;""" + as_bot("violette") + """
      perform public.accept_invite(a, 'maybe');""" + as_postgres() + f"""
      raise exception 'résultat: decoche=% statut=% sans_parametre=% choix=%', m, r->'guest_group'->>'status', {IN_GROUP},
        (select count(*) from private.guest_group_choices where event_id = e);""")
    assert "résultat: decoche=0 statut=declined sans_parametre=0 choix=0" in out, out


def test_the_invite_card_shows_the_box_with_the_group_and_its_size():
    out = run(ada_event() + as_bot("violette") + """
      r := public.invite_preview(a);""" + as_bot("victor") + """
      raise exception 'résultat: groupe=% membres=% hote=% victor=%', r->'guest_group'->>'name',
        (r->'guest_group'->>'members')::int > 1, r->'guest_group'->>'owner' is not null,
        coalesce(public.invite_preview(a)->>'guest_group', 'rien');""")
    # Victor est déjà dans Bots : aucune case pour lui.
    assert "résultat: groupe=Bots membres=t hote=t victor=rien" in out, out


def test_only_a_group_she_manages_and_belongs_to_never_vendredi_party():
    out = run(ada_event(group=False) + as_bot("olga") + """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test olga', 'draft', 'invited', false, false, now() + interval '30 days') returning id into e2;
      begin perform public.set_event_guest_group(e2, bots); m := 1; exception when others then m := 0; end;""" + as_bot("victor") + """
      begin perform public.set_event_guest_group(e, bots); n := 1; exception when others then n := 0; end;""" + as_bot("ada") + """
      begin perform public.set_event_guest_group(e, private.vip_group_id()); s := 'oui'; exception when others then s := 'non'; end;
      begin update public.events set guest_group = private.vip_group_id() where id = e; s := s || '/oui'; exception when others then s := s || '/non'; end;
      raise exception 'résultat: olga_simple_membre=% victor_pas_organisateur=% vendredi_party=%', m, n, s;""")
    assert "résultat: olga_simple_membre=0 victor_pas_organisateur=0 vendredi_party=non/non" in out, out


def test_a_new_group_is_created_with_the_event_and_its_name_is_filtered():
    out = run(ada_event(group=False) + as_bot("ada") + """
      r := public.set_event_guest_group(e, null, 'Raclette chez Ada');
      g := (r->'group'->>'id')::uuid;
      begin perform public.set_event_guest_group(e, null, 'connard'); s := 'accepté'; exception when others then s := 'refusé'; end;
      raise exception 'résultat: nom=% ada_dedans=% insulte=%', r->'group'->>'name',
        (select count(*) from public.member_group_members where group_id = g and user_id = ada), s;""")
    assert "résultat: nom=Raclette chez Ada ada_dedans=1 insulte=refusé" in out, out


def test_never_with_a_block_or_an_incomplete_profile():
    blocked = run(ada_event() + as_postgres() + """
      insert into public.direct_blocks (user_id, blocked_id) values (violette, ada);""" + as_bot("violette") + """
      r := public.accept_invite_group(a, 'yes', true);
      raise exception 'résultat: carte=% statut=% groupe=%', coalesce(public.invite_preview(a)->>'guest_group', 'rien'),
        r->'guest_group'->>'status', """ + IN_GROUP + ";")
    # Le blocage avec Ada empêche déjà de répondre au lien d'Ada : passage par une réponse notée sans le lien.
    if "Tu ne peux pas répondre" in blocked:
        blocked = run(ada_event() + as_postgres() + """
          insert into public.direct_blocks (user_id, blocked_id) values (violette, ada);
          insert into public.event_invites (event_id, user_id, invited_by) values (e, violette, ada);
          insert into public.rsvps (event_id, user_id, status) values (e, violette, 'yes');""" + as_bot("violette") + """
          r := public.set_guest_group_choice(e, true);
          raise exception 'résultat: statut=% groupe=%', r->>'status', """ + IN_GROUP + ";")
        assert "résultat: statut=refused groupe=0" in blocked, blocked
    else:
        assert "statut=refused groupe=0" in blocked, blocked
    incomplete = run(ada_event() + as_postgres() + """
      insert into public.event_invites (event_id, user_id, invited_by) values (e, violette, ada);
      insert into public.rsvps (event_id, user_id, status) values (e, violette, 'no');
      -- Ancien compte au prénom seul (la garde du profil l'interdit aujourd'hui) : simulé le temps de la transaction.
      alter table public.profiles disable trigger profiles_guard;
      update public.profiles set last_name = '' where id = violette;
      alter table public.profiles enable trigger profiles_guard;""" + as_bot("violette") + """
      r := public.set_guest_group_choice(e, true);
      raise exception 'résultat: statut=% groupe=%', r->>'status', """ + IN_GROUP + ";")
    assert "résultat: statut=refused groupe=0" in incomplete, incomplete


def test_someone_who_left_is_never_put_back_except_by_ticking_at_a_new_event():
    out = run(ada_event() + as_bot("violette") + """
      perform public.accept_invite_group(a, 'yes', true);
      delete from public.member_group_members where group_id = bots and user_id = violette;
      r := public.set_guest_group_choice(e, true);
      s := r->>'status';""" + as_postgres() + """
      m := (select count(*) from private.group_departures where group_id = bots and user_id = violette);""" + ada_event("e2") + as_postgres() + """
      update public.events set created_at = now() + interval '1 second' where id = e2;
      update private.group_departures set left_at = now() where group_id = bots and user_id = violette;""" + as_bot("violette") + """
      r := public.accept_invite_group(a, 'maybe', true);""" + as_postgres() + f"""
      raise exception 'résultat: meme_evenement=% depart_note=% nouvel_evenement=% groupe=% depart_efface=%', s, m,
        r->'guest_group'->>'status', {IN_GROUP},
        (select count(*) from private.group_departures where group_id = bots and user_id = violette);""")
    assert "résultat: meme_evenement=refused depart_note=1 nouvel_evenement=joined groupe=1 depart_efface=0" in out, out


def test_a_departure_by_cascade_is_not_noted_and_deleting_the_group_takes_it_away():
    out = run(as_bot("ada") + """
      insert into public.member_groups (name, created_by) values ('Test départs', ada) returning id into g;
      insert into public.member_group_members (group_id, user_id) values (g, victor);""" + as_bot("victor") + """
      delete from public.member_group_members where group_id = g and user_id = victor;""" + as_postgres() + """
      m := (select count(*) from private.group_departures where group_id = g);
      delete from public.member_groups where id = g;
      raise exception 'résultat: depart=% apres_suppression=%', m, (select count(*) from private.group_departures where group_id = g);""")
    assert "résultat: depart=1 apres_suppression=0" in out, out


def test_she_is_told_personally_and_no_member_of_the_group_is():
    out = run(ada_event() + as_bot("violette") + """
      perform public.accept_invite_group(a, 'yes', true);""" + as_postgres() + """
      raise exception 'résultat: perso=% titre=% autorise=% membres=% createur=% annonces=%',
        (select count(*) from public.notifications where user_id = violette and kind = 'group_added' and data->>'group_id' = bots::text),
        (select title from public.notifications where user_id = violette and kind = 'group_added' limit 1),
        (select private.web_push_allowed(x) from public.notifications x where x.user_id = violette and x.kind = 'group_added' limit 1),
        (select count(*) from public.notifications x where x.user_id in (come, olga, victor, valentin)
           and x.created_at >= now() and (x.data->>'group_id' = bots::text or x.event_id = e or x.title like '%Bots%')),
        (select count(*) from public.notifications where user_id = ada and kind = 'group_join' and created_at >= now()),
        (select count(*) from public.event_announcements where event_id = e);""")
    assert "résultat: perso=1 titre=Tu es dans le groupe « Bots » autorise=" in out, out
    assert "membres=0 createur=1 annonces=0" in out, out


def test_the_switch_turns_the_personal_notification_off():
    out = run(ada_event() + as_postgres() + """
      insert into public.notification_prefs (user_id) values (violette) on conflict do nothing;
      update public.notification_prefs set push_enabled = true, group_added = false where user_id = violette;""" + as_bot("violette") + """
      perform public.accept_invite_group(a, 'yes', true);""" + as_postgres() + """
      raise exception 'résultat: envoyee=%', (select private.web_push_allowed(x) from public.notifications x
        where x.user_id = violette and x.kind = 'group_added' limit 1);""")
    assert "résultat: envoyee=f" in out, out


def test_the_banner_shows_once_and_the_guest_card_counts_who_is_in():
    out = run(ada_event() + as_bot("violette") + """
      perform public.accept_invite_group(a, 'yes', true);
      r := public.take_group_join_note(bots);
      s := coalesce(public.take_group_join_note(bots)::text, 'rien');""" + as_bot("ada") + """
      raise exception 'résultat: evenement=% second=% badge=% groupe=%', r->>'event_title', s,
        (select p->>'in_group' from jsonb_array_elements(public.event_guest_list(e)->'people') p where p->>'id' = violette::text),
        public.event_guest_list(e)->'guest_group'->>'name';""")
    assert "résultat: evenement=Test raclette bots second=rien badge=true groupe=Bots" in out, out


def test_who_answered_before_the_option_joins_with_the_button_only():
    out = run(ada_event(group=False) + as_bot("violette") + """
      perform public.accept_invite(a, 'yes');""" + as_bot("ada") + """
      perform public.set_event_guest_group(e, bots);""" + as_bot("violette") + f"""
      r := public.event_guest_group(e);
      m := {IN_GROUP};
      perform public.set_guest_group_choice(e, true);
      raise exception 'résultat: propose=% avant=% apres=%', r->>'offer', m, {IN_GROUP};""")
    assert "résultat: propose=true avant=0 apres=1" in out, out


def test_with_the_organizer_approval_she_joins_when_accepted():
    out = run(ada_event() + as_postgres() + """
      insert into public.event_invites (event_id, user_id, invited_by) values (e, victor, ada);""" + as_bot("victor") + """
      r := public.create_event_invite(e, 0, null, 'Copains de Victor');
      a := (r->>'token')::uuid;""" + as_bot("violette") + """
      r := public.accept_invite_group(a, 'no', true);
      s := r->'guest_group'->>'status';
      m := """ + IN_GROUP + ";" + as_bot("ada") + """
      perform public.decide_join_request(e, violette, true);
      raise exception 'résultat: attente=% avant=% apres=%', s, m, """ + IN_GROUP + ";")
    assert "résultat: attente=pending avant=0 apres=1" in out, out


def test_the_ai_never_sets_the_option_an_event_starts_without_it():
    out = run(as_bot("ada") + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at)
        values ('Test IA', 'draft', 'invited', false, now() + interval '30 days') returning id into e;
      raise exception 'résultat: groupe=%', coalesce((select guest_group::text from public.events where id = e), 'aucun');""")
    assert "résultat: groupe=aucun" in out, out


def test_keep_the_band_invites_once_never_the_unticked():
    out = run(ada_event(days="-1 day") + as_postgres() + """
      insert into public.event_invites (event_id, user_id, invited_by) values (e, victor, ada), (e, violette, ada), (e, valentin, ada);
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'yes'), (e, violette, 'yes'), (e, valentin, 'no');
      insert into private.guest_group_choices (event_id, user_id, join_group) values (e, violette, false);""" + as_bot("ada") + """
      r := public.event_guest_group(e);
      s := (r->'band'->>'present') || '/' || (r->'band'->>'all');
      r := public.keep_band(e, 'present', null, 'Les raclettes');
      g := (r->>'group_id')::uuid;
      begin perform public.keep_band(e, 'all', g); m := 1; exception when others then m := 0; end;""" + as_postgres() + """
      raise exception 'résultat: compte=% invites=% victor=% violette=% entres=% second=%', s, r->>'invited',
        (select count(*) from private.group_invitations where group_id = g and user_id = victor and status = 'pending'),
        (select count(*) from private.group_invitations where group_id = g and user_id = violette),
        (select count(*) from public.member_group_members where group_id = g), m;""")
    # Présents : Victor et Violette (Violette a décoché : jamais invitée) ; tous : + Valentin. Seule Ada est dans le groupe.
    assert "résultat: compte=1/2 invites=1 victor=1 violette=0 entres=1 second=0" in out, out


def test_invite_to_group_refuses_someone_blocked_with_the_group_creator():
    """Un admin du site (pas le créateur) invite dans le groupe d'Ada quelqu'un qui a bloqué Ada : refusé, rien n'est créé."""
    out = run(as_postgres() + """
      insert into public.direct_blocks (user_id, blocked_id) values (violette, ada);
      select id into a from public.profiles where phone = '41790000004';""" + as_bot("a") + """
      begin perform public.invite_to_group(bots, violette); s := 'invitée'; exception when others then s := sqlerrm; end;""" + as_postgres() + """
      raise exception 'résultat: % invitations=% notifs=%', s,
        (select count(*) from private.group_invitations where group_id = bots and user_id = violette and status = 'pending'),
        (select count(*) from public.notifications where user_id = violette and kind = 'group_invite' and created_at >= now());""")
    assert "résultat: blocked: Tu ne peux pas inviter cette personne. invitations=0 notifs=0" in out, out


def test_deleting_a_group_with_members_works():
    """Bug du 17.11 (base de TEST) : supprimer un groupe échouait (la cascade des membres notait un départ vers le groupe
    supprimé). Sa créatrice le supprime, membres et départs compris ; rien ne reste."""
    out = run(as_bot("ada") + """
      insert into public.member_groups (name, created_by) values ('Test suppression', ada) returning id into g;
      insert into public.member_group_members (group_id, user_id) values (g, victor), (g, valentin);""" + as_bot("victor") + """
      delete from public.member_group_members where group_id = g and user_id = victor;""" + as_bot("ada") + """
      delete from public.member_groups where id = g;
      get diagnostics n = row_count;""" + as_postgres() + """
      raise exception 'résultat: supprime=% membres=% departs=%', n,
        (select count(*) from public.member_group_members where group_id = g),
        (select count(*) from private.group_departures where group_id = g);""")
    assert "résultat: supprime=1 membres=0 departs=0" in out, out


def test_the_gathering_event_shows_on_the_group_page_and_list():
    """Recette iPhone du 17.11 : l'événement qui réunit ses invités dans le groupe compte parmi les événements du groupe
    (page du groupe, prochain événement de la liste) pour qui peut le voir (migration 20261117120000)."""
    out = run(ada_event(days="1 minute") + as_bot("violette") + """
      r := public.accept_invite_group(a, 'no', true);
      s := (select string_agg(x->>'id', ',') from jsonb_array_elements(public.group_events(bots)) x);
      raise exception 'résultat: page=% liste=%', coalesce(s, '') like '%' || e::text || '%',
        (select x->'next_event'->>'id' from jsonb_array_elements(public.my_groups_overview()) x where x->>'id' = bots::text) = e::text;""")
    assert "résultat: page=t liste=t" in out, out
