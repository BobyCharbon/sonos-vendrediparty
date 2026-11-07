"""« Créer avec l'IA » en deux étapes (demandes de l'admin, 06.11), module web dans un vrai navigateur (Supabase simulé,
personne de réel n'est prévenu) : l'app iPhone enregistre le brouillon puis ouvre l'étape 2 « Qui est invité »
(/events/event/<id>/invite?suggested=…). Un toucher sur « qui voit » PUBLIE (ou envoie pour validation) :
- sur invitation : la feuille « Inviter » s'ouvre avec le lien prêt, la personne citée à l'IA cochée ;
- un groupe ou les Membres : la fiche, « ＋ Inviter d'autres personnes » en avant ; public : la fiche ;
- sans le droit de publier : envoyé pour validation, le lien arrive après ; invitations v2 éteintes : carte du lien.
Captures (390 px) dans $AI_STEPS_SHOTS si la variable est définie."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import CORS, IDS, mock_invites, v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SHOTS = Path(os.environ['AI_STEPS_SHOTS']) if os.environ.get('AI_STEPS_SHOTS') else None
TOM = IDS[1]
PEOPLE = [{'id': TOM, 'display_name': 'Tom', 'role': 'member'}, {'id': IDS[2], 'display_name': 'Léa', 'role': 'member'}]
EMPTY_LIST = {'vip': False, 'public': False, 'vip_name': 'Vendredi Party', 'groups': [], 'people': [], 'links': []}


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


def draft_event(page, ai_suggested=None) -> list:
    """L'événement que l'IA vient d'enregistrer : un brouillon public + lien (le défaut, en attendant l'étape 2), sans
    invité. Garde les écritures."""
    writes = []
    event = {'id': EVENT, 'title': 'Raclette chez Camille', 'description': 'Chacun amène une salade.', 'created_by': USER, 'status': 'draft',
             'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'all_day': False, 'visibility': 'all',
             'public_link': True, 'location_name': 'Chez Camille', 'location_address': 'Chemin des Vignes 4, 1095 Lutry',
             'category': None, 'event_tags': [], 'date_options': [], 'rsvps': [], 'event_organizers': [], 'polls': [], 'bring_items': [],
             'event_groups': [], 'event_invites': [], 'event_phone_invites': [], 'author': {'display_name': 'Compte de démonstration'},
             'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': True, 'max_plus_ones': 10, 'max_participants': None,
             'rsvp_deadline': None, 'forum_enabled': True, 'price_chf': None, 'tickets_enabled': False}
    if ai_suggested is not None:
        event['ai_suggested'] = ai_suggested

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        path = urlparse(request.url).path
        if request.method in ('PATCH', 'POST', 'DELETE'):
            body = json.loads(request.post_data or 'null')
            writes.append((request.method, path.rsplit('/', 1)[-1], body))
            if path.endswith('/events') and isinstance(body, dict):
                event.update(body)
            return route.fulfill(status=204, headers=CORS)
        single = 'id' in parse_qs(urlparse(request.url).query)
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(event if single else [event]))
    for table in ('events', 'event_groups', 'event_invites', 'event_phone_invites'):
        page.route(f'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/{table}*', handle)
    return writes


VIP_GROUP = 'cccccccc-0000-4000-8000-000000000001'
SKI = 'cccccccc-0000-4000-8000-000000000002'
FOOT = 'cccccccc-0000-4000-8000-000000000003'


def member_without_vip(page):
    """Compte Membre (pas admin) hors du groupe Vendredi Party, dans « Ski » mais pas dans « Foot » (qu'il a créé)."""
    groups = [{'id': VIP_GROUP, 'name': 'Vendredi Party', 'created_by': None, 'system_key': 'vip', 'member_group_members': [{'user_id': TOM}]},
              {'id': SKI, 'name': 'Ski', 'created_by': TOM, 'system_key': None, 'member_group_members': [{'user_id': USER}, {'user_id': TOM}]},
              {'id': FOOT, 'name': 'Foot', 'created_by': USER, 'system_key': None, 'member_group_members': [{'user_id': TOM}]}]
    perms = ['events.view', 'events.rsvp', 'events.create', 'events.publish_direct', 'chat.write']
    reply = lambda body: lambda route: route.fulfill(status=204, headers=CORS) if route.request.method == 'OPTIONS' else \
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/member_groups*', reply(groups))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/my_permissions*', reply(perms))


