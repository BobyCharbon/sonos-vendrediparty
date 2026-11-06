"""Invitations v2 (05.11.2026, bêta), module web dans un vrai navigateur (Supabase simulé, aucun SMS réel) :
- organisateur : carte « Invités » (compteurs, filtres, qui a invité qui, liens envoyés), relance, feuille « Inviter »
  (lien pour une personne / pour plusieurs, places, QR), ajouter quelqu'un de Party hors du groupe ;
- invité sans app : carte lisible sans compte (noms échappés) → « Je viens » → prénom + numéro → code (autocomplétion
  one-time-code) → confirmation avec calendrier, itinéraire et Party proposé sans obligation ;
- Android : le doigt posé sur une ligne d'invité (qui glisse à gauche) fait toujours défiler la page.
Captures (390 px, thème sombre) dans $INVITES_SHOTS si la variable est définie."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.test_events_browser import ANDROID_PHONE, DIST, EVENT, ROOT, USER, browser, login, mock_services, pw  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
TOKEN = '6b1f6f0e-4a8e-4c55-9d43-2f0b7c1d9e21'
SHOTS = Path(os.environ['INVITES_SHOTS']) if os.environ.get('INVITES_SHOTS') else None
SNEAKY = '<img src=x onerror="window.__xss=1">Ludo'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile',
        'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS'}
IDS = [f'aaaaaaaa-0000-4000-8000-00000000000{i}' for i in range(10)]


def guest(i, name, status, source, **more):
    return {'id': IDS[i], 'name': name, 'avatar_url': None, 'status': status, 'waitlisted': False, 'plus_ones': 0, 'source': source,
            'group': 'Vendredi Party' if source == 'vip' else None, 'invited_by': None, 'invited_by_id': None, 'link_label': None,
            'link_token': None, 'has_app': True, 'light': False, 'nudged_today': False, 'removable': source in ('person', 'link'), **more}


GUEST_LIST = {
    'vip': True, 'public': False, 'vip_name': 'Vendredi Party', 'groups': [],
    'people': [
        guest(0, 'Mariana', 'yes', 'vip'), guest(1, 'Julien', 'yes', 'vip'), guest(2, 'Sofia', 'maybe', 'vip'), guest(3, 'Kevin', None, 'vip'),
        guest(4, 'Marco Costa', 'yes', 'person', invited_by='Compte de démonstration', invited_by_id=USER),
        guest(5, 'Léa', 'maybe', 'link', link_label='Léa', has_app=False, light=True, invited_by='Compte de démonstration', invited_by_id=USER,
              link_token=TOKEN),
        guest(6, 'Anaïs', None, 'person', invited_by='Julien', invited_by_id=IDS[1], has_app=False),
        guest(7, 'Tom', 'no', 'link', has_app=False, light=True),
    ],
    'links': [
        {'token': TOKEN, 'label': 'Tom', 'max_uses': 1, 'uses': 0, 'created_at': '2030-11-01T10:00:00Z', 'expires_at': '2030-11-15T10:00:00Z',
         'opened_at': None, 'state': 'pending', 'version': 2, 'created_by': 'Compte de démonstration', 'created_by_id': USER,
         'nudged_today': False, 'arrivals': []},
        {'token': IDS[9], 'label': None, 'max_uses': 4, 'uses': 2, 'created_at': '2030-11-01T10:00:00Z', 'expires_at': '2030-11-15T10:00:00Z',
         'opened_at': '2030-11-01T12:00:00Z', 'state': 'opened', 'version': 2, 'created_by': 'Compte de démonstration', 'created_by_id': USER,
         'nudged_today': False, 'arrivals': [{'id': IDS[7], 'name': 'Tom', 'status': 'no'}, {'id': IDS[5], 'name': 'Léa', 'status': 'maybe'}]},
    ],
}
CARD = {'state': 'pending', 'version': 2, 'label': 'Léa', 'places_left': None, 'inviter': SNEAKY, 'title': 'Halloween chez Ludo',
        'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-13T19:00:00Z', 'ends_at': None, 'all_day': False,
        'location_name': 'Chez Ludo, Sion', 'cover_url': None, 'description': 'Déguisement bienvenu. Amène un truc à grignoter.',
        'allow_maybe': True, 'closed': False, 'going': 11, 'going_names': ['Mariana', 'Marco', 'Sofia'], 'mine': None, 'event_id': None,
        'location_address': None, 'location_url': None, 'me_named': False}
ACCEPTED = {'event_id': EVENT, 'status': 'yes', 'title': 'Halloween chez Ludo', 'starts_at': '2030-11-13T19:00:00Z', 'ends_at': None,
            'all_day': False, 'date_mode': 'fixed', 'location_name': 'Chez Ludo', 'location_address': 'Rue du Marché 4, Sion',
            'location_url': None, 'description': None, 'waitlisted': False}


@pytest.fixture(scope='module')
def v2_origin(tmp_path_factory):
    """Party avec les Invitations v2 allumées (comme le site de test)."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-invites-data')), 'EVENTS_WEB_DIR': str(DIST), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1', 'INVITES_V2_ENABLED': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'],
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(origin, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        else:
            raise AssertionError('Le serveur Party de test ne démarre pas')
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=5)


