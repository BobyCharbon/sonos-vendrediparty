"""Recette RÉELLE de « Réunir les invités dans un groupe » (17.11) : vrai navigateur, vrai serveur Party, base de TEST,
connexion normale (code fixe des comptes de test), drapeaux de la prod (Invitations v2, Discussions et bar allumés,
Zicou éteint), CGU exigées. L'Admin de test crée un événement « sur invitation » avec un NOUVEAU groupe (créé d'un coup) ;
Guest B ouvre le lien, voit la case DÉCOCHÉE, la coche, répond « Je ne peux pas », se connecte : il est dans le groupe ;
la discussion du groupe montre le bandeau « Tu es dans le groupe … » une fois ; il quitte : la base note son départ.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $GUEST_GROUP_SHOTS si la variable est définie."""
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

from tests.supabase_live.party_shell import in_party, where_visible
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_B, complete_profile, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['GUEST_GROUP_SHOTS']) if os.environ.get('GUEST_GROUP_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    """Serveur Party local branché sur la base de TEST, drapeaux de la prod du 16.11 (Discussions et bar allumés)."""
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée (jamais la prod)'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(tmp_path_factory.mktemp('party-groupe')), 'EVENTS_WEB_DIR': str(DIST), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'INVITES_V2_ENABLED': '1', 'DISCUSSIONS_ENABLED': '1',
           'BAR_ENABLED': '1', 'COMPAGNON_ENABLED': '0',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 120
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
def event():
    admin, guest = Session(ADMIN), Session(GUEST_B)
    for s in (admin, guest):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    complete_profile(guest, 'Guest B')  # une autre recette peut l'avoir remis à vide
    e = create_event(admin, 'Raclette recette groupe', visibility='invited', public_link=False)
    r = admin.rpc('set_event_guest_group', e=e, grp=None, new_name='Raclette recette groupe')
    assert r.status_code == 200, r.text
    group = r.json()['group']['id']
    token = admin.rpc('create_event_invite', e=e, places=0, label='Tout le monde').json()['token']
    yield guest, e, group, token
    sql(f"delete from public.events where id = '{e}'")
    sql(f"delete from public.member_groups where id = '{group}'")


def test_a_guest_ticks_the_box_answers_no_joins_sees_the_banner_and_leaves(browser, party, event):  # noqa: F811
    guest, e, group, token = event
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', locale='fr-CH', device_scale_factor=2)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda x: errors.append(str(x)))
    try:
        page.goto(f'{party}/events/invite/{token}', wait_until='domcontentloaded')
        # L'émoji du groupe (graphisme des groupes, 17.11) précède le nom quand la base le connaît.
        box = page.get_by_role('checkbox', name=re.compile(r'^Rejoindre aussi le groupe « (\S+ )?Raclette recette groupe » de '))
        pw.expect(box).to_be_visible(timeout=30000)
        pw.expect(box).to_have_attribute('aria-checked', 'false')  # décochée par défaut
        shot(page, 'live-01-case-decochee')
        box.click()
        pw.expect(box).to_have_attribute('aria-checked', 'true')
        page.get_by_role('button', name='Je ne peux pas').click()
        sign_in(page, '079 000 00 02')
        where_visible(page, re.compile(r'Tu es dans le groupe « (\S+ )?Raclette recette groupe »'))  # seul ou dans Party
        shot(page, 'live-02-pas-present-dans-le-groupe')
        assert sql(f"select status::text s from public.rsvps where event_id = '{e}' and user_id = '{guest.uid}'")[0]['s'] == 'no'
        assert sql(f"select count(*) n from public.member_group_members where group_id = '{group}' and user_id = '{guest.uid}'")[0]['n'] == 1
        assert sql(f"select count(*) n from public.notifications where user_id = '{guest.uid}' and kind = 'group_added' "
                   f"and data->>'group_id' = '{group}'")[0]['n'] == 1

        # La discussion du groupe : le bandeau, une seule fois, avec « Quitter ».
        # Page du module ouverte seule : renvoyée dans Party (cadre, barre d'onglets), party_shell.py.
        page.goto(f'{party}/events/chats/{group}', wait_until='domcontentloaded')
        note = in_party(page, f'/events/chats/{group}').get_by_test_id('group-join-note')
        pw.expect(note).to_be_visible(timeout=30000)
        pw.expect(note.get_by_text('Ajouté avec ta réponse à « Raclette recette groupe »', exact=False)).to_be_visible()
        shot(page, 'live-03-bandeau-groupe')
        note.get_by_role('button', name='Quitter le groupe').click()
        note.get_by_role('button', name='Confirmer : quitter le groupe').click()
        pw.expect(note).to_have_count(0, timeout=15000)
        shot(page, 'live-04-quitte')
        assert sql(f"select count(*) n from public.member_group_members where group_id = '{group}' and user_id = '{guest.uid}'")[0]['n'] == 0
        assert sql(f"select count(*) n from private.group_departures where group_id = '{group}' and user_id = '{guest.uid}'")[0]['n'] == 1
        assert not errors, errors
    finally:
        context.close()
