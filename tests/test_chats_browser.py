"""Discussions (site, module Événements) — avis de l'admin du 3 novembre 2026 et ses réponses, dans un vrai navigateur :
créer un groupe depuis Discussions, suggestions de l'@ (membres filtrés en direct, @tout selon le groupe), @annonce des
admins et organisateurs épinglée en surbrillance en haut et retirée d'un appui long, rôle Organisateur, choix @tout,
réglage « Annonces et @tout des groupes ». Supabase est simulé (aucune donnée réelle)."""
import json
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_events_browser import USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

GROUP = '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a01'
NEW_GROUP = '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a02'
LEA, LEON, TOM = ('7a1c2b3d-0000-4000-8000-00000000000' + str(i) for i in (1, 2, 3))
SUPABASE = 'https://gsuetixzobooggeaubvb.supabase.co/**'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile'}


def message(mid, user, body, at, **extra):
    return {'id': mid, 'group_id': GROUP, 'user_id': user, 'body': body, 'photo_path': None, 'reply_to': None, 'mentions': [],
            'mention_all': False, 'pinned': False, 'announcement': False, 'created_at': at, 'edited_at': None, 'deleted_at': None,
            'deleted_by_admin': False, 'audio_path': None, 'audio_seconds': None, **extra}


def chat_services(page, admin=False, organizer=False, everyone='all'):
    """Base simulée des discussions ; state garde les messages et groupes écrits par la page."""
    mock_services(page)
    state = {'admin': admin, 'organizers': [USER] if organizer else [], 'everyone': everyone, 'broadcasts': True, 'groups': {GROUP: 'Les amis'}, 'members': {GROUP: [USER, LEA, LEON, TOM]}, 'posts': [], 'rpc': [],
             'messages': [message('a0000000-0000-4000-8000-000000000001', LEA, 'Salut tout le monde', '2026-11-03T10:00:00Z'),
                          message('a0000000-0000-4000-8000-000000000002', TOM, '@annonce Soirée samedi 20h chez Léa',
                                  '2026-11-03T10:01:00Z', pinned=True, announcement=True)]}
    names = {USER: 'Compte de démonstration', LEA: 'Léa', LEON: 'Léon', TOM: 'Tom'}

    def group_of(query):
        return (query.get('group_id') or query.get('id') or ['eq.' + GROUP])[0].removeprefix('eq.')

    def handle(route):
        request = route.request
        url = urlparse(request.url)
        path, query = url.path, parse_qs(url.query)
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '')
        body = json.loads(request.post_data) if request.post_data else None
        result = None
        if path.endswith('/rpc/my_chats'):
            result = [{'id': g, 'name': n, 'system': False, 'member': USER in state['members'][g], 'admin': state['admin'],
                       'creator': False, 'members': len(state['members'][g]), 'notify': 'mentions', 'unread': 0,
                       'last_at': None, 'last': None} for g, n in state['groups'].items()]
        elif path.endswith('/member_groups') and request.method == 'POST':
            state['groups'][NEW_GROUP] = body['name']
            state['members'][NEW_GROUP] = []
            state['posts'].append(('group', body))
            result = {'id': NEW_GROUP} if single else [{'id': NEW_GROUP}]
        elif path.endswith('/member_groups'):
            g = group_of(query)
            result = {'id': g, 'name': state['groups'][g], 'created_by': USER if g == NEW_GROUP else TOM, 'everyone_tag': state['everyone'],
                      'member_group_members': [{'user_id': u} for u in state['members'][g]]}
        elif path.endswith('/member_group_members') and request.method == 'POST':
            state['members'][body['group_id']].append(body['user_id'])
            state['posts'].append(('member', body))
        elif path.endswith('/group_messages') and request.method == 'POST':
            state['posts'].append(('message', body))
            staff = state['admin'] or USER in state['organizers']
            announced = staff and '@annonce' in body['body'].lower()
            state['messages'].append(message(body['id'], USER, body['body'], '2026-11-03T10:05:00Z', mentions=body['mentions'],
                                             mention_all=body['mention_all'], pinned=announced, announcement=announced))
        elif path.endswith('/group_messages'):
            g = group_of(query)
            rows = [m for m in state['messages'] if m['group_id'] == g]
            if query.get('pinned') == ['eq.true']:
                rows = [m for m in rows if m['pinned'] and not m['deleted_at']]
            result = sorted(rows, key=lambda m: m['created_at'], reverse=True)
        elif path.endswith('/rpc/group_chat_people'):
            g = body['grp']
            result = [{'id': u, 'display_name': names[u], 'avatar_url': None, 'member': True} for u in state['members'][g]]
        elif path.endswith('/rpc/pin_group_message'):
            state['rpc'].append(('pin', body))
            for m in state['messages']:
                if m['id'] == body['msg']:
                    m.update(pinned=body['pin'], announcement=m['announcement'] and body['pin'])
        elif path.endswith('/group_organizers'):
            result = [{'user_id': u} for u in state['organizers']]
        elif path.endswith('/rpc/set_group_organizer') or path.endswith('/rpc/set_group_everyone_tag'):
            state['rpc'].append((path.rsplit('/', 1)[1], body))
            if 'everyone' in path:
                state['everyone'] = body['who']
            elif body['organizer']:
                state['organizers'].append(body['member'])
            else:
                state['organizers'].remove(body['member'])
        elif path.endswith('/notification_prefs') and request.method == 'PATCH':
            state['rpc'].append(('prefs', body))
            state['broadcasts'] = body.get('group_broadcasts', state['broadcasts'])
        elif path.endswith('/notification_prefs'):
            prefs = {'user_id': USER, 'push_enabled': True, 'quiet_start': None, 'quiet_end': None, 'new_event': 'all',
                     'event_changed': True, 'poll_new': True, 'poll_nudge': True, 'date_fixed': True, 'waitlist': True,
                     'proposals': True, 'rsvp_mine': True, 'chat': 'mentions', 'reminders': ['2h'], 'muted_until': None,
                     'chats_muted_until': None, 'group_broadcasts': state['broadcasts']}
            result = prefs if single else [prefs]
        elif path.endswith('/rpc/mark_group_read') or path.endswith('/rpc/group_chat_phones'):
            result = [] if path.endswith('phones') else None
        elif path.endswith('/group_admins') or path.endswith('/group_message_reactions'):
            result = []
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route(SUPABASE, handle)
    # Compte Party lié : l'onglet Discussions s'affiche (comptes connectés seulement).
    page.route('**/api/account/link', lambda route: route.fulfill(content_type='application/json', body=json.dumps(
        {'guest_id': 'acct-test', 'name': 'Compte de démonstration', 'photo': None, 'beta': True})))
    return state