def open_step_two(page, origin, query=f'suggested={TOM},pas-un-id'):
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}/invite?{query}', wait_until='domcontentloaded')
    pw.expect(page.get_by_role('progressbar', name='Étape 2 sur 3 : Qui est invité')).to_be_visible(timeout=15000)


def test_v2_invitation_only_publishes_in_one_touch_then_the_link_is_ready_to_share(browser, v2_origin):  # noqa: F811
    """Retour de l'admin (06.11) : « Sur invitation » publie tout de suite, puis la feuille « Inviter » s'ouvre avec le
    LIEN PRÊT (Partager, WhatsApp, Messages, QR), la personne citée à l'IA cochée. Jamais de lien « après publication »."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        calls = mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page)
        open_step_two(page, v2_origin)
        pw.expect(page.get_by_text('Un toucher le publie', exact=False)).to_be_visible()
        pw.expect(page.get_by_text('Il arrive dès la publication', exact=False)).to_have_count(0)
        shot(page, '02-web-qui-voit-un-toucher-v2')
        page.get_by_role('button', name='✉️ Sur invitation seulement : Publier et envoyer le lien').click()
        sheet = page.get_by_label('Inviter à Raclette chez Camille')
        pw.expect(sheet.get_by_text('C’est en ligne : envoie le lien à tes invités', exact=True)).to_be_visible(timeout=10000)
        pw.expect(sheet.get_by_role('button', name='Partager le lien…')).to_be_visible()
        for how in ('WhatsApp', 'Messages', 'QR code'):
            pw.expect(sheet.get_by_role('button', name=how, exact=True)).to_be_visible()
        pw.expect(sheet.get_by_role('button', name='Retirer Tom')).to_be_visible(timeout=5000)  # cité à l'IA, coché
        assert not [c for c in calls if c[0] == 'invite_people']  # jamais invité sans son « Inviter »
        visibility = writes.index(('PATCH', 'events', {'visibility': 'invited', 'public_link': False}))
        assert visibility < writes.index(('PATCH', 'events', {'status': 'published', 'announce_group': False}))
        # Lot C1 (campagne 2) : l'annonce part seulement avec le statut, en dernier (un échec en route n'annonce rien).
        assert all('status' in w[2] for w in writes if w[0] == 'PATCH' and isinstance(w[2], dict) and 'announce_group' in w[2])
        assert 'invite=link' in page.url
        shot(page, '03-web-lien-pret-v2')
        sheet.get_by_role('button', name='WhatsApp', exact=True).click()
        pw.expect(sheet.get_by_text('✓ Lien prêt', exact=False)).to_be_visible(timeout=5000)
        assert any(c[0] == 'create_event_invite' for c in calls)
        assert not errors, errors
    finally:
        context.close()


def test_v2_members_publish_in_one_touch_then_the_guest_card_offers_to_invite_more(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page)
        open_step_two(page, v2_origin)
        page.get_by_role('button', name='👥 Membres Vendredi Party : Publier pour les Membres Vendredi Party').click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_role('button', name='＋ Inviter d’autres personnes')).to_be_visible()
        pw.expect(page.get_by_label('Inviter à Raclette chez Camille')).to_have_count(0)  # la fiche, pas la feuille
        assert ('PATCH', 'events', {'visibility': 'all', 'public_link': False}) in writes
        assert ('PATCH', 'events', {'status': 'published', 'announce_group': False}) in writes
        shot(page, '03-web-membres-fiche-v2')
    finally:
        context.close()


def test_a_group_is_chosen_then_published_for_it(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        member_without_vip(page)
        mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page)
        open_step_two(page, v2_origin)
        page.get_by_role('button', name='👥 Un groupe', exact=True).click()
        assert not [w for w in writes if w[0] == 'PATCH' and isinstance(w[2], dict) and 'status' in w[2]]  # choisir le groupe d'abord
        page.get_by_role('button', name='Publier pour « Ski »').click()
        pw.expect(page.get_by_role('button', name='＋ Inviter d’autres personnes')).to_be_visible(timeout=10000)
        assert ('POST', 'event_groups', [{'event_id': EVENT, 'group_id': SKI}]) in writes
        assert ('PATCH', 'events', {'status': 'published', 'announce_group': False}) in writes
    finally:
        context.close()


def test_without_the_right_to_publish_invitation_only_is_sent_for_validation_and_says_when_the_link_comes(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        mock_invites(page, guest_list=EMPTY_LIST)
        perms = ['events.view', 'events.rsvp', 'events.create', 'chat.write']  # pas « publier sans validation »
        page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/my_permissions*', lambda route: route.fulfill(
            status=204, headers=CORS) if route.request.method == 'OPTIONS' else route.fulfill(
            status=200, content_type='application/json', headers=CORS, body=json.dumps(perms)))
        writes = draft_event(page)
        open_step_two(page, v2_origin)
        pw.expect(page.get_by_text('Un toucher l’envoie pour validation', exact=False)).to_be_visible()
        page.get_by_role('button', name='✉️ Sur invitation seulement : Envoyer pour validation').click()
        pw.expect(page.get_by_text('Envoyé pour validation', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('Le lien à partager à tes invités sera disponible dès la validation.', exact=False)).to_be_visible()
        assert ('PATCH', 'events', {'status': 'pending', 'announce_group': False}) in writes
        pw.expect(page.get_by_role('button', name='Partager le lien…')).to_have_count(0)
    finally:
        context.close()


def test_back_from_step_two_opens_the_draft_event_not_the_home_page(browser, events_origin):  # noqa: F811
    """Retour de l'admin (07.11) : le retour de l'étape 2 menait à l'accueil, il fallait deviner que l'événement était
    dans les brouillons. Il ouvre la fiche du brouillon, rien n'est publié."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin)
        pw.expect(page.get_by_role('button', name='Retour : Événements', exact=True)).to_have_count(0)
        page.get_by_role('button', name='Retour : L’événement', exact=True).click()
        page.wait_for_url(f'**/events/event/{EVENT}', timeout=10000)
        pw.expect(page.get_by_role('progressbar', name='Étape 2 sur 3 : Qui est invité')).to_have_count(0)
        assert not [w for w in writes if w[0] == 'PATCH' and w[1] == 'events' and 'status' in w[2]]
        shot(page, '07-retour-etape-2-fiche')
    finally:
        context.close()


