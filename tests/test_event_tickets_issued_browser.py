"""Billets QR remis par l'organisateur (migration 20261104233000) dans le vrai module Événements (navigateur,
Supabase simulé : aucun SMS, aucune notification réelle) :
- option « Billets QR » éteinte : pas de billet, pas de QR, pas de Wallet (seulement payer sa place) ;
- option active, billet pas encore remis : « Ton billet arrivera quand l'organisateur l'aura validé » ;
- billet remis : QR et « Ajouter à Apple Wallet » ;
- l'organisateur active l'option, remet un billet, à tous, ou par « Reçu » (place payée) ; le scanner refuse un billet
  non remis.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json

import pytest

from tests.test_event_tickets_browser import (CODE, DIST, LEA, LEA_YES, MINE_YES, TOKEN, origin, person, shot,  # noqa: F401
                                              tickets_backend, with_rsvps)
from tests.test_events_browser import EVENT, USER, browser, login, mock_services  # noqa: F401 (fixture browser)
from tests.test_wallet_browser import BADGE, IPHONE, wallet_server

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
BASE = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
TITLE = 'Sortie de démonstration (test local)'


def reply(route, body):
    if route.request.method == 'OPTIONS':
        return route.fulfill(status=204, headers=HEADERS)
    route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=HEADERS)


def issued_backend(page, mine: str, enabled: bool, event: dict, lea_issued: bool = False, lea_pending: bool = False):
    """Par-dessus tickets_backend : mon billet dans l'état voulu (off / pending / ok) et les fonctions de remise."""
    state = {'enabled': enabled, 'lea_issued': lea_issued, 'lea_paid': False, 'lea_pending': lea_pending,
             'issued': [], 'all': 0, 'toggles': [], 'confirmed': []}

    def lea():
        return person(issued=state['lea_issued'], tickets_enabled=state['enabled'], paid=state['lea_paid'],
                      pay_pending=state['lea_pending'])

    def my_ticket(route):
        pay = {'plus_ones': 0, 'paid': False, 'pay_pending': False, 'price_chf': 20}
        reply(route, {'state': 'ok', 'token': TOKEN, 'code': CODE, 'checked_in_at': None, **pay} if mine == 'ok'
              else {'state': mine, **pay})

    def issue(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        body = json.loads(route.request.post_data)
        state['issued'].append(body['issued'])
        state['lea_issued'] = body['issued']
        reply(route, lea())

    def issue_all(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        state['all'] += 1
        count = 0 if state['lea_issued'] else 1
        state['lea_issued'] = True
        reply(route, count)

    def toggle(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        state['enabled'] = event['tickets_enabled'] = json.loads(route.request.post_data)['enabled']
        state['toggles'].append(state['enabled'])
        reply(route, state['enabled'])

    def confirm(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        received = json.loads(route.request.post_data)['received']
        state['confirmed'].append(received)
        state['lea_paid'], state['lea_pending'] = received, False
        state['lea_issued'] = state['lea_issued'] or received  # place payée : billet remis
        reply(route, lea())

    def check_in(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        reply(route, {'result': 'ok' if state['lea_issued'] else 'not_issued', 'person': lea()})

    page.route(BASE + 'my_event_ticket', my_ticket)
    page.route(BASE + 'issue_event_ticket', issue)
    page.route(BASE + 'issue_all_event_tickets', issue_all)
    page.route(BASE + 'set_event_tickets', toggle)
    page.route(BASE + 'confirm_ticket_payment', confirm)
    page.route(BASE + 'check_in_ticket', check_in)
    page.route(BASE + 'event_checkins', lambda r: reply(r, [lea()]))
    page.route('**/api/wallet/notify', lambda r: r.fulfill(status=200, content_type='application/json', body='{"devices": 0}'))
    return state


def launch(browser, origin, rsvps, mine='ok', enabled=True, user_agent=IPHONE, **backend):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=user_agent)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}])
    event = with_rsvps(page, rsvps, tickets_enabled=enabled)
    tickets_backend(page)
    wallet_server(page, True)
    state = issued_backend(page, mine, enabled, event=event, **backend)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    frame.get_by_text(TITLE, exact=True).click()
    return context, page, frame, state, errors


def test_option_off_means_no_qr_and_no_wallet(browser, origin):
    context, page, frame, _, errors = launch(browser, origin, [MINE_YES], mine='off', enabled=False)
    try:
        pw.expect(frame.get_by_role('button', name='Payer l’organisateur · 20 CHF', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(500)
        assert frame.get_by_text('Ton billet', exact=True).count() == 0
        assert frame.get_by_role('button', name=BADGE, exact=True).count() == 0
        assert frame.get_by_label('QR code de ton billet', exact=True).count() == 0
        assert not errors
    finally:
        context.close()


def test_option_on_but_not_handed_out_says_to_wait(browser, origin):
    context, page, frame, _, errors = launch(browser, origin, [MINE_YES], mine='pending')
    try:
        pw.expect(frame.get_by_text('Ton billet arrivera quand l’organisateur l’aura validé.', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_role('button', name='Payer l’organisateur · 20 CHF', exact=True)).to_be_visible()
        page.wait_for_timeout(500)
        assert frame.get_by_role('button', name=BADGE, exact=True).count() == 0
        assert frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True).count() == 0
        frame.get_by_test_id('ticket-pending').scroll_into_view_if_needed()
        shot(page, 'billet-en-attente')
        assert not errors
    finally:
        context.close()


def test_handed_out_ticket_shows_the_qr_and_apple_wallet(browser, origin):
    context, page, frame, _, errors = launch(browser, origin, [MINE_YES], mine='ok')
    try:
        pw.expect(frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_role('button', name=BADGE, exact=True)).to_be_visible(timeout=10000)
        frame.get_by_role('button', name=BADGE, exact=True).scroll_into_view_if_needed()
        shot(page, 'billet-remis-wallet')
        assert not errors
    finally:
        context.close()


def test_the_organizer_switches_tickets_on_and_hands_them_out(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, [LEA_YES], mine='none', enabled=False)
    try:
        switch = frame.get_by_role('switch', name='Billets QR', exact=True)
        pw.expect(switch).to_be_visible(timeout=15000)
        switch.click()
        pw.expect(frame.get_by_text('Billet pas encore remis', exact=True)).to_be_visible(timeout=10000)
        assert state['toggles'] == [True]
        frame.get_by_role('button', name='Remettre le billet', exact=True).click()
        pw.expect(frame.get_by_text('✓ Billet remis', exact=True)).to_be_visible(timeout=10000)
        assert state['issued'] == [True]
        frame.get_by_role('button', name='Retirer', exact=True).click()
        pw.expect(frame.get_by_text('Billet pas encore remis', exact=True)).to_be_visible(timeout=10000)
        frame.get_by_role('button', name='Remettre à tous les présents (1)', exact=True).click()
        pw.expect(frame.get_by_text('1 billet remis : chacun est prévenu.', exact=True)).to_be_visible(timeout=10000)
        assert state['all'] == 1 and state['issued'] == [True, False]
        frame.get_by_text('1 billet remis : chacun est prévenu.', exact=True).scroll_into_view_if_needed()
        shot(page, 'billets-organisateur')
        assert not errors
    finally:
        context.close()


def test_received_payment_hands_out_the_ticket(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, [LEA_YES], mine='none', enabled=True, lea_pending=True)
    try:
        pw.expect(frame.get_by_text('Billet pas encore remis', exact=True)).to_be_visible(timeout=15000)
        frame.get_by_role('button', name='Reçu ✓', exact=True).click()
        pw.expect(frame.get_by_text('✓ Billet remis', exact=True)).to_be_visible(timeout=10000)
        assert state['confirmed'] == [True]
        assert not errors
    finally:
        context.close()


def test_the_scanner_refuses_a_ticket_not_handed_out_then_hands_it_out(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, [LEA_YES], mine='none', enabled=True)
    try:
        frame.get_by_role('button', name='📷 Scanner les billets', exact=True).click()
        frame.get_by_label('Code du billet', exact=True).fill(CODE)
        frame.get_by_role('button', name='Valider', exact=True).click()
        pw.expect(frame.get_by_role('alert')).to_contain_text('Billet pas encore remis', timeout=10000)
        shot(page, 'scan-billet-pas-remis')
        # La page de l'événement reste dessous (cachée) : seul le bouton visible du résultat du scan.
        frame.locator('[role=button]:visible', has_text='Remettre le billet').first.click()
        pw.expect(frame.get_by_text('Bienvenue !', exact=True)).to_be_visible(timeout=10000)
        assert state['issued'] == [True]
        assert not errors
    finally:
        context.close()
