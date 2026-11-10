"""Recette RÉELLE de l'inscription des invités (avis 39f148377a8f du 10.11, sondage du paintball) : vrai navigateur, vrai
serveur Party, vraie base (base de TEST ou sa copie locale Supabase dans Docker), CGU exigées comme en prod.

Parcours testés comme un invité sur son téléphone (390 px) :
1. lien d'invitation d'un sondage PUBLIC → « Choisir mes dates » → page de connexion NORMALE (pays, numéro, code SMS) →
   retour sur le lien → « Faisons connaissance » (prénom, nom, surnom) → CGU → votes → la fiche de l'événement ;
2. lien public (« Partager le lien ») d'un sondage → connexion → profil complet → la FICHE, où l'on vote ;
puis l'organisateur voit ces deux personnes, d'où elles viennent, et leurs votes.

Lancement (module construit contre CETTE base, voir PARTY_TEST_EVENTS_DIST) :
SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<dist> python -m pytest tests/supabase_live/test_inscription_complete_browser_live.py -q
Captures de chaque étape dans $INSCRIPTION_SHOTS si la variable est définie."""
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_inscription_complete_live import reset_account
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
SHOTS = Path(os.environ['INSCRIPTION_SHOTS']) if os.environ.get('INSCRIPTION_SHOTS') else None
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
LINK_GUEST, SHARE_GUEST = ('41768163120', '076 816 31 20'), ('41790000006', '079 000 00 06')


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    """Serveur Party local, module Événements branché sur la base de test, Invitations v2 allumées (comme la prod)."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    # Le module visé doit parler à CETTE base (adresse figée à la construction), jamais à la prod.
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée'
    # Environnement minimal : aucun secret de la machine ne passe au serveur de recette.
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-inscription')), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '8462', 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'INVITES_V2_ENABLED': '1',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'PYTHONDONTWRITEBYTECODE': '1'}
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


@pytest.fixture(scope='module')
def poll():
    """Sondage PUBLIC (le cas du paintball : public par défaut), deux dates, un lien pour plusieurs personnes."""
    admin = Session(ADMIN)
    assert admin.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    accounts = [Session(phone) for phone, _ in (LINK_GUEST, SHARE_GUEST)]
    for s in accounts:
        reset_account(s.uid)
    event = create_event(admin, 'Paintball recette', visibility='all', public_link=True, date_mode='poll', starts_at=None)
    options = []
    for days in (20, 27):
        r = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                       json={'event_id': event, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()})
        assert r.status_code == 201, r.text
        options.append(r.json()[0]['id'])
    link = admin.rpc('create_event_invite', e=event, places=10, label='Groupe paintball').json()
    yield admin, event, options, link['token'], accounts
    sql(f"delete from public.events where id = '{event}'")
    for s in accounts:
        reset_account(s.uid)


def phone_page(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', locale='fr-CH')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    return context, page, errors


def sign_in(page, number: str):
    """La page de connexion normale de l'app : pays, numéro, code SMS (code fixe des numéros de test)."""
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
    pw.expect(page.get_by_role('radio', name='Suisse +41')).to_be_visible()
    page.get_by_label('Ton numéro de téléphone', exact=True).fill(number)
    code = page.get_by_placeholder('123456', exact=True)
    for _ in range(3):  # limite d'Auth : un code par minute et par numéro (la préparation du test en a déjà demandé un)
        page.get_by_role('button', name='Recevoir un code par SMS').click()
        try:
            code.wait_for(timeout=15000)
            break
        except Exception:
            if not page.get_by_text('Attends quelques secondes', exact=False).is_visible():
                shot(page, 'zz-echec-code-sms')
                raise
            page.wait_for_timeout(31000)
    code.fill('123456')
    page.get_by_role('button', name='Se connecter', exact=True).click()


def complete_profile(page, first: str, last: str, nickname: str):
    """« Faisons connaissance » : le formulaire de toute l'app, puis les CGU (exigées comme en prod)."""
    pw.expect(page.get_by_text('Faisons connaissance', exact=True)).to_be_visible(timeout=20000)
    page.get_by_label('Prénom', exact=True).fill(first)
    page.get_by_label('Nom', exact=True).fill(last)
    page.get_by_label('Surnom', exact=False).fill(nickname)
    page.get_by_role('button', name=re.compile('^Continuer')).click()
    accept = page.get_by_role('button', name='J’accepte')
    accept.wait_for(timeout=15000)
    accept.click()