def open_chats(page, events_origin, admin=False, **options):
    state = chat_services(page, admin, **options)
    page.goto(events_origin, wait_until='domcontentloaded')
    page.locator('#accountTab').click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_role('button', name='Mon profil : Compte de démonstration')).to_be_visible(timeout=15000)
    page.locator('#tabs [data-tab="chats"]').click()
    pw.expect(frame.get_by_role('button', name='Discussion Les amis')).to_be_visible(timeout=15000)
    return frame, state


@pytest.fixture
def phone(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    yield page, errors
    context.close()


def test_new_group_from_discussions_includes_me_and_opens_its_chat(phone, events_origin):
    page, errors = phone
    frame, state = open_chats(page, events_origin)
    frame.get_by_role('button', name='Nouveau groupe', exact=True).first.click()
    frame.get_by_label('Nom du groupe', exact=True).fill('Apéro du jeudi')
    frame.get_by_role('button', name='Créer', exact=True).click()
    # Même création que Réglages › Groupes, avec moi dedans d'office, puis la discussion du nouveau groupe s'ouvre.
    pw.expect(frame.get_by_text('Aucun message pour l’instant. Lance la discussion !')).to_be_visible(timeout=15000)
    pw.expect(frame.get_by_role('button', name='Ajouter des membres')).to_be_visible()
    assert ('group', {'name': 'Apéro du jeudi', 'created_by': USER}) in state['posts']
    assert ('member', {'group_id': NEW_GROUP, 'user_id': USER}) in state['posts']
    pw.expect(frame.get_by_label('Message', exact=True)).to_be_visible()
    assert not errors, errors


def test_at_sign_suggests_group_members_as_you_type_and_everyone(phone, events_origin):
    page, errors = phone
    frame, state = open_chats(page, events_origin)
    frame.get_by_role('button', name='Discussion Les amis').click()
    field = frame.get_by_label('Message', exact=True)
    pw.expect(field).to_be_visible(timeout=15000)
    field.press_sequentially('Salut @')
    menu = frame.get_by_label('Suggestions de citation')
    pw.expect(menu.get_by_role('menuitem', name='Citer Léa')).to_be_visible()
    pw.expect(menu.get_by_role('menuitem', name='Citer Tom')).to_be_visible()
    pw.expect(menu.get_by_role('menuitem', name='@tout : Tout le groupe')).to_be_visible()
    pw.expect(menu.get_by_role('menuitem', name='Citer Compte de démonstration')).to_have_count(0)  # pas moi
    pw.expect(menu.get_by_role('menuitem', name='@annonce : Annonce épinglée en haut du groupe')).to_have_count(0)  # pas organisateur
    field.press_sequentially('le')  # sans accents ni casse : « le » trouve Léa et Léon, plus Tom
    pw.expect(menu.get_by_role('menuitem', name='Citer Léa')).to_be_visible()
    pw.expect(menu.get_by_role('menuitem', name='Citer Léon')).to_be_visible()
    pw.expect(menu.get_by_role('menuitem', name='Citer Tom')).to_have_count(0)
    menu.get_by_role('menuitem', name='Citer Léon').click()
    pw.expect(field).to_have_value('Salut @Léon ')
    pw.expect(frame.get_by_label('Suggestions de citation')).to_have_count(0)
    field.press_sequentially('et @to')
    frame.get_by_role('menuitem', name='@tout : Tout le groupe').click()
    pw.expect(field).to_have_value('Salut @Léon et @tout ')
    frame.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(frame.get_by_text('Salut @Léon et @tout', exact=True)).to_be_visible()
    sent = next(b for kind, b in state['posts'] if kind == 'message')
    # Citation enregistrée comme avant (identifiant du membre) ; @tout : tous les membres par défaut dans ce groupe.
    assert sent['mentions'] == [LEON] and sent['mention_all'] is True
    assert not errors, errors


def test_announcement_is_highlighted_on_top_and_an_admin_removes_it_with_a_long_press(phone, events_origin):
    page, errors = phone
    frame, state = open_chats(page, events_origin, admin=True)
    frame.get_by_role('button', name='Discussion Les amis').click()
    banner = frame.get_by_role('button', name='Annonce : Tom, @annonce Soirée samedi 20h chez Léa')
    pw.expect(banner).to_be_visible(timeout=15000)
    assert frame.get_by_text('📣 Annonce').first.is_visible()
    banner.click(delay=900)  # appui long
    frame.get_by_role('button', name='Retirer l’annonce').click()
    pw.expect(banner).to_have_count(0)
    assert ('pin', {'msg': 'a0000000-0000-4000-8000-000000000002', 'pin': False}) in state['rpc']
    # Un membre annonce à son tour : sa bulle s'affiche en annonce aussitôt, la base l'épingle.
    field = frame.get_by_label('Message', exact=True)
    field.fill('@annonce Apportez des chips')
    frame.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(frame.get_by_role('button', name='Annonce : Compte de démonstration, @annonce Apportez des chips')).to_be_visible()
    assert not errors, errors


def test_a_simple_member_sees_the_announcement_cannot_remove_it_and_is_told_before_announcing(phone, events_origin):
    page, errors = phone
    frame, state = open_chats(page, events_origin, admin=False)
    frame.get_by_role('button', name='Discussion Les amis').click()
    banner = frame.get_by_role('button', name='Annonce : Tom, @annonce Soirée samedi 20h chez Léa')
    pw.expect(banner).to_be_visible(timeout=15000)
    banner.click(delay=900)
    pw.expect(frame.get_by_role('button', name='Retirer l’annonce')).to_have_count(0)
    field = frame.get_by_label('Message', exact=True)
    field.fill('@annonce moi aussi')
    pw.expect(frame.get_by_text('ton message partira comme un message normal', exact=False)).to_be_visible()
    frame.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(frame.get_by_text('@annonce moi aussi', exact=True)).to_be_visible()
    pw.expect(frame.get_by_role('button', name='Annonce : Compte de démonstration, @annonce moi aussi')).to_have_count(0)
    assert not errors, errors


def test_an_organizer_announces_and_removes_announcements(phone, events_origin):
    page, errors = phone
    frame, state = open_chats(page, events_origin, organizer=True)
    frame.get_by_role('button', name='Discussion Les amis').click()
    field = frame.get_by_label('Message', exact=True)
    pw.expect(field).to_be_visible(timeout=15000)
    field.press_sequentially('@ann')
    frame.get_by_role('menuitem', name='@annonce : Annonce épinglée en haut du groupe').click()
    pw.expect(field).to_have_value('@annonce ')
    banner = frame.get_by_role('button', name='Annonce : Tom, @annonce Soirée samedi 20h chez Léa')
    banner.click(delay=900)
    frame.get_by_role('button', name='Retirer l’annonce').click()
    pw.expect(banner).to_have_count(0)
    assert ('pin', {'msg': 'a0000000-0000-4000-8000-000000000002', 'pin': False}) in state['rpc']
    assert not errors, errors


def test_everyone_tag_reserved_by_the_group_hides_it_and_warns(phone, events_origin):
    page, errors = phone
    frame, _ = open_chats(page, events_origin, everyone='staff')
    frame.get_by_role('button', name='Discussion Les amis').click()
    field = frame.get_by_label('Message', exact=True)
    pw.expect(field).to_be_visible(timeout=15000)
    field.press_sequentially('@to')
    pw.expect(frame.get_by_role('menuitem', name='Citer Tom')).to_be_visible()
    pw.expect(frame.get_by_role('menuitem', name='@tout : Tout le groupe')).to_have_count(0)
    field.press_sequentially('ut ')
    pw.expect(frame.get_by_text('seuls les admins et organisateurs peuvent écrire @tout', exact=False)).to_be_visible()
    assert not errors, errors


def test_group_admin_names_an_organizer_and_chooses_who_writes_everyone(phone, events_origin):
    page, errors = phone
    frame, state = open_chats(page, events_origin, admin=True)
    frame.get_by_role('button', name='Discussion Les amis').click()
    frame.get_by_role('button', name='Infos du groupe').click()
    pw.expect(frame.get_by_text('@tout dans ce groupe', exact=True)).to_be_visible(timeout=15000)
    frame.get_by_text('Admins et organisateurs', exact=True).click()
    frame.get_by_label('Organisateur', exact=True).first.click()
    page.wait_for_timeout(500)
    assert ('set_group_everyone_tag', {'grp': GROUP, 'who': 'staff'}) in state['rpc']
    assert any(k == 'set_group_organizer' and b['organizer'] is True for k, b in state['rpc'])
    assert not errors, errors


def test_settings_turn_off_group_announcements_and_everyone_notifications(phone, events_origin):
    """Règle de l'admin : toute nouvelle forme de notification se coupe dans Réglages."""
    page, errors = phone
    frame, state = open_chats(page, events_origin)
    page.locator('#accountTab').click()
    frame.get_by_text('Notifications', exact=True).click()
    toggle = frame.get_by_label('Annonces et @tout des groupes', exact=False)
    pw.expect(toggle.first).to_be_visible(timeout=15000)
    toggle.first.click()
    page.wait_for_timeout(500)
    assert ('prefs', {'group_broadcasts': False}) in state['rpc']
    assert not errors, errors
