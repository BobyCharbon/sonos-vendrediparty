"""Pastille des présents et billets QR dans le vrai module Événements (navigateur, Supabase simulé : aucun SMS réel).
- la carte et la page d'un événement montrent « qui vient » en haut à droite (plus de « Toi + 1 présent ») ;
- un présent voit son billet (QR lisible + code court) ;
- l'organisateur scanne (code tapé ou lien du QR ouvert par l'appareil photo) : « Bienvenue », puis « Déjà scanné ».
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

from tests.test_events_browser import EVENT, USER, browser, login, mock_services  # noqa: F401 (fixture browser)

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
DIST = Path(os.environ.get('EVENTS_TEST_DIST') or ROOT / 'web/events/dist')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
LEA = '5b0c7e1e-1d3a-4c8e-9a51-6f2f4b9d0a11'
TOKEN = 'ab' * 32
CODE = 'K7M2QX'


@pytest.fixture(scope='module')
def origin(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-tickets-data')), 'EVENTS_WEB_DIR': str(DIST), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'],
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(url, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        else:
            raise AssertionError('Le serveur Party de test ne démarre pas')
        yield url
    finally:
        process.terminate()
        process.wait(timeout=5)


def shot(page, name):
    """Captures de relecture (dossier ignoré par git), comme les autres tests du module."""
    folder = ROOT / '.impeccable/review'
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / f'{name}.png'))


def person(**extra):
    return {'user_id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'status': 'yes', 'waitlisted': False, 'plus_ones': 1,
            'checked_in_at': None, 'paid': False, 'pay_pending': False, 'price_chf': 20, **extra}


def tickets_backend(page, attendance=None, my_rsvp='yes'):
    """Fonctions de la migration 20261103130000, simulées par-dessus mock_services (la dernière route gagne)."""
    state = {'checked_in': None, 'paid': False, 'pending': False, 'scans': [], 'paid_calls': [], 'declared': [], 'confirmed': []}
    headers = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}

    def reply(route, body):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=headers)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=headers)

    def attendance_rpc(route):
        reply(route, [{'event_id': EVENT, **(attendance or {'going': 3, 'maybe': 1, 'waitlist': 0, 'faces': [
            {'id': USER, 'name': 'Compte de démonstration', 'avatar_url': None}, {'id': LEA, 'name': 'Léa', 'avatar_url': None}]})}])

    def my_ticket(route):
        reply(route, {'state': 'ok', 'token': TOKEN, 'code': CODE, 'plus_ones': 0, 'checked_in_at': state['checked_in'],
                      'paid': state['paid'], 'pay_pending': state['pending'], 'price_chf': 20} if my_rsvp == 'yes' else {'state': 'none'})

    def check_in(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        scanned = json.loads(route.request.post_data)['scanned']
        state['scans'].append(scanned)
        if scanned not in (TOKEN, CODE):
            return reply(route, {'result': 'unknown'})
        already = state['checked_in'] is not None
        state['checked_in'] = state['checked_in'] or '2030-11-14T20:04:00Z'
        reply(route, {'result': 'already' if already else 'ok',
                      'person': person(checked_in_at=state['checked_in'], paid=state['paid'], pay_pending=state['pending'])})

    def declare(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        state['pending'] = json.loads(route.request.post_data)['declared']
        state['declared'].append(state['pending'])
        my_ticket(route)

    def confirm(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        received = json.loads(route.request.post_data)['received']
        state['confirmed'].append(received)
        state['paid'], state['pending'] = received, False
        reply(route, person(checked_in_at=state['checked_in'], paid=state['paid'], pay_pending=False))

    def pay_info(route):
        reply(route, {'organizer_id': USER, 'organizer_name': 'Compte de démonstration', 'amount': 20, 'payment_info': None,
                      'iban': 'CH9300762011623852957', 'holder': 'Boby', 'links': {'twint': '+41791234567', 'revolut': 'https://revolut.me/boby'},
                      'note': None, 'reference': 'Party · Sortie de démonstration (test local)'})

    def paid(route):
        if route.request.method == 'OPTIONS':
            return reply(route, None)
        state['paid'] = json.loads(route.request.post_data)['is_paid']
        state['paid_calls'].append(state['paid'])
        reply(route, person(checked_in_at=state['checked_in'], paid=state['paid']))

    base = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
    page.route(base + 'event_attendance', attendance_rpc)
    page.route(base + 'my_event_ticket', my_ticket)
    page.route(base + 'check_in_ticket', check_in)
    page.route(base + 'set_ticket_paid', paid)
    page.route(base + 'event_checkins', lambda r: reply(r, [person(checked_in_at=state['checked_in'], paid=state['paid'], pay_pending=state['pending'])]))
    page.route(base + 'declare_ticket_payment', declare)
    page.route(base + 'confirm_ticket_payment', confirm)
    page.route(base + 'event_pay_info', pay_info)
    return state


def with_rsvps(page, rsvps, **extra):
    """L'événement simulé (même forme que mock_services) avec ces réponses et un prix : liste et détail."""
    category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
    event = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': None, 'created_by': USER,
             'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
             'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
             'category_id': category['id'], 'category': category, 'event_tags': [], 'date_options': [], 'rsvps': rsvps,
             'event_organizers': [], 'polls': [], 'bring_items': [], 'event_groups': [], 'author': {'display_name': 'Compte de démonstration'},
             'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': True, 'max_plus_ones': 2, 'max_participants': None,
             'rsvp_deadline': None, 'forum_enabled': False, 'all_day': False, 'price_chf': 20, 'visibility': 'all', **extra}
    headers = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}

    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=headers)
        single = 'id=eq.' in route.request.url
        route.fulfill(status=200, content_type='application/json', body=json.dumps(event if single else [event]), headers=headers)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/events?**', handle)
    return event  # modifiable par un test (l'option « Billets QR » allumée, par exemple)


