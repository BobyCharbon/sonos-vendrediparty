"""Discussions v2 — la conversation web « Néon club » (contrat §2, §6, §8 ; maquette 1-neon/4-conversation), dans un vrai
navigateur (module Événements, Supabase simulé, aucune donnée réelle) :
- en-tête photo + nom (toucher : mini-profil), plus aucun bouton « … » à côté des bulles : menu à l'appui long / clic droit ;
- carte de soirée dans une bulle (« Je viens », Voir), « Vu » sur mon dernier message, Modifier (15 min, « modifié ») ;
- « écrit… » : signal en direct sur le canal `typing:direct:<id>` (envoyé et reçu), jamais dans une demande ;
- demande de message : « X veut t'écrire » + Accepter / Supprimer / Bloquer / Signaler chez le destinataire, « Demande
  envoyée » et saisie fermée après le premier message chez l'expéditeur ;
- Répondre en privé depuis un groupe (open_direct_chat + citation) ; Signaler avec « Joindre les 10 messages précédents » ;
- « Envoyer à un ami » sur la fiche d'un événement (page web, ou PartyNative.chat.newMessage dans l'app iPhone).
Captures : scratchpad/discussions/apres/w3/ (PARTY_SHOTS_W3 pour un autre dossier)."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tests.test_chats_browser import CORS, GROUP, LEA, SUPABASE, chat_services, phone  # noqa: F401 (fixtures)
from tests.test_direct_messages_browser import signed_in
from tests.test_events_browser import EVENT, USER, browser, events_origin, pw  # noqa: F401 (fixtures)
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401 (fixture)

DM = '6f1e7b62-9a2d-4d62-8b3c-3c2f9f5d1b01'
SHOTS = Path(os.environ.get('PARTY_SHOTS_W3') or
             '/private/tmp/claude-502/-Users-ludovictrombert-sonos-vendrediparty/2593be6d-12b9-4238-a528-30280e4e74a6/scratchpad/discussions/apres/w3')


def iso(delta):
    return (datetime.now(timezone.utc) + delta).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def dm(i, user, body, at, **extra):
    return {'id': f'd0000000-0000-4000-8000-00000000000{i}', 'chat_id': DM, 'user_id': user, 'body': body, 'photo_path': None,
            'reply_to': None, 'pinned': False, 'created_at': at, 'edited_at': None, 'deleted_at': None, 'audio_path': None,
            'audio_seconds': None, 'event_id': None, 'quote': None, **extra}


def maquette_messages():
    """La conversation de la maquette 4 : soirée raclette chez Léa, citation, réaction, vocal, « Vu »."""
    return [
        dm(0, LEA, '', iso(timedelta(days=-1, hours=-3)), event_card={'title': 'Apéro annulé', 'start': '2030-11-15T17:00:00Z', 'place': 'Vevey'}),
        dm(1, LEA, 'Hello ! Tu viens vendredi ? 🧀', iso(timedelta(days=-1, hours=-2))),
        dm(2, LEA, '', iso(timedelta(days=-1, hours=-2, minutes=1)), event_id=EVENT),
        dm(3, LEA, 'Du pain et des cornichons si tu peux…', iso(timedelta(hours=-3))),
        dm(4, USER, 'Ok pour le pain ! 🥖', iso(timedelta(hours=-2)), reply_to='d0000000-0000-4000-8000-000000000003'),
        dm(5, LEA, '', iso(timedelta(minutes=-20)), audio_path=f'{DM}/vocal.m4a', audio_seconds=38),
        dm(6, USER, 'Trop beau 😍 À vendredi !', iso(timedelta(minutes=-2))),
    ]


def conversation_services(page, status='active', requested_by=None, messages=None, seen=None, link='direct'):
    """Base simulée : groupes (chat_services) + une conversation directe avec Léa et les fonctions de Discussions v2."""
    state = chat_services(page)
    state.update(dm_messages=list(messages or []), dm_posts=[], calls=[], broadcasts=[], rsvps=[],
                 status=status, requested_by=requested_by)
    card = {'id': EVENT, 'title': 'Soirée raclette chez Léa', 'start': '2030-11-22T18:30:00Z', 'place': 'Lausanne, Chailly',
            'cover': None, 'going': 8, 'mine': None}

    def handle(route):
        request = route.request
        url = urlparse(request.url)
        path, query = url.path, parse_qs(url.query)
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '')
        body = json.loads(request.post_data) if request.post_data else None
        name = path.rsplit('/', 1)[1]
        result = None
        if path.endswith('/realtime/v1/api/broadcast'):
            state['broadcasts'].append(body)
            return route.fulfill(status=202, headers=CORS, body='')
        if path.endswith('/direct_chats'):
            row = {'id': DM, 'user_a': USER, 'user_b': LEA, 'status': state['status'], 'requested_by': state['requested_by'],
                   'requested_at': None, 'declined_at': None}
            wanted = (query.get('id') or [''])[0].removeprefix('eq.')
            result = (row if single else [row]) if wanted == DM else (None if single else [])
        elif path.endswith('/direct_messages') and request.method == 'POST':
            state['dm_posts'].append(body)
            state['dm_messages'].append({**dm(9, USER, '', iso(timedelta())), **body, 'user_id': USER})
        elif path.endswith('/direct_messages'):
            rows = [m for m in state['dm_messages'] if query.get('pinned') != ['eq.true'] or m['pinned']]
            result = sorted(rows, key=lambda m: m['created_at'], reverse=True)
        elif path.endswith('/direct_message_reactions') and request.method == 'GET':
            result = [{'message_id': 'd0000000-0000-4000-8000-000000000004', 'user_id': LEA, 'emoji': '❤️'}]
        elif path.endswith('/rpc/direct_chat_people'):
            result = [{'id': USER, 'display_name': 'Compte de démonstration', 'avatar_url': None, 'member': True},
                      {'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'member': True}]
        elif path.endswith('/direct_chat_settings') or path.endswith('/direct_blocks'):
            result = None if single else []
        elif name == 'direct_seen':
            result = seen
        elif name == 'chat_link':
            result = link
        elif name == 'chat_badge':
            result = 5
        elif name == 'chat_event_cards':
            state['calls'].append((name, body))
            result = [card] if EVENT in body['ids'] else []
        elif name == 'open_direct_chat':
            state['calls'].append((name, body))
            result = {'chat': DM, 'status': 'active', 'reason': None}
        elif name in ('accept_message_request', 'decline_message_request', 'set_direct_block', 'mark_direct_read', 'edit_direct_message',
                      'report_content', 'member_mini'):
            state['calls'].append((name, body))
            if name == 'accept_message_request':
                state['status'] = 'active'
            result = {'id': LEA, 'name': 'Léa', 'nickname': 'Léa', 'photo': None, 'link': 'direct'} if name == 'member_mini' else None
        elif name == 'take_group_join_note':
            result = None
        elif name == 'my_terms':
            result = {'version': '2026-11-18', 'accepted': True, 'accepted_at': None, 'contact_email': None, 'enforced': True}
        elif path.endswith('/rsvps') and request.method == 'POST':
            state['rsvps'].append(body)
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route(SUPABASE, handle)
    return state


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / f'{name}.png'))


def open_dm(page, events_origin, path=f'/chats/{DM}', again=False):
    if again:  # déjà connecté : la page seule
        page.goto(f'{events_origin}/events{path}', wait_until='domcontentloaded')
    else:
        signed_in(page, events_origin, path)
    pw.expect(page.get_by_role('button', name='Léa. Ouvrir son profil')).to_be_visible(timeout=15000)


def test_direct_conversation_neon_card_seen_edit_menu_and_typing(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, messages=maquette_messages(), seen=iso(timedelta(minutes=-1)))
    open_dm(page, events_origin)
    pw.expect(page.get_by_text('Trop beau 😍 À vendredi !', exact=True)).to_be_visible()
    # Plus de « … » à côté de chaque bulle (audit §4, 9).
    pw.expect(page.get_by_role('button', name='Actions du message')).to_have_count(0)
    # Carte de la soirée dans la bulle, « Vu » sur mon dernier message, citation, retour avec les non lus.
    pw.expect(page.get_by_text('Soirée raclette chez Léa', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('8 présents', exact=True)).to_be_visible()
    # Soirée supprimée : la copie gardée dans le message (event_card), sans « Je viens » ni Voir.
    pw.expect(page.get_by_text('Apéro annulé', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('Cette soirée a été retirée.', exact=True)).to_be_visible()
    pw.expect(page.get_by_role('button', name='Voir la soirée Apéro annulé')).to_have_count(0)
    pw.expect(page.get_by_text('· Vu', exact=False)).to_have_count(1)
    pw.expect(page.get_by_role('button', name='Réponse à Léa : Du pain et des cornichons si tu peux…')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Retour aux Discussions, 5 non lus')).to_be_visible()
    shot(page, '4-conversation')
    assert ('mark_direct_read', {'chat': DM}) in state['calls']  # conversation acceptée : lue

    # « Je viens » sur la carte : réponse Présent.
    page.get_by_role('button', name='Répondre : je viens').click()
    page.wait_for_timeout(600)
    assert state['rsvps'] and state['rsvps'][-1]['status'] == 'yes' and state['rsvps'][-1]['event_id'] == EVENT

    # « écrit… » : un signal sur typing:direct:<id> (jamais écrit en base).
    field = page.get_by_label('Message', exact=True)
    field.press_sequentially('Je prends')
    page.wait_for_timeout(800)
    sent = [m for b in state['broadcasts'] for m in b.get('messages', [])]
    assert any(m['topic'] == f'typing:direct:{DM}' and m['event'] == 'typing' and m['payload']['user'] == USER for m in sent), state['broadcasts']
    field.fill('')

    # Menu à l'appui long / clic droit : sur le message de Léa (pas de « Répondre en privé » à deux).
    page.get_by_text('Hello ! Tu viens vendredi ? 🧀', exact=True).click(button='right')
    menu = page.get_by_role('menu')
    pw.expect(menu.get_by_role('button', name='Répondre', exact=True)).to_be_visible()
    pw.expect(menu.get_by_role('button', name='Signaler')).to_be_visible()
    pw.expect(menu.get_by_role('button', name='Répondre en privé')).to_have_count(0)
    pw.expect(page.get_by_role('button', name='Réagir 🔥')).to_be_visible()
    shot(page, '4b-menu')
    page.get_by_role('button', name='Signaler').click()
    # Signaler : « Joindre les 10 messages précédents », décochée par défaut.
    context = page.get_by_role('checkbox', name='Joindre les 10 messages précédents')
    pw.expect(context).not_to_be_checked()
    context.click()
    page.get_by_role('radio', name='Harcèlement').click()
    page.get_by_role('button', name='Envoyer').last.click()
    pw.expect(page.get_by_text('Merci, c’est envoyé')).to_be_visible()
    report = [b for n, b in state['calls'] if n == 'report_content'][-1]
    assert report['p_kind'] == 'direct_message' and report['p_target'] == 'd0000000-0000-4000-8000-000000000001' and report['p_context'] is True
    page.get_by_role('button', name='Fermer', exact=True).click()

    # Modifier mon message récent (moins de 15 min) : le texte revient dans la barre, la base reçoit la nouvelle version.
    page.get_by_text('Trop beau 😍 À vendredi !', exact=True).click(button='right')
    page.get_by_role('button', name='Modifier').click()
    pw.expect(field).to_have_value('Trop beau 😍 À vendredi !')
    pw.expect(page.get_by_text('Modifier le message', exact=True)).to_be_visible()
    field.fill('Trop beau 😍 À vendredi soir !')
    page.get_by_role('button', name='Enregistrer la modification').click()
    page.wait_for_timeout(600)
    assert ('edit_direct_message', {'msg': 'd0000000-0000-4000-8000-000000000006', 'new_body': 'Trop beau 😍 À vendredi soir !'}) in state['calls']
    # Un vieux message ne se modifie plus.
    page.get_by_text('Ok pour le pain ! 🥖', exact=True).click(button='right')
    pw.expect(page.get_by_role('button', name='Supprimer')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Modifier')).to_have_count(0)
    page.get_by_role('button', name='Fermer le menu').click()
    pw.expect(page.get_by_role('button', name='Fermer le menu')).to_have_count(0)
    # Au clavier (lecteur d'écran) : Entrée sur la bulle ouvre le même menu.
    page.get_by_text('Hello ! Tu viens vendredi ? 🧀', exact=True).locator('xpath=ancestor::*[@tabindex="0"][1]').focus()
    page.keyboard.press('Enter')
    pw.expect(page.get_by_role('button', name='Réagir 👍')).to_be_visible()
    page.keyboard.press('Escape')
    pw.expect(page.get_by_role('button', name='Réagir 👍')).to_have_count(0)

    # Infos de la conversation (néon) : profil, notifications, bloquer, signaler.
    page.get_by_role('button', name='Infos de la conversation').click()
    pw.expect(page.get_by_role('button', name='Signaler Léa')).to_be_visible()
    shot(page, '4i-infos')
    page.get_by_role('button', name='Infos de la conversation').click()

    # Nom ou photo de l'en-tête : le mini-profil de Léa (fiche en repli).
    page.get_by_role('button', name='Léa. Ouvrir son profil').click()
    page.wait_for_timeout(800)
    assert ('member_mini', {'target': LEA}) in state['calls'] or page.url.endswith(f'/member/{LEA}')
    assert not errors, errors


def test_someone_typing_shows_in_the_header_and_the_thread(phone, events_origin):
    """Le signal d'en face (canal typing:direct:<id>) : « écrit… » dans l'en-tête et trois points dans le fil."""
    page, errors = phone
    conversation_services(page, messages=maquette_messages()[:1])
    sockets = []

    def realtime(ws):
        def on_message(raw):
            msg = json.loads(raw)
            array = isinstance(msg, list)
            topic, event, ref, join_ref = (msg[2], msg[3], msg[1], msg[0]) if array else (msg['topic'], msg['event'], msg.get('ref'), msg.get('join_ref'))
            if event == 'phx_join' and topic.startswith('realtime:typing:'):
                reply = {'status': 'ok', 'response': {}}
                ws.send(json.dumps([join_ref, ref, topic, 'phx_reply', reply] if array else
                                   {'topic': topic, 'event': 'phx_reply', 'payload': reply, 'ref': ref, 'join_ref': join_ref}))
                sockets.append((ws, topic, array, join_ref))
        ws.on_message(on_message)
    page.route_web_socket('wss://gsuetixzobooggeaubvb.supabase.co/**', realtime)
    open_dm(page, events_origin)
    for _ in range(50):
        if sockets:
            break
        page.wait_for_timeout(100)
    ws, topic, array, join_ref = sockets[-1]
    assert topic == f'realtime:typing:direct:{DM}'
    payload = {'type': 'broadcast', 'event': 'typing', 'payload': {'user': LEA, 'name': 'Léa'}}
    ws.send(json.dumps([join_ref, None, topic, 'broadcast', payload] if array else {'topic': topic, 'event': 'broadcast', 'payload': payload, 'ref': None}))
    pw.expect(page.get_by_text('écrit…', exact=True).first).to_be_visible(timeout=5000)
    shot(page, '4c-ecrit')
    # Sans nouveau signal, « écrit… » s'efface au bout de 4 s.
    pw.expect(page.get_by_text('écrit…', exact=True)).to_have_count(0, timeout=8000)
    assert not errors, errors


def test_incoming_request_banner_accept_and_no_read_receipt(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, status='request', requested_by=LEA,
                                  messages=[dm(1, LEA, 'Salut ! On s’est croisés à la raclette, tu as le numéro du DJ ?', iso(timedelta(minutes=-30)))])
    open_dm(page, events_origin)
    pw.expect(page.get_by_role('heading', name='Léa veut t’écrire')).to_be_visible()
    # Saisie fermée tant que la demande n'est pas acceptée ; pas de « lu » envoyé.
    pw.expect(page.get_by_label('Message', exact=True)).to_have_count(0)
    pw.expect(page.get_by_text('Accepte la demande pour répondre à Léa.')).to_be_visible()
    for label in ('Supprimer la demande', 'Bloquer Léa', 'Signaler'):
        pw.expect(page.get_by_role('button', name=label, exact=True)).to_be_visible()
    shot(page, '4d-demande-recue')
    assert not [c for c in state['calls'] if c[0] == 'mark_direct_read']
    page.get_by_role('button', name='Accepter', exact=True).click()
    pw.expect(page.get_by_label('Message', exact=True)).to_be_visible(timeout=10000)
    assert ('accept_message_request', {'chat': DM}) in state['calls']
    assert not errors, errors


def test_incoming_request_can_be_deleted_or_blocked(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, status='request', requested_by=LEA, messages=[dm(1, LEA, 'Coucou', iso(timedelta(minutes=-5)))])
    open_dm(page, events_origin)
    page.get_by_role('button', name='Bloquer Léa', exact=True).click()
    page.get_by_role('button', name='Confirmer le blocage').click()
    page.wait_for_url('**/events/chats', timeout=10000)
    assert ('set_direct_block', {'target': LEA, 'blocked': True}) in state['calls']
    open_dm(page, events_origin, again=True)
    page.get_by_role('button', name='Supprimer la demande').click()
    page.wait_for_url('**/events/chats', timeout=10000)
    assert ('decline_message_request', {'chat': DM}) in state['calls']
    assert not errors, errors


def test_outgoing_request_is_one_text_message_then_the_composer_closes(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, status='request', requested_by=USER, messages=[], link='request')
    open_dm(page, events_origin)
    pw.expect(page.get_by_role('heading', name='Demande envoyée')).to_be_visible()
    pw.expect(page.get_by_text('Ce sera une demande de message', exact=False)).to_be_visible()
    # Texte seul : ni photo, ni vocal.
    pw.expect(page.get_by_role('button', name='Envoyer une photo')).to_have_count(0)
    pw.expect(page.get_by_role('button', name='Enregistrer un message vocal')).to_have_count(0)
    field = page.get_by_label('Message', exact=True)
    field.fill('Salut Léa, c’est Camille de la raclette !')
    shot(page, '4e-demande-a-envoyer')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(page.get_by_text('Demande envoyée · tu pourras écrire à nouveau quand elle sera acceptée.')).to_be_visible(timeout=10000)
    pw.expect(field).to_have_count(0)
    assert state['dm_posts'][-1]['body'] == 'Salut Léa, c’est Camille de la raclette !'
    # Jamais d'« écrit… » dans une demande.
    assert not state['broadcasts']
    shot(page, '4f-demande-envoyee')
    assert not errors, errors


def test_reply_privately_from_a_group_quotes_the_message_in_the_direct_chat(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, messages=[])
    signed_in(page, events_origin, f'/chats/{GROUP}')
    pw.expect(page.get_by_text('Salut tout le monde', exact=True)).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='Actions du message')).to_have_count(0)
    shot(page, '4g-groupe')
    page.get_by_text('Salut tout le monde', exact=True).click(button='right')
    page.get_by_role('button', name='Répondre en privé').click()
    pw.expect(page.get_by_role('button', name='Léa. Ouvrir son profil')).to_be_visible(timeout=15000)
    assert ('open_direct_chat', {'target': LEA}) in state['calls']
    pw.expect(page.get_by_text('Réponse privée · Léa dans Les amis', exact=True)).to_be_visible()
    # La discussion du groupe reste derrière dans la pile : la barre de saisie visible est la dernière.
    page.get_by_label('Message', exact=True).last.fill('Je t’envoie ça en privé')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    page.wait_for_timeout(800)
    post = state['dm_posts'][-1]
    assert post['quote'] == {'from': 'group', 'title': 'Les amis', 'author': 'Léa', 'excerpt': 'Salut tout le monde'}, post
    pw.expect(page.get_by_text('Je t’envoie ça en privé', exact=True)).to_be_visible()
    shot(page, '4h-reponse-privee')
    assert not errors, errors


def test_send_to_a_friend_from_an_event_attaches_its_card(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, messages=[])
    signed_in(page, events_origin, f'/event/{EVENT}')
    page.get_by_role('button', name='Envoyer à un ami').click(timeout=15000)
    page.wait_for_url(f'**/events/chats/new?event={EVENT}', timeout=10000)
    # Nouveau message (écran de W2) puis la conversation : /chats/<id>?event=<id> joint la carte au message.
    open_dm(page, events_origin, f'/chats/{DM}?event={EVENT}', again=True)
    pw.expect(page.get_by_role('button', name='Retirer la soirée du message')).to_be_visible()
    pw.expect(page.get_by_text('Soirée raclette chez Léa', exact=True)).to_be_visible()
    page.get_by_role('button', name='Envoyer', exact=True).click()  # la carte seule suffit
    page.wait_for_timeout(800)
    assert state['dm_posts'][-1]['event_id'] == EVENT and state['dm_posts'][-1]['body'] == ''
    assert not errors, errors


def test_inside_the_iphone_app_send_to_a_friend_opens_the_native_new_message(phone, events_origin):
    page, errors = phone
    page.add_init_script("window.__new = []; window.PartyNative = { chat: { openEvent: () => {}, newMessage: (o) => window.__new.push(o) } };")
    conversation_services(page, messages=[])
    signed_in(page, events_origin, f'/event/{EVENT}')
    page.get_by_role('button', name='Envoyer à un ami').click(timeout=15000)
    page.wait_for_function('window.__new.length > 0', timeout=10000)
    assert page.evaluate('window.__new') == [{'event_id': EVENT}]
    assert not errors, errors


def test_an_event_chat_is_marked_read_in_the_list_state(browser, v2_origin):  # noqa: F811
    """Discussions v2 : l'état « lu » d'une discussion de soirée passe par mark_event_chat_read (chat_list_state)."""
    from tests.test_c2_acces_browser import SUPA, VICTOR, chat_routes, message, mock_terms, new_page, open_chat
    from tests.test_event_chat_browser import chat_state
    from tests.test_events_browser import mock_services
    ctx, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=False)
        chat_routes(page, [message(1, VICTOR, 'Coucou')])
        reads = []
        page.route(f'{SUPA}/rest/v1/rpc/mark_event_chat_read', lambda r: (reads.append(r.request.post_data), r.fulfill(
            status=200, content_type='application/json', headers=CORS, body='null')) if r.request.method != 'OPTIONS'
            else r.fulfill(status=204, headers=CORS))
        open_chat(page, v2_origin)
        pw.expect(page.get_by_text('Coucou', exact=True)).to_be_visible(timeout=15000)
        for _ in range(40):
            if reads:
                break
            page.wait_for_timeout(100)
        assert reads and json.loads(reads[-1]) == {'e': EVENT}
    finally:
        ctx.close()
