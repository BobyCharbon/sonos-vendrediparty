"""Vrai navigateur + VRAIE base de test (jamais la prod) : connexion SMS de Root avec le code fixe, puis
Utilisateurs, Membres et Journal remplis par la base. Module construit avec la base de test :
EXPO_PUBLIC_SUPABASE_URL=… EXPO_PUBLIC_SUPABASE_ANON_KEY=… npm run build (dans web/events)."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
TEST_URL = 'https://ewromqfsmcqsthftyhzm.supabase.co'
KEY_FILE = Path.home() / '.config/supabase-claude/test-publishable-key'
DIST = ROOT / 'web/events/dist'

pytestmark = pytest.mark.skipif(
    not (os.environ.get('SUPABASE_LIVE_TESTS') and KEY_FILE.exists() and DIST.exists()
         and any('ewromqfsmcqsthftyhzm' in f.read_text(errors='ignore') for f in DIST.rglob('entry-*.js'))),
    reason='SUPABASE_LIVE_TESTS=1, clé et module construit avec la base de test nécessaires')


@pytest.fixture(scope='module')
def origin(tmp_path_factory):
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('live')), 'EVENTS_WEB_DIR': str(DIST), 'EVENTS_ENABLED': '1',
           'ADMIN_PIN': '8462', 'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'SPOTIFY_CLIENT_ID': ''}
    proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', str(port), '--lifespan', 'off'],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            if httpx.get(url, timeout=1).status_code == 200: break
        except httpx.HTTPError: time.sleep(0.1)
    yield url
    proc.terminate(); proc.wait(timeout=5)


def sign_in_as_root(page):
    page.get_by_label('Ton numéro de téléphone', exact=True).fill('076 557 69 00')
    page.get_by_role('button', name='Recevoir un code par SMS').click()
    page.get_by_placeholder('123456', exact=True).fill('123456')
    page.get_by_role('button', name='Se connecter', exact=True).click()


def test_root_signs_in_on_the_test_database_and_sees_users_members_and_journal(browser, origin):
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(origin + '/events/admin/users', wait_until='domcontentloaded')
        sign_in_as_root(page)
        pw.expect(page.get_by_text('personne(s) inscrite(s) avec leur numéro', exact=False)).to_be_visible(timeout=30000)
        boby = page.get_by_label('Utilisateur Boby')
        pw.expect(boby).to_contain_text('+41765576900')
        pw.expect(boby).to_contain_text('Dernière connexion : ')
        page.get_by_role('button', name='Nom', exact=True).click()
        page.goto(origin + '/events/admin/journal', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Boby a ouvert la liste des membres (numéros compris)', exact=True).first).to_be_visible(timeout=30000)
        page.goto(origin + '/events/admin/members', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('compte(s) inscrit(s)', exact=False)).to_be_visible(timeout=30000)
        pw.expect(page.get_by_text('Boby (toi)', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        page.close()