def mock_invites(page, guest_list=None, card=None) -> list:
    """Fonctions des Invitations v2, comme la base (après mock_services : ces routes passent devant)."""
    calls = []
    replies = {'event_guest_list': guest_list or GUEST_LIST, 'invite_preview': card or CARD, 'accept_invite': ACCEPTED,
               'create_event_invite': {'token': TOKEN, 'expires_at': '2030-11-15T10:00:00Z', 'max_uses': 1, 'label': None},
               'invite_people': {'people': 1, 'groups': 0}, 'nudge_invitees': {'notified': 0, 'skipped': 0, 'share': [IDS[3]]},
               'nudge_invite_link': None, 'remove_invitee': None, 'revoke_invite_link': None}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        name = request.url.split('?')[0].rsplit('/', 1)[-1]
        calls.append((name, json.loads(request.post_data or '{}')))
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(replies[name]))
    for name in replies:
        page.route(f'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/{name}', handle)
    return calls


def shot(page, name: str, full: bool = False):
    if SHOTS:
        page.wait_for_timeout(900)  # fin des apparitions (fondu, montée)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=full)


def open_event(page, origin):
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    page.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    card = page.get_by_label('Invités', exact=True)
    pw.expect(card.get_by_text('Invités · 9', exact=True)).to_be_visible(timeout=15000)
    return card


