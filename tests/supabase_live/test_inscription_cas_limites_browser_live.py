"""Cas limites de l'inscription par lien (campagne du 14.11.2026), comme un invité sur son téléphone (390 × 844) : vrai
navigateur, vrai serveur Party, base de TEST, réglages de la prod (Invitations v2 allumées, Zicou, Discussions et Bar
éteints, CGU exigées).

- lien mal formé, inconnu, arrêté, expiré, plein (événement, groupe, invitation Party, lien public) : une phrase claire en
  français, jamais d'écran blanc ni d'erreur technique ;
- connexion SMS : code faux, code redemandé trop tôt (429) : une phrase claire.
Les parcours avec un compte neuf (abandon au milieu de « Faisons connaissance », surnom, CGU, déjà invité, deux appareils,
compte bloqué) sont dans test_inscription_cas_limites_compte_neuf_browser_live.py.

Lancement (module construit contre CETTE base, voir PARTY_TEST_EVENTS_DIST) :
SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<dist> python -m pytest tests/supabase_live/test_inscription_cas_limites_browser_live.py -q
Captures de chaque étape dans $INSCRIPTION_SHOTS si la variable est définie."""
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, create_event
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
SHOTS = Path(os.environ['INSCRIPTION_SHOTS']) if os.environ.get('INSCRIPTION_SHOTS') else None
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
# Ce qu'un invité ne doit jamais voir : erreur brute de la base, de Supabase ou de JavaScript.
TECHNICAL = re.compile(r'22P02|PGRST|invalid input syntax|uuid|null value|TypeError|undefined|Unexpected|HTTP \d{3}|'
                       r'JWT|For security purposes|otp_expired|Token has expired|rate limit', re.I)


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    """Serveur Party local branché sur la base de test, avec les drapeaux de la prod."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée'
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-cas-limites')), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '9999', 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1',
           'COMPAGNON_ENABLED': '0', 'DISCUSSIONS_ENABLED': '0', 'INVITES_V2_ENABLED': '1', 'BAR_ENABLED': '0',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip()}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(origin, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            raise AssertionError('Le serveur Party de recette ne démarre pas')
        assert httpx.get(f'{origin}/api/features').json() == {'compagnon': False, 'discussions': False, 'invites_v2': True, 'bar': False,
                                                               'patates': False, 'agenda': False, 'pronos': False}
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope='module')
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


def phone_page(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', locale='fr-CH')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    return context, page, errors


SESSIONS: dict[str, Session] = {}
LAST_LOGIN = [0.0]


def session(phone: str, fresh: bool = False) -> Session:
    """Connexion d'un compte de test, gardée (jeton réutilisé) : tous les tests de la base de TEST sortent par la même
    adresse IP et Auth limite les demandes de code par IP (429). Au moins 30 s entre deux connexions ; après un 429,
    2 min 30 d'attente avant chaque nouvel essai (5 essais au plus)."""
    if phone in SESSIONS and not fresh:
        return SESSIONS[phone]
    key = KEY_FILE.read_text().strip()
    base = {'apikey': key, 'Content-Type': 'application/json'}
    for attempt in range(5):
        time.sleep(max(0.0, LAST_LOGIN[0] + 30 - time.monotonic()))
        LAST_LOGIN[0] = time.monotonic()
        sent = httpx.post(f'{TEST_URL}/auth/v1/otp', headers=base, json={'phone': phone}, timeout=30)
        if sent.status_code == 429 and attempt < 4:
            time.sleep(150)
            continue
        assert sent.status_code == 200, sent.text
        r = httpx.post(f'{TEST_URL}/auth/v1/verify', headers=base, json={'type': 'sms', 'phone': phone, 'token': '123456'}, timeout=30)
        assert r.status_code == 200, r.text
        s = Session.__new__(Session)
        s.key, s.uid = key, r.json()['user']['id']
        s.headers = {**base, 'Authorization': f"Bearer {r.json()['access_token']}"}
        SESSIONS[phone] = s
        return s


def assert_clear(page, errors: list):
    """Ni écran blanc, ni texte technique, ni erreur JavaScript."""
    text = page.locator('body').inner_text()
    assert len(text.strip()) > 20, f'écran presque vide : {text!r}'
    assert not TECHNICAL.search(text), text
    assert not errors, errors


@pytest.fixture(scope='module')
def links():
    """Un événement sur invitation (aucune notification) et ses liens : arrêté, plein. Un lien vit au moins une heure
    (create_event_invite) : le lien « expiré » est un vrai lien dont seul l'état lu par la page est remplacé (faux)."""
    admin, guest = session(ADMIN), session(GUEST_A)
    for s in (admin, guest):
        assert s.rpc('accept_terms', p_version=s.rpc('my_terms').json()['version']).status_code in (200, 204)
    event = create_event(admin, 'Recette liens cas limites', visibility='invited')
    revoked = admin.rpc('create_event_invite', e=event, places=3, label='Arrêté').json()['token']
    assert admin.rpc('revoke_invite_link', tok=revoked).status_code in (200, 204)
    full = admin.rpc('create_event_invite', e=event, places=1, label='Une place').json()['token']
    r = guest.rpc('accept_invite', token=full, answer='maybe', first_name=None)
    assert r.status_code == 200, r.text
    expired = admin.rpc('create_event_invite', e=event, places=2, label='Bientôt expiré').json()['token']
    yield {'revoked': revoked, 'full': full, 'expired': expired, 'event': event}
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def expire_in_page(page):
    """La vraie réponse de invite_preview, avec l'état « expired » (une heure d'attente sinon)."""
    def handle(route):
        response = route.fetch()
        body = response.json()
        route.fulfill(response=response, json={**body, 'state': 'expired'} if isinstance(body, dict) else body)
    page.route('**/rest/v1/rpc/invite_preview', handle)


