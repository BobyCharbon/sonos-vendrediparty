"""Couverture d'un événement (25.11), module web dans un vrai navigateur (Supabase et serveur de couvertures simulés) :
bulle « Nouveau » (une fois), « Changer la couverture » pour l'organisation seulement, photos proposées choisies par leur
numéro, crédit sous la couverture, ma photo recadrée en 16:9 puis envoyée, image officielle introuvable dite simplement,
retour à l'affiche Party. Captures dans $COVER_SHOTS si la variable est définie."""
import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.test_event_participant_browser import EVENT, GUEST_PERMS, HEADERS, REST, event_row
from tests.test_events_browser import DIST, USER, browser, events_origin, login, mock_services  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SHOTS = Path(os.environ['COVER_SHOTS']) if os.environ.get('COVER_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


def thumb(color) -> str:
    import base64
    out = io.BytesIO()
    Image.new('RGB', (480, 270), color).save(out, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


def open_cover(browser, origin, **fields):  # noqa: F811
    """La fiche, avec une base qui garde la couverture écrite par le serveur (la fiche se relit après chaque choix)."""
    perms = fields.pop('perms', None)
    ev = event_row(**fields)
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)
    if perms is not None:
        page.route(REST + 'rpc/my_permissions', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps(perms)))
    calls = []

    def events(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        single = 'vnd.pgrst.object' in (route.request.headers.get('accept') or '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ev if single else [ev]), headers=HEADERS)
    page.route(REST + 'events?**', events)
    page.route(REST + 'rpc/my_terms', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS,
                                                         body=json.dumps({'version': '2026-11-25', 'accepted': True, 'enforced': True})))

    def server(route):
        name = route.request.url.rsplit('/', 1)[1]
        body = json.loads(route.request.post_data or '{}')
        calls.append((name, body))
        out = {}
        if name == 'suggest':
            out = {'photos': [{'pick': 'pick-aaaa-1', 'thumb': thumb((200, 60, 120)), 'credit': 'Photo : Ana Lumière / Pexels', 'alt': 'Scène de concert'},
                              {'pick': 'pick-bbbb-2', 'thumb': thumb((40, 80, 200)), 'credit': 'Photo : Jo / Pexels', 'alt': 'Foule'}],
                   'ai': True, 'ai_note': '', 'source': 'pexels'}
        elif name == 'official':
            out = {'found': False, 'message': 'Aucune page officielle trouvée pour cet événement.'}
        else:
            credit = {'choose': ('Photo : Ana Lumière / Pexels', 'https://www.pexels.com/photo/1/')}.get(name, (None, None))
            url = None if name == 'remove' else f'https://party.test/covers/{"a" * 24}{"p" if name == "poster" else ""}.jpg'
            ev.update(cover_url=url, cover_credit=credit[0], cover_credit_url=credit[1])
            out = {'cover_url': url, 'cover_credit': credit[0], 'cover_credit_url': credit[1], 'status': 'published'}
        route.fulfill(status=200, content_type='application/json', body=json.dumps(out))
    page.route('**/api/account/event-cover/*', server)
    page.goto(origin + '/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(ev['title'], exact=True).first).to_be_visible(timeout=15000)
    return context, page, calls


def test_the_organizer_picks_a_proposed_photo_and_its_credit_shows(browser, events_origin):  # noqa: F811
    context, page, calls = open_cover(browser, events_origin, created_by=USER, title='Concert au Romandie')
    try:
        tip = page.get_by_test_id('cover-tip')
        pw.expect(tip).to_be_visible(timeout=15000)
        shot(page, '01-bulle-nouveau')
        page.get_by_role('button', name='🖼️  Ajouter une couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        pw.expect(sheet.get_by_text('Couverture de l’événement', exact=True)).to_be_visible()
        pw.expect(tip).to_have_count(0)  # la bulle ne revient plus
        sheet.get_by_role('tab', name='🔎 Proposées').click()
        sheet.get_by_role('button', name='🔎 Proposer des photos').click()
        pw.expect(sheet.get_by_role('radio', name='Photo 1 : Scène de concert')).to_be_visible(timeout=10000)
        pw.expect(sheet.get_by_text('Choisies par l’IA de Party, sans boisson.', exact=False)).to_be_visible()
        sheet.get_by_role('radio', name='Photo 1 : Scène de concert').click()
        shot(page, '02-photos-proposees')
        sheet.get_by_role('button', name='Utiliser cette photo').click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=10000)
        pw.expect(page.get_by_role('link', name='Photo : Ana Lumière / Pexels')).to_have_attribute('href', 'https://www.pexels.com/photo/1/')
        pw.expect(page.get_by_role('button', name='🖼️  Changer la couverture')).to_be_visible()
        shot(page, '03-credit-sous-la-couverture')
        assert ('choose', {'token': calls[-1][1]['token'], 'event_id': calls[-1][1]['event_id'], 'pick': 'pick-aaaa-1'}) == calls[-1]
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='🖼️  Changer la couverture')).to_be_visible(timeout=15000)
        assert page.get_by_test_id('cover-tip').count() == 0  # une seule fois par appareil
    finally:
        context.close()