def launch(browser, origin, rsvps, native_scan=None, **backend):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    if native_scan:  # app iPhone : le pont natif existe dès le chargement (cadre du module compris)
        page.add_init_script(f"window.PartyNative = {{ platform: 'ios', scan: {{ qr: () => Promise.resolve({json.dumps(native_scan)}) }} }};")
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    calls = mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}])
    with_rsvps(page, rsvps)
    state = tickets_backend(page, **backend)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    return context, page, frame, state, errors, calls


MINE_YES = {'event_id': EVENT, 'user_id': USER, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False, 'set_by': None}
LEA_YES = {'event_id': EVENT, 'user_id': LEA, 'status': 'yes', 'plus_ones': 1, 'note': None, 'waitlisted': False, 'set_by': None}


def test_the_card_and_the_event_show_who_comes_at_the_top_right(browser, origin):
    context, page, frame, _, errors, _ = launch(browser, origin, [MINE_YES, LEA_YES])
    try:
        # Un seul nombre : présents (accompagnants compris) + peut-être ; le détail au toucher et pour VoiceOver.
        label = '4 présents ou peut-être : 3 présents, 1 peut-être'
        badge = frame.get_by_role('button', name=label, exact=True).first
        pw.expect(badge).to_be_visible(timeout=15000)
        pw.expect(badge).to_contain_text('4')
        badge.click()
        pw.expect(frame.get_by_text('3 présents · 1 peut-être', exact=True).first).to_be_visible()
        assert frame.get_by_text('Toi + ', exact=False).count() == 0  # l'ancien « Toi + 1 présent » a disparu
        card = frame.get_by_role('link', name='Sortie de démonstration (test local)', exact=False).first
        card_box, badge_box = card.bounding_box(), badge.bounding_box()
        # En haut à droite de la carte.
        assert badge_box['x'] + badge_box['width'] > card_box['x'] + card_box['width'] * 0.7
        assert badge_box['y'] < card_box['y'] + card_box['height'] * 0.5
        shot(page, 'presents-carte')
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        big = frame.get_by_role('button', name=label, exact=True).last  # la liste reste dessous, cachée
        pw.expect(big).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('3 présents · 1 peut-être', exact=True).last).to_be_visible()
        shot(page, 'presents-page')
        assert not errors
    finally:
        context.close()


def test_nobody_yet_invites_to_be_the_first(browser, origin):
    context, page, frame, _, errors, _ = launch(browser, origin, [], attendance={'going': 0, 'maybe': 0, 'waitlist': 0, 'faces': []})
    try:
        pw.expect(frame.get_by_text('Sois le 1er ✨', exact=True).first).to_be_visible(timeout=15000)
        assert not errors
    finally:
        context.close()


