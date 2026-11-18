"""Discussions v2 — personnes (web, module Événements), dans un vrai navigateur, Supabase simulé (aucune donnée réelle) :
- mini-profil au toucher d'une personne (participant d'un événement) : « Déjà vu N fois » + ses 3 dernières soirées,
  « À venir ensemble », groupes en commun ; « Envoyer un message » → open_direct_chat puis la conversation ; désactivé
  avec sa raison quand la base dit « none » (« Jamais rencontré ») ; dans l'app iPhone → pont natif openDirect ;
- Nouveau message : suggestions (Croisés récemment, Dans tes groupes), recherche, 1 personne → « Écrire à … » (demande de
  message annoncée), 2 personnes → « Créer un groupe avec … » (groupe existant ouvert, sinon formulaire 2b ; refusés :
  « écris-leur d'abord ») ; ?event=<id> : la carte de la soirée part avec le premier message ;
- fiche membre : « Envoyer un message » passe par open_direct_chat.
Captures : PARTY_SHOTS=<dossier> (sinon rien n'est écrit). Module construit ailleurs : EVENTS_TEST_DIST=<dossier>."""
import json
import os
from pathlib import Path
import re

import pytest

from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services  # noqa: F401 (fixtures)

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

REST = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
LEA, NOE, CHLOE, ANAIS, KEVIN, SOPHIE = ('7a1c2b3d-0000-4000-8000-00000000001' + str(i) for i in range(6))
CHAT = 'c0000000-0000-4000-8000-000000000001'
GROUP = 'c0000000-0000-4000-8000-000000000002'
PAST = [('e0000000-0000-4000-8000-00000000000' + str(i), t, d) for i, t, d in
        ((1, 'Raclette chez Léa', '2026-11-07T19:00:00Z'), (2, 'Paintball à Bulle', '2026-10-24T13:00:00Z'), (3, 'Anniv’ Bastien', '2026-09-12T19:00:00Z'))]
SHOTS = Path(os.environ['PARTY_SHOTS']) if os.environ.get('PARTY_SHOTS') else None


