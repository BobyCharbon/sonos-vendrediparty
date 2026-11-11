"""Recette RÉELLE des écrans du bar de la soirée (maquettes v6) : vrai navigateur (téléphone 390 px), vrai serveur Party
(BAR_ENABLED=1), vraie base (base de TEST ou sa copie locale), comptes de test à code SMS fixe.
1. Invité « Présent » : la carte du bar sur la fiche (solde EN GRAND), « Mon bar », maximum en attente, commande avec la
   case d'engagement (bouton éteint tant qu'elle n'est pas cochée), annulation d'un verre en attente ;
2. barman : « Scanner au bar », code du QR, choix des quantités, « Servir 1 article · 4.50 CHF », « Servi à … », suivant ;
3. invité : solde débité (4.50 CHF) en grand, « J'ai remboursé » ;
4. organisateur : « Gérer le bar » (articles, ajout d'un article, onglets), « Direct », fiche personne.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<dist construit contre cette base> python -m pytest \
  tests/supabase_live/test_bar_soiree_browser_live.py -q   (captures dans $BAR_SHOTS si défini)"""
import os
import re
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, complete_profile, create_event
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import KEY_FILE, LOCAL_TEST, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
SHOTS = Path(os.environ['BAR_SHOTS']) if os.environ.get('BAR_SHOTS') else None
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
PHONES = {ADMIN: '079 000 00 04', GUEST_A: '079 000 00 01', VIP: '079 000 00 03'}


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée (jamais la prod)'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-bar')), 'EVENTS_WEB_DIR': str(DIST), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'INVITES_V2_ENABLED': '1', 'BAR_ENABLED': '1',
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
def bar():
    admin, guest, barman = Session(ADMIN), Session(GUEST_A), Session(VIP)
    for s in (admin, guest, barman):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    complete_profile(barman, 'VIP test')  # remis à vide par la recette de l'inscription : le bar exige un profil complet
    event = create_event(admin, 'Soirée bar recette', visibility='all', public_link=True)
    for s in (admin, guest, barman):
        r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=s.headers, timeout=30, json={'event_id': event, 'user_id': s.uid, 'status': 'yes'})
        assert r.status_code in (200, 201, 409), r.text
    assert admin.rpc('bar_create', e=event).status_code == 200
    admin.rpc('bar_save_item', e=event, item={'name': 'Vodka Red Bull', 'emoji': '🍸', 'price_chf': 4.5, 'stock': 5, 'age_min': 18, 'max_pending': 2})
    admin.rpc('bar_save_item', e=event, item={'name': 'Coca', 'emoji': '🥤', 'price_chf': 2})
    admin.rpc('bar_save_settings', e=event, settings={'orders_open': True, 'pay_method': 'revolut',
                                                       'repay_by': (date.today() + timedelta(days=3)).isoformat()})
    assert admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True).status_code == 200
    if not LOCAL_TEST:
        time.sleep(61)  # base de TEST : un code SMS par minute et par numéro (connexions faites ci-dessus)
    yield admin, guest, barman, event
    sql(f"delete from public.events where id = '{event}'")


