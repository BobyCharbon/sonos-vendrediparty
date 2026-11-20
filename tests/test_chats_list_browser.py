"""Discussions v2 — la liste (maquette 1 « Néon club », contrat discussions §3, §8), dans un vrai navigateur, base simulée :
une seule liste (groupes, messages directs, soirées) via chat_list, épinglées en tuiles, filtres, « écrit… » (signal en direct),
@, sourdine, Vu, Membres Vendredi Party = logo officiel ; recherche Personnes / Discussions / Messages ; appui long, « … » au
survol et glissés (épingler, sourdine, archiver) ; Demandes (Accepter / Supprimer / Bloquer / Signaler) et Archivées ; état vide
avec des personnes croisées ; pastille de l'onglet (chat_badge). Captures : CHATS_SHOTS=<dossier> (sinon un dossier temporaire)."""
import json
import re
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest

from tests.test_events_browser import USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

SUPABASE = 'https://gsuetixzobooggeaubvb.supabase.co/**'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile'}


def uid(n):
    return f'0c000000-0000-4000-8000-{n:012d}'


LEA, MATHIEU, CHLOE, ANAIS, MAMAN, NOE, ZOE, MALIK = (uid(i) for i in range(1, 9))
DM_LEA, DM_MATHIEU, DM_CHLOE, DM_ANAIS, DM_MAMAN, REQ_NOE, REQ_ZOE = (uid(100 + i) for i in range(7))
G_COLOC, G_JURA, G_BASKET, G_VP, G_OLD = (uid(200 + i) for i in range(5))
E_RACLETTE, E_PAINTBALL = uid(300), uid(301)