def portrait(c1, c2, hair):
    """Visage dessiné (comme la maquette) : servi comme « photo » déjà signée."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
            f'<rect width="100" height="100" fill="url(#g)"/><path d="M14 106c2-26 18-34 36-34s34 8 36 34z" fill="#2A1E4A"/>'
            f'<rect x="43" y="54" width="14" height="20" rx="7" fill="#E9B48F"/><ellipse cx="50" cy="43" rx="15.5" ry="17.5" fill="#F2C29B"/>'
            f'<path d="M34 41c-1-14 8-20 16-20 10 0 17 6 16 20-2-6-8-10-16-10s-14 4-16 10z" fill="{hair}"/></svg>')


PHOTOS = {'lea': portrait('#F7B2C4', '#D9667F', '#6B3A1F'), 'noe': portrait('#9FE3C1', '#3E8F6C', '#B07A45'),
          'anais': portrait('#E9D7A8', '#B88A4A', '#2A1A12')}


def person(pid, name, sub='', link='direct', met=0, photo=None, nickname=None):
    return {'id': pid, 'name': name, 'nickname': nickname, 'photo': f'https://photos.test/{photo}.svg' if photo else None,
            'sub': sub, 'link': link, 'met_count': met}


SUGGESTIONS = {
    'recent': [],
    'crossed': [person(LEA, 'Léa Morel', 'Raclette', met=3, photo='lea', nickname='Léa'), person(NOE, 'Noé Gaillard', 'Paintball', photo='noe', nickname='Noé'),
                person(CHLOE, 'Chloé Borel', 'Raclette', link='request', nickname='Chloé'), person(ANAIS, 'Anaïs Python', 'Anniv’ Bastien', photo='anais', nickname='Anaïs')],
    'groups': [person(KEVIN, 'Kevin Monnier', 'Basket du mardi'), person(SOPHIE, 'Sophie Berset', 'Coloc’ de la Cité', met=2)],
}


def mini(link='direct', met=3, blocked=False):
    return {'id': LEA, 'name': 'Léa Morel', 'nickname': 'Léa', 'photo': 'https://photos.test/lea.svg', 'since': '2026-10-02T10:00:00Z',
            'link': link, 'blocked': blocked, 'blocked_me': False, 'chat': None, 'met_count': met,
            'met': [{'id': i, 'title': t, 'start': d} for i, t, d in PAST][:met],
            'events': [{'id': EVENT, 'title': 'Soirée raclette chez Léa', 'start': '2030-11-21T18:00:00Z', 'mine': 'yes', 'theirs': 'yes'},
                       {'id': 'e0000000-0000-4000-8000-000000000009', 'title': 'Paintball à Bulle', 'start': '2030-11-22T09:00:00Z', 'mine': 'maybe', 'theirs': 'yes'}],
            'groups': [{'id': GROUP, 'name': 'Les Copains du Jura', 'emoji': '🥾', 'color': 'mint', 'photo': None},
                       {'id': 'c0000000-0000-4000-8000-000000000003', 'name': 'Basket du mardi', 'emoji': '🏀', 'color': 'sky', 'photo': None}],
            'events_count': 2, 'groups_count': 2}


def people_backend(page, state):
    """Fonctions des Discussions v2 (contrat §4-6), par-dessus la base simulée de test_events_browser."""
    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        fn = request.url.split('?')[0].removeprefix(REST)
        body = json.loads(request.post_data) if request.post_data else None
        state['calls'].append((request.method, fn, body))
        answers = {
            'rpc/member_mini': state.get('mini'),
            'rpc/chat_people_suggestions': SUGGESTIONS,
            'rpc/chat_people_search': [p for p in SUGGESTIONS['crossed'] + SUGGESTIONS['groups'] if (body or {}).get('q', '').lower()[:2] in p['name'].lower()],
            'rpc/open_direct_chat': state.get('open', {'chat': CHAT, 'status': 'active', 'reason': None}),
            'rpc/chat_group_with': state.get('existing'),
            'rpc/create_chat_group': {'group': GROUP, 'invited': 1, 'refused': state.get('refused', [])},
            'rpc/chat_event_cards': [{'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'start': '2030-11-14T18:00:00Z',
                                      'place': 'Lieu de démonstration', 'cover': None, 'going': 4, 'mine': 'yes'}],
        }
        if fn in answers:
            return route.fulfill(status=200, headers=HEADERS, content_type='application/json', body=json.dumps(answers[fn]))
        if fn in ('direct_messages', 'group_messages') and request.method == 'POST':
            state['posts'].append((fn, body))
            return route.fulfill(status=201, headers=HEADERS, content_type='application/json', body='[]')
        return route.fallback()

    page.route(REST + '**', handle)
    page.route('https://photos.test/**', lambda r: r.fulfill(content_type='image/svg+xml', body=PHOTOS[r.request.url.rsplit('/', 1)[1][:-4]]))


@pytest.fixture
def phone(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    yield context
    context.close()


def start(context, origin, state, native=False):
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    if native:
        page.add_init_script("window.PartyNative = { platform: 'ios', chat: { openEvent() {}, openDirect: (id) => { (window.top.__direct = window.top.__direct || []).push(id); } } };")
    mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}],
                  rsvps=[{'event_id': EVENT, 'user_id': LEA, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False, 'updated_at': '2026-11-13T20:17:00Z'}])
    state.setdefault('calls', [])
    state.setdefault('posts', [])
    people_backend(page, state)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
    return page, frame, errors


def frame_path(page):
    return page.evaluate("document.getElementById('eventsFrame').contentWindow.location.pathname")


def go(page, path):
    """Ouvre une page du module dans le cadre, comme l'app iPhone (PartyEvents.open ; connexion gardée)."""
    page.evaluate(f"PartyEvents.open('/events{path}')")


def shot(page, name):
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.wait_for_timeout(600)  # fin des apparitions
        page.locator('#eventsFrame').screenshot(path=str(SHOTS / f'{name}.png'))


def rpc_args(state, fn):
    return [b for m, f, b in state['calls'] if f == f'rpc/{fn}']


def open_lea(frame):
    frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    frame.get_by_role('button', name='Profil de Léa').first.click()
    sheet = frame.get_by_test_id('mini-profile')
    pw.expect(sheet).to_be_visible(timeout=15000)
    return sheet


def test_a_participant_opens_the_mini_profile_and_writes(phone, events_origin):
    state = {'mini': mini()}
    page, frame, errors = start(phone, events_origin, state)
    sheet = open_lea(frame)
    pw.expect(sheet.get_by_role('heading', name='Léa Morel')).to_be_visible()
    pw.expect(sheet.get_by_test_id('mini-met')).to_have_text('Déjà vu 3 fois')
    for _, title, _ in PAST:  # ses 3 dernières soirées vécues ensemble
        pw.expect(sheet.get_by_role('link', name=re.compile(f'^{title}, Il y a '))).to_be_visible()
    pw.expect(sheet.get_by_text('À venir ensemble', exact=True)).to_be_visible()
    pw.expect(sheet.get_by_role('link', name='Soirée raclette chez Léa, Vous venez tous les deux')).to_be_visible()
    pw.expect(sheet.get_by_role('link', name='Paintball à Bulle, Léa vient · toi : peut-être')).to_be_visible()
    pw.expect(sheet.get_by_role('link', name='Groupe Les Copains du Jura')).to_be_visible()
    pw.expect(sheet.get_by_role('button', name='Signaler Léa')).to_be_visible()
    assert rpc_args(state, 'member_mini') == [{'target': LEA}]
    shot(page, 'mini-profil')
    frame.get_by_role('button', name='Agrandir le profil').click()
    shot(page, 'mini-profil-plein')
    sheet.get_by_test_id('mini-write').click()
    page.wait_for_function(f"document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/chats/{CHAT}')", timeout=10000)
    assert rpc_args(state, 'open_direct_chat') == [{'target': LEA}]
    assert not errors, errors


