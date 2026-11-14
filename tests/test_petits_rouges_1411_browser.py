"""Petits rouges de la campagne du 14.11.2026, module web dans un vrai navigateur (Supabase simulé) :
- l'organisateur n'est pas sollicité comme un invité sur la fiche de SON événement (plus de « Tu viens ? À répondre ») ;
- un lien « Plusieurs » arrêté se lit comme arrêté dans la carte Invités ;
- la fiche d'un membre ne plante pas si member_card ne renvoie pas un objet."""
import copy
import json

import pytest

from tests.test_chats_browser import CORS, LEA, phone  # noqa: F401 (fixtures)
from tests.test_direct_messages_browser import signed_in
from tests.test_events_browser import DIST, browser, events_origin, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import GUEST_LIST, mock_invites, open_event, v2_origin  # noqa: F401
from tests.test_moderation_browser import moderation_services

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')


def test_the_organizer_is_not_asked_to_answer_his_own_event(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)  # la sortie de démonstration est créée par le compte connecté
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button', name='Événements', exact=True).click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        pw.expect(frame.get_by_text('Ta présence', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('Dis aux invités si tu y seras, toi aussi.', exact=True)).to_be_visible()
        assert frame.get_by_text('À répondre', exact=True).count() == 0
        assert frame.get_by_text('Tu viens ?', exact=True).count() == 0
        # Il peut toujours dire qu'il sera là.
        frame.get_by_role('button', name='Présent', exact=True).click()
        pw.expect(frame.get_by_text('Ta réponse', exact=True)).to_be_visible(timeout=10000)
    finally:
        context.close()


def test_a_stopped_link_reads_as_stopped_in_the_guest_card(browser, v2_origin):  # noqa: F811
    guest_list = copy.deepcopy(GUEST_LIST)
    guest_list['links'][1]['state'] = 'revoked'  # « Plusieurs » arrêté après deux arrivées
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, guest_list=guest_list)
        card = open_event(page, v2_origin)
        pw.expect(card.get_by_text('Lien pour plusieurs (arrêté)', exact=True)).to_be_visible(timeout=10000)
        assert card.get_by_text('Lien pour plusieurs', exact=True).count() == 0
        pw.expect(card.get_by_text('Arrêté', exact=True)).to_be_visible()  # l'état, pas « 2/4 »
        assert card.get_by_text('2/4', exact=True).count() == 0
        assert card.get_by_role('button', name='Copier le lien : Lien pour plusieurs (arrêté)').count() == 0
    finally:
        context.close()


@pytest.mark.parametrize('reply', ['"oups"', '[]', 'null', '{"display_name": "Léa"}'])
def test_member_card_survives_an_unexpected_reply(phone, events_origin, reply):  # noqa: F811
    page, errors = phone
    moderation_services(page, accepted=True)
    page.route('**/rest/v1/rpc/member_card', lambda route: route.fulfill(
        status=200, content_type='application/json', headers=CORS, body=reply))
    signed_in(page, events_origin, f'/member/{LEA}')
    pw.expect(page.get_by_text('Ce profil n’est pas disponible.', exact=True)).to_be_visible(timeout=15000)
    assert not errors, errors


def test_member_card_without_groups_still_shows_the_profile(phone, events_origin):  # noqa: F811
    page, errors = phone
    moderation_services(page, accepted=True)
    card = {'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'role': 'guest', 'root': False, 'me': False,
            'first_name': None, 'last_name': None, 'phone': None}
    page.route('**/rest/v1/rpc/member_card', lambda route: route.fulfill(
        status=200, content_type='application/json', headers=CORS, body=json.dumps(card)))
    signed_in(page, events_origin, f'/member/{LEA}')
    pw.expect(page.get_by_role('button', name='Bloquer Léa')).to_be_visible(timeout=15000)
    assert not errors, errors