def test_invitations_off_public_publishes_in_one_touch_and_invites_nobody(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin)
        pw.expect(page.get_by_role('button', name='Ouvrir l’événement (finir à la main)')).to_be_visible()
        page.get_by_role('button', name='🌍 Public + lien public : Publier').click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        assert not [w for w in writes if w[1] == 'event_invites' and w[0] == 'POST']
        assert ('PATCH', 'events', {'visibility': 'all', 'public_link': True}) in writes
        assert ('PATCH', 'events', {'status': 'published', 'announce_group': False}) in writes
        assert not errors, errors
    finally:
        context.close()


def test_invitations_off_invitation_only_opens_the_event_with_its_link_card_first(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin, f'audience=invite&suggested={TOM}')  # « j'invite seulement Tom » dit à l'IA
        pw.expect(page.get_by_text('Suggéré', exact=True)).to_be_visible()
        page.get_by_role('button', name='✉️ Sur invitation seulement : Publier et envoyer le lien').click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('Lien d’invitation', exact=True)).to_be_visible()
        assert ('PATCH', 'events', {'visibility': 'invited', 'public_link': False}) in writes
        assert not [w for w in writes if w[1] == 'event_invites' and w[0] == 'POST']
    finally:
        context.close()


def test_only_the_groups_the_organizer_is_in_are_offered(browser, events_origin):  # noqa: F811
    """Question de l'admin (06.11) : Vendredi Party seulement si on en fait partie, pareil pour les autres groupes."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        member_without_vip(page)
        draft_event(page)
        open_step_two(page, events_origin, f'audience=vip&groups={FOOT}')  # pré-réglage non permis : ignoré
        pw.expect(page.get_by_role('button', name='🌍 Public + lien public : Publier')).to_be_visible()
        pw.expect(page.get_by_role('button', name='👥 Membres Vendredi Party', exact=False)).to_have_count(0)
        page.get_by_role('button', name='👥 Un groupe', exact=True).click()
        pw.expect(page.get_by_role('button', name='Ski · 2')).to_be_visible()
        pw.expect(page.get_by_role('button', name='Foot · 1')).to_have_count(0)  # créé par lui, mais il n'en fait pas partie
        # Formulaire classique : pas de « Vendredi Party », seulement ses groupes, public par défaut.
        page.goto(f'{events_origin}/events/event/new', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Publique + lien')).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Sur invitation').click()
        pw.expect(page.get_by_role('button', name='👥 Vendredi Party', exact=False)).to_have_count(0)
        pw.expect(page.get_by_role('button', name='Ski · 2')).to_be_visible()
        pw.expect(page.get_by_role('button', name='Foot · 1')).to_have_count(0)
    finally:
        context.close()


@pytest.mark.parametrize('start', ['events', 'account'])
def test_iphone_app_opens_step_two_in_the_party_page_and_it_stays_open(browser, events_origin, start):  # noqa: F811
    """Bug de prod (06.11) : l'app iPhone ouvre l'étape 2 par PartyEvents.open('/events/event/<id>/invite…') ; le module
    rechargé disait « prêt » sur /event/<id>/invite, la page Party (qui croyait encore le module sur « / » ou « /account »)
    le renvoyait aussitôt à sa page d'avant : l'étape 2 se fermait. Elle doit rester ouverte, puis la fiche aussi."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        draft_event(page)
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button', name='Événements', exact=True).click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        pw.expect(frame.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
        if start == 'account':  # assistant ouvert depuis Réglages : le module est sur /account
            page.evaluate("showTab('account')")
            pw.expect(frame.get_by_text('Confidentialité', exact=False).first).to_be_visible(timeout=15000)
            page.evaluate("showTab('events')")  # ce que fait l'app (selectTab) juste avant d'ouvrir l'étape 2
        page.evaluate(f"PartyEvents.open('/events/event/{EVENT}/invite?suggested={TOM}')")
        step = frame.get_by_role('progressbar', name='Étape 2 sur 3 : Qui est invité')
        pw.expect(step).to_be_visible(timeout=15000)
        page.wait_for_timeout(2500)  # le renvoi arrivait juste après « prêt »
        pw.expect(step).to_be_visible()
        assert page.frame(url=lambda u: '/invite' in u) is not None
        shot(page, f'02-app-etape-2-reste-ouverte-{start}')
        # « Ouvrir l'événement » de l'assistant (PartyEvents.open de la fiche) : la fiche reste ouverte elle aussi.
        page.evaluate(f"PartyEvents.open('/events/event/{EVENT}')")
        pw.expect(frame.get_by_role('button', name='Inviter et publier')).to_be_visible(timeout=15000)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_role('button', name='Inviter et publier')).to_be_visible()
        # Reprendre le brouillon depuis sa fiche : « Inviter et publier » ouvre l'étape 2.
        frame.get_by_role('button', name='Inviter et publier').click()
        pw.expect(step).to_be_visible(timeout=15000)
    finally:
        context.close()