def test_the_mini_profile_says_why_one_cannot_write_and_closes(phone, events_origin):
    state = {'mini': mini(link='none', met=0)}
    page, frame, errors = start(phone, events_origin, state)
    sheet = open_lea(frame)
    pw.expect(sheet.get_by_test_id('mini-met')).to_have_text('Jamais rencontré')
    pw.expect(sheet.get_by_test_id('mini-write')).to_be_disabled()
    pw.expect(sheet.get_by_test_id('mini-why')).to_have_text('Tu ne peux pas écrire à Léa pour l’instant.')
    shot(page, 'mini-profil-impossible')
    # Bloquer se confirme en deux temps.
    sheet.get_by_role('button', name='Bloquer Léa').click()
    pw.expect(sheet.get_by_role('button', name='Confirmer le blocage de Léa')).to_be_visible()
    frame.get_by_role('button', name='Fermer', exact=True).click()
    pw.expect(frame.get_by_test_id('mini-profile')).to_have_count(0)
    assert not rpc_args(state, 'open_direct_chat')
    assert not errors, errors


def test_in_the_iphone_app_the_mini_profile_opens_the_native_conversation(phone, events_origin):
    state = {'mini': mini()}
    page, frame, errors = start(phone, events_origin, state, native=True)
    sheet = open_lea(frame)
    sheet.get_by_test_id('mini-write').click()
    page.wait_for_function('(window.__direct || []).length === 1')
    assert page.evaluate('window.__direct') == [LEA]
    assert not rpc_args(state, 'open_direct_chat')  # l'app ouvre elle-même la conversation native
    pw.expect(frame.get_by_test_id('mini-profile')).to_have_count(0)
    assert not errors, errors


def test_old_base_without_mini_profile_falls_back_to_the_full_card(phone, events_origin):
    state = {'mini': []}  # réponse inattendue (base d'avant) : la fiche complète, comme avant
    page, frame, errors = start(phone, events_origin, state)
    frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    frame.get_by_role('button', name='Profil de Léa').first.click()
    page.wait_for_function(f"document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/member/{LEA}')", timeout=10000)
    assert not errors, errors


def test_new_message_to_one_person_and_to_a_request(phone, events_origin):
    state = {}
    page, frame, errors = start(phone, events_origin, state)
    go(page, '/chats/new')
    pw.expect(frame.get_by_role('heading', name='Nouveau message')).to_be_visible(timeout=15000)
    pw.expect(frame.get_by_text('Croisés récemment', exact=True)).to_be_visible()
    pw.expect(frame.get_by_text('Dans tes groupes', exact=True)).to_be_visible()
    pw.expect(frame.get_by_role('checkbox', name='Sophie Berset, Coloc’ de la Cité')).to_be_visible()
    shot(page, 'nouveau-message-vide')
    # Chloé n'a qu'un lien faible : une demande de message.
    frame.get_by_role('checkbox', name='Chloé Borel, Raclette').click()
    pw.expect(frame.get_by_text('Ce sera une demande de message : Chloé choisit de l’accepter.', exact=True)).to_be_visible()
    pw.expect(frame.get_by_test_id('new-message-go')).to_have_text('Écrire à Chloé')
    frame.get_by_role('button', name='Retirer Chloé Borel').click()
    frame.get_by_role('checkbox', name='Léa Morel, Raclette').click()
    pw.expect(frame.get_by_test_id('new-message-go')).to_have_text('Écrire à Léa')
    frame.get_by_test_id('new-message-go').click()
    page.wait_for_function(f"document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/chats/{CHAT}')", timeout=10000)
    assert rpc_args(state, 'open_direct_chat') == [{'target': LEA}]
    assert not state['posts']  # sans soirée : aucun message envoyé à sa place
    assert not errors, errors


def test_search_finds_people_by_name_never_by_number(phone, events_origin):
    state = {}
    page, frame, errors = start(phone, events_origin, state)
    go(page, '/chats/new')
    field = frame.get_by_label('Ajouter quelqu’un')
    pw.expect(field).to_be_visible(timeout=15000)
    field.press_sequentially('Ke')
    results = frame.get_by_test_id('people-results')
    pw.expect(results.get_by_role('checkbox', name='Kevin Monnier, Basket du mardi')).to_be_visible()
    shot(page, 'nouveau-message-recherche')
    results.get_by_role('checkbox', name='Kevin Monnier, Basket du mardi').click()
    pw.expect(frame.get_by_role('button', name='Retirer Kevin Monnier')).to_be_visible()
    pw.expect(field).to_have_value('')
    assert {'q': 'Ke'} in rpc_args(state, 'chat_people_search')
    assert not errors, errors


