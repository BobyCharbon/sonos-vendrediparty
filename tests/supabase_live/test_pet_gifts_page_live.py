"""Écran « Cadeaux de l'événement » (module Événements) dans un vrai navigateur + VRAIE base de test (jamais la prod) :
l'Admin de test prépare les objets à gagner et leur chance, voit l'aperçu des chances, publie (chances figées) ; le
règlement dit « Apple et Google ne sont ni organisateurs ni sponsors ». Module construit avec la base de test
(EVENTS_DIST, par défaut web/events/dist). Captures dans E2E_SHOTS."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_admin_pages_live import sign_in_as_admin
from tests.supabase_live.test_pet_live import sql_test

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
TEST_URL = 'https://ewromqfsmcqsthftyhzm.supabase.co'
KEY_FILE = Path.home() / '.config/supabase-claude/test-publishable-key'
DIST = Path(os.environ.get('EVENTS_DIST', ROOT / 'web/events/dist'))
SHOTS = Path(os.environ.get('E2E_SHOTS', ROOT / 'test-results' / 'shots'))
EVENT = '6e7a0000-0000-4000-8000-00000000c0ff'
ADMIN_ID = 'a7610087-3f63-43d0-8657-a3459f0fddcb'

pytestmark = pytest.mark.skipif(
    not (os.environ.get('SUPABASE_LIVE_TESTS') and KEY_FILE.exists() and DIST.exists()
         and any('ewromqfsmcqsthftyhzm' in f.read_text(errors='ignore') for f in DIST.rglob('entry-*.js'))),
    reason='SUPABASE_LIVE_TESTS=1, clé et module construit avec la base de test nécessaires')


@pytest.fixture(scope='module')
def origin(tmp_path_factory):
    sql_test(f"""delete from public.events where id = '{EVENT}';
      insert into public.events (id, title, created_by, status, starts_at, ends_at, notify_on_publish, reminders)
      values ('{EVENT}', 'Soirée disco (test cadeaux)', '{ADMIN_ID}', 'published', now() + interval '3 days', now() + interval '3 days 6 hours', false, '{{}}');""")
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('live')), 'EVENTS_WEB_DIR': str(DIST), 'EVENTS_ENABLED': '1',
           'ADMIN_PIN': '8462', 'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'SPOTIFY_CLIENT_ID': ''}
    proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', str(port), '--lifespan', 'off'],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}'
    for _ in range(600):
        try:
            if httpx.get(url, timeout=1).status_code == 200: break
        except httpx.HTTPError: time.sleep(0.1)
    yield url
    proc.terminate(); proc.wait(timeout=5)
    sql_test(f"delete from public.events where id = '{EVENT}';")


def test_the_admin_prepares_previews_and_publishes_the_event_gifts(browser, origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=3)
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(origin + '/events/admin/users', wait_until='domcontentloaded')
        sign_in_as_admin(page)
        pw.expect(page.get_by_text('personne(s) inscrite(s) avec leur numéro', exact=False)).to_be_visible(timeout=30000)
        page.goto(f'{origin}/events/event/{EVENT}', wait_until='domcontentloaded')
        link = page.get_by_text('🎁 Cadeaux Zicou de l’événement')
        pw.expect(link).to_be_visible(timeout=30000)
        link.click()
        pw.expect(page.get_by_text('Ajouter un objet')).to_be_visible(timeout=30000)
        page.get_by_text('Nœud doré', exact=True).click()
        page.get_by_role('button', name='Épique', exact=True).click()
        page.get_by_text('Lumi la luciole', exact=True).click()
        page.get_by_role('button', name='Légendaire', exact=True).click()
        page.get_by_text('« Hôte de la soirée » : projecteurs', exact=True).click()
        pw.expect(page.get_by_text('Aperçu des chances')).to_be_visible()
        page.get_by_role('button', name='Enregistrer le brouillon').click()
        pw.expect(page.get_by_role('button', name='Publier les chances')).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Apple et Google ne sont ni organisateurs ni sponsors', exact=False)).to_be_visible()
        page.screenshot(path=str(SHOTS / 'coll-8-admin-cadeaux-evenement.png'), full_page=True)
        page.get_by_role('button', name='Publier les chances').click()
        page.get_by_role('button', name='Publier : elles ne changeront plus').click()
        pw.expect(page.get_by_text('Chances publiées (figées)')).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Empreinte de la graine (sha256)', exact=False)).to_be_visible()
        page.screenshot(path=str(SHOTS / 'coll-9-cadeaux-publies.png'), full_page=True)
        row = sql_test(f"select status, jsonb_array_length(prizes) as n from public.pet_event_drops where event_id = '{EVENT}';")
        assert row == [{'status': 'published', 'n': 3}]
        assert not errors, errors
    finally:
        page.close()