def test_a_present_guest_shows_a_readable_qr_ticket_with_its_short_code(browser, origin):
    context, page, frame, _, errors, _ = launch(browser, origin, [MINE_YES])
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True).click()
        pw.expect(frame.get_by_text('K7M 2QX', exact=True)).to_be_visible(timeout=10000)
        pw.expect(frame.get_by_text('20 CHF à payer à l’organisateur', exact=True)).to_be_visible()
        qr = frame.get_by_label('QR code de ton billet', exact=True)
        pw.expect(qr).to_be_visible()
        src = qr.evaluate("e => (e.querySelector('img') || e).getAttribute('src') || getComputedStyle(e).backgroundImage")
        assert 'svg' in src
        # Le QR est lu par un vrai lecteur (BarcodeDetector de Chromium, quand la machine l'a).
        events = page.frame(url=lambda u: '/events/' in u)
        decoded = events.evaluate("""async () => {
          if (!('BarcodeDetector' in window)) return null;
          const el = [...document.querySelectorAll('img')].find((i) => i.src.startsWith('data:image/svg') && i.width > 100);
          const img = new Image(); img.src = el.src; await img.decode();
          const c = document.createElement('canvas'); c.width = c.height = 600; c.getContext('2d').drawImage(img, 0, 0, 600, 600);
          const found = await new BarcodeDetector({ formats: ['qr_code'] }).detect(c);
          return found[0]?.rawValue ?? '';
        }""")
        if decoded is not None:
            assert decoded.endswith(f'/?tab=events&event={EVENT}&ticket={TOKEN}')
        try:  # sinon, lecture de la capture d'écran par zxing-cpp quand il est installé
            import io
            import zxingcpp
            from PIL import Image
            capture = Image.open(io.BytesIO(qr.screenshot()))
            read = zxingcpp.read_barcodes(capture)
            assert read and read[0].text == f'{origin}/?tab=events&event={EVENT}&ticket={TOKEN}'
        except ImportError:
            pass
        shot(page, 'billet')
        frame.get_by_role('button', name='Fermer', exact=True).click()
        assert not errors
    finally:
        context.close()


def test_no_ticket_for_someone_not_present(browser, origin):
    context, page, frame, _, errors, _ = launch(browser, origin, [LEA_YES], my_rsvp='no')
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        pw.expect(frame.get_by_text('Tu viens ?', exact=True)).to_be_visible(timeout=15000)
        assert frame.get_by_text('Ton billet', exact=True).count() == 0
        assert not errors
    finally:
        context.close()