def signed_in_page(browser, phone: str, origin: str, event: str, errors: list):
    """La connexion normale de l'app (numéro, code fixe des comptes de test), puis la fiche de l'événement."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', locale='fr-CH')
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{origin}/events/sign-in')
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
    page.get_by_label('Ton numéro de téléphone', exact=True).fill(PHONES[phone])
    page.get_by_role('button', name='Recevoir un code par SMS').click()
    page.get_by_placeholder('123456', exact=True).fill('123456')
    page.get_by_role('button', name='Se connecter', exact=True).click()
    page.wait_for_timeout(3000)
    page.goto(f'{origin}/events/event/{event}')
    return context, page


def test_a_guest_orders_with_the_pledge_the_barman_serves_and_the_balance_shows_big(browser, party, bar):
    _admin, guest, _barman, event = bar
    errors: list = []
    gctx, g = signed_in_page(browser, GUEST_A, party, event, errors)
    try:
        # Fiche : la carte du bar, solde en grand, puis « Mon bar ».
        pw.expect(g.get_by_text('🍹 Bar de la soirée')).to_be_visible(timeout=30000)
        pw.expect(g.get_by_test_id('bar-balance').first).to_be_visible()
        shot(g, '01-fiche-invite')
        g.get_by_text('Ouvrir le bar ›').click()
        pw.expect(g.get_by_role('button', name='Ajouter : Vodka Red Bull')).to_be_visible(timeout=15000)
        # Maximum 2 en attente : le + se bloque, avec la phrase de l'admin.
        g.get_by_role('button', name='Ajouter : Vodka Red Bull').click()
        g.get_by_role('button', name='Ajouter : Vodka Red Bull').click()
        pw.expect(g.get_by_text('Maximum 2 en attente par personne', exact=False)).to_be_visible()
        pw.expect(g.get_by_role('button', name='Ajouter : Vodka Red Bull')).to_be_disabled()
        g.get_by_role('button', name='Ajouter : Coca').click()
        shot(g, '02-mon-bar-panier')
        # Engagement coché à CHAQUE commande : bouton éteint tant que la case n'est pas cochée.
        g.get_by_role('button', name='Commander · 11 CHF').click()
        pw.expect(g.get_by_text('Ta commande')).to_be_visible()
        pw.expect(g.get_by_text(re.compile('Je m.engage à rembourser à')).first).to_be_visible()
        pw.expect(g.get_by_role('button', name='Valider la commande')).to_be_disabled()
        shot(g, '03-engagement')
        g.get_by_role('checkbox').click()
        g.get_by_role('button', name='Valider la commande').click()
        pw.expect(g.get_by_text('En attente', exact=True)).to_be_visible(timeout=15000)
        assert sql(f"select count(*) n from public.event_bar_pledges where event_id = '{event}' and user_id = '{guest.uid}'") == [{'n': 1}]
        g.get_by_role('button', name='Annuler 1 Coca').click()
        pw.expect(g.get_by_role('button', name='Annuler 1 Coca')).to_have_count(0, timeout=10000)
        shot(g, '04-en-attente')
        code = guest.rpc('my_bar', e=event).json()['qr']['code']

        # Barman : scanner, choisir, servir, suivant.
        bctx, b = signed_in_page(browser, VIP, party, event, errors)
        try:
            b.get_by_role('button', name='🍹 Scanner au bar').click()
            pw.expect(b.get_by_label('Code du QR')).to_be_visible(timeout=15000)
            b.get_by_label('Code du QR').fill(code)
            b.get_by_role('button', name='Valider', exact=True).click()
            pw.expect(b.get_by_text('A commandé (choisis ce que tu sers) :')).to_be_visible(timeout=15000)
            b.get_by_role('button', name='Ajouter : Vodka Red Bull').click()
            shot(b, '05-barman-choix')
            b.get_by_role('button', name='Servir 1 article · 4.50 CHF').click()
            pw.expect(b.get_by_text('Servi à', exact=False)).to_be_visible(timeout=15000)
            pw.expect(b.get_by_role('button', name=re.compile('^Annuler ce service, encore'))).to_be_visible()
            shot(b, '06-barman-servi')
            b.get_by_role('button', name='📷 Scanner le suivant').click()
            pw.expect(b.get_by_label('Code du QR')).to_be_visible()
        finally:
            bctx.close()

        # Invité : le solde débité, en grand ; « J'ai remboursé ».
        g.reload()
        pw.expect(g.get_by_test_id('bar-balance').first).to_contain_text('4.50', timeout=20000)
        shot(g, '07-solde-debite')
        g.get_by_role('button', name='J’ai remboursé').click()
        g.wait_for_timeout(2000)
        assert sql(f"select amount_chf::text a from public.event_bar_refunds where event_id = '{event}' and user_id = '{guest.uid}'") == [{'a': '4.50'}]
        shot(g, '08-rembourse')
        assert not errors, errors
    finally:
        gctx.close()


def test_the_organizer_manages_items_and_sees_who_owes_what(browser, party, bar):
    _admin, guest, _barman, event = bar
    errors: list = []
    actx, a = signed_in_page(browser, ADMIN, party, event, errors)
    try:
        a.get_by_role('button', name='🍹 Gérer le bar').click()
        pw.expect(a.get_by_text('Commandes ouvertes')).to_be_visible(timeout=15000)
        a.get_by_role('button', name='+ Ajouter un article').click()
        a.get_by_label('Nom', exact=True).fill('Bière')
        a.get_by_label('Prix (CHF)').fill('3')
        a.get_by_label('Stock acheté').fill('24')
        a.get_by_role('button', name='16+').click()
        a.get_by_role('button', name='Ajouter l’article').click()
        pw.expect(a.get_by_role('button', name='Modifier Bière')).to_be_visible(timeout=15000)
        assert sql(f"select price_chf::text p, stock, age_min from public.event_bar_items where event_id = '{event}' and name = 'Bière'") == \
            [{'p': '3.00', 'stock': 24, 'age_min': 16}]
        shot(a, '09-orga-articles')
        for tab in ('Rembourser', 'Barmans', 'Direct'):
            a.get_by_role('tab', name=tab).click()
            a.wait_for_timeout(800)
            shot(a, f'10-orga-{tab.lower()}')
        name = sql(f"select display_name from public.profiles where id = '{guest.uid}'")[0]['display_name']
        detail = a.get_by_role('button', name=f'Détail de {name}', exact=False).first
        pw.expect(detail).to_be_visible(timeout=15000)
        detail.click()
        pw.expect(a.get_by_text('Réservé, pas encore servi')).to_be_visible(timeout=15000)
        shot(a, '11-orga-personne')
        assert not errors, errors
    finally:
        actx.close()
