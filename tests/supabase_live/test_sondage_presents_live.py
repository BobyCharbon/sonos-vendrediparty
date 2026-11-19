"""Sondages de la fiche (demande de l'admin, 19.11.2026) : on ne vote qu'après Présent ou Peut-être ; l'organisation vote
toujours. Base de TEST, bots seulement, tout annulé à la fin."""
from tests.supabase_live.test_annonces_groupe_live import as_bot, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

POLL = """
      insert into public.polls (event_id, question, created_by) values (e, 'On mange quoi ?', olga) returning id into a;
      insert into public.poll_options (poll_id, label, created_by, sort) values (a, 'Pizza', olga, 0);"""
VOTE = """
      begin
        insert into public.poll_votes (poll_id, option_id, user_id)
          values (a, (select id from public.poll_options where poll_id = a limit 1), auth.uid());
        {var} := 1;
      exception when others then {var} := case when sqlerrm like 'present_required%' then 0 else -1 end;
      end;"""


def test_vote_only_after_present_or_maybe_and_the_organizer_always_votes():
    out = run(olga_event(announce=False) + POLL + VOTE.format(var="m") + "r := to_jsonb(m);" + as_bot("victor")
              + VOTE.format(var="n") + """
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'maybe');""" + VOTE.format(var="m") + """
      raise exception 'résultat: organisatrice=% sans_reponse=% peut_etre=%', r, n, m;""")
    assert "résultat: organisatrice=1 sans_reponse=0 peut_etre=1" in out, out


def test_absent_cannot_vote():
    out = run(olga_event(announce=False) + POLL + as_bot("victor") + """
      insert into public.rsvps (event_id, user_id, status) values (e, victor, 'no');""" + VOTE.format(var="n") + """
      raise exception 'résultat: absent=%', n;""")
    assert "résultat: absent=0" in out, out