def test_step_two_without_being_signed_in_asks_to_sign_in_then_opens(browser, events_origin):  # noqa: F811
    """Banc des bots (06.11) : ouverte sans session, l'étape 2 plantait (« La page n'a pas pu s'ouvrir »)."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        draft_event(page)
        page.goto(f'{events_origin}/events/event/{EVENT}/invite', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Recevoir un code par SMS')).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('La page n’a pas pu s’ouvrir', exact=True)).to_have_count(0)
        login(page)
        pw.expect(page.get_by_role('progressbar', name='Étape 2 sur 3 : Qui est invité')).to_be_visible(timeout=15000)
    finally:
        context.close()


def test_step_two_reopened_from_the_event_keeps_the_people_named_to_the_ai(browser, v2_origin):  # noqa: F811
    """Retour de l'admin (06.11, bot n° 13) : rouverte depuis « Inviter et publier » (sans ?suggested=), l'étape 2
    retrouve les personnes citées à l'IA, gardées avec le brouillon (events.ai_suggested) ; vidées à la publication."""
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        calls = mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page, ai_suggested=[TOM])
        open_step_two(page, v2_origin, 'from=event')
        page.get_by_role('button', name='✉️ Sur invitation seulement : Publier et envoyer le lien').click()
        sheet = page.get_by_label('Inviter à Raclette chez Camille')
        pw.expect(sheet.get_by_role('button', name='Retirer Tom')).to_be_visible(timeout=10000)
        assert not [c for c in calls if c[0] == 'invite_people']
        assert ('PATCH', 'events', {'ai_suggested': []}) in writes
    finally:
        context.close()