def portrait(bg1, bg2, skin, hair, shirt):
    """Photo de profil d'illustration (comme les maquettes), en data URL : aucune ressource externe."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
           f'<stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient></defs>'
           f'<rect width="100" height="100" fill="url(#g)"/><path d="M14 106c2-26 18-34 36-34s34 8 36 34z" fill="{shirt}"/>'
           f'<rect x="43" y="54" width="14" height="20" rx="7" fill="{skin}"/><ellipse cx="50" cy="43" rx="15.5" ry="17.5" fill="{skin}"/>'
           f'<path d="M34 41c-1-14 8-20 16-20 10 0 17 6 16 20-2-6-8-10-16-10s-14 4-16 10z" fill="{hair}"/></svg>')
    return 'data:image/svg+xml,' + urllib.parse.quote(svg)


P_LEA = portrait('#F2A07B', '#9A3E6E', '#F1C3A1', '#5A2E1E', '#2B1B4A')
P_MATHIEU = portrait('#57B6C9', '#2B3F8C', '#E8B48E', '#2A1A12', '#E9E4FA')
P_ANAIS = portrait('#E2BE76', '#6B4A2E', '#A8714F', '#1E120C', '#FF8FC0')
P_MAMAN = portrait('#C46BB0', '#3C2470', '#F3CFB3', '#D8D2E0', '#5BE3A6')


def ago(minutes=0, days=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes, days=days)).isoformat()


def ahead(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(hour=18, minute=0, second=0, microsecond=0).isoformat()


def item(kind, cid, title, **extra):
    base = {'kind': kind, 'id': cid, 'title': title, 'photo': None, 'emoji': None, 'color': None, 'user_id': None, 'event_start': None,
            'event_past': False, 'last': None, 'unread': 0, 'mention': False, 'marked_unread': False, 'pinned_at': None, 'archived': False,
            'notify': 'all', 'muted_until': None, 'request': None, 'seen_by_other': None, 'members': 2, 'is_vp': False, 'blocked': False}
    base.update(extra)
    return base


def last(text, minutes=0, days=0, from_me=False, author=None, kind='text', mid=None):
    return {'id': mid or uid(900 + minutes + days * 1440), 'at': ago(minutes, days), 'from_me': from_me, 'author': author, 'type': kind, 'text': text}


def neon_list():
    """Les discussions de la maquette 1-liste (+ 2 demandes reçues et 3 archivées)."""
    return [
        item('direct', DM_LEA, 'Léa', user_id=LEA, photo=f'{LEA}/photo.svg', unread=2, pinned_at=ago(1), last=last('On se retrouve où ?', 6)),
        item('event', E_RACLETTE, 'Raclette chez Léa', event_start=ahead(3), unread=12, pinned_at=ago(2), members=14,
             last=last('Je prends le fromage !', 8, author='Tom')),
        item('group', G_COLOC, 'Coloc’ de la Cité', emoji='🏡', color='coral', pinned_at=ago(3), members=4, last=last('Courses faites', 60, author='Inès')),
        item('direct', DM_MAMAN, 'Maman', user_id=MAMAN, photo=P_MAMAN, pinned_at=ago(4), last=last('Bisous', 90, from_me=True), seen_by_other=True),
        item('direct', DM_MATHIEU, 'Mathieu Favre', user_id=MATHIEU, photo=P_MATHIEU, unread=2, last=last('Tu es où ?', 4)),
        item('group', G_JURA, 'Les Copains du Jura', emoji='🥾', color='mint', unread=3, mention=True, members=8, notify='mentions',
             last=last('@Sam tu prends la voiture samedi ?', 12, author='Noé')),
        item('direct', DM_CHLOE, 'Chloé Bonvin', user_id=CHLOE, unread=1, last=last('Message vocal · 0:42', 21, kind='audio')),
        item('event', E_PAINTBALL, 'Paintball à Bulle', event_start=ahead(4), unread=6, notify='none', members=12,
             last=last(None, 54, author='Julien', kind='photo')),
        item('direct', DM_ANAIS, 'Anaïs Perrin', user_id=ANAIS, photo=P_ANAIS, seen_by_other=True,
             last=last('Merci pour hier soir, c’était top 🙏', 160, from_me=True)),
        item('group', G_BASKET, 'Basket du mardi', emoji='🏀', color='sky', members=10, last=last('Salle 3 à Malley, même heure', 0, 1, author='Kevin')),
        item('group', G_VP, 'Membres Vendredi Party', is_vp=True, emoji='🎉', color='lavender', members=128, notify='mentions',
             last=last('📣 Annonce : nouvelle saison de jeux', 0, 3, author='Party')),
        item('direct', REQ_NOE, 'Noé Martin', user_id=NOE, request='incoming', last=last('Salut ! On s’est vus à la raclette, tu as le lien des photos ?', 30, mid=uid(990))),
        item('direct', REQ_ZOE, 'Zoé', user_id=ZOE, request='incoming', last=last('Hello, tu viens au paintball ?', 300, mid=uid(991))),
        item('group', G_OLD, 'Anniversaire de Malik', emoji='🎂', color='pink', archived=True, last=last('Merci à tous !', 0, 20, author='Malik')),
        item('direct', uid(150), 'Sacha', user_id=uid(50), archived=True, last=last('Bonne année !', 0, 40)),
        item('event', uid(350), 'Karaoké d’octobre', event_start=ahead(-30), event_past=True, archived=True, last=last('🎤', 0, 29, author='Léa')),
    ]


PEOPLE = [{'id': LEA, 'name': 'Léa Rochat', 'nickname': 'Léa', 'photo': P_LEA, 'sub': 'Raclette chez Léa', 'link': 'direct', 'met_count': 4},
          {'id': uid(60), 'name': 'Léonie Favre', 'nickname': 'Léo', 'photo': None, 'sub': None, 'link': 'request', 'met_count': 0}]
CROSSED = [{'id': LEA, 'name': 'Léa', 'nickname': 'Léa', 'photo': P_LEA, 'sub': 'la Soirée raclette', 'link': 'direct', 'met_count': 1},
           {'id': MATHIEU, 'name': 'Mathieu', 'nickname': None, 'photo': P_MATHIEU, 'sub': 'la Soirée raclette', 'link': 'direct', 'met_count': 1},
           {'id': CHLOE, 'name': 'Chloé', 'nickname': None, 'photo': None, 'sub': 'la Soirée raclette', 'link': 'request', 'met_count': 1}]


def list_services(page, chats=None):
    """Base simulée : chat_list et les fonctions de la liste ; state garde les appels."""
    mock_services(page)
    state = {'chats': neon_list() if chats is None else chats, 'rpc': [], 'sockets': [], 'signed': []}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        path = urlparse(request.url).path
        body = json.loads(request.post_data) if request.post_data else None
        name = path.rsplit('/', 1)[1]
        if '/rpc/' in path and name not in ('get_member_directory', 'my_permissions', 'my_rank'):
            state['rpc'].append((name, body))
        if name == 'chat_list':
            result = state['chats']
        elif name == 'chat_badge':
            result = 24
        elif name == 'set_chat_state':
            for c in state['chats']:
                if c['id'] == body['chat']:
                    if body.get('archived') is not None:
                        c['archived'] = body['archived']
                    if body.get('pinned') is not None:
                        c['pinned_at'] = ago() if body['pinned'] else None
                    if body.get('muted_until') is not None:
                        c['muted_until'] = body['muted_until']
            result = None
        elif name == 'reorder_chat_pins':  # ordre choisi : la première à gauche = la plus récente (20.11)
            now = datetime.now(timezone.utc)
            for i, item in enumerate(body['chats']):
                for c in state['chats']:
                    if c['id'] == item['id'] and c['kind'] == item['kind'] and c['pinned_at']:
                        c['pinned_at'] = (now - timedelta(seconds=i)).isoformat()
            result = None
        elif name == 'chat_people_search':
            result = [p for p in PEOPLE if body['q'].lower()[:2] in p['name'].lower()]
        elif name == 'chat_event_search':  # mes événements encore sans message (19.11)
            result = [{'kind': 'event', 'id': uid(888), 'title': 'Lézard Party', 'photo': None, 'emoji': None, 'color': None,
                       'user_id': None, 'event_start': ago(days=-5), 'event_past': False, 'last': None, 'unread': 0,
                       'mention': False, 'marked_unread': False, 'pinned_at': None, 'archived': False, 'notify': 'all',
                       'muted_until': None, 'request': None, 'seen_by_other': None, 'members': 4, 'is_vp': False,
                       'blocked': False}]
        elif name == 'chat_search':
            result = [{'kind': 'group', 'id': G_JURA, 'title': 'Les Copains du Jura', 'message_id': uid(777),
                       'excerpt': 'On passe prendre Léa à 18 h', 'at': ago(200)}]
        elif name == 'chat_people_suggestions':
            result = {'recent': [], 'crossed': CROSSED, 'groups': []}
        elif name == 'open_direct_chat':
            result = {'chat': DM_LEA, 'status': 'active', 'reason': None}
        elif name in ('accept_message_request', 'decline_message_request', 'set_direct_block', 'mark_direct_read', 'mark_group_read', 'set_block',
                      'set_direct_chat_notify', 'set_group_chat_notify', 'report_content'):
            if name in ('accept_message_request', 'decline_message_request'):
                state['chats'] = [c for c in state['chats'] if c['id'] != body['chat']]
            result = None
        elif path.endswith('/notification_prefs'):
            result = None
        elif '/storage/v1/object/sign/' in path and request.method == 'POST':
            # Photos : chat_list donne des chemins du stockage ; la page les signe (profile-photos, group-photos).
            state['signed'].append(path.split('/object/sign/', 1)[1])
            result = {'signedURL': '/object/sign/' + path.split('/object/sign/', 1)[1] + '?token=t'}
        elif '/storage/v1/object/sign/' in path:
            svg = urllib.parse.unquote(P_LEA.split(',', 1)[1])
            return route.fulfill(status=200, content_type='image/svg+xml', body=svg, headers=CORS)
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route(SUPABASE, handle)

    # Temps réel : on garde les sockets pour envoyer un « écrit… » (protocole Phoenix 2.0.0 : tableaux JSON).
    def socket(ws):
        state['sockets'].append(ws)
        def on_message(message):
            try:
                join_ref, ref, topic, event, _payload = json.loads(message)
            except (ValueError, TypeError):
                return
            if event == 'phx_join':
                ws.send(json.dumps([join_ref, ref, topic, 'phx_reply', {'status': 'ok', 'response': {'postgres_changes': []}}]))
            elif event == 'heartbeat':
                ws.send(json.dumps([None, ref, 'phoenix', 'phx_reply', {'status': 'ok', 'response': {}}]))
        ws.on_message(on_message)
    page.route_web_socket('wss://gsuetixzobooggeaubvb.supabase.co/**', socket)
    return state


def typing(state, kind, cid, user, name):
    for ws in state['sockets']:
        ws.send(json.dumps([None, None, f'realtime:typing:{kind}:{cid}', 'broadcast',
                            {'type': 'broadcast', 'event': 'typing', 'payload': {'user': user, 'name': name}}]))


SHOTS = Path(os.environ.get('CHATS_SHOTS') or '/tmp/party-chats-list-shots')


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(700)  # animations d'entrée finies
    page.screenshot(path=str(SHOTS / name))


def open_list(page, events_origin, path='/chats'):
    """Module Événements seul (comme dans l'app), connecté, sur la liste."""
    page.goto(events_origin + '/events/', wait_until='domcontentloaded')
    login(page)
    page.wait_for_timeout(500)
    page.goto(f'{events_origin}/events{path}', wait_until='domcontentloaded')


@pytest.fixture
def phone(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, has_touch=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    yield page, errors
    context.close()


def test_the_list_looks_like_the_neon_mockup(phone, events_origin):
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin)
    pw.expect(page.get_by_role('heading', name='Discussions')).to_be_visible(timeout=15000)
    # Épinglées en tuiles (4), dans l'ordre d'épinglage ; Demandes (2) et Archivées (3).
    pins = page.get_by_role('list', name='Épinglées').get_by_role('button')
    pw.expect(pins).to_have_count(4)
    assert pins.nth(0).get_attribute('aria-label').startswith('Message direct Léa, 2 non lus')
    assert pins.nth(1).get_attribute('aria-label').startswith('Événement Raclette chez Léa, 12 non lus')
    pw.expect(page.get_by_role('link', name='Demandes de message, 2 nouvelles')).to_be_visible()
    pw.expect(page.get_by_role('link', name='Archivées, 3')).to_be_visible()
    rows = page.get_by_role('list', name='Toutes les discussions').get_by_role('button', name='Message direct', exact=False)
    pw.expect(rows.first).to_be_visible()
    # Les demandes et les archivées ne sont pas dans la liste ; les épinglées non plus (elles sont en tuiles).
    listing = page.get_by_role('list', name='Toutes les discussions')
    pw.expect(listing.get_by_role('button', name='Message direct Noé Martin', exact=False)).to_have_count(0)
    pw.expect(listing.get_by_role('button', name='Discussion Anniversaire de Malik', exact=False)).to_have_count(0)
    pw.expect(listing.get_by_role('button', name='Message direct Léa,', exact=False)).to_have_count(0)
    # @ (on te cite), sourdine (pastille grise), Vu, aperçu « Toi : », groupe « Noé : », logo officiel de Membres Vendredi Party.
    pw.expect(listing.get_by_role('button', name='Discussion Les Copains du Jura, 3 non lus, on te cite')).to_be_visible()
    pw.expect(listing.get_by_role('button', name='Événement Paintball à Bulle, 6 non lus, en sourdine')).to_be_visible()
    pw.expect(listing.get_by_text('Toi : Merci pour hier soir, c’était top 🙏')).to_be_visible()
    pw.expect(listing.get_by_label('Vu').first).to_be_attached()
    pw.expect(listing.get_by_text('Noé : @Sam tu prends la voiture samedi ?')).to_be_visible()
    assert '/static/icon-192.png' in page.get_by_test_id('vp-logo').locator('img').first.get_attribute('src')
    # « écrit… » : signal en direct sur typing:direct:<id>.
    page.wait_for_timeout(800)
    typing(state, 'direct', DM_MATHIEU, MATHIEU, 'Mathieu')
    pw.expect(listing.get_by_role('button', name='Message direct Mathieu Favre, 2 non lus, Mathieu écrit')).to_be_visible(timeout=5000)
    pw.expect(listing.get_by_text('écrit', exact=True)).to_be_visible()
    # Pastille de l'onglet : chat_badge.
    assert any(n == 'chat_badge' for n, _ in state['rpc'])
    assert f'profile-photos/{LEA}/photo.svg' in state['signed']  # photo = chemin signé par la page
    pw.expect(page.get_by_role('button', name='Nouveau message')).to_be_visible()
    shot(page, '1-liste.png')
    assert not errors, errors


def test_dark_like_party_and_light_tokens_on_demand(browser, events_origin):
    """Sombre comme tout Party, même sur un appareil en mode clair ; ?theme=light montre les jetons clairs (maquette 1b)."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, color_scheme='light')
    page = context.new_page()
    try:
        state = list_services(page)
        open_list(page, events_origin)
        heading = page.get_by_role('heading', name='Discussions')
        pw.expect(heading).to_be_visible(timeout=15000)
        assert heading.evaluate('e => getComputedStyle(e).color') == 'rgb(244, 241, 255)'  # #F4F1FF
        page.goto(f'{events_origin}/events/chats?theme=light', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('heading', name='Discussions')).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        typing(state, 'direct', DM_MATHIEU, MATHIEU, 'Mathieu')
        pw.expect(page.get_by_text('écrit', exact=True)).to_be_visible(timeout=5000)
        color = page.get_by_role('heading', name='Discussions').evaluate('e => getComputedStyle(e).color')
        assert color == 'rgb(29, 21, 48)'  # #1D1530 : texte du mode clair
        shot(page, '1b-liste-clair.png')
    finally:
        context.close()


def test_filters_and_search_people_chats_and_messages(phone, events_origin):
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin)
    listing = page.get_by_role('list', name='Toutes les discussions')
    pw.expect(listing.get_by_role('button').first).to_be_visible(timeout=15000)
    page.get_by_role('tab', name='Non lus, 6').click()
    pw.expect(listing.get_by_role('button', name='Basket du mardi', exact=False)).to_have_count(0)
    pw.expect(listing.get_by_role('button', name='Message direct Léa, 2 non lus', exact=False)).to_be_visible()  # épinglée : ligne ici
    page.get_by_role('tab', name='Événements').click()
    pw.expect(listing.get_by_role('button', name='Événement', exact=False)).to_have_count(2)
    page.get_by_role('tab', name='Groupes').click()
    pw.expect(listing.get_by_role('button', name='Discussion Membres Vendredi Party', exact=False)).to_be_visible()
    pw.expect(listing.get_by_role('button', name='Message direct', exact=False)).to_have_count(0)
    page.get_by_role('tab', name='Tout').click()

    page.get_by_label('Rechercher dans les discussions').fill('Lé')
    pw.expect(page.get_by_role('heading', name='Personnes')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Léa Rochat', exact=False)).to_be_visible()
    pw.expect(page.get_by_role('button', name='Léonie Favre, demande de message')).to_be_visible()
    pw.expect(page.get_by_role('heading', name='Discussions', exact=True).nth(1)).to_be_visible()
    pw.expect(page.get_by_role('button', name='Ouvrir Léa')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Message dans Les Copains du Jura : On passe prendre Léa à 18 h')).to_be_visible()
    assert ('chat_people_search', {'q': 'Lé'}) in state['rpc'] and ('chat_search', {'q': 'Lé'}) in state['rpc']
    pw.expect(page.get_by_role('heading', name='Événements')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Discussion de l’événement Lézard Party')).to_be_visible()
    shot(page, '6-recherche.png')
    page.get_by_role('button', name='Message dans Les Copains du Jura', exact=False).click()
    pw.expect(page).to_have_url(f'{events_origin}/events/chats/{G_JURA}?message={uid(777)}', timeout=10000)
    assert not errors, errors


def test_long_press_menu_pins_mutes_and_swipe_archives(phone, events_origin):
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin)
    row = page.get_by_role('button', name='Discussion Basket du mardi', exact=False)
    pw.expect(row).to_be_visible(timeout=15000)
    row.click(delay=700)  # appui long
    sheet = page.get_by_label('Options : Basket du mardi', exact=True)
    pw.expect(sheet).to_be_visible()
    pw.expect(sheet.get_by_text('Salle 3 à Malley, même heure')).to_be_visible()  # aperçu du dernier message
    shot(page, '7-menu.png')
    sheet.get_by_role('menuitem', name='Épingler').click()
    pw.expect(page.get_by_role('list', name='Épinglées').get_by_role('button')).to_have_count(5)
    assert ('set_chat_state', {'kind': 'group', 'chat': G_BASKET, 'pinned': True, 'archived': None, 'unread': None}) in state['rpc']
    # Sixième épingle : refusée à l'écran (5 au plus).
    page.get_by_role('button', name='Discussion Les Copains du Jura', exact=False).click(delay=700)
    page.get_by_role('menuitem', name='Épingler').click()
    pw.expect(page.get_by_role('alert')).to_contain_text('5 discussions au plus')
    # Sourdine 1 h.
    page.get_by_role('button', name='Message direct Chloé Bonvin', exact=False).click(delay=700)
    page.get_by_role('menuitem', name='Sourdine…').click()
    page.get_by_role('menuitem', name='Sourdine : 1 heure').click()
    pw.expect(page.get_by_role('button', name='Message direct Chloé Bonvin, 1 non lu, en sourdine')).to_be_visible()
    assert any(n == 'set_chat_state' and set(b) == {'kind', 'chat', 'muted_until'} and b['chat'] == DM_CHLOE and b['muted_until'] > ago()
               for n, b in state['rpc'])
    # « Toujours » : muted_until = infinity ; « Réactiver » : une date passée.
    page.get_by_role('button', name='Discussion Basket du mardi', exact=False).click(delay=700)
    page.get_by_role('menuitem', name='Sourdine…').click()
    page.get_by_role('menuitem', name='Sourdine : Toujours').click()
    pw.expect(page.get_by_role('list', name='Épinglées').get_by_role('button', name='Discussion Basket du mardi, en sourdine, épinglée')).to_be_visible()
    assert ('set_chat_state', {'kind': 'group', 'chat': G_BASKET, 'muted_until': 'infinity'}) in state['rpc']
    page.get_by_role('button', name='Message direct Chloé Bonvin', exact=False).click(delay=700)
    page.get_by_role('menuitem', name='Réactiver les notifications').click()
    pw.expect(page.get_by_role('button', name='Message direct Chloé Bonvin, 1 non lu')).to_be_visible()
    assert ('set_chat_state', {'kind': 'direct', 'chat': DM_CHLOE, 'muted_until': '1970-01-01T00:00:00.000Z'}) in state['rpc']
    # Glisser vers la gauche (doigt) : Sourdine et Archiver ; Archiver range la discussion, « Annuler » la remet.
    target = page.get_by_role('button', name='Message direct Anaïs Perrin', exact=False)
    box = target.bounding_box()
    y = box['y'] + box['height'] / 2
    page.mouse.move(box['x'] + box['width'] / 2, y)
    page.mouse.down()
    for step in range(1, 9):
        page.mouse.move(box['x'] + box['width'] / 2 - step * 22, y)
    page.mouse.up()
    archive = page.get_by_role('button', name='Archiver', exact=True)
    pw.expect(archive).to_be_visible()
    shot(page, '8-glisse.png')
    archive.click()
    pw.expect(page.get_by_role('button', name='Message direct Anaïs Perrin', exact=False)).to_have_count(0)
    pw.expect(page.get_by_role('status')).to_contain_text('Discussion archivée')
    assert ('set_chat_state', {'kind': 'direct', 'chat': DM_ANAIS, 'pinned': None, 'archived': True, 'unread': None}) in state['rpc']
    pw.expect(page.get_by_role('link', name='Archivées, 4')).to_be_visible()
    page.get_by_role('button', name='Annuler', exact=True).click()
    pw.expect(page.get_by_role('button', name='Message direct Anaïs Perrin', exact=False)).to_be_visible()
    assert not errors, errors


def test_hover_shows_more_button_on_a_computer(browser, events_origin):
    context = browser.new_context(viewport={'width': 1100, 'height': 800})
    page = context.new_page()
    try:
        list_services(page)
        open_list(page, events_origin)
        row = page.get_by_role('button', name='Discussion Basket du mardi', exact=False)
        pw.expect(row).to_be_visible(timeout=15000)
        more = page.get_by_role('button', name='Plus d’options : Basket du mardi')
        assert more.evaluate('e => getComputedStyle(e).opacity') == '0'
        row.hover()
        pw.expect(more).to_have_css('opacity', '1')
        more.click()
        pw.expect(page.get_by_label('Options : Basket du mardi', exact=True)).to_be_visible()
    finally:
        context.close()


def test_requests_accept_delete_block_and_report(phone, events_origin):
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin)
    page.get_by_role('link', name='Demandes de message, 2 nouvelles').click(timeout=15000)
    pw.expect(page.get_by_role('heading', name='Demandes')).to_be_visible(timeout=10000)
    pw.expect(page.get_by_text('Salut ! On s’est vus à la raclette, tu as le lien des photos ?')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Voir le profil de Noé Martin')).to_be_visible()
    shot(page, '9-demandes.png')
    page.get_by_role('button', name='Signaler la demande de Zoé').click()
    pw.expect(page.get_by_text('Signaler la demande de Zoé', exact=True)).to_be_visible()
    page.get_by_role('button', name='Fermer la fenêtre').click()
    page.get_by_role('button', name='Supprimer la demande de Zoé').click()
    pw.expect(page.get_by_role('status')).to_contain_text('Demande supprimée')
    pw.expect(page.get_by_text('Hello, tu viens au paintball ?')).to_have_count(0)
    assert ('decline_message_request', {'chat': REQ_ZOE}) in state['rpc']
    page.get_by_role('button', name='Accepter la demande de Noé Martin').click()
    pw.expect(page).to_have_url(f'{events_origin}/events/chats/{REQ_NOE}', timeout=10000)
    assert ('accept_message_request', {'chat': REQ_NOE}) in state['rpc']
    assert not errors, errors


def test_block_from_a_request_is_confirmed(phone, events_origin):
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin, '/chats/requests')
    page.get_by_role('button', name='Bloquer Zoé').click(timeout=15000)
    page.get_by_role('button', name='Confirmer : bloquer Zoé').click()
    pw.expect(page.get_by_role('status')).to_contain_text('Personne bloquée')
    assert ('set_block', {'target': ZOE, 'blocked': True}) in state['rpc']
    assert not errors, errors


def test_archived_screen_takes_a_chat_out(phone, events_origin):
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin)
    page.get_by_role('link', name='Archivées, 3').click(timeout=15000)
    pw.expect(page.get_by_role('heading', name='Archivées')).to_be_visible(timeout=10000)
    shot(page, '10-archivees.png')
    page.get_by_role('button', name='Discussion Anniversaire de Malik', exact=False).click(delay=700)
    page.get_by_role('menuitem', name='Sortir des archives').click()
    pw.expect(page.get_by_role('button', name='Discussion Anniversaire de Malik', exact=False)).to_have_count(0)
    assert ('set_chat_state', {'kind': 'group', 'chat': G_OLD, 'pinned': None, 'archived': False, 'unread': None}) in state['rpc']
    assert not errors, errors


def test_empty_state_suggests_people_met_and_writes_to_them(phone, events_origin):
    page, errors = phone
    state = list_services(page, chats=[])
    open_list(page, events_origin)
    pw.expect(page.get_by_role('heading', name='Ta première discussion commence ici')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('Croisés à la Soirée raclette', exact=False)).to_be_visible()
    pw.expect(page.get_by_role('button', name='Nouveau message')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Nouveau groupe', exact=True)).to_be_visible()
    shot(page, '5-vide.png')
    page.get_by_role('button', name='Écrire à Léa').click()
    pw.expect(page).to_have_url(f'{events_origin}/events/chats/{DM_LEA}', timeout=10000)
    assert ('open_direct_chat', {'target': LEA}) in state['rpc']
    assert not errors, errors


def test_new_message_button_and_more_menu(phone, events_origin):
    page, errors = phone
    list_services(page)
    open_list(page, events_origin)
    page.get_by_role('button', name='Plus : Demandes de message', exact=False).click(timeout=15000)
    menu = page.get_by_role('menu', name='Menu')
    pw.expect(menu.get_by_role('menuitem', name='Archivées (3)')).to_be_visible()
    menu.get_by_role('menuitem', name='Pause des notifications…').click()
    pw.expect(page.get_by_role('menuitem', name='Groupes et messages : 1 h')).to_be_visible()
    page.mouse.click(40, 760)  # toucher à côté ferme le menu
    pw.expect(page.get_by_role('menu', name='Menu')).to_have_count(0)
    page.get_by_role('button', name='Nouveau message').click()
    pw.expect(page).to_have_url(f'{events_origin}/events/chats/new', timeout=10000)
    assert not errors, errors


def test_in_party_the_chats_tab_is_full_screen_with_a_single_title(phone, events_origin):
    """Page Party : l'onglet Discussions est en plein écran comme les Événements (panneau fixe, style.css) ; le module porte
    le grand titre de la maquette, Party ne le répète pas."""
    page, errors = phone
    list_services(page)
    page.route('**/api/account/link', lambda route: route.fulfill(content_type='application/json', body=json.dumps(
        {'guest_id': 'acct-test', 'name': 'Compte de démonstration', 'photo': None, 'beta': True})))
    page.goto(events_origin, wait_until='domcontentloaded')
    page.locator('#accountTab').click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_role('button', name='Mon profil : Compte de démonstration')).to_be_visible(timeout=15000)
    page.locator('#tabs [data-tab="chats"]').click()
    pw.expect(frame.get_by_role('heading', name='Discussions')).to_be_visible(timeout=15000)
    pw.expect(page.locator('#appTitle')).to_be_hidden()
    assert page.locator('.events-panel').evaluate('e => getComputedStyle(e).position') == 'fixed'
    shot(page, '11-dans-party.png')
    assert not errors, errors



def pin_order(page):
    return [b.get_attribute('aria-label').split(',')[0] for b in page.get_by_role('list', name='Épinglées').get_by_role('button').all()]


def test_pinned_chats_move_left_and_right_and_the_order_stays(phone, events_origin):  # noqa: F811
    """Avis e75a1d5af3ee (20.11) : réorganiser les épinglées. Appui long sur une tuile : « Déplacer à gauche / à droite »
    (jamais au bout de la rangée) ; l'ordre change tout de suite, part à la base (reorder_chat_pins) et reste au retour."""
    page, errors = phone
    state = list_services(page)
    open_list(page, events_origin)
    pins = page.get_by_role('list', name='Épinglées')
    pw.expect(pins.get_by_role('button')).to_have_count(4, timeout=15000)
    assert pin_order(page) == ['Message direct Léa', 'Événement Raclette chez Léa', 'Discussion Coloc’ de la Cité', 'Message direct Maman']
    # Au bout de la rangée : pas de « Déplacer à gauche » sur la première, pas de « Déplacer à droite » sur la dernière.
    pins.get_by_role('button', name='Message direct Léa', exact=False).click(delay=700)
    pw.expect(page.get_by_role('menuitem', name='Déplacer à droite')).to_be_visible()
    pw.expect(page.get_by_role('menuitem', name='Déplacer à gauche')).to_have_count(0)
    sheet = page.get_by_label('Options : Léa', exact=True)
    sheet.get_by_role('button', name='Fermer', exact=True).click()  # ✕ : il était recouvert par la ligne du nom (20.11)
    pw.expect(sheet).to_have_count(0)
    pins.get_by_role('button', name='Message direct Maman', exact=False).click(delay=700)
    pw.expect(page.get_by_role('menuitem', name='Déplacer à gauche')).to_be_visible()
    pw.expect(page.get_by_role('menuitem', name='Déplacer à droite')).to_have_count(0)
    page.get_by_role('menuitem', name='Déplacer à gauche').click()
    pw.expect(page.get_by_label('Options : Maman', exact=True)).to_have_count(0)
    assert pin_order(page) == ['Message direct Léa', 'Événement Raclette chez Léa', 'Message direct Maman', 'Discussion Coloc’ de la Cité']
    sent = [b for n, b in state['rpc'] if n == 'reorder_chat_pins']
    assert [(c['kind'], c['id']) for c in sent[-1]['chats']] == [('direct', DM_LEA), ('event', E_RACLETTE), ('direct', DM_MAMAN), ('group', G_COLOC)]
    # Raclette passe en premier.
    pins.get_by_role('button', name='Événement Raclette chez Léa', exact=False).click(delay=700)
    page.get_by_role('menuitem', name='Déplacer à gauche').click()
    pw.expect(pins.get_by_role('button').first).to_have_attribute('aria-label', re.compile('^Événement Raclette chez Léa'))
    shot(page, '9-epinglees-ordre.png')
    # Retour sur la liste (relue de la base) : le même ordre.
    page.reload(wait_until='domcontentloaded')
    pw.expect(pins.get_by_role('button')).to_have_count(4, timeout=15000)
    assert pin_order(page) == ['Événement Raclette chez Léa', 'Message direct Léa', 'Message direct Maman', 'Discussion Coloc’ de la Cité']
    assert not errors, errors
