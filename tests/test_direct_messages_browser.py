"""Messages directs (décision de l'admin du 4.11), dans un vrai navigateur (module Événements, Supabase simulé) :
« Écrire » sur la fiche d'un membre ouvre la conversation à deux ; elle se mêle aux groupes dans Discussions, avec la
photo et le nom de la personne ; pas de suggestions @tout/@annonce ; infos : notifications de la conversation et
blocage ; interrupteur « Messages directs » dans Réglages › Notifications."""
import json
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_chats_browser import CORS, GROUP, LEA, SUPABASE, chat_services, phone  # noqa: F401 (fixtures)
from tests.test_events_browser import USER, browser, events_origin, login, pw  # noqa: F401 (fixtures)

DM = '6f1e7b62-9a2d-4d62-8b3c-3c2f9f5d1b01'


def direct_services(page):
    """Ajoute à la base simulée des discussions : une conversation directe avec Léa (vide au départ)."""
    state = chat_services(page)
    state.update(dm_messages=[], dm_posts=[], dm_rpc=[], prefs_patches=[], started=False)

    def handle(route):
        request = route.request
        url = urlparse(request.url)
        path, query = url.path, parse_qs(url.query)
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '')
        body = json.loads(request.post_data) if request.post_data else None
        result = None
        if path.endswith('/rpc/start_direct_chat'):
            state['started'] = True
            state['dm_rpc'].append(('start', body))
            result = DM
        elif path.endswith('/rpc/my_chats'):
            route.fallback()
            return
        elif path.endswith('/direct_chats'):
            wanted = (query.get('id') or [''])[0].removeprefix('eq.')
            row = {'id': DM, 'user_a': USER, 'user_b': LEA} if wanted == DM and state['started'] else None
            result = row if single else ([row] if row else [])
        elif path.endswith('/direct_messages') and request.method == 'POST':
            state['dm_posts'].append(body)
            state['dm_messages'].append({**body, 'user_id': USER, 'pinned': False, 'created_at': '2026-11-04T10:00:00Z',
                                         'edited_at': None, 'deleted_at': None})
        elif path.endswith('/direct_messages'):
            rows = [m for m in state['dm_messages'] if query.get('pinned') != ['eq.true'] or m['pinned']]
            result = sorted(rows, key=lambda m: m['created_at'], reverse=True)
        elif path.endswith('/rpc/direct_chat_people'):
            result = [{'id': USER, 'display_name': 'Compte de démonstration', 'avatar_url': None, 'member': True},
                      {'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'member': True}]
        elif path.endswith('/direct_chat_settings') or path.endswith('/direct_blocks') or path.endswith('/direct_message_reactions'):
            result = None if single else []
        elif path.endswith('/rpc/set_direct_chat_notify') or path.endswith('/rpc/set_direct_block') or path.endswith('/rpc/mark_direct_read'):
            state['dm_rpc'].append((path.rsplit('/', 1)[1], body))
        elif path.endswith('/rpc/member_card'):
            result = {'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'role': 'guest', 'root': False, 'me': False,
                      'first_name': None, 'last_name': None, 'phone': None, 'groups': ['Les amis']}
        elif path.endswith('/notification_prefs') and request.method == 'PATCH':
            state['prefs_patches'].append(body)
            return route.fallback()
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route(SUPABASE, handle)

    # Liste : les groupes de chat_services + la conversation directe dès qu'elle a un message.
    def chats(route):
        rows = [{'id': GROUP, 'name': 'Les amis', 'kind': 'group', 'system': False, 'member': True, 'admin': False, 'creator': False,
                 'members': 4, 'notify': 'mentions', 'unread': 0, 'last_at': '2026-11-03T10:00:00Z', 'last': 'Léa : Salut'}]
        if state['dm_messages']:
            rows.insert(0, {'id': DM, 'name': 'Léa', 'kind': 'direct', 'user_id': LEA, 'avatar_url': None, 'blocked': False,
                            'system': False, 'member': True, 'admin': False, 'creator': False, 'members': 2, 'notify': 'all',
                            'unread': 0, 'last_at': '2026-11-04T10:00:00Z', 'last': 'Toi : ' + state['dm_messages'][-1]['body']})
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(rows), headers=CORS)

    page.route('**/rest/v1/rpc/my_chats', chats)
    return state


def signed_in(page, events_origin, path):
    """Module Événements ouvert seul (comme l'app iPhone le charge), connecté, puis à la page voulue."""
    page.goto(events_origin + '/events/', wait_until='domcontentloaded')
    login(page)
    page.wait_for_timeout(500)
    page.goto(f'{events_origin}/events{path}', wait_until='domcontentloaded')


def test_write_from_a_member_card_opens_a_private_conversation_listed_with_the_groups(phone, events_origin):
    page, errors = phone
    state = direct_services(page)
    signed_in(page, events_origin, f'/member/{LEA}')
    page.get_by_role('button', name='💬 Écrire').click(timeout=15000)
    field = page.get_by_label('Message', exact=True)
    pw.expect(field).to_be_visible(timeout=15000)
    assert ('start', {'target': LEA}) in state['dm_rpc']
    pw.expect(field).to_have_attribute('placeholder', 'Message…')
    field.press_sequentially('Salut @')
    pw.expect(page.get_by_label('Suggestions de citation')).to_have_count(0)  # ni @surnom, ni @tout, ni @annonce à deux
    field.fill('Tu viens samedi ?')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(page.get_by_text('Tu viens samedi ?', exact=True)).to_be_visible()
    sent = state['dm_posts'][-1]
    assert sent['chat_id'] == DM and sent['body'] == 'Tu viens samedi ?' and 'mentions' not in sent and 'mention_all' not in sent

    page.get_by_role('button', name='Infos de la conversation').click()
    pw.expect(page.get_by_role('button', name='Voir la fiche')).to_be_visible()
    page.get_by_role('switch', name='Nouveaux messages').click()
    page.get_by_role('button', name='Bloquer Léa').click()
    page.get_by_role('button', name='Confirmer le blocage').click()
    page.wait_for_timeout(500)
    assert ('set_direct_chat_notify', {'chat': DM, 'level': 'none'}) in state['dm_rpc']
    assert ('set_direct_block', {'target': LEA, 'blocked': True}) in state['dm_rpc']

    page.goto(f'{events_origin}/events/chats', wait_until='domcontentloaded')
    pw.expect(page.get_by_role('button', name='Message direct Léa')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='Discussion Les amis')).to_be_visible()
    pw.expect(page.get_by_text('Toi : Tu viens samedi ?')).to_be_visible()
    assert not errors, errors


def test_direct_messages_have_their_own_notification_switch(phone, events_origin):
    page, errors = phone
    state = direct_services(page)
    signed_in(page, events_origin, '/settings/notifications')
    switch = page.get_by_role('switch', name='Messages directs')
    pw.expect(switch).to_be_visible(timeout=15000)
    switch.click()
    page.wait_for_timeout(500)
    assert {'direct_messages': False} in state['prefs_patches']
    assert not errors, errors
