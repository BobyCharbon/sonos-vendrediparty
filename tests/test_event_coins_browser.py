"""Pièces Zicou d'un événement (droit « zicou.event_coins », migration 20261105090000) dans le vrai module Événements
(navigateur, Supabase simulé : aucun SMS, aucune notification réelle), page « Cadeaux de l'événement » :
- avec le droit : « Pièces pour les présents » s'active, 20 est proposé, montant borné, enregistré par la base ;
- une fois versées : montant figé, nombre de présents servis ;
- sans le droit : rien de ce réglage n'apparaît (le reste de la page, oui).
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json

import pytest

from tests.test_events_browser import DIST, EVENT, browser, events_origin, login, mock_services  # noqa: F401 (fixtures)

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
DROP = {'event': {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'starts_at': '2030-11-14T18:00:00Z',
                  'ends_at': None, 'status': 'published', 'started': False},
        'role': None, 'drop': None, 'eligible_now': None, 'bounds': None, 'catalog': None, 'mine': []}


def setting(coins=None, given=0):
    return {'coins': coins, 'set_at': None, 'min': 5, 'max': 100, 'pay_at': '2030-11-15T00:00:00Z',
            'open_until': '2030-11-22T00:00:00Z', 'late': False, 'given': given, 'eligible_now': 12}


def coins_backend(page, allowed: bool, given: int = 0):
    state = {'coins': 20 if given else None, 'sent': []}

    def reply(route, body):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=HEADERS)

    def view():
        return {'allowed': allowed, 'mine': None, 'setting': setting(state['coins'], given) if allowed else None}

    def set_coins(route):
        if route.request.method != 'OPTIONS':
            body = json.loads(route.request.post_data)
            state['sent'].append(body)
            state['coins'] = body['p_coins']
        reply(route, view())

    base = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
    page.route(base + 'pet_event_drop_get', lambda route: reply(route, DROP))
    page.route(base + 'pet_event_coins_get', lambda route: reply(route, view()))
    page.route(base + 'pet_event_coins_set', set_coins)
    return state


def open_gifts(browser, events_origin, allowed, given=0):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)
    state = coins_backend(page, allowed, given)
    page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_role('button', name='Proposer un événement')).to_be_visible(timeout=15000)
    page.goto(f'{events_origin}/events/event/{EVENT}/gifts', wait_until='domcontentloaded')
    pw.expect(page.get_by_text('Règlement', exact=True)).to_be_visible(timeout=15000)
    return context, page, state


def test_with_the_right_coins_for_present_people_are_set_with_20_suggested(browser, events_origin):  # noqa: F811
    context, page, state = open_gifts(browser, events_origin, allowed=True)
    try:
        switch = page.get_by_role('switch', name='Pièces pour les présents')
        pw.expect(switch).to_be_visible()
        switch.click()
        field = page.get_by_label('Pièces par présent (5 à 100)')
        pw.expect(field).to_have_value('20')
        field.fill('150')
        pw.expect(page.get_by_text('De 5 à 100 pièces.', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Enregistrer les pièces')).to_be_disabled()
        field.fill('20')
        pw.expect(page.get_by_text('≈ 240 pièces pour 12 présent(s) aujourd’hui')).to_be_visible()
        page.get_by_role('button', name='Enregistrer les pièces').click()
        for _ in range(50):
            if state['sent']:
                break
            page.wait_for_timeout(100)
        assert state['sent'] == [{'p_event': EVENT, 'p_coins': 20}]
    finally:
        context.close()


def test_once_paid_the_amount_is_frozen(browser, events_origin):  # noqa: F811
    context, page, _ = open_gifts(browser, events_origin, allowed=True, given=7)
    try:
        pw.expect(page.get_by_text('20 pièces versées à 7 présents', exact=False)).to_be_visible()
        assert page.get_by_role('switch', name='Pièces pour les présents').count() == 0
    finally:
        context.close()


def test_without_the_right_the_setting_is_invisible(browser, events_origin):  # noqa: F811
    context, page, _ = open_gifts(browser, events_origin, allowed=False)
    try:
        pw.expect(page.get_by_text('Pas d’objets Zicou à gagner pour cet événement.')).to_be_visible()
        page.wait_for_timeout(500)
        assert page.get_by_text('Pièces pour les présents').count() == 0
        assert page.get_by_role('switch', name='Pièces pour les présents').count() == 0
    finally:
        context.close()
