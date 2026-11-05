"""Zicou sur la fiche d'un membre du module Événements (Discussions, participants, amis), dans un vrai navigateur :
vedette avec son Zicou (toucher → onglet Zicou sur sa visite), œuf terne « Pas encore de Zicou » + « Adopter le mien »,
et rien quand le Zicou est éteint (production). Supabase simulé ; /api/pet/profile simulée (route testée par
tests/test_zicou_profile.py). Captures si E2E_SHOTS est donné."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

from tests.test_chats_browser import CORS, LEA, phone  # noqa: F401 (fixtures)
from tests.test_direct_messages_browser import signed_in
from tests.test_events_browser import DIST, ROOT, browser, pw  # noqa: F401 (fixtures)
from tests.test_moderation_browser import moderation_services

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

SPOTLIGHT = {'member': LEA, 'me': False, 'friend': True, 'mine': True,
             'zicou': {'name': 'Paillette', 'stage': 'adult', 'variant': 'star', 'emotion': 'happy', 'outfit': None,
                       'acc': {'head': 'couronne'}, 'shiny': True, 'gen': 2, 'age_days': 5,
                       'best': {'id': 'couronne', 'slot': 'head', 'label': 'Couronne', 'emoji': '👑', 'rarity': 'epic',
                                'rarity_label': 'Épique', 'color': '#a565ff'},
                       'acc_items': [{'id': 'couronne', 'slot': 'head', 'label': 'Couronne', 'emoji': '👑', 'rarity': 'epic',
                                      'rarity_label': 'Épique', 'color': '#a565ff'}]}}
NONE = {'member': LEA, 'me': False, 'friend': False, 'mine': False, 'zicou': None}


def party(tmp_path_factory, compagnon: str):
    """Party qui sert le module construit, Zicou allumé (site de test) ou éteint (production)."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('zicou-profile')), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '8462', 'COMPAGNON_ENABLED': compagnon, 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': ''}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                urlopen(origin + '/api/features', timeout=1).read()
                break
            except OSError:
                time.sleep(0.2)
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope='module')
def zicou_origin(tmp_path_factory):
    yield from party(tmp_path_factory, '1')


@pytest.fixture(scope='module')
def zicou_off_origin(tmp_path_factory):
    yield from party(tmp_path_factory, '0')


def serve_zicou(page, body):
    calls = []

    def handle(route):
        calls.append(json.loads(route.request.post_data or '{}'))
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
    page.route('**/api/pet/profile', handle)
    return calls


def shot(page, name):
    if os.environ.get('E2E_SHOTS'):
        Path(os.environ['E2E_SHOTS']).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(os.environ['E2E_SHOTS']) / f'{name}.png'), full_page=True)


def test_a_member_with_a_zicou_is_shown_in_the_spotlight(phone, zicou_origin):
    page, errors = phone
    moderation_services(page, accepted=True)['blocks'] = []   # Léa n'est pas bloquée
    calls = serve_zicou(page, SPOTLIGHT)
    signed_in(page, zicou_origin, f'/member/{LEA}')
    block = page.get_by_test_id('zicou-profile')
    pw.expect(block).to_contain_text('Paillette', timeout=15000)
    pw.expect(block).to_contain_text('Génération 2 · 5 jours')
    pw.expect(block.locator('.zp-shiny-tag')).to_be_visible()
    assert block.locator('svg.pt-svg').count() == 1
    assert calls and calls[0]['member'] == LEA and calls[0]['token']
    page.wait_for_timeout(600)
    shot(page, 'zicou_profile_events_with')
    page.get_by_role('button', name='Lui rendre visite ›').click()
    page.wait_for_url('**/?pet=1&visit=' + LEA)   # module ouvert seul : la page Party, onglet Zicou, sur sa visite
    assert not [e for e in errors if 'pet' not in e], errors


def test_without_a_zicou_a_dull_egg_and_adopt_mine(phone, zicou_origin):
    page, errors = phone
    moderation_services(page, accepted=True)['blocks'] = []   # Léa n'est pas bloquée
    serve_zicou(page, NONE)
    signed_in(page, zicou_origin, f'/member/{LEA}')
    block = page.get_by_test_id('zicou-profile')
    pw.expect(block).to_contain_text('Pas encore de Zicou', timeout=15000)
    assert block.locator('.zp-halo, .zp-glint, .zp-chrome').count() == 0
    shot(page, 'zicou_profile_events_without')
    page.get_by_role('button', name='Adopter le mien').click()
    page.wait_for_url('**/?pet=1')
    assert not errors, errors


def test_nothing_when_zicou_is_off(phone, zicou_off_origin):
    page, errors = phone
    moderation_services(page, accepted=True)['blocks'] = []   # Léa n'est pas bloquée
    calls = serve_zicou(page, SPOTLIGHT)
    signed_in(page, zicou_off_origin, f'/member/{LEA}')
    pw.expect(page.get_by_text('Léa').first).to_be_visible(timeout=15000)
    page.wait_for_timeout(800)
    pw.expect(page.get_by_test_id('zicou-profile')).to_have_count(0)
    assert calls == []
    shot(page, 'zicou_profile_events_off')
    assert not errors, errors
