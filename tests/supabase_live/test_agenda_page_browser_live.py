"""Recette RÉELLE de la page publique d'un lien de dispo (17.11.2026) : vrai serveur Party local, base de TEST, vrai
navigateur (Chromium). Un compte de test crée un lien « Rendez-vous pro » (demandes allumées) ; un inconnu ouvre la page
sur téléphone : vue graphique, « Voir en liste », choisit un créneau, remplit le formulaire, envoie ; le créneau est
réservé (il disparaît de la page) ; le propriétaire accepte ; la page de suivi dit « Rendez-vous confirmé ».
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_agenda_page_browser_live.py
Captures dans $AGENDA_SHOTS si la variable est définie."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_agenda_live import anon, ok
from tests.supabase_live.test_audiences_live import GUEST_A, complete_profile
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
pytestmark = [live]
ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(os.environ['AGENDA_SHOTS']) if os.environ.get('AGENDA_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-agenda')), 'ADMIN_PIN': '8462', 'SPOTIFY_CLIENT_ID': '',
           'SPOTIFY_CLIENT_SECRET': '', 'COMPAGNON_ENABLED': '0', 'DISCUSSIONS_ENABLED': '0', 'BAR_ENABLED': '0',
           'PARTY_PUBLIC_URL': f'http://127.0.0.1:{port}',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                if httpx.get(f'{origin}/api/features', timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope='module')
def link():
    owner = Session(GUEST_A)
    complete_profile(owner, 'Agenda Léa')
    sql(f"delete from private.agenda_links where user_id = '{owner.uid}'")
    sql("delete from private.agenda_ip_hits where ip_hash = private.agenda_fp('ip', '127.0.0.1')")
    made = ok(owner.rpc('agenda_link_save', link={
        'name': 'Rendez-vous pro', 'display_name': 'Léa', 'horizon_days': 21, 'duration_min': 60, 'booking_enabled': True,
        'rules': [{'days': [1, 2, 3, 4, 5], 'from': '09:00', 'to': '18:00'}],
        'booking_fields': {'first_name': 'required', 'last_name': 'optional', 'email': 'required', 'phone': 'off', 'message': 'optional'}}))
    yield owner, made
    sql(f"delete from private.agenda_links where id = '{made['id']}'")
    sql(f"delete from public.agenda_items where user_id = '{owner.uid}'")
    sql(f"delete from public.notifications where user_id = '{owner.uid}' and kind like 'booking%'")


@pytest.fixture(scope='module')
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


def test_a_stranger_sees_the_grid_and_the_list_requests_a_slot_and_gets_the_answer(browser, party, link):
    owner, made = link
    slots_before = ok(anon('agenda_public_page', t=made['token'], count_view=False))['slots']
    context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='fr-CH', timezone_id='Europe/Zurich')
    page = context.new_page()
    errors, external = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: None if r.url.startswith(party) else external.append(r.url))
    page.on('dialog', lambda d: d.accept())
    try:
        r = page.goto(f"{party}/d/{made['token']}")
        assert r.status == 200 and r.headers['x-robots-tag'] == 'noindex, nofollow, noarchive'
        pw.expect(page.get_by_role('heading', name='Léa')).to_be_visible()
        pw.expect(page.get_by_text('Prendre rendez-vous avec')).to_be_visible()
        # Vue graphique : bande de jours et blocs « Disponible » à toucher.
        pw.expect(page.get_by_role('tab').first).to_be_visible()
        first = page.locator('.grid.day button.slot').first
        pw.expect(first).to_be_visible()
        shot(page, '01-grille-telephone')
        # La même chose en texte.
        page.get_by_role('button', name='Voir en liste').click()
        pw.expect(page.locator('.lday').first).to_be_visible()
        shot(page, '02-liste-telephone')
        choice = page.locator('button.ls').first
        label = choice.locator('.t').inner_text()
        choice.click()
        pw.expect(page.get_by_role('heading', name='Demander un rendez-vous')).to_be_visible()
        pw.expect(choice).to_have_attribute('aria-pressed', 'true')
        pw.expect(page.get_by_text('obligatoire pour ce rendez-vous').first).to_be_visible()
        assert page.locator('input[type=checkbox]').count() == 0                       # aucune case de consentement
        page.get_by_label('Prénom').fill('Marc')
        page.get_by_label('Adresse e-mail').fill('marc.rochat@example.com')
        page.get_by_label('Votre message').fill('Un appel d’une heure vous irait ?')
        page.wait_for_timeout(3200)                                                     # temps de saisie minimal
        shot(page, '03-formulaire')
        page.get_by_role('button', name='Demander ce rendez-vous').click()
        page.wait_for_url(f'{party}/d/r/**')
        pw.expect(page.get_by_role('heading', name='Demande envoyée')).to_be_visible()
        pw.expect(page.get_by_text('En attente de confirmation')).to_be_visible()
        pw.expect(page.get_by_text(label.replace('–', '–'))).to_be_visible()
        pw.expect(page.get_by_role('button', name='Effacer mes données')).to_be_visible()
        shot(page, '04-demande-envoyee')
        follow = page.url
        # Réservé : le créneau n'est plus proposé à personne.
        slots_after = ok(anon('agenda_public_page', t=made['token'], count_view=False))['slots']
        assert len(slots_after) == len(slots_before) - 1
        # Le propriétaire voit la demande (pastille) et accepte.
        assert ok(owner.rpc('agenda_badge'))['pending'] == 1
        request = ok(owner.rpc('agenda_booking_requests', link=made['id']))[0]
        assert request['first_name'] == 'Marc' and request['verified'] is False
        accepted = ok(owner.rpc('agenda_booking_decide', id=request['id'], accept=True))
        assert owner.get(f"agenda_items?id=eq.{accepted['item_id']}&select=title").json()[0]['title'] == 'Rendez-vous · Marc'
        page.goto(follow)
        pw.expect(page.get_by_role('heading', name='Rendez-vous confirmé')).to_be_visible()
        pw.expect(page.get_by_role('link', name='Ajouter à mon agenda')).to_be_visible()
        shot(page, '05-confirme')
        assert not errors, errors
        assert not external, external                                                    # aucune ressource externe
    finally:
        context.close()


def test_the_desktop_grid_shows_the_week_in_columns_and_a_dead_link_is_neutral(browser, party, link):
    _, made = link
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='fr-CH', color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(f"{party}/d/{made['token']}")
        pw.expect(page.locator('.grid.week .gc').first).to_be_visible()
        assert page.locator('.grid.week .gc').count() >= 1 and page.locator('.grid.week button.slot').count() >= 1
        shot(page, '06-grille-ordinateur-sombre')
        dead = page.goto(f"{party}/d/{'z' * 24}")
        assert dead.status == 404
        pw.expect(page.get_by_role('heading', name='Ce lien n’est plus actif')).to_be_visible()
        shot(page, '07-lien-inactif')
        assert not errors, errors
    finally:
        context.close()
