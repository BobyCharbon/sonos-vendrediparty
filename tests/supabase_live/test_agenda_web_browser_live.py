"""Recette RÉELLE des écrans de l'Agenda dans Party (17.11.2026) : vrai navigateur (Chromium, téléphone 390 px), vrai
serveur Party local, module Événements construit contre la base de TEST, drapeaux comme la prod, CGU exigées.

Guest A (propriétaire) dans Party :
1. « 📅 Agenda » de l'en-tête d'Événements → la semaine ; crée un rendez-vous (« Recette agenda web », demain) ;
2. Calendriers › Partager › « Partager mes dispos » : tout décoché, coche le groupe de recette → « C'est fait » ;
3. « Qui est libre ? » : Guest B (qui partage, occupé un soir) a sa ligne, le 3e membre (qui ne partage pas) est grisé
   dans « Les autres membres », sans texte ;
4. Mes liens de dispo : crée un lien (Jours de semaine, demandes allumées) ;
puis un INCONNU (autre navigateur, sans compte) ouvre la page publique et demande un rendez-vous : la pastille « 1 »
apparaît chez Guest A sans recharger (signal user:<id>), il ouvre la demande et l'accepte ; la pastille disparaît, le
rendez-vous « Rendez-vous · Marc » est dans son agenda.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $AGENDA_WEB_SHOTS si la variable est définie."""
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest

