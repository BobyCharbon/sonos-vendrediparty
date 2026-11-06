"""« Créer avec l'IA » en deux étapes (demande de l'admin, 06.11), module web dans un vrai navigateur (Supabase simulé,
personne de réel n'est prévenu) : l'app iPhone enregistre le brouillon puis ouvre l'étape 2 « Les invités »
(/events/event/<id>/invite?suggested=…) ; la personne invite elle-même, publie, et la fiche s'ouvre (étape 3).
- invitations v2 (site de test) : la feuille « Inviter » s'ouvre tout de suite, la personne citée à l'IA déjà cochée,
  pas encore de lien (brouillon) ; « Inviter Tom » puis « Publier » ;
- production (v2 éteint) : le sélecteur du formulaire, Tom coché ; « Publier sans inviter pour l'instant » n'invite personne.
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


def draft_event(page) -> list:
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


def test_v2_who_sees_it_is_chosen_first_public_by_default_then_the_invite_sheet_then_publish(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        calls = mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page)
        open_step_two(page, v2_origin)
        # En haut : qui voit, le défaut (public + lien) en surbrillance avec ce que ça veut dire.
        pw.expect(page.get_by_text('Qui voit l’événement ?', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('radio', name='🌍 Public + lien public')).to_have_attribute('aria-checked', 'true')
        pw.expect(page.get_by_text('Tout le monde peut le voir', exact=False)).to_be_visible()
        for name in ('👥 Membres Vendredi Party', '✉️ Sur invitation seulement'):
            pw.expect(page.get_by_role('radio', name=name)).to_be_visible()
        assert not [c for c in calls if c[0] == 'invite_people']  # jamais invitée sans son « Inviter »
        shot(page, '02-web-qui-est-invite-v2')
        # Puis les invités : la feuille « Inviter », Tom (cité à l'IA) déjà coché, pas encore de lien (brouillon).
        page.get_by_role('button', name='＋ Inviter Tom…').click()
        sheet = page.get_by_label('Inviter à Raclette chez Camille')
        pw.expect(sheet.get_by_text('🔗 Le lien à partager', exact=True)).to_be_visible(timeout=5000)
        pw.expect(sheet.get_by_role('button', name='Retirer Tom')).to_be_visible(timeout=5000)
        pw.expect(sheet.get_by_role('button', name='Partager le lien…')).to_have_count(0)
        shot(page, '02b-web-feuille-inviter-v2')
        sheet.get_by_role('button', name='Inviter Tom').click()
        pw.expect(page.get_by_text('Tom : invités, prévenus à la publication', exact=True)).to_be_visible(timeout=5000)
        assert ('invite_people', {'e': EVENT, 'people': [TOM], 'groups': []}) in calls
        sheet.get_by_role('button', name='Fermer').click()
        # Membres Vendredi Party : la phrase change ; enregistré au moment de publier, avant le statut.
        page.get_by_role('radio', name='👥 Membres Vendredi Party').click()
        pw.expect(page.get_by_text('Tous les Membres VIP et au-dessus le voient', exact=False)).to_be_visible()
        page.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_role('progressbar', name='Étape 3 sur 3 : C’est en ligne')).to_be_visible()
        visibility = writes.index(('PATCH', 'events', {'visibility': 'all', 'public_link': False}))
        assert visibility < writes.index(('PATCH', 'events', {'status': 'published'}))
        assert 'step=online' in page.url
        shot(page, '03-web-c-est-en-ligne-v2')
        assert page.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
        assert not errors, errors
    finally:
        context.close()


def test_production_public_by_default_publish_without_inviting_invites_nobody(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin)
        pw.expect(page.get_by_text('Public : pas besoin d’inviter', exact=False)).to_be_visible(timeout=5000)
        pw.expect(page.get_by_role('button', name='Ouvrir l’événement (finir à la main)')).to_be_visible()
        page.get_by_role('button', name='Publier sans inviter pour l’instant').click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        assert not [w for w in writes if w[1] == 'event_invites' and w[0] == 'POST']
        assert ('PATCH', 'events', {'visibility': 'all', 'public_link': True}) in writes
        assert ('PATCH', 'events', {'status': 'published'}) in writes
        assert not errors, errors
    finally:
        context.close()


def test_production_invite_only_preset_checks_the_named_person_and_invites_before_publishing(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin, f'audience=invite&suggested={TOM}')  # « j'invite seulement Tom » dit à l'IA
        pw.expect(page.get_by_role('radio', name='✉️ Sur invitation seulement')).to_have_attribute('aria-checked', 'true')
        pw.expect(page.get_by_role('button', name='✕ Tom')).to_be_visible(timeout=5000)  # sélecteur actuel, Tom coché
        shot(page, '02-web-prod-qui-est-invite-v2')
        page.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        invited = [w for w in writes if w[1] == 'event_invites' and w[0] == 'POST']
        assert invited and invited[0][2] == [{'event_id': EVENT, 'user_id': TOM}]
        assert ('PATCH', 'events', {'visibility': 'invited', 'public_link': False}) in writes
        assert writes.index(invited[0]) < writes.index(('PATCH', 'events', {'status': 'published'}))
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
        pw.expect(page.get_by_role('radio', name='🌍 Public + lien public')).to_have_attribute('aria-checked', 'true')
        pw.expect(page.get_by_role('radio', name='👥 Membres Vendredi Party')).to_have_count(0)
        page.get_by_role('radio', name='👥 Un groupe').click()
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
