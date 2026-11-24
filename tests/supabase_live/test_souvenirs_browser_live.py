"""Recette RÉELLE des écrans web des Souvenirs (24.11.2026) : vrai navigateur (Chromium, téléphone 390 px), vrai serveur
Party local (photos sur SON disque : original pleine résolution sans GPS, version écran 2048 px, liens signés par le
serveur ; migration 20261124150000), module Événements construit contre la base de TEST, CGU exigées comme en prod.

Guest A organise un événement « sur invitation » (personne d'autre n'est prévenu), Souvenirs allumés ; Guest B, invité, a
répondu Présent. Le temps avance en déplaçant l'événement (SQL sur la base de TEST) :
1. pendant la soirée : Guest B voit l'avis, prend une photo (<input capture>), « Annuler » 5 s sans aperçu ; Guest A a pris
   la sienne (par le serveur) ;
2. Guest A relit les photos (celle de B, jamais la sienne), une photo masquée en tête « 🚩 Signalée », « Remettre » ;
3. la soirée finie : Guest A « Dévoiler maintenant » sur la fiche ;
4. Guest B ouvre la story (?souvenirs=1), garde la photo de A (⭐), voit la sienne « déjà dans tes souvenirs » ;
5. après la story : « Mes souvenirs » de Guest B (prise par moi + gardée, filtre) ; « Enregistrer » télécharge l'ORIGINAL
   (pleine résolution, sans GPS, octets de l'image intacts) ; puis la corbeille vidée par le serveur efface les fichiers.
Aucun signalement réel (il préviendrait les vrais modérateurs de la base de test) : la photo « signalée » est masquée en SQL.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $SOUVENIRS_WEB_SHOTS si la variable est définie."""
import io
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
from PIL import Image, ImageDraw

from app.souvenirs import Files

from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B, complete_profile
from tests.supabase_live.test_inscription_complete_browser_live import phone_page, sign_in
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
SHOTS = Path(os.environ['SOUVENIRS_WEB_SHOTS']) if os.environ.get('SOUVENIRS_WEB_SHOTS') else None
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
TITLE = 'Recette souvenirs web'


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


STATE: dict = {}


def phone_jpeg_with_gps() -> bytes:
    exif = Image.Exif()
    exif[0x8825] = {1: 'N', 2: (46.0, 13.0, 0.0), 3: 'E', 4: (7.0, 21.0, 0.0)}
    out = io.BytesIO()
    Image.new('RGB', (64, 64), '#123456').save(out, 'JPEG', exif=exif)
    return out.getvalue()


def jpeg(color: str) -> bytes:
    """Photo d'iPhone 12 Mpx (4032 × 3024), JPEG 92, avec position GPS, numéro de série et date de prise."""
    img = Image.new('RGB', (4032, 3024), color)
    draw = ImageDraw.Draw(img)
    draw.ellipse((1416, 912, 2616, 2112), fill='#FFE08A')
    draw.arc((1716, 1272, 2316, 1872), 20, 160, fill='#3a2300', width=50)
    exif = Image.Exif()
    exif[0x0112] = 1
    exif[0x8769] = {0x9003: '2026:11:24 22:15:00', 0xA431: 'SN-RECETTE-0001'}
    exif[0x8825] = {1: 'N', 2: (46.0, 13.0, 0.0), 3: 'E', 4: (7.0, 21.0, 0.0)}
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=92, exif=exif)
    return out.getvalue()


def sos(data: bytes) -> bytes:
    i = 2
    while data[i + 1] != 0xDA:
        i += 2 + int.from_bytes(data[i + 2:i + 4], 'big')
    return data[i:]


