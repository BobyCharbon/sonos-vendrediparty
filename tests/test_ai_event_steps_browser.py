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
    """L'événement que l'IA vient d'enregistrer : un brouillon « sur invitation », sans invité. Garde les écritures."""
    writes = []
    event = {'id': EVENT, 'title': 'Raclette chez Camille', 'description': 'Chacun amène une salade.', 'created_by': USER, 'status': 'draft',
             'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'all_day': False, 'visibility': 'invited',
             'public_link': False, 'location_name': 'Chez Camille', 'location_address': 'Chemin des Vignes 4, 1095 Lutry',
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


def open_step_two(page, origin):
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_label('Rechercher un événement')).to_be_visible(timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}/invite?suggested={TOM},pas-un-id', wait_until='domcontentloaded')
    pw.expect(page.get_by_role('progressbar', name='Étape 2 sur 3 : Les invités')).to_be_visible(timeout=15000)


def test_invitations_v2_open_the_invite_sheet_with_the_named_person_then_publish_opens_the_event(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        calls = mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page)
        open_step_two(page, v2_origin)
        sheet = page.get_by_label('Inviter à Raclette chez Camille')
        pw.expect(sheet.get_by_text('🔗 Le lien à partager', exact=True)).to_be_visible(timeout=5000)
        pw.expect(sheet.get_by_role('button', name='Retirer Tom')).to_be_visible(timeout=5000)  # citée à l'IA : cochée
        pw.expect(sheet.get_by_role('button', name='Partager le lien…')).to_have_count(0)  # brouillon : pas encore de lien
        assert not [c for c in calls if c[0] == 'invite_people']  # jamais invitée sans son « Inviter »
        shot(page, '02-web-les-invites-feuille-inviter')
        sheet.get_by_role('button', name='Inviter Tom').click()
        pw.expect(page.get_by_text('Tom : invités, prévenus à la publication', exact=True)).to_be_visible(timeout=5000)
        assert ('invite_people', {'e': EVENT, 'people': [TOM], 'groups': []}) in calls
        sheet.get_by_role('button', name='Fermer').click()
        pw.expect(page.get_by_text('Qui voit l’événement ?', exact=True)).to_be_visible()
        shot(page, '02b-web-les-invites-ecran')
        page.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_role('progressbar', name='Étape 3 sur 3 : C’est en ligne')).to_be_visible()
        assert ('PATCH', 'events', {'status': 'published'}) in writes
        assert 'step=online' in page.url
        shot(page, '03-web-c-est-en-ligne')
        assert page.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
        assert not errors, errors
    finally:
        context.close()


def test_production_picker_checks_the_named_person_and_publish_without_inviting_invites_nobody(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin)
        pw.expect(page.get_by_role('button', name='✕ Tom')).to_be_visible(timeout=5000)  # sélecteur actuel, Tom coché
        pw.expect(page.get_by_role('button', name='Ouvrir l’événement (finir à la main)')).to_be_visible()
        shot(page, '02-web-prod-les-invites-selecteur')
        page.get_by_role('button', name='Publier sans inviter pour l’instant').click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        assert not [w for w in writes if w[1] == 'event_invites' and w[0] == 'POST']
        assert ('PATCH', 'events', {'status': 'published'}) in writes
        assert not errors, errors
    finally:
        context.close()


def test_production_publish_invites_the_checked_person(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page, people=PEOPLE)
        writes = draft_event(page)
        open_step_two(page, events_origin)
        page.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(page.get_by_text('C’est en ligne !', exact=True)).to_be_visible(timeout=10000)
        invited = [w for w in writes if w[1] == 'event_invites' and w[0] == 'POST']
        assert invited and invited[0][2] == [{'event_id': EVENT, 'user_id': TOM}]
        published = writes.index(('PATCH', 'events', {'status': 'published'}))
        assert writes.index(invited[0]) < published  # invités enregistrés AVANT la publication (et ses notifications)
    finally:
        context.close()