def test_the_organizer_scans_a_code_then_sees_already_scanned_and_ticks_paid(browser, origin):
    context, page, frame, state, errors, _ = launch(browser, origin, [LEA_YES])
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        frame.get_by_role('button', name='📷 Scanner les billets', exact=True).click()
        pw.expect(frame.get_by_text('Scanner les billets', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('Attendu·e', exact=False)).to_be_visible(timeout=10000)
        frame.get_by_label('Code du billet', exact=True).fill('k7m 2qx')
        frame.get_by_role('button', name='Valider', exact=True).click()
        pw.expect(frame.get_by_text('Bienvenue !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(frame.get_by_text('✗ Pas payé · 20 CHF', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('+ 1 accompagnant · 2 personnes', exact=True)).to_be_visible()
        frame.get_by_role('button', name='Marquer payé', exact=True).click()
        pw.expect(frame.get_by_text('✓ Payé', exact=True)).to_be_visible(timeout=10000)
        shot(page, 'entree-scan')
        assert state['paid_calls'] == [True]
        frame.get_by_role('button', name='Billet suivant', exact=True).click()
        frame.get_by_label('Code du billet', exact=True).fill('K7M2QX')
        frame.get_by_role('button', name='Valider', exact=True).click()
        pw.expect(frame.get_by_text('Déjà scanné', exact=True)).to_be_visible(timeout=10000)
        pw.expect(frame.get_by_text('ne laisse pas entrer deux fois', exact=False)).to_be_visible()
        frame.get_by_role('button', name='Billet suivant', exact=True).click()
        frame.get_by_label('Code du billet', exact=True).fill('ZZZZ')  # trop court : pas un billet
        frame.get_by_role('button', name='Valider', exact=True).click()
        pw.expect(frame.get_by_text('Ce QR n’est pas un billet Party', exact=True)).to_be_visible(timeout=10000)
        assert state['scans'] == ['K7M2QX', 'K7M2QX']
        assert not errors
    finally:
        context.close()


def test_the_phone_camera_opens_the_ticket_link_and_checks_the_guest_in(browser, origin):
    context, page, frame, state, errors, _ = launch(browser, origin, [LEA_YES])
    try:
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.goto(f'{origin}/?tab=events&event={EVENT}&ticket={TOKEN}', wait_until='domcontentloaded')
        frame = page.frame_locator('#eventsFrame')
        pw.expect(frame.get_by_text('Bienvenue !', exact=True)).to_be_visible(timeout=20000)
        pw.expect(frame.get_by_text('Léa', exact=True).first).to_be_visible()
        assert state['scans'] == [TOKEN]
        assert 'ticket=' not in page.url  # le jeton ne reste pas dans la barre d'adresse
        assert not errors
    finally:
        context.close()


def test_native_iphone_scanner_is_used_when_the_app_provides_it(browser, origin):
    context, page, frame, state, errors, _ = launch(browser, origin, [LEA_YES],
                                                    native_scan=f'https://party.example/?tab=events&event={EVENT}&ticket={TOKEN}')
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        frame.get_by_role('button', name='📷 Scanner les billets', exact=True).click()
        frame.get_by_role('button', name='📷 Scanner un billet', exact=True).click()
        pw.expect(frame.get_by_text('Bienvenue !', exact=True)).to_be_visible(timeout=10000)
        assert state['scans'] == [TOKEN]
        assert not errors
    finally:
        context.close()


def test_friends_payment_the_guest_pays_then_waits_for_the_organizer(browser, origin):
    context, page, frame, state, errors, _ = launch(browser, origin, [MINE_YES])
    context.grant_permissions(['clipboard-read', 'clipboard-write'])
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        frame.get_by_role('button', name='Payer l’organisateur · 20 CHF', exact=True).click()
        pw.expect(frame.get_by_text('20 CHF', exact=True)).to_be_visible(timeout=10000)
        frame.get_by_role('button', name='Copier Twint : numéro à copier dans l’app Twint : +41791234567', exact=True).click()
        pw.expect(frame.get_by_text('Copié ✓', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('CH93 0076 2011 6238 5295 7', exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('button', name='Payer avec Revolut', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('Party · Sortie de démonstration (test local)', exact=True)).to_be_visible()
        shot(page, 'payer-organisateur')
        frame.get_by_role('button', name='J’ai payé', exact=True).click()
        pw.expect(frame.get_by_text('Payé · en attente de confirmation', exact=True).first).to_be_visible(timeout=10000)
        assert state['declared'] == [True]
        frame.get_by_role('button', name='Annuler', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Payer l’organisateur · 20 CHF', exact=True)).to_be_visible(timeout=10000)
        assert state['declared'] == [True, False]
        assert not errors
    finally:
        context.close()


def test_the_organizer_confirms_a_declared_payment_on_the_event_and_at_the_entry(browser, origin):
    context, page, frame, state, errors, _ = launch(browser, origin, [LEA_YES])
    state['pending'] = True
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        pw.expect(frame.get_by_text('1 à confirmer · 20 CHF chacun', exact=True)).to_be_visible(timeout=15000)
        frame.get_by_role('button', name='Reçu ✓', exact=True).click()
        pw.expect(frame.get_by_text('Aucun paiement à confirmer.', exact=False)).to_be_visible(timeout=10000)
        assert state['confirmed'] == [True]
        # À l'entrée : une autre personne dit avoir payé, le scan propose « Reçu ✓ / Pas reçu ».
        state.update(paid=False, pending=True)
        frame.get_by_role('button', name='📷 Scanner les billets', exact=True).click()
        frame.get_by_label('Code du billet', exact=True).fill('K7M2QX')
        frame.get_by_role('button', name='Valider', exact=True).click()
        pw.expect(frame.get_by_text('Dit avoir payé · à confirmer (20 CHF)', exact=True)).to_be_visible(timeout=10000)
        frame.get_by_role('button', name='Pas reçu', exact=True).click()
        pw.expect(frame.get_by_text('✗ Pas payé · 20 CHF', exact=True)).to_be_visible(timeout=10000)
        assert state['confirmed'] == [True, False]
        assert not errors
    finally:
        context.close()
