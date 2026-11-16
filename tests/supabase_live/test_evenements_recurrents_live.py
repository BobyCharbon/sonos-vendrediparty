"""Événements récurrents (demande de l'admin du 16.11.2026, migration 20261116170000), sur la VRAIE base de TEST, bots
seulement, transactions ANNULÉES :
- une seule occurrence à la fois : la suivante n'est créée qu'une fois la précédente terminée ;
- elle reprend titre, options, co-organisateurs et invités ajoutés un à un ; jamais les réponses ni les invités venus par lien ;
- « jusqu'au » arrête la série ; « Ne se répète pas » aussi ; seuls les organisateurs choisissent ; jamais un sondage de dates ;
- chaque mois compté depuis la première date (31 janvier → 28 février → 31 mars), heure de Suisse.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_evenements_recurrents_live.py -q"""
from tests.supabase_live.test_bar_options_live import as_bot, as_postgres, keep, note, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

# Lundi passé, terminé depuis une semaine ; la prochaine (dans 2 h) n'est pas encore passée.
PAST = as_postgres() + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, ends_at, created_by, allow_maybe)
        values ('[Recette] Sbire', 'published', 'invited', false, now() - interval '7 days' + interval '2 hours',
                now() - interval '7 days' + interval '3 hours', olga, false) returning id into e;
      insert into public.event_organizers (event_id, user_id) values (e, come);
      insert into public.event_invites (event_id, user_id) values (e, ada);
      insert into public.event_invites (event_id, user_id, via_link) values (e, victor, true);
      insert into public.rsvps (event_id, user_id, status) values (e, ada, 'yes');"""

NEXT = "(select x.id from public.events x where x.series_id = (select series_id from public.events where id = e) and x.id <> e)"


def test_the_next_date_appears_once_the_previous_one_is_over_with_the_same_people_but_no_answers():
    out = run(PAST + as_bot("olga") + "perform public.set_event_recurrence(e, 'weekly', 1, null);" + as_postgres()
              + keep("made", "private.spawn_series()")
              + "srv := " + NEXT + ";"
              + keep("gap", "(select starts_at - (select starts_at from public.events where id = e) from public.events where id = srv)")
              + keep("dur", "(select ends_at - starts_at from public.events where id = srv)")
              + keep("same", "(select title = '[Recette] Sbire' and status = 'published' and not allow_maybe and visibility = 'invited' "
                             "from public.events where id = srv)")
              + keep("orga", "(select count(*) from public.event_organizers where event_id = srv and user_id = come)")
              + keep("ada", "(select count(*) from public.event_invites where event_id = srv and user_id = ada)")
              + keep("victor_by_link", "(select count(*) from public.event_invites where event_id = srv and user_id = victor)")
              + keep("answers", "(select count(*) from public.rsvps where event_id = srv)")
              # La nouvelle n'est pas terminée : rien de plus, même en relançant.
              + keep("again", "private.spawn_series()"))
    assert "made=1" in out and "gap=7 days" in out and "dur=01:00:00" in out and "same=true" in out, out
    assert "orga=1" in out and "ada=1" in out and "victor_by_link=0" in out and "answers=0" in out, out
    assert "again=0" in out, out


def test_nothing_appears_while_the_current_date_is_not_over():
    out = run(as_postgres() + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by)
        values ('[Recette] Pas encore', 'published', 'invited', false, now() + interval '1 day', olga) returning id into e;"""
              + as_bot("olga") + "perform public.set_event_recurrence(e, 'daily', 1, null);" + as_postgres()
              + keep("made", "private.spawn_series()") + keep("count", "(select count(*) from public.events x "
                     "where x.series_id = (select series_id from public.events where id = e))"))
    assert "made=0" in out and "count=1" in out, out


def test_until_and_stop_end_the_series():
    out = run(PAST + as_bot("olga") + "perform public.set_event_recurrence(e, 'weekly', 1, (now() - interval '1 day')::date);"
              + as_postgres() + keep("until_made", "private.spawn_series()")
              + keep("stopped", "(select stopped_at is not null from public.event_series s join public.events x on x.series_id = s.id where x.id = e)")
              + as_bot("olga") + "perform public.set_event_recurrence(e, 'weekly', 1, null);"
              + "perform public.set_event_recurrence(e, 'none');"
              + as_postgres() + keep("stop_made", "private.spawn_series()"))
    assert "until_made=0" in out and "stopped=true" in out and "stop_made=0" in out, out


def test_only_organizers_choose_and_never_on_a_date_poll():
    out = run(PAST + as_bot("victor") + note("victor", "perform public.set_event_recurrence(e, 'weekly', 1, null)")
              + as_bot("come") + note("coorga", "perform public.set_event_recurrence(e, 'monthly', 1, null)")
              + as_postgres() + "update public.events set date_mode = 'poll', starts_at = null, ends_at = null where id = e;"
              + "update public.event_series set stopped_at = now();"
              + "update public.events set series_id = null where id = e;"
              + as_bot("olga") + note("poll", "perform public.set_event_recurrence(e, 'weekly', 1, null)"))
    assert "victor=forbidden" in out and "coorga=ok" in out, out
    assert "poll=Un événement qui se répète a une date fixée" in out, out


def test_each_month_counts_from_the_first_date_in_swiss_time():
    rule = "row(gen_random_uuid(), 'monthly', 1, null, timestamp '2026-01-31 20:00', 0, null, null, now())::public.event_series"
    out = run(as_postgres()
              + keep("feb", f"to_char(private.series_start({rule}, 1) at time zone 'Europe/Zurich', 'YYYY-MM-DD HH24:MI')")
              + keep("mar", f"to_char(private.series_start({rule}, 2) at time zone 'Europe/Zurich', 'YYYY-MM-DD HH24:MI')")
              + keep("apr", f"to_char(private.series_start({rule}, 3) at time zone 'Europe/Zurich', 'YYYY-MM-DD HH24:MI')"))
    assert "feb=2026-02-28 20:00" in out and "mar=2026-03-31 20:00" in out and "apr=2026-04-30 20:00" in out, out


def test_a_plain_member_cannot_make_his_own_event_recurring_but_may_stop_it():
    """Précision de l'admin (16.11) : Admin, Co-admin et Organisateur seulement (droit events.recurring)."""
    out = run(as_postgres() + """
      insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by)
        values ('[Recette] Le mien', 'published', 'invited', false, now() + interval '1 day', victor) returning id into e;"""
              + as_bot("victor") + note("member", "perform public.set_event_recurrence(e, 'weekly', 1, null)")
              + note("member_stop", "perform public.set_event_recurrence(e, 'none')")
              + as_postgres() + keep("rights", "(select string_agg(role, ',' order by role) from public.role_permissions where perm = 'events.recurring')"))
    assert "member=forbidden: les événements récurrents sont réservés" in out and "member_stop=ok" in out, out
    assert "rights=admin,coadmin,organizer" in out, out
