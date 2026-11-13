"""Covoiturage (avis 34d5c07f2e56 de l'admin, 11.11.2026), module web dans un vrai navigateur (Supabase simulé) :
la carte apparaît quand l'organisateur a allumé l'option ; on propose ses places (nombre, ville facultative), on voit qui
conduit et qui cherche, on monte dans une voiture ; sans réponse Présent / Peut-être, la carte le dit simplement."""
import json
import os
from pathlib import Path

import pytest

from tests.test_event_participant_browser import HEADERS, LEA, REST, event_row, open_event, rsvp
from tests.test_events_browser import DIST, USER, browser, events_origin  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SHOTS = Path(os.environ['CARPOOL_SHOTS']) if os.environ.get('CARPOOL_SHOTS') else None
TOM = '7c0ffee0-0000-4000-8000-0000000000bb'
ZOE = '7c0ffee0-0000-4000-8000-0000000000cc'


def shot(page, name: str):
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


def mock_carpool(page, board: dict) -> list:
    """Une petite base de covoiturage en mémoire : chaque appel répond le tableau à jour."""
    calls = []

    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        name = route.request.url.split('/rpc/')[1].split('?')[0]
        args = json.loads(route.request.post_data or '{}')
        calls.append((name, args))
        if name == 'carpool_drive':
            board['me'] = {'id': USER, 'role': 'driver', 'seats': args['seats'], 'from_city': args['from_city'], 'driver_id': None}
            board['drivers'].append({'id': USER, 'name': 'Camille', 'avatar_url': None, 'from_city': args['from_city'],
                                     'seats': args['seats'], 'passengers': []})
        if name == 'carpool_take':
            board['me'] = {'id': USER, 'role': 'passenger', 'seats': None, 'from_city': None, 'driver_id': args['driver']}
            next(d for d in board['drivers'] if d['id'] == args['driver'])['passengers'].append({'id': USER, 'name': 'Camille'})
        route.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps(board))
    page.route(REST + 'rpc/carpool*', handle)
    return calls


def board() -> dict:
    return {'enabled': True, 'member': True, 'me': None,
            'drivers': [{'id': LEA, 'name': 'Léa', 'avatar_url': None, 'from_city': 'Sion', 'seats': 3,
                         'passengers': [{'id': TOM, 'name': 'Tom'}]}],
            'seekers': [{'id': ZOE, 'name': 'Zoé', 'avatar_url': None, 'from_city': 'Martigny'}]}


def open_with_carpool(browser, origin, state: dict, status='yes'):  # noqa: F811
    ev = event_row(carpool_enabled=True, rsvps=[rsvp(USER, status)] if status else [], max_participants=None)
    context, page = open_event(browser, origin, ev)
    calls = mock_carpool(page, state)
    page.reload(wait_until='domcontentloaded')
    pw.expect(page.get_by_text('🚗 Covoiturage', exact=True)).to_be_visible(timeout=15000)
    return context, page, calls


def test_a_participant_offers_seats_with_a_city(browser, events_origin):  # noqa: F811
    context, page, calls = open_with_carpool(browser, events_origin, board())
    try:
        pw.expect(page.get_by_text('1 voiture · 2 places libres · 1 cherche une place', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Zoé', exact=False).first).to_be_visible()
        shot(page, '01-covoiturage-carte')
        page.get_by_role('button', name='🚗 Je conduis').click()
        page.get_by_role('button', name='Une place de plus').click()  # 3 → 4
        page.get_by_label('Ville de départ (facultatif)').fill('Sierre')
        shot(page, '02-covoiturage-je-conduis')
        page.get_by_role('button', name='Proposer mes places').click()
        pw.expect(page.get_by_text('Tu conduis depuis Sierre · 4 places libres', exact=True)).to_be_visible(timeout=5000)
        assert ('carpool_drive', {'e': calls[0][1]['e'], 'seats': 4, 'from_city': 'Sierre'}) in calls
        # Conducteur : il peut prendre Zoé, qui cherche une place.
        pw.expect(page.get_by_role('button', name='Prendre Zoé dans ta voiture')).to_be_visible()
        shot(page, '03-covoiturage-conducteur')
    finally:
        context.close()


def test_a_participant_takes_a_free_seat(browser, events_origin):  # noqa: F811
    context, page, calls = open_with_carpool(browser, events_origin, board())
    try:
        page.get_by_role('button', name='Monter avec Léa').click()
        pw.expect(page.get_by_text('Tu montes avec Léa (départ de Sion)', exact=True)).to_be_visible(timeout=5000)
        pw.expect(page.get_by_role('button', name='Descendre')).to_be_visible()
        pw.expect(page.get_by_text('· avec Tom, toi', exact=True)).to_be_visible()
        assert ('carpool_take', {'e': calls[0][1]['e'], 'driver': LEA}) in calls
    finally:
        context.close()


def test_without_an_answer_the_card_says_to_answer_first(browser, events_origin):  # noqa: F811
    context, page, _ = open_with_carpool(browser, events_origin, {'enabled': True, 'member': False}, status=None)
    try:
        pw.expect(page.get_by_text('Réponds Présent ou Peut-être pour proposer tes places ou en trouver une.', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='🚗 Je conduis')).to_have_count(0)
    finally:
        context.close()


def test_option_off_no_card(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.wait_for_timeout(800)
        pw.expect(page.get_by_text('🚗 Covoiturage', exact=True)).to_have_count(0)
    finally:
        context.close()