CLOSED_CASES = [
    ('invite/abc', 'Ce lien d’invitation n’est pas complet'),
    ('invite/4b1c0d2e-9a7f-4c3e-8d21', 'Ce lien d’invitation n’est pas complet'),          # lien coupé dans le message
    (f'invite/{uuid.uuid4()}', 'Ce lien d’invitation n’existe plus.'),
    ('revoked', 'La personne qui t’a invité a arrêté ce lien. Demande-lui un nouveau lien.'),
    ('expired', 'Ce lien n’est plus valable (date limite passée). Demande un nouveau lien à la personne qui t’a invité.'),
    ('full', 'Ce lien a déjà servi : toutes ses places sont prises. Demande ton propre lien à la personne qui t’a invité.'),
]


@pytest.mark.parametrize('path, expected', CLOSED_CASES, ids=['mal-forme', 'coupe', 'inconnu', 'arrete', 'expire', 'plein'])
def test_a_broken_stopped_expired_or_full_event_link_says_so_in_plain_french(browser, party, links, path, expected):
    expired = path == 'expired'
    if path in links:
        path = f'invite/{links[path]}'
    context, page, errors = phone_page(browser)
    try:
        if expired:
            expire_in_page(page)
        page.goto(f'{party}/events/{path}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text(expected, exact=False)).to_be_visible(timeout=20000)
        shot(page, f'lien-{path.split("/")[0]}-{expected[:20]}')
        # Aucun bouton de réponse sur un lien fermé.
        pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
        assert_clear(page, errors)
    finally:
        context.close()


@pytest.mark.parametrize('path', ['group-invite/abc', f'group-invite/{uuid.uuid4()}', 'join/abc', f'join/{uuid.uuid4()}',
                                  'share/abc', f'share/{uuid.uuid4()}'],
                         ids=['groupe-mal-forme', 'groupe-inconnu', 'party-mal-forme', 'party-inconnu', 'public-mal-forme', 'public-inconnu'])
def test_other_broken_links_without_account_never_show_a_blank_or_technical_screen(browser, party, path):
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/{path}', wait_until='domcontentloaded')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1500)
        shot(page, f'autre-{path.replace("/", "-")[:30]}')
        assert_clear(page, errors)
    finally:
        context.close()


def test_a_wrong_sms_code_then_a_code_asked_again_too_early_are_said_clearly(browser, party):
    """Code faux : « Code incorrect ou expiré. » ; code redemandé aussitôt (429 d'Auth) : attendre, en secondes."""
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/invite/{uuid.uuid4()}', wait_until='domcontentloaded')
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
        page.get_by_label('Ton numéro de téléphone', exact=True).fill('079 000 00 02')
        code = page.get_by_placeholder('123456', exact=True)
        for _ in range(3):  # un code par numéro et par minute : d'autres tests ont pu en demander un
            page.get_by_role('button', name='Recevoir un code par SMS').click()
            try:
                code.wait_for(timeout=15000)
                break
            except Exception:
                pw.expect(page.get_by_text(re.compile('^Attends (quelques|\\d+) secondes'))).to_be_visible()
                page.wait_for_timeout(31000)
        code.fill('000000')
        page.get_by_role('button', name='Se connecter', exact=True).click()
        pw.expect(page.get_by_text('Code incorrect ou expiré.', exact=True)).to_be_visible(timeout=15000)
        shot(page, 'sms-code-faux')
        assert_clear(page, errors)
        page.get_by_role('button', name='Changer de numéro').click()
        page.get_by_role('button', name='Recevoir un code par SMS').click()
        pw.expect(page.get_by_text(re.compile('^(Attends (quelques|\\d+) secondes avant de redemander un code\\.|'
                                              'Trop de demandes de code\\. Réessaie dans quelques minutes\\.)$'))).to_be_visible(timeout=15000)
        shot(page, 'sms-trop-tot')
        assert_clear(page, errors)
    finally:
        context.close()


def test_a_signed_in_member_opening_broken_links_reads_a_clear_sentence(browser, party):
    """Compte complet (Testeur, 41790000001) : groupe inconnu, invitation inconnue, lien public d'un événement inconnu."""
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
        page.get_by_label('Ton numéro de téléphone', exact=True).fill('079 000 00 01')
        code = page.get_by_placeholder('123456', exact=True)
        for _ in range(6):
            page.get_by_role('button', name='Recevoir un code par SMS').click()
            try:
                code.wait_for(timeout=15000)
                break
            except Exception:
                page.wait_for_timeout(31000)
        code.fill('123456')
        page.get_by_role('button', name='Se connecter', exact=True).click()
        page.wait_for_timeout(3000)
        cases = [(f'group-invite/{uuid.uuid4()}', 'le lien du groupe change quand il est renouvelé'),
                 (f'invite/{uuid.uuid4()}', 'Ce lien d’invitation n’existe plus.'),
                 (f'share/{uuid.uuid4()}', None)]
        for path, expected in cases:
            page.goto(f'{party}/events/{path}', wait_until='domcontentloaded')
            if expected:
                pw.expect(page.get_by_text(expected, exact=False)).to_be_visible(timeout=20000)
            else:
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(2500)
            shot(page, f'connecte-{path.split("/")[0]}')
            assert_clear(page, errors)
    finally:
        context.close()
