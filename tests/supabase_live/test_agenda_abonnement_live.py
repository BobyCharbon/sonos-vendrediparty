"""Agenda abonné d'un sondage (retour de l'admin du 11.11.2026), sur la base de TEST, bots seulement, tout annulé à la
fin. La personne reçoit son lien secret ; l'agenda (sans compte) voit ses dates votées Oui / Si besoin, puis, la date
fixée, la seule bonne ; une personne sans accès n'obtient pas de lien."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

POLL = olga_event(announce=False) + """
  update public.events set date_mode = 'poll', starts_at = null where id = e;
  insert into public.date_options (event_id, starts_at) values (e, now() + interval '40 days');
  insert into public.date_options (event_id, starts_at) values (e, now() + interval '47 days');
  insert into public.date_options (event_id, starts_at) values (e, now() + interval '54 days');"""

AS_ANON = "execute 'reset role'; perform set_config('request.jwt.claims', json_build_object('role', 'anon')::text, true); execute 'set local role anon';"


def opt(rank: int) -> str:
    return f"(select id from public.date_options where event_id = e order by starts_at offset {rank} limit 1)"


def test_the_subscribed_calendar_follows_my_votes_then_the_fixed_date():
    out = run(POLL + as_bot("victor") + f"""
      insert into public.date_votes (option_id, user_id, vote) values ({opt(0)}, victor, 'yes');
      insert into public.date_votes (option_id, user_id, vote) values ({opt(1)}, victor, 'no');
      insert into public.date_votes (option_id, user_id, vote) values ({opt(2)}, victor, 'if_needed');
      perform set_config('party.t', public.calendar_feed_token(e), true);
      if public.calendar_feed_token(e) <> current_setting('party.t') then raise exception 'jeton changé'; end if;
      {AS_ANON}
      r := public.calendar_feed(current_setting('party.t'));
      n := jsonb_array_length(r->'dates');
      {as_bot('olga')}
      perform public.fix_event_date(e, {opt(0)});
      {AS_ANON}
      raise exception 'résultat: sondage=% actif=% mode=% venir=% inconnu=%', n, r->>'active',
        public.calendar_feed(current_setting('party.t'))->>'date_mode', public.calendar_feed(current_setting('party.t'))->>'my_rsvp',
        coalesce(public.calendar_feed(repeat('0', 36))::text, 'vide');""")
    assert "résultat: sondage=2 actif=true mode=fixed venir=yes inconnu=vide" in out, out


def test_no_vote_yet_means_every_date_and_a_stranger_gets_no_link():
    out = run(POLL + as_bot("victor") + f"""
      perform set_config('party.t', public.calendar_feed_token(e), true);
      {AS_ANON}
      n := jsonb_array_length(public.calendar_feed(current_setting('party.t'))->'dates');
      {as_postgres()}
      {as_bot('violette')}
      begin
        perform public.calendar_feed_token(e);
        m := 1;
      exception when others then m := 0;
      end;
      raise exception 'résultat: dates=% inconnu_a_un_lien=%', n, m;""")
    assert "résultat: dates=3 inconnu_a_un_lien=0" in out, out


def test_the_table_is_closed_to_everyone():
    out = run(POLL + as_bot("victor") + """
      perform public.calendar_feed_token(e);
      begin
        perform count(*) from public.calendar_feeds;
        m := 1;
      exception when others then m := 0;
      end;
      raise exception 'résultat: lecture=%', m;""")
    assert "résultat: lecture=0" in out, out
