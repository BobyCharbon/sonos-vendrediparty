"""Pot commun dit sur la page d'invitation (contrôle Apple du 26.11, migration 20261126120000) : invite_preview dit si
l'événement a un pot commun, pour que « Je viens ! » le dise avant la réponse. Base de TEST, bots seulement, tout annulé."""
import pytest

from tests.supabase_live.test_annonces_groupe_live import as_bot, as_postgres, olga_event, run
from tests.supabase_live.test_member_admin_live import pytestmark  # noqa: F401


@pytest.mark.parametrize('pot', [True, False])
def test_the_invitation_page_says_whether_the_event_has_a_common_pot(pot):
    out = run(olga_event(announce=False) + f"""
      update public.events set pot_enabled = {str(pot).lower()} where id = e;
      r := public.create_event_invite(e, 0, null, 'Pot');
      a := (r->>'token')::uuid;""" + as_bot("violette") + """
      raise exception 'résultat: %', public.invite_preview(a, false)->'pot_enabled';""" + as_postgres())
    assert f'résultat: {str(pot).lower()}' in out, out