@pytest.fixture(scope='module')
def party(tmp_path_factory):
    """Serveur Party local, module branché sur la base de test, drapeaux de la prod."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    bundle = b''.join(p.read_bytes() for p in (DIST / '_expo').rglob('*.js'))
    assert urlparse(TEST_URL).netloc.encode() in bundle and b'gsuetixzobooggeaubvb' not in bundle, \
        'PARTY_TEST_EVENTS_DIST doit être construit contre la base de test visée'
    STATE['data'] = tmp_path_factory.mktemp('party-souvenirs-web')
    env = {'PATH': os.environ['PATH'], 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
           'DATA_DIR': str(STATE['data']), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '8462', 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'INVITES_V2_ENABLED': '1',
           'COMPAGNON_ENABLED': '0', 'DISCUSSIONS_ENABLED': '1', 'BAR_ENABLED': '1',
           'PARTY_PUBLIC_URL': f'http://127.0.0.1:{port}',
           'SUPABASE_URL': TEST_URL, 'SUPABASE_ANON_KEY': KEY_FILE.read_text().strip(), 'PYTHONDONTWRITEBYTECODE': '1',
           # Clé du serveur (coffre de la base de TEST) : sans elle, aucun dépôt (comme SOUVENIRS_SECRET en prod).
           'SOUVENIRS_SECRET': sql("select decrypted_secret k from vault.decrypted_secrets where name = 'souvenirs_server_key'")[0]['k']}
    STATE['key'] = env['SOUVENIRS_SECRET']
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


def cleanup():
    ids = [r['id'] for r in sql(f"select id::text id from public.events where title = '{TITLE}'")]
    sql(f"delete from public.notifications where event_id in (select id from public.events where title = '{TITLE}')")
    sql(f"delete from public.events where title = '{TITLE}'")  # photos, gardées, vues : en cascade ; fichiers à la corbeille
    for eid in ids:  # sans serveur pour la vider (fin de la recette) : la corbeille de ces photos ne reste pas
        sql(f"delete from private.souvenir_trash where path like '{eid}/%'")


@pytest.fixture(scope='module')
def world():
    owner, guest = Session(GUEST_A), Session(GUEST_B)
    complete_profile(owner, 'Souv Maé')
    complete_profile(guest, 'Souv Léo')
    cleanup()
    now = datetime.now(timezone.utc)
    r = httpx.post(f'{TEST_URL}/rest/v1/events', timeout=30, headers={**owner.headers, 'Prefer': 'return=representation'},
                   json={'title': TITLE, 'status': 'published', 'visibility': 'invited', 'public_link': False, 'notify_on_publish': False,
                         'starts_at': (now - timedelta(hours=1)).isoformat(), 'ends_at': (now + timedelta(hours=1)).isoformat(),
                         'souvenirs_enabled': True, 'souvenirs_keep': True})
    assert r.status_code == 201, r.text
    eid = r.json()[0]['id']
    # Un compte « Guest » propose (en attente de validation) : publié ici, sans notification (notify_on_publish éteint).
    sql(f"update public.events set status = 'published' where id = '{eid}'")
    sql(f"insert into public.event_invites (event_id, user_id) values ('{eid}', '{guest.uid}') on conflict do nothing")
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{eid}', '{guest.uid}', 'yes') "
        "on conflict (event_id, user_id) do update set status = 'yes'")
    yield owner, guest, eid
    cleanup()


def move(eid: str, start_h: float, end_h: float, reveal_h: float | None = None):
    """Déplace l'événement (heures relatives à maintenant) : la phase des Souvenirs suit."""
    reveal = 'null' if reveal_h is None else f"now() + interval '{reveal_h} hours'"
    sql(f"update public.events set starts_at = now() + interval '{start_h} hours', ends_at = now() + interval '{end_h} hours', "
        f"souvenirs_reveal_at = {reveal} where id = '{eid}'")


