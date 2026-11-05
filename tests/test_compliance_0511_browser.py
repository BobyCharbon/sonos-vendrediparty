"""Contrôle App Store du 05.11 dans le vrai module Événements (navigateur, Supabase simulé, serveur Party en
configuration de production : Discussions éteintes) :
- O2 : « Signaler cet événement » sur la fiche d'un événement d'un autre membre (type « event » envoyé à la base),
  jamais sur le sien ; sur le lien public sans compte, l'adresse de contact ;
- O3 : la page d'invitation ne promet pas les discussions de groupe ; la confidentialité nomme la dictée d'Apple et Google."""
import json
import os

import pytest

from tests.test_app_invites_browser import TOKEN, mock_invites
from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
SUPABASE = 'https://gsuetixzobooggeaubvb.supabase.co'
OTHER = '5b0f7c2e-1d2a-4f3b-9c8d-7e6f5a4b3c21'
TITLE = 'Soirée signalable (test local)'


@pytest.fixture(scope='module', autouse=True)
def production_features():
    """Serveur de ce module en configuration de production (tests/conftest.py allume les Discussions par défaut) ;
    autouse : posé avant que events_origin ne lance le serveur."""
    before = os.environ.get('DISCUSSIONS_ENABLED')
    os.environ['DISCUSSIONS_ENABLED'] = '0'
    yield
    if before is None:
        os.environ.pop('DISCUSSIONS_ENABLED', None)
    else:
        os.environ['DISCUSSIONS_ENABLED'] = before


def event_row(created_by: str) -> dict:
    category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
    return {'id': EVENT, 'title': TITLE, 'description': 'Description fictive.', 'created_by': created_by,
            'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
            'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
            'location_address': None, 'location_url': None, 'category_id': category['id'], 'category': category, 'event_tags': [],
            'date_options': [], 'rsvps': [], 'event_organizers': [], 'polls': [], 'bring_items': [], 'event_groups': [],
            'author': {'id': created_by, 'display_name': 'Organisateur fictif'}, 'show_participants': True, 'allow_maybe': True,
            'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None, 'rsvp_deadline': None, 'forum_enabled': False,
            'all_day': False, 'price_chf': None, 'payment_info': None, 'visibility': 'all', 'public_link': True}


def json_route(page, pattern: str, body, sent: list | None = None):
    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if sent is not None:
            sent.append(json.loads(route.request.post_data or '{}'))
        value = body(route.request) if callable(body) else body
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(value))
    page.route(pattern, handle)


def open_event(browser, origin, created_by: str):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page)
    ev = event_row(created_by)
    json_route(page, f'{SUPABASE}/rest/v1/events?**', lambda r: ev if 'id=eq.' in r.url else [ev])
    reports: list = []
    json_route(page, f'{SUPABASE}/rest/v1/rpc/report_content', 'a1b2c3d4-0000-4000-8000-000000000001', reports)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    frame.get_by_text(TITLE, exact=True).first.click()
    pw.expect(frame.get_by_text('À propos', exact=True)).to_be_visible(timeout=15000)
    return context, frame, reports, errors


def test_a_member_reports_someone_elses_event(browser, events_origin):  # noqa: F811
    context, frame, reports, errors = open_event(browser, events_origin, OTHER)
    try:
        frame.get_by_role('button', name='Signaler cet événement').click()
        pw.expect(frame.get_by_text('Signaler cet événement', exact=True).last).to_be_visible()
        frame.get_by_role('radio', name='Contenu choquant').click()
        frame.get_by_label('Commentaire').fill('Titre déplacé')
        frame.get_by_role('button', name='Envoyer').click()
        pw.expect(frame.get_by_text('Merci, c’est envoyé')).to_be_visible(timeout=10000)
        assert reports == [{'p_kind': 'event', 'p_target': EVENT, 'p_reason': 'shocking', 'p_comment': 'Titre déplacé'}]
        assert not errors, errors
    finally:
        context.close()


def test_no_report_button_on_my_own_event(browser, events_origin):  # noqa: F811
    context, frame, reports, errors = open_event(browser, events_origin, USER)
    try:
        assert frame.get_by_role('button', name='Signaler cet événement').count() == 0
    finally:
        context.close()


def test_public_link_without_account_points_to_the_contact_address(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        public = {k: v for k, v in event_row(OTHER).items() if k in ('id', 'title', 'description', 'status', 'date_mode', 'starts_at',
                  'ends_at', 'location_name', 'location_address', 'location_url', 'price_chf', 'allow_maybe', 'rsvp_deadline', 'max_participants')}
        json_route(page, f'{SUPABASE}/rest/v1/rpc/public_event', {**public, 'going': 3, 'mine': None})
        page.goto(f'{events_origin}/events/share/{EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('link', name='Signaler cet événement par e-mail')).to_be_visible()
        pw.expect(page.get_by_text('Un contenu choquant ? Signale-le à support@vendrediparty.ch')).to_be_visible()
    finally:
        context.close()


def test_invite_page_does_not_promise_group_chats_in_production(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page)
        page.goto(f'{events_origin}/events/join/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Événements, jeux et musique de la soirée : rejoins tes amis sur Party.', exact=False)).to_be_visible(timeout=15000)
        assert page.get_by_text('discussions de groupe', exact=False).count() == 0
    finally:
        context.close()


def test_privacy_names_apple_and_google_for_dictation(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        page.goto(f'{events_origin}/events/privacy', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('service vocal de ton système', exact=False)).to_be_visible(timeout=15000)
        assert page.get_by_text('faite par ton téléphone', exact=False).count() == 0
        pw.expect(page.get_by_text('la dictée vocale dans Chrome', exact=False)).to_be_visible()
    finally:
        context.close()