from tests.supabase_live.test_agenda_live import ok
from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B, VIP, complete_profile
from tests.supabase_live.test_inscription_complete_browser_live import phone_page, sign_in
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
SHOTS = Path(os.environ['AGENDA_WEB_SHOTS']) if os.environ.get('AGENDA_WEB_SHOTS') else None
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SWISS = ZoneInfo('Europe/Zurich')
GROUP = 'Agenda recette web'
ITEM = 'Recette agenda web'


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(800)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    """Serveur Party local, module branché sur la base de test, drapeaux de la prod (/api/features)."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée'
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-agenda-web')), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '8462', 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'INVITES_V2_ENABLED': '1',
           'COMPAGNON_ENABLED': '0', 'DISCUSSIONS_ENABLED': '1', 'BAR_ENABLED': '1',
           'PARTY_PUBLIC_URL': f'http://127.0.0.1:{port}',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if httpx.get(f'{origin}/api/features', timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.2)
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


def cleanup(people):
    ids = "', '".join(s.uid for s in people)
    for s in people:
        s.rpc('agenda_stop_sharing')
    sql(f"delete from private.agenda_links where user_id in ('{ids}')")
    sql(f"delete from public.agenda_items where user_id in ('{ids}')")
    sql(f"delete from public.agenda_prefs where user_id in ('{ids}')")
    sql(f"delete from public.notifications where user_id in ('{ids}') and kind like 'booking%'")
    sql(f"delete from public.member_groups where name = '{GROUP}'")
    sql("delete from private.agenda_ip_hits where ip_hash = private.agenda_fp('ip', '127.0.0.1')")


@pytest.fixture(scope='module')
def people():
    owner, friend, other = Session(GUEST_A), Session(GUEST_B), Session(VIP)
    complete_profile(owner, 'Agenda Léa')
    complete_profile(friend, 'Agenda Yanis')
    complete_profile(other, 'Agenda Sam')
    cleanup([owner, friend, other])
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**owner.headers, 'Prefer': 'return=representation'},
                   json={'name': GROUP}, timeout=30)
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{friend.uid}'), ('{gid}', '{other.uid}') "
        "on conflict do nothing")
    # Guest B partage ses dispos avec le groupe (ce qu'il note « Occupé » dans Party) : pris chaque soir dès demain, 19 h – 21 h.
    busy = (datetime.now(SWISS) + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    ok(friend.rpc('agenda_item_save', item={'title': 'Entraînement', 'starts_at': busy.isoformat(),
                                             'ends_at': (busy + timedelta(hours=2)).isoformat(), 'repeat': 'daily'}))
    ok(friend.rpc('agenda_set_sharing', groups=[gid], share_party=True, share_manual=True))
    yield owner, friend, other, gid
    cleanup([owner, friend, other])


def test_the_agenda_in_party_for_real(browser, party, people):
    owner, friend, other, gid = people
    context, page, errors = phone_page(browser, alone=True)
    stranger = browser.new_context(viewport={'width': 390, 'height': 844}, locale='fr-CH', timezone_id='Europe/Zurich')
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 01')
        agenda = page.get_by_test_id('home-agenda')
        pw.expect(agenda).to_be_visible(timeout=30000)
        shot(page, '01-evenements-bouton-agenda')

        # 1. La semaine, puis un rendez-vous demain.
        agenda.click()
        pw.expect(page.get_by_test_id('agenda-week')).to_be_visible(timeout=30000)
        shot(page, '02-semaine')
        page.get_by_role('button', name='Nouveau rendez-vous').click()
        page.get_by_label('Titre du rendez-vous').fill(ITEM)
        page.get_by_role('button', name='Demain', exact=True).click()
        shot(page, '03-nouveau-rendez-vous')
        page.get_by_role('button', name='Ajouter le rendez-vous').click()
        pw.expect(page.get_by_test_id('agenda-week')).to_be_visible(timeout=30000)
        rows = sql(f"select title, busy from public.agenda_items where user_id = '{owner.uid}'")
        assert rows == [{'title': ITEM, 'busy': True}], rows
        tomorrow = (datetime.now(SWISS) + timedelta(days=1)).date()
        if tomorrow.isocalendar()[1] != datetime.now(SWISS).date().isocalendar()[1]:
            page.get_by_role('button', name='Semaine suivante').click()
        pw.expect(page.get_by_test_id(f'week-day-{tomorrow.isoformat()}').get_by_text(ITEM)).to_be_visible(timeout=30000)
        shot(page, '04-semaine-avec-rendez-vous')

        # 2. Partager mes dispos : tout décoché, puis le groupe de recette.
        page.goto(f'{party}/events/agenda/share', wait_until='domcontentloaded')
        box = page.get_by_test_id(f'share-group-{gid}')
        pw.expect(box).to_have_attribute('aria-checked', 'false', timeout=30000)
        pw.expect(page.get_by_role('button', name='Partager mes dispos')).to_be_disabled()
        shot(page, '05-partager-decoche')
        box.click()
        page.get_by_test_id('share-manual').click()
        page.get_by_role('button', name='Partager avec 1 groupe').click()
        pw.expect(page.get_by_test_id('share-done')).to_contain_text(f'{GROUP} voit tes heures occupées', timeout=30000)
        assert sql(f"select count(*)::int n from private.agenda_group_shares where user_id = '{owner.uid}' and group_id = '{gid}'") == [{'n': 1}]
        shot(page, '06-partage-fait')

        # 3. Qui est libre ? Guest B a sa ligne ; le 3e membre est grisé, sans texte de refus.
        page.goto(f'{party}/events/agenda/free?group={gid}', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id('free-summary')).to_contain_text('sur 2', timeout=30000)
        others = page.get_by_test_id('free-others')
        pw.expect(others).to_contain_text('Agenda', timeout=15000)
        assert 'partag' not in others.inner_text().lower()
        shot(page, '07-qui-est-libre')
        busy_day = (datetime.now(SWISS) + timedelta(days=2)).date().isoformat()
        page.get_by_test_id(f'free-card-{busy_day}').click()
        pw.expect(page.get_by_test_id(f'free-person-{friend.uid}')).to_contain_text('Occupé')
        pw.expect(page.get_by_test_id(f'free-person-{friend.uid}')).to_contain_text('de 19 h à 21 h')
        shot(page, '08-qui-est-libre-occupe')

        # 4. Un lien de dispo, demandes allumées.
        page.goto(f'{party}/events/agenda/links', wait_until='domcontentloaded')
        page.get_by_test_id('empty-model-week').click(timeout=30000)
        page.get_by_role('button', name='J’ai compris, continuer').click()
        page.get_by_role('switch', name='Demandes de rendez-vous').click()
        pw.expect(page.get_by_test_id('link-preview')).to_contain_text('Aujourd’hui n’est jamais montré', timeout=15000)
        shot(page, '09-lien-reglage')
        page.get_by_role('button', name='Créer le lien').click()
        address = page.get_by_test_id('link-address')
        pw.expect(address).to_contain_text('/d/', timeout=30000)
        token = sql(f"select token from private.agenda_links where user_id = '{owner.uid}'")[0]['token']
        pw.expect(address).to_contain_text(f'{party}/d/{token}')
        shot(page, '10-lien-cree')

        # 5. Un inconnu demande un rendez-vous par la page publique ; la pastille arrive en temps réel.
        page.goto(f'{party}/events/agenda/links', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Mes liens de dispo')).to_be_visible(timeout=30000)
        public = stranger.new_page()
        public.goto(f'{party}/d/{token}')
        public.get_by_role('button', name='Voir en liste').click()
        public.locator('button.ls').first.click()
        public.get_by_label('Prénom').fill('Marc')
        public.get_by_label('Adresse e-mail').fill(f'marc.{int(time.time())}@example.com')
        public.wait_for_timeout(3200)
        public.get_by_role('button', name='Demander ce rendez-vous').click()
        public.wait_for_url(f'{party}/d/r/**')
        pw.expect(public.get_by_role('heading', name='Demande envoyée')).to_be_visible()
        link_id = sql(f"select id::text from private.agenda_links where user_id = '{owner.uid}'")[0]['id']
        pw.expect(page.get_by_test_id(f'link-requests-{link_id}')).to_contain_text('1 demande de rendez-vous', timeout=30000)   # sans recharger
        shot(page, '11-pastille-demande')
        page.goto(f'{party}/events/', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id('home-agenda-badge')).to_have_text('1', timeout=30000)
        shot(page, '12-pastille-evenements')
        page.goto(f'{party}/events/account', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id('settings-other-apps').get_by_role('button', name='Agenda, 1 à voir')).to_be_visible(timeout=30000)
        shot(page, '13-pastille-reglages')

        # 6. Accepter dans Party : le rendez-vous entre dans l'agenda, la pastille disparaît.
        page.goto(f'{party}/events/agenda/requests', wait_until='domcontentloaded')
        page.get_by_role('link', name='Demande de Marc', exact=False).click(timeout=30000)
        detail = page.get_by_test_id('request-detail')
        pw.expect(detail).to_contain_text('non vérifié', timeout=30000)
        shot(page, '14-demande-recue')
        detail.get_by_role('button', name='Accepter la demande de Marc').click()
        pw.expect(detail.get_by_text('✓ Accepté · dans ton agenda')).to_be_visible(timeout=30000)
        shot(page, '15-demande-acceptee')
        assert sql(f"select count(*)::int n from public.agenda_items where user_id = '{owner.uid}' and title like 'Rendez-vous · Marc%'") == [{'n': 1}]
        page.goto(f'{party}/events/', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id('home-agenda')).to_be_visible(timeout=30000)
        pw.expect(page.get_by_test_id('home-agenda-badge')).to_have_count(0, timeout=30000)
        shot(page, '16-pastille-partie')
        assert not errors, errors
    finally:
        stranger.close()
        context.close()
