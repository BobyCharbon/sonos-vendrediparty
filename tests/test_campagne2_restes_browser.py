"""Restes de la campagne 2 (07.11.2026), module web dans un vrai navigateur (Supabase simulé) :
- carte « Invités » : chaque lien « pour plusieurs » a son propre nom pour VoiceOver (« Relancer Lien pour plusieurs »
  ×2 ne disait pas lequel) ;
- formulaire : un refus de la base sur un sondage ou un objet ne montre jamais sa clé technique (« content_refused: »)."""
import copy
from pathlib import Path

import pytest

from tests.test_events_browser import DIST, browser, pw  # noqa: F401
from tests.test_invitations_v2_browser import GUEST_LIST, IDS, mock_invites, open_event, v2_origin  # noqa: F401
from tests.test_events_browser import mock_services

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SRC = Path(__file__).resolve().parents[1] / 'web/events/src'


def test_each_link_for_several_people_has_its_own_spoken_name(browser, v2_origin):  # noqa: F811
    guest_list = copy.deepcopy(GUEST_LIST)
    second = {**guest_list['links'][1], 'token': IDS[8], 'max_uses': 6, 'uses': 0, 'arrivals': [], 'state': 'pending',
              'opened_at': None, 'created_at': '2030-11-03T10:00:00Z'}
    guest_list['links'].append(second)
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, guest_list=guest_list)
        card = open_event(page, v2_origin)
        nudges = card.get_by_role('button', name='Relancer Lien pour plusieurs', exact=False)
        pw.expect(nudges).to_have_count(2, timeout=10000)
        names = [b.get_attribute('aria-label') for b in nudges.all()]
        assert len(set(names)) == 2, names
        assert names[0].startswith('Relancer Lien pour plusieurs n° 1, 4 places') and 'n° 2, 6 places' in names[1], names
        assert card.get_by_role('button', name='Relancer Lien pour plusieurs', exact=True).count() == 0
        stops = [b.get_attribute('aria-label') for b in card.get_by_role('button', name='Arrêter Lien pour plusieurs').all()]
        assert len(set(stops)) == 2, stops
        pw.expect(card.get_by_role('button', name='Relancer Lien pour Tom', exact=True)).to_have_count(1)  # titre unique : inchangé
    finally:
        context.close()


def test_the_event_form_never_shows_the_technical_key_of_a_refusal():
    form = (SRC / 'components/EventForm.tsx').read_text(encoding='utf-8')
    assert 'const text = friendlyError(dbMessage(message, message));' in form
    assert "setError(error.message.includes('duplicate') ? 'Ce tag existe déjà' : error.message)" not in form
