"""Annonces d'événement aux groupes (décision de l'admin du 06.11.2026), module Événements dans un vrai navigateur
(Supabase simulé, personne de réel n'est prévenu) :
- étape 2 de « Créer avec l'IA » : « Prévenir le groupe » éteint par défaut, seulement pour un groupe, phrase claire
  (demande à l'admin du groupe, envoi d'office après 48 h) ; allumé, la publication l'enregistre ;
- formulaire : l'interrupteur suit l'audience (absent pour un événement public) ;
- Activité › « À valider » : aperçu de l'événement et du message, Accepter ; la seconde réponse dit qui a répondu ;
- fiche : « Annonce en attente » pour l'organisateur ;
- Réglages › Notifications : les trois interrupteurs ; Réglages › Groupes : les deux réglages du créateur.
Captures (390 px) dans $ANNONCES_SHOTS si la variable est définie."""
import json
import os
import re
from pathlib import Path

import pytest

from tests.test_ai_event_steps_browser import SKI, draft_event, member_without_vip, open_step_two
from tests.test_events_browser import DIST, EVENT, USER, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import CORS, mock_invites, v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
BASE = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1'
SHOTS = Path(os.environ['ANNONCES_SHOTS']) if os.environ.get('ANNONCES_SHOTS') else None
REQUEST = {'kind': 'announce', 'id': 'aaaaaaaa-0000-4000-8000-000000000001', 'event_id': EVENT, 'group_id': SKI, 'group': 'Ski',
           'title': 'Raclette au chalet', 'starts_at': '2030-11-14T18:00:00Z', 'all_day': False, 'date_mode': 'fixed',
           'location_name': 'Chalet', 'cover_url': None, 'description': 'Chacun amène une salade.', 'organizer': 'Olga',
           'requested_at': '2030-11-01T10:00:00Z', 'auto_at': '2030-11-03T10:00:00Z', 'members': 7,
           'message_title': '🔒 Invitation à un événement privé', 'message_body': 'On t’invite à « Raclette au chalet » avec le groupe Ski.'}


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


def rpc(page, name: str, answer, calls: list | None = None):
    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if calls is not None:
            calls.append((name, json.loads(route.request.post_data or 'null')))
        body = answer(calls) if callable(answer) else answer
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    page.route(f'{BASE}/rpc/{name}*', handle)


def new_page(browser):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    return context, page, errors


def test_step_two_switch_is_off_by_default_explains_the_request_and_is_saved(browser, v2_origin):  # noqa: F811
    context, page, errors = new_page(browser)
    try:
        mock_services(page)
        mock_invites(page)
        writes = draft_event(page)
        member_without_vip(page)
        rpc(page, 'my_announce_modes', {SKI: 'request'})
        open_step_two(page, v2_origin, 'audience=public')
        pw.expect(page.get_by_role('switch', name=re.compile('^Prévenir'))).to_have_count(0)  # public, sur invitation : jamais
        page.get_by_role('button', name='👥 Un groupe').click()
        # Lot C1 (campagne 2) : le nom lu par VoiceOver dit QUEL groupe est prévenu.
        switch = page.get_by_role('switch', name='Prévenir « Ski »', exact=True)
        pw.expect(switch).to_be_visible(timeout=5000)
        pw.expect(switch).not_to_be_checked()
        pw.expect(page.get_by_text('Le groupe voit l’événement dans Party, sans notification.', exact=True)).to_be_visible()
        switch.click()
        pw.expect(page.get_by_text('Ta demande sera envoyée à l’admin du groupe ; sans réponse sous 48 h, l’annonce part automatiquement.',
                                   exact=True)).to_be_visible()
        shot(page, '01-etape2-prevenir-le-groupe')
        page.get_by_role('button', name='Publier pour « Ski »').click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        # Lot C1 : l'annonce part avec le statut, en dernier (un échec en route ne prévient personne).
        visibility = writes.index(('PATCH', 'events', {'visibility': 'invited', 'public_link': False}))
        assert visibility < writes.index(('PATCH', 'events', {'status': 'published', 'announce_group': True})), writes
        assert not errors, errors
    finally:
        context.close()


def test_validator_sees_the_request_with_the_message_and_accepts_first(browser, v2_origin):  # noqa: F811
    context, page, errors = new_page(browser)
    try:
        mock_services(page)
        calls: list = []
        rpc(page, 'my_group_requests', lambda c: [] if any(n == 'answer_announcement' for n, _ in c) else [REQUEST], calls)
        rpc(page, 'answer_announcement', {'status': 'accepted', 'already': False}, calls)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/activity', wait_until='domcontentloaded')
        card = page.get_by_label('Annonce à valider : Raclette au chalet, pour Ski')
        pw.expect(card).to_be_visible(timeout=15000)
        pw.expect(card.get_by_text('On t’invite à « Raclette au chalet » avec le groupe Ski.', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Notification envoyée aux 7 membres :', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Sans réponse, l’annonce part d’office', exact=False)).to_be_visible()
        shot(page, '02-activite-a-valider')
        card.get_by_role('button', name='Accepter').click()
        pw.expect(page.get_by_text('C’est parti : Ski est prévenu.', exact=True)).to_be_visible(timeout=10000)
        assert ('answer_announcement', {'a': REQUEST['id'], 'accept': True}) in calls
        assert not errors, errors
    finally:
        context.close()