def test_two_people_make_a_new_group_and_refused_ones_are_told(phone, events_origin):
    state = {'existing': None, 'refused': [NOE]}
    page, frame, errors = start(phone, events_origin, state)
    go(page, '/chats/new')
    frame.get_by_role('checkbox', name='Léa Morel, Raclette').click(timeout=15000)
    frame.get_by_role('checkbox', name='Noé Gaillard, Paintball').click()
    pw.expect(frame.get_by_text('2 personnes : ce sera un groupe', exact=True)).to_be_visible()
    pw.expect(frame.get_by_test_id('new-message-go')).to_have_text('Créer un groupe avec Léa et Noé')
    shot(page, 'nouveau-message-deux')
    frame.get_by_test_id('new-message-go').click()
    pw.expect(frame.get_by_role('heading', name='Nouveau groupe')).to_be_visible()
    assert rpc_args(state, 'chat_group_with') == [{'members': [LEA, NOE]}]
    pw.expect(frame.get_by_test_id('group-create')).to_be_disabled()
    frame.get_by_label('Nom du groupe', exact=True).fill('La bande du vendredi')
    frame.get_by_role('radio', name='Emoji 🪩').click()
    frame.get_by_role('radio', name='Rose').click()
    pw.expect(frame.get_by_test_id('group-cover')).to_contain_text('Toi, Léa et Noé')
    shot(page, 'nouveau-groupe')
    frame.get_by_test_id('group-create').click()
    pw.expect(frame.get_by_test_id('group-refused')).to_contain_text('Noé n’a pas reçu d’invitation : écris-lui d’abord')
    assert rpc_args(state, 'create_chat_group') == [{'name': 'La bande du vendredi', 'emoji': '🪩', 'color': 'pink', 'members': [LEA, NOE]}]
    frame.get_by_role('button', name='Ouvrir le groupe').click()
    page.wait_for_function(f"document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/chats/{GROUP}')", timeout=10000)
    assert not errors, errors


def test_the_same_people_open_their_existing_group(phone, events_origin):
    state = {'existing': GROUP}
    page, frame, errors = start(phone, events_origin, state)
    go(page, '/chats/new')
    frame.get_by_role('checkbox', name='Léa Morel, Raclette').click(timeout=15000)
    frame.get_by_role('checkbox', name='Anaïs Python, Anniv’ Bastien').click()
    frame.get_by_test_id('new-message-go').click()
    page.wait_for_function(f"document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/chats/{GROUP}')", timeout=10000)
    assert not rpc_args(state, 'create_chat_group')
    assert not errors, errors


def test_send_to_a_friend_joins_the_event_card_to_the_first_message(phone, events_origin):
    state = {}
    page, frame, errors = start(phone, events_origin, state)
    go(page, f'/chats/new?event={EVENT}')
    card = frame.get_by_test_id('new-message-event')
    pw.expect(card).to_contain_text('Sortie de démonstration (test local)', timeout=15000)
    pw.expect(card).to_contain_text('Jointe à ton message')
    frame.get_by_role('checkbox', name='Noé Gaillard, Paintball').click()
    shot(page, 'nouveau-message-soiree')
    frame.get_by_test_id('new-message-go').click()
    page.wait_for_function(f"document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/chats/{CHAT}')", timeout=10000)
    (table, row), = state['posts']
    assert table == 'direct_messages' and row['chat_id'] == CHAT and row['event_id'] == EVENT and row['body'] == ''
    assert not errors, errors


def test_the_member_card_sends_a_message_through_open_direct_chat(phone, events_origin):
    state = {'open': {'chat': None, 'status': 'none', 'reason': 'limit'}}
    page, frame, errors = start(phone, events_origin, state)
    page.route(REST + 'rpc/member_card', lambda r: r.fulfill(status=204 if r.request.method == 'OPTIONS' else 200, headers=HEADERS,
               content_type='application/json', body=json.dumps({'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'role': 'member',
                                                                 'root': False, 'me': False, 'first_name': None, 'last_name': None, 'phone': None, 'groups': []})))
    go(page, f'/member/{LEA}')
    frame.get_by_role('button', name='Envoyer un message').click(timeout=15000)
    pw.expect(frame.get_by_text('Tu as envoyé beaucoup de demandes de message. Réessaie demain.', exact=True)).to_be_visible()
    assert rpc_args(state, 'open_direct_chat') == [{'target': LEA}]
    assert not rpc_args(state, 'start_direct_chat')
    assert not errors, errors
