"""Configuration PRODUCTION (plan « bêta → main » du 04.11), dans un vrai navigateur : Événements ouverts à tous (plus de
« Bientôt »), Discussions absentes (ni onglet, ni « Écrire », ni page), Zicou absent. Serveur lancé comme en prod :
COMPAGNON_ENABLED=0, DISCUSSIONS_ENABLED=0. Supabase et la liaison de compte sont simulés : aucun SMS réel."""
import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from tests.test_events_browser import ROOT, browser, login, mock_services, pw, pytestmark  # noqa: F401 (fixture)


@pytest.fixture(scope='module')
def prod_origin(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-prod-data')), 'COMPAGNON_ENABLED': '0',
           'DISCUSSIONS_ENABLED': '0', 'PARTY_PUBLIC_URL': 'https://party.bobycharbon.ch',
           'EVENTS_WEB_DIR': str(ROOT / 'web/events/dist'), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'],
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60  # machine chargée : démarrage parfois lent
        while time.monotonic() < deadline:
            try:
                if httpx.get(origin, timeout=1).status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(.05)
        else: raise AssertionError('Le serveur Party de test ne démarre pas')
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=5)


def linked(page):
    """Compte Party relié (bêta-testeur ou non : plus aucune différence en production)."""
    mock_services(page)
    page.route('**/api/account/link', lambda route: route.fulfill(content_type='application/json', body=json.dumps(
        {'guest_id': 'acct-test', 'name': 'Compte de démonstration', 'photo': None, 'beta': True})))


events_tab = lambda page: page.locator('#tabs [data-tab="events"]')
chats_tab = lambda page: page.locator('#tabs [data-tab="chats"]')


def test_server_says_production_features(prod_origin):
    assert httpx.get(f'{prod_origin}/api/features').json() == {'compagnon': False, 'discussions': False, 'invites_v2': False}
    page = httpx.get(prod_origin).text
    assert 'data-discussions="off"' in page and 'data-compagnon="off"' in page and 'data-events=' not in page
    module = httpx.get(f'{prod_origin}/events/').text
    assert 'data-discussions="off"' in module and 'data-invites="off"' in module and 'data-events=' not in module
    assert httpx.post(f'{prod_origin}/api/account/chats', json={'token': 'x' * 30}).status_code == 404
    assert httpx.post(f'{prod_origin}/api/account/chats/send', json={'token': 'x'}).status_code == 404
    assert httpx.get(f'{prod_origin}/static/pet/pet.js').status_code == 404
    # Lien public d'un événement : la page se sert sans compte (le module lit public_event, la réponse après le SMS).
    share = httpx.get(f'{prod_origin}/events/share/6f1e7b62-9a2d-4d62-8b3c-3c2f9f5d1b01')
    assert share.status_code == 200 and 'data-events=' not in share.text


def test_visitor_opens_events_without_soon_and_sees_no_discussions_nor_zicou(browser, prod_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); mock_services(page)
    try:
        page.goto(prod_origin, wait_until='domcontentloaded')
        pw.expect(events_tab(page)).not_to_have_attribute('aria-disabled', 'true')
        assert not page.evaluate("document.documentElement.classList.contains('events-soon')")
        events_tab(page).click()
        pw.expect(events_tab(page)).to_have_attribute('aria-current', 'page')
        pw.expect(page.frame_locator('#eventsFrame').get_by_role('button', name='Recevoir un code par SMS')).to_be_visible(timeout=15000)
        pw.expect(chats_tab(page)).to_be_hidden()
        assert page.locator('#tabs [data-tab="pet"]').count() == 0
        assert 'Bientôt' not in page.locator('#tabs').inner_text() and 'Zicou' not in page.locator('#tabs').inner_text()
    finally:
        context.close()


def test_signed_in_member_has_events_but_never_discussions(browser, prod_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); linked(page)
    try:
        page.goto(prod_origin, wait_until='domcontentloaded')
        page.locator('#accountTab').click()
        login(page.frame_locator('#eventsFrame'))
        events_tab(page).click()
        frame = page.frame_locator('#eventsFrame')
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        pw.expect(chats_tab(page)).to_be_hidden()
        # Lien de notification d'une ancienne discussion : retombe sur la musique.
        page.goto(prod_origin + '/?tab=chats', wait_until='domcontentloaded')
        pw.expect(page.locator('body')).to_have_attribute('data-tab', 'music')
        pw.expect(chats_tab(page)).to_be_hidden()
    finally:
        context.close()


def test_old_discussions_address_shows_nothing(browser, prod_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); linked(page)
    try:
        page.goto(prod_origin + '/events/chats', wait_until='domcontentloaded')
        login(page)  # le module ramène à la page demandée après la connexion
        pw.expect(page.get_by_text('Cette page n’existe pas.')).to_be_visible(timeout=15000)
        assert page.get_by_role('button', name='Nouveau groupe').count() == 0
    finally:
        context.close()