def test_a_late_answer_says_who_answered_first(browser, v2_origin):  # noqa: F811
    context, page, _ = new_page(browser)
    try:
        mock_services(page)
        rpc(page, 'my_group_requests', [REQUEST])
        rpc(page, 'answer_announcement', {'status': 'accepted', 'already': True, 'answered_by': 'Bot Côme'})
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/activity', wait_until='domcontentloaded')
        page.get_by_role('button', name='Refuser').click()
        pw.expect(page.get_by_text('Bot Côme a déjà répondu : rien n’a changé.', exact=True)).to_be_visible(timeout=10000)
    finally:
        context.close()


def test_organizer_sees_the_announcement_waiting_on_the_event(browser, v2_origin):  # noqa: F811
    context, page, errors = new_page(browser)
    try:
        mock_services(page)
        mock_invites(page)
        event = {'id': EVENT, 'title': 'Raclette au chalet', 'description': '', 'created_by': USER, 'status': 'published',
                 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'all_day': False, 'visibility': 'invited',
                 'public_link': False, 'announce_group': True, 'location_name': 'Chalet', 'category': None, 'event_tags': [],
                 'date_options': [], 'rsvps': [], 'event_organizers': [], 'polls': [], 'bring_items': [], 'event_groups': [{'group_id': SKI}],
                 'author': {'display_name': 'Compte de démonstration'}, 'show_participants': True, 'allow_maybe': True,
                 'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None, 'rsvp_deadline': None, 'forum_enabled': True,
                 'price_chf': None, 'tickets_enabled': False, 'created_at': '2030-11-01T10:00:00Z', 'updated_at': '2030-11-01T10:00:00Z'}
        page.route(f'{BASE}/events*', lambda r: r.fulfill(status=204, headers=CORS) if r.request.method == 'OPTIONS' else r.fulfill(
            status=200, content_type='application/json', headers=CORS, body=json.dumps(event if 'id=' in r.request.url else [event])))
        rpc(page, 'event_announcement_status', [{'group': 'Ski', 'status': 'pending', 'answered_by': None, 'auto_at': '2030-11-03T10:00:00Z'}])
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/event/{EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Annonce au groupe', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Ski · Annonce en attente', exact=False)).to_be_visible()
        shot(page, '03-fiche-annonce-en-attente')
        assert not errors, errors
    finally:
        context.close()


def test_the_three_switches_are_in_the_notification_settings(browser, v2_origin):  # noqa: F811
    context, page, _ = new_page(browser)
    try:
        mock_services(page)
        prefs = {'user_id': USER, 'push_enabled': True, 'quiet_start': None, 'quiet_end': None, 'new_event': 'all', 'event_changed': True,
                 'poll_new': True, 'date_fixed': True, 'poll_nudge': True, 'waitlist': True, 'proposals': True, 'rsvp_mine': True,
                 'chat': 'mentions', 'reminders': ['1d'], 'announce_requests': True, 'announce_results': True, 'group_event_requests': True}
        patches: list = []

        def handle(route):
            if route.request.method == 'OPTIONS':
                return route.fulfill(status=204, headers=CORS)
            if route.request.method == 'PATCH':
                patches.append(json.loads(route.request.post_data))
            route.fulfill(status=200, content_type='application/json', headers=CORS,
                          body=json.dumps(prefs if 'vnd.pgrst.object' in (route.request.headers.get('accept') or '') else [prefs]))
        page.route(f'{BASE}/notification_prefs*', handle)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/settings/notifications', wait_until='domcontentloaded')
        for label in ('Annonce à valider', 'Événement à valider pour mon groupe', 'Réponse du groupe à mes demandes'):
            pw.expect(page.get_by_role('switch', name=label)).to_be_visible(timeout=15000)
        page.get_by_role('switch', name='Annonce à valider').click()
        page.wait_for_timeout(1000)
        assert any(p.get('announce_requests') is False for p in patches), patches
    finally:
        context.close()


def test_the_group_creator_sets_both_rules(browser, v2_origin):  # noqa: F811
    context, page, _ = new_page(browser)
    try:
        mock_services(page)
        group = {'id': SKI, 'name': 'Ski', 'created_by': USER, 'system_key': None, 'events_need_approval': False, 'announce_mode': 'request',
                 'member_group_members': [{'user_id': USER}]}
        page.route(f'{BASE}/member_groups*', lambda r: r.fulfill(status=204, headers=CORS) if r.request.method == 'OPTIONS' else r.fulfill(
            status=200, content_type='application/json', headers=CORS, body=json.dumps([group])))
        calls: list = []
        rpc(page, 'set_group_event_rules', None, calls)
        rpc(page, 'my_privacy', {'phone_groups': []})
        rpc(page, 'my_group_invitations', [])
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/groups?open={SKI}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Les membres créent des événements pour le groupe', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Notifications des événements', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Sans réponse sous 48 h, l’annonce part automatiquement.', exact=False)).to_be_visible()
        shot(page, '04-groupe-reglages')
        page.get_by_text('Avec validation', exact=True).click()
        page.wait_for_timeout(800)
        assert ('set_group_event_rules', {'grp': SKI, 'need_approval': True, 'mode': 'request'}) in calls, calls
    finally:
        context.close()