def test_my_photo_is_cropped_wide_then_sent_and_the_official_search_says_when_nothing_is_found(browser, events_origin, tmp_path):  # noqa: F811
    context, page, calls = open_cover(browser, events_origin, created_by=USER)
    try:
        page.get_by_role('button', name='🖼️  Ajouter une couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        photo = tmp_path / 'photo.png'
        Image.new('RGB', (1200, 1600), (30, 160, 90)).save(photo)
        sheet.get_by_test_id('cover-photo-input').set_input_files(str(photo))
        canvas = page.get_by_label('Aperçu du recadrage')
        pw.expect(canvas).to_be_visible(timeout=10000)
        box = canvas.bounding_box()
        assert abs(box['width'] / box['height'] - 16 / 9) < 0.02  # cadre large, pas un cercle
        shot(page, '04-recadrage-16-9')
        page.get_by_role('button', name='Valider la photo').click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=10000)
        name, body = next(c for c in calls if c[0] == 'photo')
        assert body['photo'].startswith('data:image/jpeg;base64,')
        sent = Image.open(io.BytesIO(__import__('base64').b64decode(body['photo'].split(',', 1)[1])))
        assert sent.size == (1600, 900)

        page.get_by_role('button', name='🖼️  Changer la couverture').click()
        sheet = page.get_by_test_id('cover-sheet')
        sheet.get_by_role('tab', name='🌐 Officielle').click()
        sheet.get_by_role('button', name='🌐 Chercher l’image officielle').click()
        pw.expect(sheet.get_by_text('Aucune page officielle trouvée pour cet événement.', exact=True)).to_be_visible(timeout=10000)
        shot(page, '05-officielle-introuvable')
        sheet.get_by_role('tab', name='🎨 Affiche').click()
        sheet.get_by_role('button', name='🎨 Utiliser l’affiche Party').click()
        pw.expect(page.get_by_test_id('cover-sheet')).to_have_count(0, timeout=10000)
        assert calls[-1][0] == 'poster'
    finally:
        context.close()


def test_a_guest_never_sees_the_cover_button(browser, events_origin):  # noqa: F811
    context, page, _ = open_cover(browser, events_origin, perms=GUEST_PERMS,
                                  cover_url='https://party.test/covers/aaaaaaaaaaaaaaaaaaaaaaaa.jpg', cover_credit='Visuel : leromandie.ch',
                                  cover_credit_url='https://www.leromandie.ch/agenda')
    try:
        pw.expect(page.get_by_role('link', name='Visuel : leromandie.ch')).to_be_visible(timeout=15000)
        assert page.get_by_role('button', name='🖼️  Changer la couverture').count() == 0
        assert page.get_by_test_id('cover-tip').count() == 0
    finally:
        context.close()
