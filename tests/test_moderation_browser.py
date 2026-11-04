"""Modération commune (4.11, Apple 1.2 / Google UGC) dans un vrai navigateur (module Événements, Supabase simulé) :
conditions d'utilisation demandées avant le premier message, « Signaler » un message avec raison et commentaire,
refus du filtre affiché tel quel, bloquer depuis la fiche, Personnes bloquées dans Réglages › Confidentialité,
fiche réduite d'un membre qui m'a bloqué, écran admin Signalements, page des conditions."""
import json
from urllib.parse import urlparse

import pytest

from tests.test_chats_browser import CORS, GROUP, LEA, chat_services, phone  # noqa: F401 (fixtures)
from tests.test_direct_messages_browser import signed_in
from tests.test_events_browser import browser, events_origin, pw  # noqa: F401 (fixtures)

REPORT = 'c0000000-0000-4000-8000-000000000001'


def moderation_services(page, accepted=False, refuse=None, restricted=False, moderator=False):
    """Base simulée : discussions (chat_services) + modération ; state garde les appels."""
    state = chat_services(page)
    state.update(mod=[], accepted=accepted, blocks=[{'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'at': '2026-11-04T10:00:00Z'}],
                 queue=[{'id': REPORT, 'kind': 'group_message', 'target_id': 'm1', 'reason': 'harassment', 'comment': 'insultes',
                         'snapshot': {'text': "t'es un •••••••", 'place': 'Les amis'}, 'status': 'open', 'resolution': None,
                         'note': None, 'created_at': '2026-11-04T10:00:00Z', 'handled_at': None, 'handled_by': None,
                         'reporter': {'id': 'x', 'name': 'Tom'},
                         'target_user': {'id': LEA, 'name': 'Léa', 'avatar_url': None, 'status': 'active', 'role': 'guest'},
                         'same_target': 1, 'user_reports': 2, 'sanctions': []}])

    def handle(route):
        request = route.request
        path = urlparse(request.url).path
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        body = json.loads(request.post_data) if request.post_data else None
        name = path.rsplit('/', 1)[1]
        status, result = 200, None
        if name in ('report_content', 'accept_terms', 'set_block', 'moderation_act', 'set_moderation_settings'):
            state['mod'].append((name, body))
        if name == 'my_permissions' and moderator:  # modérateur (droit « Modérer les signalements » + bannir)
            result = ['events.view', 'events.rsvp', 'chat.write', 'moderation.reports', 'members.ban']
        elif name == 'my_permissions':
            return route.fallback()
        elif name == 'my_terms':
            result = {'version': '2026-11-04', 'accepted': state['accepted'], 'accepted_at': None, 'contact_email': None, 'enforced': False}
        elif name == 'accept_terms':
            state['accepted'] = True
            result = {'version': '2026-11-04', 'accepted': True, 'accepted_at': '2026-11-04T10:00:00Z', 'contact_email': None, 'enforced': False}
        elif name == 'report_content':
            result = REPORT
        elif name == 'my_blocks':
            result = state['blocks']
        elif name == 'set_block':
            state['blocks'] = [b for b in state['blocks'] if b['id'] != body['target']] + (
                [{'id': body['target'], 'display_name': 'Léa', 'avatar_url': None, 'at': '2026-11-04T10:00:00Z'}] if body['blocked'] else [])
        elif name == 'moderation_queue':
            result = state['queue'] if body['p_status'] in ('open', 'all') else []
        elif name == 'moderation_act':
            state['queue'] = []
            result = {'id': REPORT, 'status': 'actioned'}
        elif name == 'moderation_public_info':
            result = {'terms_version': '2026-11-04', 'contact_email': 'contact@exemple.ch', 'terms_enforced': False}
        elif name == 'set_moderation_settings':
            result = {'terms_version': '2026-11-04', 'contact_email': body['p_contact_email'] or None, 'terms_enforced': False}
        elif name == 'member_card':
            result = {'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'role': 'guest', 'root': False, 'me': False,
                      'first_name': None, 'last_name': None, 'phone': None, 'groups': [] if restricted else ['Les amis'],
                      'restricted': restricted, 'blocked': any(b['id'] == LEA for b in state['blocks'])}
        else:
            return route.fallback()
        route.fulfill(status=status, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route('**/rest/v1/rpc/**', handle)

    if refuse:
        def refuse_post(route):
            if route.request.method == 'OPTIONS':
                return route.fulfill(status=204, headers=CORS)
            if route.request.method != 'POST':
                return route.fallback()
            route.fulfill(status=400, content_type='application/json', headers=CORS,
                          body=json.dumps({'code': '23514', 'message': 'content_refused: ' + refuse}))
        page.route('**/rest/v1/group_messages', refuse_post)
    return state


def open_group(page, events_origin):
    signed_in(page, events_origin, f'/chats/{GROUP}')
    field = page.get_by_label('Message', exact=True)
    pw.expect(field).to_be_visible(timeout=15000)
    return field


def test_terms_are_asked_before_the_first_message_then_the_message_leaves(phone, events_origin):
    page, errors = phone
    state = moderation_services(page, accepted=False)
    field = open_group(page, events_origin)
    field.fill('Premier message')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(page.get_by_text('Avant de publier')).to_be_visible()
    assert not [p for p in state['posts'] if p[0] == 'message']  # rien n'est parti
    page.get_by_role('button', name='J’accepte').click()
    pw.expect(page.get_by_text('Premier message', exact=True)).to_be_visible()
    assert ('accept_terms', {'p_version': '2026-11-04'}) in state['mod']
    for _ in range(40):  # la bulle s'affiche avant la fin de l'envoi
        if [p for p in state['posts'] if p[0] == 'message']:
            break
        page.wait_for_timeout(100)
    assert [p for p in state['posts'] if p[0] == 'message'][-1][1]['body'] == 'Premier message'
    assert not errors, errors


def test_a_refused_message_says_why(phone, events_origin):
    page, errors = phone
    moderation_services(page, accepted=True, refuse='Message non envoyé : il contient des propos haineux. Les règles de Party l\'interdisent.')
    field = open_group(page, events_origin)
    field.fill('texte refusé')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(page.get_by_text('Message non envoyé : il contient des propos haineux.', exact=False)).to_be_visible()
    pw.expect(field).to_have_value('texte refusé')  # le texte revient pour être corrigé
    assert not errors, errors


def test_report_a_message_with_a_reason_and_a_comment(phone, events_origin):
    page, errors = phone
    state = moderation_services(page, accepted=True)
    open_group(page, events_origin)
    page.get_by_role('button', name='Actions du message').first.click()
    page.get_by_role('button', name='Signaler').click()
    send = page.get_by_role('button', name='Envoyer').last
    pw.expect(send).to_be_disabled()  # une raison d'abord
    page.get_by_role('radio', name='Harcèlement').click()
    page.get_by_label('Commentaire').fill('il insiste')
    send.click()
    pw.expect(page.get_by_text('Merci, c’est envoyé')).to_be_visible()
    kind, body = state['mod'][-1]
    assert kind == 'report_content' and body['p_kind'] == 'group_message' and body['p_reason'] == 'harassment'
    assert body['p_comment'] == 'il insiste' and body['p_target'] == 'a0000000-0000-4000-8000-000000000001'
    assert not errors, errors


def test_block_and_report_from_a_member_card(phone, events_origin):
    page, errors = phone
    state = moderation_services(page, accepted=True)
    state['blocks'] = []
    signed_in(page, events_origin, f'/member/{LEA}')
    page.get_by_role('button', name='Bloquer Léa').click(timeout=15000)
    page.get_by_role('button', name='Confirmer le blocage').click()
    pw.expect(page.get_by_role('button', name='Débloquer Léa')).to_be_visible()
    assert ('set_block', {'target': LEA, 'blocked': True}) in state['mod']
    pw.expect(page.get_by_role('button', name='💬 Écrire')).to_have_count(0)  # bloquée : plus de message direct
    page.get_by_role('button', name='Signaler le profil').click()
    page.get_by_role('radio', name='Spam').click()
    page.get_by_role('button', name='Envoyer').last.click()
    pw.expect(page.get_by_text('Merci, c’est envoyé')).to_be_visible()
    assert state['mod'][-1][1]['p_kind'] == 'profile'
    assert not errors, errors


def test_a_member_who_blocked_me_shows_only_a_nickname(phone, events_origin):
    page, errors = phone
    moderation_services(page, accepted=True, restricted=True)
    signed_in(page, events_origin, f'/member/{LEA}')
    pw.expect(page.get_by_text('Léa').first).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='💬 Écrire')).to_have_count(0)
    pw.expect(page.get_by_text('Groupes en commun')).to_have_count(0)
    assert not errors, errors


def test_blocked_people_list_unblocks_in_privacy_settings(phone, events_origin):
    page, errors = phone
    state = moderation_services(page, accepted=False)
    signed_in(page, events_origin, '/settings/privacy')
    pw.expect(page.get_by_text('Léa', exact=True)).to_be_visible(timeout=15000)
    page.get_by_role('button', name='Débloquer').click()
    pw.expect(page.get_by_text('Personne n’est bloqué.')).to_be_visible()
    assert ('set_block', {'target': LEA, 'blocked': False}) in state['mod']
    page.get_by_role('button', name='J’accepte les conditions').click()
    pw.expect(page.get_by_text('Acceptées', exact=False)).to_be_visible()
    page.get_by_role('button', name='Lire les conditions').click()
    pw.expect(page.get_by_text('Le jeu n’a aucune valeur en argent')).to_be_visible()
    pw.expect(page.get_by_text('contact@exemple.ch', exact=False).first).to_be_visible()
    assert not errors, errors


def test_moderators_handle_the_report_queue(phone, events_origin):
    page, errors = phone
    state = moderation_services(page, accepted=True, moderator=True)
    signed_in(page, events_origin, '/admin/reports')
    pw.expect(page.get_by_text("t'es un •••••••")).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('Signalé par Tom : « insultes »')).to_be_visible()
    page.get_by_label('Note (envoyée avec l’avertissement)').fill('Reste correct')
    page.get_by_role('button', name='Avertir').click()
    pw.expect(page.get_by_text('Aucun signalement à traiter. 🎉')).to_be_visible()
    assert ('moderation_act', {'p_report': REPORT, 'p_action': 'warn', 'p_note': 'Reste correct', 'p_days': None}) in state['mod']
    page.get_by_label('Adresse de contact publiée').fill('contact@exemple.ch')
    page.get_by_role('button', name='Enregistrer l’adresse').click()
    pw.expect(page.get_by_text('Enregistré.')).to_be_visible()
    assert not errors, errors