def test_souvenirs_for_real_from_the_camera_to_my_souvenirs(browser, party, world):
    owner, guest, eid = world
    # La photo de l'organisatrice, envoyée par le serveur Party (comme l'app iPhone).
    token = owner.headers['Authorization'].split(' ', 1)[1]
    raw_owner = jpeg('#FF4F9A')
    up = httpx.post(f'{party}/api/account/souvenirs/photo?event_id={eid}', content=raw_owner, timeout=60,
                    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'image/jpeg'})
    assert up.status_code == 200, up.text
    owner_photo = up.json()['id']
    owner_path = up.json()['path']
    # Sur le disque du serveur : l'original (octets de l'image intacts, GPS et numéro de série retirés, date gardée) et la
    # version écran de 2048 px. Rien dans Supabase Storage.
    folder = STATE['data'] / 'souvenirs' / owner_path.rsplit('/', 1)[0]
    stem = owner_path.rsplit('/', 1)[1][:-4]
    original = (folder / f'{stem}.orig.jpg').read_bytes()
    assert sos(original) == sos(raw_owner) and b'SN-RECETTE' not in original
    with Image.open(io.BytesIO(original)) as img:
        assert img.size == (4032, 3024) and 0x8825 not in img.getexif()
        assert img.getexif().get_ifd(0x8769)[0x9003] == '2026:11:24 22:15:00'
    with Image.open(folder / f'{stem}.screen.jpg') as img:
        assert img.size == (2048, 1536)
    assert sql(f"select count(*)::int n from storage.objects where bucket_id = 'souvenirs' and name like '{eid}/%'") == [{'n': 0}]
    # Faille fermée : un client qui dépose lui-même dans le compartiment (avec EXIF / GPS) est toujours refusé.
    direct = httpx.post(f"{TEST_URL}/storage/v1/object/souvenirs/{eid}/{owner.uid}/{owner_photo[:-4]}0000.jpg",
                        content=phone_jpeg_with_gps(), timeout=30, headers={**owner.headers, 'Content-Type': 'image/jpeg'})
    assert direct.status_code in (400, 403) and 'row-level security' in direct.text, direct.text

    ctx_b, page, errors = phone_page(browser, alone=True)
    ctx_a, org, org_errors = phone_page(browser, alone=True)
    for each in (page, org):  # le didacticiel (première ouverture) a son propre test : tests/test_souvenirs_browser.py
        each.add_init_script("try { localStorage.setItem('party-souvenirs-tutorial-off', '1'); } catch (e) {}")
    try:
        # 1. Guest B pendant la soirée : l'avis, l'appareil jetable, une photo, « Annuler » sans aperçu.
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 02')
        page.wait_for_timeout(1500)
        page.goto(f'{party}/events/event/{eid}', wait_until='domcontentloaded')
        card = page.get_by_test_id('souvenirs')
        pw.expect(card).to_be_visible(timeout=30000)
        pw.expect(page.get_by_text('📸 Souvenirs actif', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('L’organisation peut les voir avant.', exact=False)).to_be_visible()
        pw.expect(card).to_contain_text('Il te reste 3 poses')
        pw.expect(card).to_contain_text('Au labo : 1 photo de la bande')
        card.scroll_into_view_if_needed()
        shot(page, '01-invite-fiche-pendant')
        with page.expect_file_chooser() as chooser:
            page.get_by_role('button', name='📸 Prendre une photo · 3 restantes').click()
        raw_guest = jpeg('#2bd4c4')  # envoyée telle quelle (jamais réduite dans le navigateur)
        chooser.value.set_files(files=[{'name': 'IMG_0001.jpg', 'mimeType': 'image/jpeg', 'buffer': raw_guest}])
        undo = page.get_by_test_id('souvenir-undo')
        pw.expect(undo).to_contain_text('🧪 Partie au labo', timeout=30000)
        assert page.locator('img[src^="blob:"]').count() == 0
        shot(page, '02-invite-annuler-5s')
        pw.expect(undo).to_have_count(0, timeout=10000)  # 5 s passées : la photo reste au labo
        pw.expect(card).to_contain_text('Il te reste 2 poses', timeout=15000)
        rows = sql(f"select count(*)::int n, bool_and(path like '{eid}/{guest.uid}/%') mine from public.souvenir_photos "
                   f"where event_id = '{eid}' and author_id = '{guest.uid}'")
        assert rows == [{'n': 1, 'mine': True}], rows
        guest_photo = sql(f"select id::text from public.souvenir_photos where event_id = '{eid}' and author_id = '{guest.uid}'")[0]['id']

        # 2. Guest A relit : la photo de B (jamais la sienne) ; une photo masquée passe en tête, « Remettre ».
        sql(f"update public.souvenir_photos set hidden_at = now() where id = '{guest_photo}'")
        org.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(org, '079 000 00 01')
        org.wait_for_timeout(1500)
        org.goto(f'{party}/events/event/{eid}?souvenirs=review', wait_until='domcontentloaded')
        review = org.get_by_label('Relire les photos', exact=True)
        pw.expect(review.get_by_test_id('review-reported')).to_have_count(1, timeout=30000)
        pw.expect(review.get_by_test_id('review-photo')).to_have_count(0)  # la sienne n'y est pas
        # Le signalement va à l'organisation, qui décide : elle VOIT la photo masquée (lien signé, fichier lisible).
        org.wait_for_function("[...document.querySelectorAll('[data-testid=\"review-reported\"] img')].some((i) => i.complete "
                              "&& i.naturalWidth > 0 && i.src.includes('/api/souvenirs/file/'))", timeout=30000)
        shot(org, '03-organisation-relecture-signalee')
        review.get_by_role('button', name='Remettre la photo de', exact=False).click()
        pw.expect(review.get_by_test_id('review-photo')).to_have_count(1, timeout=15000)
        assert sql(f"select hidden_at is null h from public.souvenir_photos where id = '{guest_photo}'") == [{'h': True}]
        shot(org, '04-organisation-relecture-remise')
        review.get_by_role('button', name='Fermer la relecture').click()

        # 3. La soirée est finie : « Dévoiler maintenant » sur la fiche.
        move(eid, -5, -3)
        org.reload(wait_until='domcontentloaded')
        org_card = org.get_by_test_id('souvenirs')
        pw.expect(org_card.get_by_role('button', name='Dévoiler maintenant')).to_be_visible(timeout=30000)
        org_card.scroll_into_view_if_needed()
        shot(org, '05-organisation-devoiler')
        org_card.get_by_role('button', name='Dévoiler maintenant').click()
        org_card.get_by_role('button', name='Oui, dévoiler').click()
        pw.expect(org_card).to_contain_text('Les souvenirs sont arrivés', timeout=30000)
        assert sql(f"select souvenirs_reveal_at is not null r from public.events where id = '{eid}'") == [{'r': True}]

        # 4. Guest B : la story par le lien de la notification, ⭐ sur la photo de A, la sienne déjà gardée.
        page.goto(f'{party}/events/event/{eid}?souvenirs=1', wait_until='domcontentloaded')
        viewer = page.get_by_label('Story des souvenirs')
        pw.expect(viewer.get_by_test_id('story-photo')).to_be_visible(timeout=30000)
        pw.expect(viewer.get_by_text('1 / 2', exact=True)).to_be_visible()
        page.wait_for_function("[...document.querySelectorAll('img')].some((i) => i.complete && i.naturalWidth > 0 && i.src.includes('/api/souvenirs/file/'))", timeout=30000)
        viewer.get_by_role('button', name='⭐ Garder dans mes souvenirs').click()
        pw.expect(viewer.get_by_role('button', name='⭐ Gardée')).to_be_visible(timeout=15000)
        shot(page, '06-invite-story-gardee')
        assert sql(f"select count(*)::int n from public.souvenir_keeps where photo_id = '{owner_photo}' and user_id = '{guest.uid}'") == [{'n': 1}]
        assert sql(f"select count(*)::int n from public.souvenir_seen where event_id = '{eid}' and user_id = '{guest.uid}'") == [{'n': 1}]
        viewer.get_by_role('button', name='Photo suivante').click()
        pw.expect(viewer.get_by_text('📸 Ta photo · déjà dans tes souvenirs', exact=True)).to_be_visible()
        shot(page, '07-invite-story-sa-photo')
        viewer.get_by_role('button', name='Fermer la story').click()
        mine = page.get_by_test_id('souvenir-item')
        pw.expect(mine).to_have_count(2, timeout=30000)

        # 5. Après la story : « Mes souvenirs », prise par moi + gardée, dans l'ordre de la soirée.
        move(eid, -40, -38, -30)
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text('📸 Mes souvenirs', exact=True)).to_be_visible(timeout=30000)
        pw.expect(mine).to_have_count(2, timeout=30000)
        pw.expect(page.get_by_text('Les souvenirs sont arrivés', exact=True)).to_have_count(0)
        pw.expect(page.get_by_role('tab', name='Gardées 1')).to_be_visible()
        link = page.get_by_role('link', name='⬇︎ Enregistrer').first
        href = link.get_attribute('href') or ''
        assert href.startswith('/api/souvenirs/file/') and 'v=original' in href and 'download=' in href, href
        # « Enregistrer » donne l'ORIGINAL : pleine résolution, sans GPS (téléchargé pour de vrai, comme le navigateur).
        got = httpx.get(f'{party}{href}', timeout=30)
        assert got.status_code == 200 and got.headers['cache-control'].startswith('private') and got.headers['etag']
        assert 'attachment' in got.headers['content-disposition']
        with Image.open(io.BytesIO(got.content)) as img:
            assert img.size == (4032, 3024) and 0x8825 not in img.getexif()
        assert sos(got.content) in (sos(raw_owner), sos(raw_guest))
        page.get_by_text('📸 Mes souvenirs', exact=True).scroll_into_view_if_needed()
        shot(page, '08-invite-mes-souvenirs')
        page.get_by_role('tab', name='Prises par moi 1').click()
        pw.expect(mine).to_have_count(1)
        shot(page, '09-invite-prises-par-moi')
        # Lien falsifié : refusé.
        assert httpx.get(f'{party}{href.replace("/file/", "/file/x")}', timeout=30).status_code == 403
        # 7 jours plus tard (horloge du fichier reculée) : l'original devient une version de 2560 px, même lien.
        files = Files(STATE['data'] / 'souvenirs')
        for orig in (STATE['data'] / 'souvenirs').rglob('*.orig.jpg'):
            os.utime(orig, (time.time() - 8 * 86400,) * 2)
        assert files.shrink_old(days=7) == 2
        with Image.open(io.BytesIO(httpx.get(f'{party}{href}', timeout=30).content)) as img:
            assert img.size == (2560, 1920)
        # Guest B supprime sa photo : la base la met à la corbeille ; le serveur (sa clé) la vide et efface le disque.
        guest_token = guest.headers['Authorization'].split(' ', 1)[1]
        gone = httpx.post(f'{party}/api/account/souvenirs/rpc', timeout=30,
                          json={'token': guest_token, 'fn': 'souvenir_delete', 'args': {'id': guest_photo}})
        assert gone.status_code == 200, gone.text
        anon = {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json'}
        trash = httpx.post(f'{TEST_URL}/rest/v1/rpc/souvenir_trash_take', headers=anon, timeout=30,
                           json={'p_key': STATE['key'], 'n': 500}).json()
        guest_path = f'{eid}/{guest.uid}/{guest_photo}.jpg'
        assert guest_path in trash, trash
        assert files.remove(guest_path) == 2 and files.find(guest_path, 'original') is None
        done = httpx.post(f'{TEST_URL}/rest/v1/rpc/souvenir_trash_done', headers=anon, timeout=30,
                          json={'p_key': STATE['key'], 'paths': [guest_path]})
        assert done.json() == 1
        assert httpx.post(f'{TEST_URL}/rest/v1/rpc/souvenir_trash_take', headers=anon, timeout=30,
                          json={'p_key': 'fausse-cle-0123456789-0123456789-0123', 'n': 5}).status_code >= 400
        assert not errors, errors
        assert not org_errors, org_errors
    finally:
        ctx_b.close()
        ctx_a.close()
