"""Notification du lien d'invitation (retour de l'admin, 19.11.2026) : elle dit CE QUE la personne a répondu. Base de TEST,
bots seulement, tout annulé à la fin."""
import pytest

from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401


@pytest.mark.parametrize('answer,phrase', [('yes', 'vient'), ('maybe', 'viendra peut-être')])
def test_the_link_notification_says_the_answer(answer, phrase):
    out = run(olga_event(announce=False) + """
      r := public.create_event_invite(e, 0, null, 'Paintball');
      a := (r->>'token')::uuid;""" + as_bot("violette") + f"""
      perform public.accept_invite(a, '{answer}');""" + as_postgres() + """
      raise exception 'résultat: %', (select string_agg(x.body, ' | ') from public.notifications x
        where x.user_id = olga and x.event_id = e and x.kind = 'link_join');""")
    assert f"résultat: Bot Violette {phrase} · par ton lien d'invitation" in out, out


def test_no_notification_when_the_person_does_not_come():
    """20.11 : « Ne vient pas » par le lien ne prévient pas l'organisateur."""
    out = run(olga_event(announce=False) + """
      r := public.create_event_invite(e, 0, null, 'Paintball');
      a := (r->>'token')::uuid;""" + as_bot("violette") + """
      perform public.accept_invite(a, 'no');""" + as_postgres() + """
      raise exception 'résultat: %', (select count(*) from public.notifications x
        where x.user_id = olga and x.event_id = e and x.kind = 'link_join');""")
    assert 'résultat: 0' in out, out