def test_organizer_sees_who_comes_filters_nudges_and_invites(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=[{'id': IDS[8], 'display_name': 'Marcel'}])
        calls = mock_invites(page)
        card = open_event(page, v2_origin)
        # Vue d'ensemble : la règle, les compteurs, qui a invité qui, les liens envoyés.
        pw.expect(card.get_by_text('Vendredi Party + 4 invités', exact=True)).to_be_visible()
        for label in ('3 Viennent', '2 Peut-être', '1 Absents', '2 Pas répondu', '1 Lien pas ouvert'):
            pw.expect(card.get_by_role('tab', name=label)).to_be_visible()
        pw.expect(card.get_by_text('Ajouté par toi', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Par le lien « Léa » · de toi', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Ajouté par Julien', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Lien pour Tom', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('2 sur 4 places', exact=False)).to_be_visible()
        card.scroll_into_view_if_needed()
        shot(page, '01-organisateur-carte-invites', full=True)
        page.mouse.move(195, 600)
        page.mouse.wheel(0, 700)
        shot(page, '01b-organisateur-en-plus-et-liens')

        # Filtre « Pas répondu » : seulement Kevin (dans le groupe) et Anaïs.
        card.get_by_role('tab', name='2 Pas répondu').click()
        pw.expect(card.get_by_text('Anaïs', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Mariana', exact=True)).to_have_count(0)
        shot(page, '02-organisateur-filtre-pas-repondu', full=True)
        # Relancer Anaïs (sans l'app) : la base note la relance, la feuille de partage s'ouvre (ici : le message copié).
        context.grant_permissions(['clipboard-read', 'clipboard-write'])
        card.get_by_role('button', name='Relancer Anaïs').click()
        pw.expect(page.get_by_text('Message copié', exact=False)).to_be_visible(timeout=5000)
        assert ('nudge_invitees', {'e': EVENT, 'people': [IDS[6]]}) in calls
        card.get_by_role('tab', name='2 Pas répondu').click()  # retour à tout

        # « + » : la feuille Inviter. Lien pour une personne, prénom noté, copié.
        card.get_by_role('button', name='Inviter', exact=True).click()
        sheet = page.get_by_label('Inviter à Sortie de démonstration (test local)')
        pw.expect(sheet.get_by_text('🔗 Envoyer le lien', exact=True)).to_be_visible(timeout=5000)
        page.wait_for_timeout(600)  # la feuille finit de monter
        shot(page, '03-organisateur-feuille-inviter')
        sheet.get_by_role('tab', name='Une personne').click()
        sheet.get_by_label('Pour qui ? (facultatif)').fill('Léa')
        pw.expect(sheet.get_by_text('Hello Léa !', exact=False)).to_be_visible()
        sheet.get_by_role('button', name='Copier').click()
        pw.expect(sheet.get_by_text('✓ Lien prêt', exact=False)).to_be_visible(timeout=5000)
        created = [c for c in calls if c[0] == 'create_event_invite']
        assert created == [('create_event_invite', {'e': EVENT, 'places': 1, 'until': None, 'label': 'Léa'})]
        shot(page, '04-organisateur-lien-une-personne')
        # Pour plusieurs : 11 places, valable 7 jours, QR code.
        sheet.get_by_role('tab', name='Plusieurs').click()
        sheet.get_by_role('button', name='Une place de plus').click()
        sheet.get_by_role('radio', name='7 jours').click()
        sheet.get_by_role('button', name='QR code').click()
        pw.expect(page.get_by_text('Montre ce code', exact=True)).to_be_visible(timeout=5000)
        args = [c for c in calls if c[0] == 'create_event_invite'][-1][1]
        assert args['places'] == 11 and args['label'] is None and args['until']
        shot(page, '05-organisateur-qr-plusieurs')
        page.get_by_role('button', name='Fermer', exact=True).last.click()

        # Ajouter quelqu'un de Party, hors du groupe : puce, puis « Inviter Marcel ».
        sheet.get_by_label('Chercher une personne ou un groupe').fill('marc')
        sheet.get_by_role('button', name='Ajouter Marcel').click()
        pw.expect(sheet.get_by_text('Vendredi Party + 5 invités', exact=True)).to_be_visible()
        shot(page, '06-organisateur-ajouter-quelqu-un-de-party')
        sheet.get_by_role('button', name='Inviter Marcel').click()
        pw.expect(page.get_by_text('Marcel : invités, prévenus dans Party', exact=True)).to_be_visible(timeout=5000)
        assert ('invite_people', {'e': EVENT, 'people': [IDS[8]], 'groups': []}) in calls
        assert page.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
        assert not errors, errors
    finally:
        context.close()


def test_guest_without_app_answers_with_first_name_phone_and_code(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        calls = mock_invites(page, card={**CARD, 'inviter': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        # Sans compte : qui invite, quoi, quand, où, qui vient.
        pw.expect(page.get_by_text('Ludo t’invite, Léa', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Halloween chez Ludo', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('L’adresse exacte après ta réponse', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Mariana, Marco, Sofia et 8 autres viennent', exact=True)).to_be_visible()
        assert ('invite_preview', {'token': TOKEN, 'opened': True}) in calls  # « A ouvert » chez l'organisateur
        shot(page, '07-invite-carte-sans-compte', full=True)

        page.get_by_role('button', name='Je viens !').click()
        page.get_by_label('Prénom', exact=True).fill('Léa')
        page.get_by_label('Numéro de portable').fill('079 456 12 38')
        shot(page, '08-invite-prenom-numero')
        page.get_by_role('button', name='Recevoir mon code par SMS').click()
        code = page.get_by_placeholder('123456', exact=True)
        pw.expect(code).to_be_visible(timeout=5000)
        assert code.get_attribute('autocomplete') == 'one-time-code'
        code.fill('123456')
        shot(page, '09-invite-code-sms')
        page.get_by_role('button', name='Confirmer', exact=True).click()
        pw.expect(page.get_by_text('C’est noté, Léa !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('Ludo est prévenu.', exact=True)).to_be_visible()
        assert ('accept_invite', {'token': TOKEN, 'answer': 'yes', 'first_name': 'Léa'}) in calls
        pw.expect(page.get_by_text('Rue du Marché 4, Sion', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Ajouter à mon agenda')).to_be_visible()
        pw.expect(page.get_by_role('button', name='📍 Itinéraire')).to_be_visible()
        pw.expect(page.get_by_role('button', name='Installer Party')).to_be_visible()
        shot(page, '10-invite-confirmation', full=True)
        page.get_by_role('button', name='Plus tard').click()
        pw.expect(page.get_by_role('button', name='Installer Party')).to_have_count(0)
        assert page.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
        assert not errors, errors
    finally:
        context.close()


def test_a_used_link_says_why_and_offers_no_answer(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'state': 'full'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ce lien a déjà servi', exact=False)).to_be_visible(timeout=15000)
        # Le prénom de qui invite est du texte, jamais du HTML.
        pw.expect(page.get_by_text(f'{SNEAKY} t’invite, Léa', exact=True)).to_be_visible()
        assert page.evaluate('window.__xss') is None and page.locator('img[src="x"]').count() == 0
        pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    finally:
        context.close()


def test_android_finger_on_a_guest_row_scrolls_the_page(browser, v2_origin):  # noqa: F811
    """Lignes qui glissent vers la gauche (Relancer, Retirer) : un geste vertical qui part d'une ligne fait défiler la
    fiche (retour #10 : jamais de doigt « bloqué » sur une carte)."""
    many = {**GUEST_LIST, 'people': [guest(i % 8, f'Invité {i}', None, 'person') | {'id': f'bbbbbbbb-0000-4000-8000-{i:012d}'} for i in range(30)]}
    context = browser.new_context(**ANDROID_PHONE)
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, guest_list=many)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        row = page.get_by_text('Invité 3', exact=True)
        pw.expect(row).to_be_visible(timeout=15000)
        row.scroll_into_view_if_needed()
        scroller = """() => { let el = [...document.querySelectorAll('*')].find(e => e.textContent === 'Invité 3' && !e.children.length);
                       while (el && !(el.scrollHeight > el.clientHeight + 50 && /(auto|scroll)/.test(getComputedStyle(el).overflowY))) el = el.parentElement;
                       return el ? el.scrollTop : null; }"""
        before = page.evaluate(scroller)
        assert before is not None
        box = row.bounding_box()
        cdp = context.new_cdp_session(page)
        cdp.send('Input.synthesizeScrollGesture', {'x': box['x'] + 20, 'y': box['y'] + box['height'] / 2,
                                                    'yDistance': -350, 'gestureSourceType': 'touch', 'speed': 1200})
        page.wait_for_timeout(500)
        assert page.evaluate(scroller) > before + 100, 'le doigt sur une ligne d’invité n’a pas fait défiler la page'
    finally:
        context.close()
