"""Production (EVENTS_ENABLED=0) : Événements réservés aux bêta-testeurs, « Se connecter » ouvert à tous.
Supabase et la liaison de compte sont simulés : aucun SMS réel."""
import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from tests.test_events_browser import ROOT, USER, browser, login, mock_services, pw, pytestmark  # noqa: F401 (fixture)


@pytest.fixture(scope='module')
def prod_origin(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-beta-data')), 'EVENTS_ENABLED': '0',
           'EVENTS_WEB_DIR': str(ROOT / 'web/events/dist'), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'],
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 10
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


def beta_services(page, state):
    """state['beta'] : réponse de la base (is_beta_tester) et de la liaison de compte Party, modifiable en cours de test."""
    mock_services(page)
    cors = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile'}
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/is_beta_tester', lambda route: route.fulfill(
        status=204 if route.request.method == 'OPTIONS' else 200, headers=cors, content_type='application/json', body=json.dumps(state['beta'])))
    page.route('**/api/account/link', lambda route: route.fulfill(content_type='application/json', body=json.dumps(
        {'guest_id': 'acct-test', 'name': 'Compte de démonstration', 'photo': None, 'beta': state['beta']})))


events_tab = lambda page: page.locator('#tabs [data-tab="events"]')


def back_to_app(page):
    """La web app revient au premier plan (sans être relancée)."""
    page.evaluate("linkedAt = 0; document.dispatchEvent(new Event('visibilitychange'))")


def test_visitor_sees_soon_and_can_sign_in(browser, prod_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); beta_services(page, {'beta': False})
    try:
        page.goto(prod_origin, wait_until='domcontentloaded')
        pw.expect(events_tab(page)).to_have_attribute('aria-disabled', 'true')
        assert page.evaluate("document.documentElement.classList.contains('events-soon')")
        events_tab(page).click(force=True)
        pw.expect(page.locator('.toast')).to_contain_text('bientôt')
        assert page.evaluate('document.body.dataset.tab') != 'events'
        pw.expect(page.locator('#accountTab')).to_be_visible()
        page.locator('#accountTab').click()
        frame = page.frame_locator('#eventsFrame')
        pw.expect(frame.get_by_role('button', name='Recevoir un code par SMS')).to_be_visible()
    finally:
        context.close()


def test_beta_checked_by_admin_opens_events_when_app_comes_back(browser, prod_origin):
    """Bug du 2026-10-21 : la case cochée n'ouvrait l'onglet qu'après une relance complète de l'app."""
    state = {'beta': False}
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); beta_services(page, state)
    try:
        page.goto(prod_origin, wait_until='domcontentloaded')
        page.locator('#accountTab').click()
        login(page.frame_locator('#eventsFrame'))
        frame = page.frame_locator('#eventsFrame')
        # Membre, pas encore bêta : Réglages ouverts, sorties « bientôt », pas de demande d'adhésion.
        pw.expect(frame.get_by_text('réservées aux bêta-testeurs')).to_be_visible()
        pw.expect(frame.get_by_text('Demander à rejoindre')).to_have_count(0)
        pw.expect(events_tab(page)).to_have_attribute('aria-disabled', 'true')

        state['beta'] = True  # l'admin coche « 🧪 Bêta-testeur »
        back_to_app(page)
        pw.expect(events_tab(page)).not_to_have_attribute('aria-disabled', 'true')
        assert not page.evaluate("document.documentElement.classList.contains('events-soon')")
        events_tab(page).click()
        pw.expect(events_tab(page)).to_have_attribute('aria-current', 'page')
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)')).to_be_visible()

        state['beta'] = False  # case décochée : retour à « Bientôt »
        back_to_app(page)
        pw.expect(events_tab(page)).to_have_attribute('aria-disabled', 'true')
    finally:
        context.close()


def test_beta_status_survives_a_relaunch_without_waiting(browser, prod_origin):
    """Relance de l'app : l'onglet est ouvert dès l'affichage (statut mémorisé), puis confirmé par la liaison."""
    state = {'beta': True}
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); beta_services(page, state)
    try:
        page.goto(prod_origin, wait_until='domcontentloaded')
        page.locator('#accountTab').click()
        login(page.frame_locator('#eventsFrame'))
        pw.expect(events_tab(page)).not_to_have_attribute('aria-disabled', 'true')
        assert json.loads(page.evaluate("localStorage.getItem('vp_account')"))['beta'] is True
        page.reload(wait_until='domcontentloaded')
        pw.expect(events_tab(page)).not_to_have_attribute('aria-disabled', 'true')
        events_tab(page).click()
        pw.expect(events_tab(page)).to_have_attribute('aria-current', 'page')
    finally:
        context.close()
