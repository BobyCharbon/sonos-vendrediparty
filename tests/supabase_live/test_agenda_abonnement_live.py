"""Agenda abonné « Vendredi Party » (retours de l'admin du 11.11.2026), sur la base de TEST, bots seulement, tout annulé
à la fin. Un seul lien par personne ; chaque événement ajouté y apparaît et suit ses changements (date, lieu, titre,
description) ; sondage : dates votées Oui / Si besoin puis la seule date fixée ; une personne sans accès n'obtient rien."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

POLL = olga_event(announce=False) + """
  update public.events set date_mode = 'poll', starts_at = null where id = e;
  insert into public.date_options (event_id, starts_at) values (e, now() + interval '40 days');
  insert into public.date_options (event_id, starts_at) values (e, now() + interval '47 days');
  insert into public.date_options (event_id, starts_at) values (e, now() + interval '54 days');"""

AS_ANON = "execute 'reset role'; perform set_config('request.jwt.claims', json_build_object('role', 'anon')::text, true); execute 'set local role anon';"
MINE = "(public.calendar_feed(current_setting('party.t'))->'events'->0)"
# Victor sans agenda encore abonné (annulé avec le reste de la transaction).
FRESH_VICTOR = "delete from public.calendar_feeds where user_id = victor;"
OUT_OF_BOTS = "delete from public.member_group_members where group_id = bots and user_id = victor;"


def test_removed_from_the_group_the_event_leaves_the_agenda_and_nothing_leaks():
    """Question de l'admin (11.11) : retiré du groupe, plus invité → l'agenda ne montre plus rien, même pas le titre."""
    out = run(olga_event(announce=False) + as_bot("victor") + f"""
      perform set_config('party.t', public.calendar_feed_token(e, true)->>'token', true);
      {AS_ANON}
      n := jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'events');
      {as_postgres()}
      {OUT_OF_BOTS}
      {AS_ANON}
      r := public.calendar_feed(current_setting('party.t'));
      raise exception 'résultat: membre=% retiré=% titre_visible=%', n, jsonb_array_length(r->'events'),
        (r::text like '%Test annonce bots%')::text;""")
    assert "résultat: membre=1 retiré=0 titre_visible=false" in out, out


def test_an_event_made_private_or_cancelled_leaves_the_agenda():
    out = run(olga_event(announce=False, public=True) + as_postgres() + OUT_OF_BOTS + as_bot("victor") + f"""
      perform set_config('party.t', public.calendar_feed_token(e, true)->>'token', true);
      {AS_ANON}
      n := jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'events');
      {as_bot('olga')}
      update public.events set visibility = 'invited', public_link = false where id = e;
      {AS_ANON}
      m := jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'events');
      {as_bot('olga')}
      update public.events set visibility = 'all', public_link = true, status = 'cancelled' where id = e;
      {AS_ANON}
      raise exception 'résultat: public=% prive=% annule=%', n, m,
        jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'events');""")
    assert "résultat: public=1 prive=0 annule=0" in out, out


def test_reading_the_agenda_does_not_change_who_the_caller_is():
    out = run(olga_event(announce=False) + as_bot("victor") + f"""
      perform set_config('party.t', public.calendar_feed_token(e, true)->>'token', true);
      {AS_ANON}
      perform public.calendar_feed(current_setting('party.t'));
      raise exception 'résultat: apres=%', coalesce(auth.uid()::text, 'personne');""")
    assert "résultat: apres=personne" in out, out


def opt(rank: int) -> str:
    return f"(select id from public.date_options where event_id = e order by starts_at offset {rank} limit 1)"


def test_the_subscribed_calendar_follows_my_votes_then_the_fixed_date():
    out = run(POLL + as_bot("victor") + f"""
      insert into public.date_votes (option_id, user_id, vote) values ({opt(0)}, victor, 'yes');
      insert into public.date_votes (option_id, user_id, vote) values ({opt(1)}, victor, 'no');
      insert into public.date_votes (option_id, user_id, vote) values ({opt(2)}, victor, 'if_needed');
      r := public.calendar_feed_token(e, true);
      perform set_config('party.t', r->>'token', true);
      if public.calendar_feed_token(e, true)->>'token' <> current_setting('party.t') then raise exception 'jeton changé'; end if;
      {AS_ANON}
      r := {MINE};
      n := jsonb_array_length(r->'dates');
      {as_bot('olga')}
      perform public.fix_event_date(e, {opt(0)});
      {AS_ANON}
      raise exception 'résultat: sondage=% actif=% mode=% venir=% inconnu=%', n, r->>'active',
        {MINE}->>'date_mode', {MINE}->>'my_rsvp',
        coalesce(public.calendar_feed(repeat('0', 36))::text, 'vide');""")
    assert "résultat: sondage=2 actif=true mode=fixed venir=yes inconnu=vide" in out, out


def test_one_link_per_person_any_event_follows_its_changes_and_knows_when_subscribed():
    out = run(FRESH_VICTOR + olga_event(announce=False) + as_bot("victor") + f"""
      r := public.calendar_feed_token(e, true);
      perform set_config('party.t', r->>'token', true);
      m := case when (r->>'subscribed')::boolean then 1 else 0 end;
      {as_bot('olga')}
      update public.events set title = 'Soirée déplacée', location_name = 'Chez Olga', description = 'Nouveau programme',
        starts_at = now() + interval '9 days', ends_at = null where id = e;
      {AS_ANON}
      r := {MINE};
      {as_bot('victor')}
      raise exception 'résultat: avant=% après=% titre=% lieu=% desc=% mode=% n=%', m,
        public.calendar_feed_token(e, true)->>'subscribed', r->>'title', r->>'location', r->>'description', r->>'date_mode',
        jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'events');""")
    assert "résultat: avant=0 après=true titre=Soirée déplacée lieu=Chez Olga desc=Nouveau programme mode=fixed n=1" in out, out


def test_no_vote_yet_means_every_date_and_a_stranger_gets_no_link():
    out = run(POLL + as_bot("victor") + f"""
      perform set_config('party.t', public.calendar_feed_token(e, true)->>'token', true);
      {AS_ANON}
      n := jsonb_array_length({MINE}->'dates');
      {as_postgres()}
      {as_bot('violette')}
      begin
        perform public.calendar_feed_token(e, true);
        m := 1;
      exception when others then m := 0;
      end;
      raise exception 'résultat: dates=% inconnu_a_un_lien=%', n, m;""")
    assert "résultat: dates=3 inconnu_a_un_lien=0" in out, out


def test_the_tables_are_closed_to_everyone():
    out = run(POLL + as_bot("victor") + """
      perform public.calendar_feed_token(e, true);
      begin
        perform count(*) from public.calendar_feeds;
        m := 1;
      exception when others then m := 0;
      end;
      begin
        perform count(*) from public.calendar_feed_events;
        n := 1;
      exception when others then n := 0;
      end;
      raise exception 'résultat: lecture=% %', m, n;""")
    assert "résultat: lecture=0 0" in out, out


def test_opening_the_sheet_adds_nothing_only_the_tap_does():
    out = run(olga_event(announce=False) + as_bot("victor") + f"""
      r := public.calendar_feed_token(e);
      perform set_config('party.t', r->>'token', true);
      m := case when (r->>'added')::boolean then 1 else 0 end;
      {AS_ANON}
      n := jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'events');
      {as_bot('victor')}
      raise exception 'résultat: ouvert=% % ajouté=%', m, n, public.calendar_feed_token(e, true)->>'added';""")
    assert "résultat: ouvert=0 0 ajouté=true" in out, out
