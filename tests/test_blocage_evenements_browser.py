"""Contrôle Apple tour 7 (1.2), module Événements dans un vrai navigateur (Supabase simulé) : l'événement d'une personne
bloquée disparaît de ma liste et de ma recherche ; sa fiche ouverte par un lien dit « indisponible », sauf si j'en fais
partie (ici : invité)."""
import json

import pytest
from urllib.parse import parse_qs, urlparse

from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401

SUPA = 'https://gsuetixzobooggeaubvb.supabase.co'
BOB = 'eeeeeeee-0000-4000-8000-0000000000b0'
BOB_EVENT = '51f18a3b-827f-4123-8cf4-33de06c9a5bb'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
PERMS = ['events.view', 'events.rsvp', 'events.create', 'events.see_participants', 'chat.write']


def fulfill(route, body):
    if route.request.method == 'OPTIONS':
        return route.fulfill(status=204, headers=CORS)
    route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))


def open_with_blocked_author(browser, events_origin, invited=False, theirs=False):  # noqa: F811
    ctx = browser.new_context(viewport={'width': 390, 'height': 844})
    page = ctx.new_page()
    mock_services(page)
    own = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': None, 'created_by': USER, 'status': 'published',
           'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'created_at': '2026-10-19T08:00:00Z',
           'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu', 'category_id': None, 'category': None, 'event_tags': [],
           'date_options': [], 'rsvps': [], 'event_organizers': [], 'event_invites': [], 'event_groups': [], 'polls': [], 'bring_items': [],
           'author': {'id': USER, 'display_name': 'Compte de démonstration'}, 'show_participants': True, 'allow_maybe': True,
           'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None, 'rsvp_deadline': None, 'forum_enabled': False,
           'all_day': False, 'price_chf': None, 'visibility': 'all'}
    bob = {**own, 'id': BOB_EVENT, 'title': 'Soirée de Bob', 'created_by': BOB, 'author': {'id': BOB, 'display_name': 'Bob'},
           'event_invites': [{'user_id': USER}] if invited else []}

    def events(route):
        q = parse_qs(urlparse(route.request.url).query)
        if 'id' in q:
            return fulfill(route, bob if BOB_EVENT in q['id'][0] else own)
        fulfill(route, [own, bob])
    page.route(f'{SUPA}/rest/v1/events*', events)
    page.route(f'{SUPA}/rest/v1/direct_blocks*', lambda r: fulfill(r, [] if theirs else [{'blocked_id': BOB}]))
    page.route(f'{SUPA}/rest/v1/rpc/blocked_with', lambda r: fulfill(r, True))
    page.route(f'{SUPA}/rest/v1/rpc/my_permissions', lambda r: fulfill(r, PERMS))
    page.route(f'{SUPA}/rest/v1/event_invites*', lambda r: fulfill(r, [{'user_id': USER, 'via_link': False}] if invited else []))
    return ctx, page


@pytest.mark.parametrize('theirs', [False, True], ids=['je-bloque', 'il-me-bloque'])
def test_the_event_of_a_blocked_person_leaves_my_list_and_its_page_is_unavailable(browser, events_origin, theirs):  # noqa: F811
    ctx, page = open_with_blocked_author(browser, events_origin, theirs=theirs)
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button', name='Événements', exact=True).click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        assert frame.get_by_text('Soirée de Bob', exact=True).count() == 0
        page.goto(f'{events_origin}/?tab=events&event={BOB_EVENT}', wait_until='domcontentloaded')
        frame = page.frame_locator('#eventsFrame')
        pw.expect(frame.get_by_text('Cet événement est indisponible.', exact=True)).to_be_visible(timeout=15000)
        assert frame.get_by_text('Soirée de Bob', exact=True).count() == 0
    finally:
        ctx.close()


def test_invited_i_still_see_the_event_of_a_blocked_person(browser, events_origin):  # noqa: F811
    ctx, page = open_with_blocked_author(browser, events_origin, invited=True)
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button', name='Événements', exact=True).click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        pw.expect(frame.get_by_text('Soirée de Bob', exact=True)).to_be_visible(timeout=15000)
        frame.get_by_text('Soirée de Bob', exact=True).click()
        pw.expect(frame.get_by_text('Cet événement est indisponible.', exact=True)).to_have_count(0, timeout=3000)
        pw.expect(frame.get_by_role('heading', name='Soirée de Bob')).to_be_visible(timeout=15000)
    finally:
        ctx.close()
