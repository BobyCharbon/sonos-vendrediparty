"""Accord de l'organisateur (décision de l'admin du 12.11.2026), module web dans un vrai navigateur (Supabase simulé) :
- l'organisateur voit « À accepter » : qui, invité par qui, par quel lien ; Accepter, ou Refuser en deux temps ;
- la personne invitée par un invité le sait AVANT de répondre, puis voit « Demande envoyée » ; rouvrir le lien dit
  « en attente », sans boutons de réponse."""
import json

import pytest

from tests.test_events_browser import DIST, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import (  # noqa: F401
    CARD, CORS, GUEST_LIST, IDS, TOKEN, mock_invites, open_event, shot, v2_origin)

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
RPC = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
REQUEST = {'id': IDS[8], 'name': 'Nina', 'avatar_url': None, 'answer': 'yes', 'created_at': '2030-11-02T10:00:00Z',
           'invited_by': 'Julien', 'invited_by_id': IDS[1], 'link_label': 'Collègues'}
PENDING = {'pending': True, 'event_id': None, 'status': 'yes', 'title': 'Halloween chez Ludo', 'starts_at': '2030-11-13T19:00:00Z',
           'ends_at': None, 'all_day': False, 'date_mode': 'fixed', 'location_name': 'Chez Ludo, Sion', 'location_address': None,
           'location_url': None, 'description': None, 'waitlisted': None, 'host': 'Ludo'}


def reply(page, name: str, body, calls: list):
    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        calls.append((name, json.loads(route.request.post_data or '{}')))
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    page.route(RPC + name, handle)


def test_the_organizer_accepts_someone_invited_by_a_guest(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        mock_invites(page, guest_list={**GUEST_LIST, 'requests': [REQUEST]})
        calls = []
        reply(page, 'decide_join_request', GUEST_LIST, calls)
        card = open_event(page, v2_origin)
        pw.expect(card.get_by_text('À ACCEPTER · 1', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Invité par Julien · lien « Collègues » · Viendrait', exact=True)).to_be_visible()
        card.get_by_text('À ACCEPTER · 1', exact=True).scroll_into_view_if_needed()
        shot(page, '30-accord-a-accepter')

        # Refuser se fait en deux temps : le premier toucher ne décide rien.
        card.get_by_role('button', name='Refuser Nina').click()
        pw.expect(card.get_by_role('button', name='Confirmer le refus de Nina')).to_be_visible()
        assert not calls
        card.get_by_role('button', name='Accepter Nina').click()
        pw.expect(page.get_by_text('Nina est invité : il voit l’événement', exact=True)).to_be_visible(timeout=5000)
        assert calls == [('decide_join_request', {'e': calls[0][1]['e'], 'person': IDS[8], 'accept': True})]
        assert not errors, errors
    finally:
        context.close()


def test_someone_invited_by_a_guest_knows_before_answering_then_waits(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Julien', 'label': None, 'approval': True, 'host': 'Ludo'})
        calls = []
        reply(page, 'accept_invite', PENDING, calls)
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ludo accepte chaque invité : tu verras l’événement dès qu’il aura dit oui.', exact=True)
                  ).to_be_visible(timeout=15000)
        shot(page, '31-accord-carte-invitation', full=True)
        page.get_by_role('button', name='Je viens !').click()
        login(page)
        pw.expect(page.get_by_text('Demande envoyée', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Ludo doit accepter ta venue', exact=False)).to_be_visible()
        # Jamais la fiche ni l'adresse avant l'accord.
        pw.expect(page.get_by_role('button', name='Voir l’événement', exact=True)).to_have_count(0)
        assert [c[0] for c in calls] == ['accept_invite']
        shot(page, '32-accord-demande-envoyee')
        assert not errors, errors
    finally:
        context.close()


def test_reopening_the_link_while_waiting_says_so_without_answers(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Julien', 'state': 'waiting', 'host': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ta demande est envoyée : Ludo doit l’accepter', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    finally:
        context.close()


def test_a_refused_person_is_told_kindly_without_answers(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Julien', 'state': 'refused', 'host': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ludo n’a pas pu accepter ta venue cette fois.', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    finally:
        context.close()
