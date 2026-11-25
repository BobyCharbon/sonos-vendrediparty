"""Recette RÉELLE de la couverture d'un événement (demande de l'admin du 25.11) : vrai navigateur (390 px), vrai serveur
Party, base de TEST, CGU exigées, drapeaux de la prod, VRAIE recherche Openverse (sans clé Pexels, comme un serveur sans
PEXELS_API_KEY) ; sans clé Anthropic sur la machine de recette : l'IA est éteinte (requêtes tirées des mots connus).
Parcours : bulle « Nouveau » → ma photo (recadrée 16:9, GPS retiré) → photo proposée (crédit sous la couverture, vue en
direct chez un invité) → image officielle (message clair sans IA) → affiche Party → retirer.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $COVER_SHOTS si la variable est définie."""
import io
import os
import re
from pathlib import Path

import httpx
import pytest
from PIL import Image

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['COVER_SHOTS']) if os.environ.get('COVER_SHOTS') else None
# Adresse publique par défaut du serveur (app/features.py) : les couvertures y sont nommées ; le navigateur de recette les
# lit sur le serveur local (aucune requête vers la prod).
PUBLIC = 'https://party.bobycharbon.ch'


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=False)


@pytest.fixture(scope='module')
def event():
    admin, guest = Session(ADMIN), Session(GUEST_A)
    for s in (admin, guest):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    e = create_event(admin, 'Concert live au bord du lac', visibility='all', public_link=True, location_name='Vevey')
    yield admin, guest, e
    sql(f"delete from public.events where id = '{e}'")


def row(e):
    return sql(f"select cover_url, cover_credit, cover_credit_url, status from public.events where id = '{e}'")[0]


def open_signed_in(browser, party, e, number):  # noqa: F811
    context, page, errors = phone_page(browser, alone=True)
    # Couvertures : servies par le serveur local de recette (jamais la prod).
    page.route(f'{PUBLIC}/covers/**', lambda r: r.fulfill(response=page.request.fetch(r.request.url.replace(PUBLIC, party))))
    page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
    sign_in(page, number)
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
    page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text('Concert live au bord du lac', exact=True).first).to_be_visible(timeout=30000)
    return context, page, errors


def photo_with_gps(path: Path):
    img = Image.new('RGB', (1600, 1200))
    for y in range(1200):  # dégradé : une vraie photo, pas un aplat
        img.paste((40 + y // 8, 20, 120 + y // 12), (0, y, 1600, y + 1))
    exif = Image.Exif()
    exif[0x8825] = {1: 'N', 2: (46.0, 27.0, 50.0), 3: 'E', 4: (6.0, 50.0, 30.0)}
    img.save(path, 'JPEG', exif=exif.tobytes())


def test_the_organizer_changes_the_cover_from_every_source_and_a_guest_sees_it_live(browser, party, event, tmp_path):  # noqa: F811
    admin, guest, e = event
    org, page, errors = open_signed_in(browser, party, e, '079 000 00 04')
    guest_context, guest_page, guest_errors = open_signed_in(browser, party, e, '079 000 00 01')
    try:
        assert guest_page.get_by_role('button', name='🖼️  Ajouter une couverture').count() == 0  # un invité : jamais

        pw.expect(page.get_by_test_id('cover-tip')).to_be_visible(timeout=15000)
        shot(page, '01-bulle-nouveau')
        page.get_by_role('button', name='🖼️  Ajouter une couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        pw.expect(sheet).to_be_visible()
        shot(page, '02-feuille-ma-photo')

        # 📷 Ma photo : recadrée en 16:9, réencodée par le serveur (GPS retiré).
        source = tmp_path / 'vacances.jpg'
        photo_with_gps(source)
        sheet.get_by_test_id('cover-photo-input').set_input_files(str(source))
        pw.expect(page.get_by_label('Aperçu du recadrage')).to_be_visible(timeout=10000)
        shot(page, '03-recadrage-16-9')
        page.get_by_role('button', name='Valider la photo').click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=30000)
        r = row(e)
        assert r['cover_url'].startswith(f'{PUBLIC}/covers/') and r['cover_credit'] is None, r
        stored = httpx.get(r['cover_url'].replace(PUBLIC, party), timeout=10)
        with Image.open(io.BytesIO(stored.content)) as img:
            assert img.size == (1600, 900) and 0x8825 not in img.getexif()
        pw.expect(page.get_by_label('Affiche de l’événement')).to_be_visible()
        shot(page, '04-fiche-avec-ma-photo')

        # 🔎 Photos proposées : vraie recherche Openverse (CC0, domaine public, CC BY), choisie par son numéro.
        page.get_by_role('button', name='🖼️  Changer la couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        sheet.get_by_role('tab', name='🔎 Proposées').click()
        sheet.get_by_role('button', name='🔎 Proposer des photos').click()
        first = sheet.get_by_role('radio').first
        pw.expect(first).to_be_visible(timeout=60000)
        shot(page, '05-photos-proposees-openverse')
        first.click()
        sheet.get_by_role('button', name='Utiliser cette photo').click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=60000)
        r = row(e)
        assert r['cover_credit'].startswith('Photo : ') and r['cover_credit'].endswith('· Openverse'), r
        assert r['cover_credit_url'].startswith('https://'), r
        pw.expect(page.get_by_role('link', name=r['cover_credit'])).to_be_visible(timeout=15000)
        shot(page, '06-fiche-photo-proposee-et-credit')
        # Temps réel : l'invité, page ouverte, voit la nouvelle couverture et son crédit sans recharger.
        pw.expect(guest_page.get_by_role('link', name=r['cover_credit'])).to_be_visible(timeout=20000)
        shot(guest_page, '07-invite-voit-en-direct')

        # 🌐 Image officielle : sans IA sur ce serveur, un message clair (jamais une image prise au hasard).
        page.get_by_role('button', name='🖼️  Changer la couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        sheet.get_by_role('tab', name='🌐 Officielle').click()
        sheet.get_by_role('button', name='🌐 Chercher l’image officielle').click()
        # Selon le compte : « Accord requis… » (droit IA sans accord) ou « L'assistant IA n'est pas… » (sans droit / sans clé).
        pw.expect(sheet.get_by_role('alert').filter(has_text=re.compile("Accord requis|L'assistant IA"))).to_be_visible(timeout=20000)
        shot(page, '08-officielle-sans-ia')

        # 🎨 Affiche Party, puis retirer.
        sheet.get_by_role('tab', name='🎨 Affiche').click()
        sheet.get_by_role('button', name='🎨 Utiliser l’affiche Party').click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=30000)
        r = row(e)
        assert r['cover_url'].endswith('p.jpg') and r['cover_credit'] is None, r
        shot(page, '09-affiche-party')
        page.get_by_role('button', name='🖼️  Changer la couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        sheet.get_by_role('button', name='Retirer la couverture').click()
        sheet.get_by_role('button', name='Retirer', exact=True).click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=30000)
        assert row(e)['cover_url'] is None
        pw.expect(page.get_by_role('button', name='🖼️  Ajouter une couverture')).to_be_visible()
        assert row(e)['status'] == 'published'
        assert not errors and not guest_errors, (errors, guest_errors)
    finally:
        org.close()
        guest_context.close()
