"""Heure de chaque vote de date (avis 2f5abe63e8ff), sur la base de TEST, tout annulé : un vote reçoit l'heure du
serveur (jamais celle envoyée par l'app) ; changer son vote la met à jour ; le revoter à l'identique ne la change pas."""
from tests.supabase_live.test_agenda_abonnement_live import POLL, opt
from tests.supabase_live.test_annonces_groupe_live import as_bot, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401

VOTE = f"(select voted_at from public.date_votes where option_id = {opt(0)} and user_id = victor)"


def test_each_date_vote_keeps_the_server_time_of_the_answer():
    out = run(POLL + as_bot("victor") + f"""
      insert into public.date_votes (option_id, user_id, vote, voted_at) values ({opt(0)}, victor, 'yes', '2001-01-01');
      perform set_config('party.first', {VOTE}::text, true);
      update public.date_votes set vote = 'yes', voted_at = '2001-01-01' where option_id = {opt(0)} and user_id = victor;
      perform set_config('party.same', {VOTE}::text, true);
      update public.date_votes set vote = 'no' where option_id = {opt(0)} and user_id = victor;
      raise exception 'résultat: serveur=% identique=% change=%',
        current_setting('party.first')::timestamptz > now() - interval '1 minute',
        current_setting('party.same') = current_setting('party.first'),
        {VOTE} >= current_setting('party.first')::timestamptz and (select vote from public.date_votes where option_id = {opt(0)} and user_id = victor) = 'no';""")
    assert "résultat: serveur=t identique=t change=t" in out, out
