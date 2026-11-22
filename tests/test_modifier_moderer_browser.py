"""Modifier son événement et droits de l'équipe (décisions de l'admin du 22.11.2026), module Événements dans un vrai
navigateur (Supabase simulé) :
- le créateur d'un événement public publié, sans « Modifier ses événements déjà publiés », voit « Modifier » ; le
  formulaire lui dit AVANT d'enregistrer que l'événement repassera en validation ;
- l'événement d'un autre : « Modifier » seulement avec events.edit_others ; « Annuler l'événement » (zone « Équipe
  Vendredi Party ») seulement avec events.remove_others."""
import pytest

from tests.test_bots_campaign_fixes_browser import OTHER, as_perms, new_page, open_event, with_event
from tests.test_events_browser import DIST, browser, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
CREATOR = ['events.view', 'events.rsvp', 'events.create']  # ni publish_direct, ni edit_own_published


def test_the_creator_edits_his_public_event_and_is_told_it_goes_back_to_validation(browser, v2_origin):  # noqa: F811
    errors = []
    context, page = new_page(browser, errors)
    try:
        mock_services(page)
        as_perms(page, CREATOR)
        with_event(page, public_link=True, event_invites=[], event_groups=[], event_phone_invites=[], reminders=[],
                   max_plus_ones=0, payment_mode='organizer')
        open_event(page, v2_origin)
        pw.expect(page.get_by_role('button', name='Modifier', exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Modifier', exact=True).click()
        pw.expect(page.get_by_text('ta modification repasse en validation', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('attend l’accord d’un organisateur, d’un co-admin ou d’un admin', exact=False)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Enregistrer', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize('perms,edit,remove', [
    ([], False, False),
    (['events.edit_others'], True, False),
    (['events.remove_others'], False, True),
])
def test_events_of_others_follow_the_new_rights(browser, v2_origin, perms, edit, remove):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        as_perms(page, CREATOR + ['events.publish_direct', 'events.edit_own_published'] + perms)  # un Organisateur
        with_event(page, created_by=OTHER, author={'display_name': 'Bot Olga'}, public_link=True)
        open_event(page, v2_origin)
        pw.expect(page.get_by_role('heading', level=1, name='Sortie de démonstration (test local)')).to_have_count(1, timeout=15000)
        pw.expect(page.get_by_role('button', name='Modifier', exact=True)).to_have_count(1 if edit else 0)
        pw.expect(page.get_by_text('ÉQUIPE VENDREDI PARTY', exact=True)).to_have_count(1 if remove else 0)
        pw.expect(page.get_by_role('button', name='Annuler l’événement')).to_have_count(1 if remove else 0)
    finally:
        context.close()
