"""« Ajouter à l'app Cartes Apple » sous le billet, dans le vrai module Événements (navigateur, Supabase simulé).
- Safari iPhone : badge officiel d'Apple, le billet est préparé avec la session du membre puis ouvert (.pkpass) ;
- app iPhone : le lien passe au pont natif PassKit (window.PartyNative.wallet.add) ;
- Android, ou serveur sans certificats : pas de badge.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json

import pytest

from tests.test_event_tickets_browser import DIST, MINE_YES, origin, shot, tickets_backend, with_rsvps  # noqa: F401 (fixture origin)
from tests.test_events_browser import EVENT, USER, browser, login, mock_services  # noqa: F401 (fixture browser)

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
          'Version/26.0 Mobile/15E148 Safari/604.1')
ANDROID = 'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36'
LINK = '/api/wallet/pass/abcDEF123.pkpass'
BADGE = 'Ajouter à l’app Cartes Apple'


def wallet_server(page, enabled=True):
    """Routes Wallet de Party simulées (le vrai serveur de test n'a pas de certificats)."""
    state = {'prepared': [], 'downloads': 0, 'notified': []}
    page.route('**/api/wallet/status', lambda r: r.fulfill(status=200, content_type='application/json',
                                                             body=json.dumps({'enabled': enabled})))

    def prepare(route):
        state['prepared'].append(json.loads(route.request.post_data))
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'url': LINK}))

    def download(route):
        state['downloads'] += 1
        route.fulfill(status=200, content_type='application/vnd.apple.pkpass', body=b'PK\x05\x06' + bytes(18),
                      headers={'Content-Disposition': 'attachment; filename="billet.pkpass"'})
    page.route('**/api/wallet/ticket', prepare)
    page.route('**/api/wallet/notify', lambda r: (state['notified'].append(json.loads(r.request.post_data)),
                                                   r.fulfill(status=200, content_type='application/json', body='{"devices": 1}')))
    page.route('**/api/wallet/pass/*', download)
    return state


def launch(browser, origin, user_agent=None, native=False, enabled=True):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=user_agent, accept_downloads=True)
    page = context.new_page()
    if native:  # app iPhone : pont natif dans tous les cadres ; les liens reçus sont notés dans la page principale
        page.add_init_script("""window.PartyNative = { platform: 'ios', wallet: { available: true,
          add: (url) => { (window.top.__walletAdded = window.top.__walletAdded || []).push(url); return Promise.resolve(true); } } };""")
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page)
    with_rsvps(page, [MINE_YES])
    tickets_backend(page)
    state = wallet_server(page, enabled)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    pw.expect(frame.get_by_text('Ton billet', exact=True)).to_be_visible(timeout=15000)
    return context, page, frame, state, errors


def test_safari_iphone_adds_the_ticket_with_the_official_badge(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, IPHONE)
    try:
        badge = frame.get_by_role('button', name=BADGE, exact=True)
        pw.expect(badge).to_be_visible(timeout=10000)
        box = badge.bounding_box()
        assert box['height'] >= 30 and abs(box['width'] / box['height'] - 113.408 / 35.291) < 0.1  # proportions d'Apple
        src = badge.evaluate("e => (e.querySelector('img') || {}).src || ''")
        assert src.endswith('/static/wallet/badge-fr.svg')
        badge.scroll_into_view_if_needed()
        shot(page, 'wallet-badge')
        with page.expect_download() as got:
            badge.click()
        assert got.value.url.endswith(LINK)
        assert state['downloads'] == 1
        sent = state['prepared'][0]
        assert sent['event_id'] == EVENT and sent['token']  # session Supabase du membre
        assert not errors
    finally:
        context.close()


def test_iphone_app_hands_the_pass_to_passkit(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, native=True)
    try:
        frame.get_by_role('button', name=BADGE, exact=True).click()
        page.wait_for_function('window.__walletAdded && window.__walletAdded.length === 1', timeout=10000)
        added = page.evaluate('window.__walletAdded')
        assert added == [f'{origin}{LINK}']
        assert state['downloads'] == 0  # c'est l'app qui télécharge le billet
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize('user_agent, enabled', [(ANDROID, True), (IPHONE, False)])
def test_no_badge_without_wallet(browser, origin, user_agent, enabled):
    context, page, frame, state, errors = launch(browser, origin, user_agent, enabled=enabled)
    try:
        pw.expect(frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True)).to_be_visible()
        page.wait_for_timeout(500)  # le statut du serveur est arrivé
        assert frame.get_by_role('button', name=BADGE, exact=True).count() == 0
        assert not state['prepared'] and not errors
    finally:
        context.close()


def test_error_from_the_server_is_shown(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, IPHONE)
    try:
        page.route('**/api/wallet/ticket', lambda r: r.fulfill(status=404, content_type='application/json',
                                                                 body=json.dumps({'detail': 'Pas de billet pour cet événement : il faut être noté Présent.'})))
        frame.get_by_role('button', name=BADGE, exact=True).click()
        pw.expect(frame.get_by_text('Pas de billet pour cet événement : il faut être noté Présent.', exact=True)).to_be_visible(timeout=10000)
        assert state['downloads'] == 0 and not errors
    finally:
        context.close()


def test_a_new_qr_updates_the_pass_already_in_cartes(browser, origin):
    context, page, frame, state, errors = launch(browser, origin, IPHONE)
    try:
        renewed = 'cd' * 32
        page.route('**/rest/v1/rpc/renew_event_ticket', lambda r: r.fulfill(
            status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*'},
            body=json.dumps({'state': 'ok', 'token': renewed, 'code': 'ABC234', 'plus_ones': 0, 'checked_in_at': None,
                             'paid': False, 'pay_pending': False, 'price_chf': 20})))
        frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True).click()
        frame.get_by_text('Nouveau QR (l’ancien ne marchera plus)', exact=True).click()
        frame.get_by_text('Oui, changer (Cartes se met à jour)', exact=True).click()
        pw.expect(frame.get_by_text('ABC 234', exact=True)).to_be_visible(timeout=10000)
        deadline = 50
        while not state['notified'] and deadline:
            page.wait_for_timeout(100)
            deadline -= 1
        assert state['notified'] and state['notified'][0]['event_id'] == EVENT and state['notified'][0]['member'] == USER
        assert state['notified'][0]['token']
        assert not errors
    finally:
        context.close()