def test_a_guest_invited_by_link_to_a_public_poll_registers_fully_and_the_organizer_sees_his_votes(browser, party, poll):
    admin, event, (first, second), token, (guest, _other) = poll
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/invite/{token}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Paintball recette', exact=True)).to_be_visible(timeout=20000)
        pw.expect(page.get_by_text('Sois le premier à voter', exact=True)).to_be_visible()
        shot(page, '01-lien-carte-sondage')
        page.get_by_role('button', name='📅 Choisir mes dates').click()
        shot(page, '02-lien-connexion-normale')
        sign_in(page, LINK_GUEST[1])
        complete_profile(page, 'Léa', 'Paint', 'Léa P.')
        shot(page, '03-lien-profil-complet')
        pw.expect(page.get_by_text('Tes dates, Léa', exact=True)).to_be_visible(timeout=20000)
        page.get_by_role('button', name=re.compile('^Oui : ')).first.click()
        page.get_by_role('button', name=re.compile('^Non : ')).nth(1).click()
        pw.expect(page.get_by_text('C’est noté, Léa !', exact=True)).to_be_visible(timeout=15000)
        shot(page, '04-lien-votes')
        page.get_by_role('button', name='Voir l’événement et les votes').click()
        page.wait_for_url(f'**/events/event/{event}', timeout=20000)
        pw.expect(page.get_by_text('Quelle date ?', exact=True)).to_be_visible(timeout=20000)
        shot(page, '05-lien-fiche')
        assert not errors, errors
    finally:
        context.close()

    # En base : profil complet, invité par le lien, votes enregistrés ; jamais un compte « léger » à purger.
    assert sql(f"select private.identity_complete('{guest.uid}') ok") == [{'ok': True}]
    assert sql(f"select via_link from public.event_invites where event_id = '{event}' and user_id = '{guest.uid}'") == [{'via_link': True}]
    votes = {row['option_id']: row['vote'] for row in sql(
        f"select option_id::text, vote::text from public.date_votes where user_id = '{guest.uid}'")}
    assert votes == {first: 'yes', second: 'no'}
    assert not sql(f"select 1 from private.light_invitees where user_id = '{guest.uid}'")
    # L'organisateur le voit : dans la liste des invités (venu par le lien, a voté) et dans le sondage.
    listed = {p['id']: p for p in admin.rpc('event_guest_list', e=event).json()['people']}
    assert listed[guest.uid]['name'] == 'Léa P.' and listed[guest.uid]['source'] == 'link' and listed[guest.uid]['voted']


def test_a_guest_from_the_public_share_link_registers_fully_and_votes_on_the_event_page(browser, party, poll):
    admin, event, (first, _second), _token, (_guest, other) = poll
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/share/{event}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Paintball recette', exact=True)).to_be_visible(timeout=20000)
        pw.expect(page.get_by_role('button', name='Présent', exact=False)).to_have_count(0)  # jamais « Présent » sur un sondage
        shot(page, '06-partage-sondage-sans-compte')
        page.get_by_role('button', name='Se connecter pour choisir mes dates').click()
        sign_in(page, SHARE_GUEST[1])
        complete_profile(page, 'Marc', 'Partage', 'Marc P.')
        # Profil complet : la fiche de l'événement, comme pour tout membre ; on y vote.
        page.wait_for_url(f'**/events/event/{event}', timeout=20000)
        pw.expect(page.get_by_text('Quelle date ?', exact=True)).to_be_visible(timeout=20000)
        page.get_by_role('button', name=re.compile('^Oui : ')).first.click()
        pw.expect(page.get_by_text('2 votants', exact=True)).to_be_visible(timeout=15000)
        shot(page, '07-partage-fiche-vote')
        assert not errors, errors
    finally:
        context.close()

    assert sql(f"select vote::text from public.date_votes where user_id = '{other.uid}' and option_id = '{first}'") == [{'vote': 'yes'}]
    listed = {p['id']: p for p in admin.rpc('event_guest_list', e=event).json()['people']}
    assert listed[other.uid]['name'] == 'Marc P.' and listed[other.uid]['voted']
