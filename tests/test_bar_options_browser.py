"""Options du bar (demande de l'admin du 10.11.2026, migration 20261110160000) dans le vrai module Événements (navigateur,
Supabase simulé : aucun SMS réel, aucune base) :
- organisateur : onglet « Options » (commandes dans l'app, comptoir, stock montré, bar offert, limites, droits des barmans),
  article avec catégorie, précision, maximum par personne, « Indisponible pour l'instant » ;
- invité : carte par catégories, « Indisponible pour l'instant », « Il en reste 3 », limites de la soirée, bar offert sans
  prix ni engagement, commandes au comptoir (carte en consultation + engagement à accepter) ;
- barman : « Carte et stock » (Il en reste…, Indisponible), service sans commande.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.test_events_browser import EVENT, USER, browser, login, mock_services  # noqa: F401 (fixture browser)

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
DIST = Path(os.environ.get('EVENTS_TEST_DIST') or ROOT / 'web/events/dist')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
BIERE, COCA, VODKA = ('b1000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000002',
                      'b1000000-0000-4000-8000-000000000003')
LEA = '5b0c7e1e-1d3a-4c8e-9a51-6f2f4b9d0a11'
OPTIONS = {'guest_orders': True, 'counter_serve': False, 'show_stock': True, 'free_bar': False, 'limit_glasses': None,
           'limit_chf': None, 'staff_adjust_stock': True, 'staff_unavailable': True, 'staff_correct': True, 'staff_prices': False,
           'staff_items': False}
RIGHTS = {'adjust_stock': True, 'unavailable': True, 'correct': True, 'prices': False, 'items': False}
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}


@pytest.fixture(scope='module')
def origin(tmp_path_factory):
    """Serveur Party local, bar allumé (BAR_ENABLED=1), module servi depuis DIST."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-bar-options')), 'EVENTS_WEB_DIR': str(DIST), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1', 'BAR_ENABLED': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'],
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(url, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        else:
            raise AssertionError('Le serveur Party de test ne démarre pas')
        yield url
    finally:
        process.terminate()
        process.wait(timeout=5)


def item(id_, name, price, category, **extra):
    return {'id': id_, 'name': name, 'emoji': None, 'price_chf': price, 'stock': None, 'age_min': 0, 'max_pending': None, 'sort': 0,
            'active': True, 'served': 0, 'pending': 0, 'available': None, 'left': None, 'category': category, 'detail': None,
            'max_per_person': None, 'unavailable': False, **extra}


def guest_item(id_, name, price, category, **extra):
    return {'id': id_, 'name': name, 'emoji': None, 'price_chf': price, 'age_min': 0, 'max_pending': None, 'available': None,
            'mine_pending': 0, 'mine_pending_chf': 0, 'category': category, 'detail': None, 'max_per_person': None,
            'unavailable': False, 'sold_out': False, 'mine_total': 0, 'active': True, **extra}


def bar_backend(page, options=None, manage=True, serve=True):
    """Fonctions du bar simulées par-dessus mock_services (la dernière route gagne) ; chaque appel est noté."""
    opts = {**OPTIONS, **(options or {})}
    calls: list = []
    items = [item(BIERE, 'Bière blonde', 4, 'bieres', detail='33 cl', stock=10, served=4, pending=1, available=5, left=6),
             item(COCA, 'Coca', 2, 'softs', stock=8, served=2, pending=0, available=6, left=6)]

    def overview():
        return {'phase': 'open', 'orders_open': True, 'preorder_enabled': False, 'preorder_until': None, 'closes_at': '2030-11-15T03:00:00Z',
                'closed_at': None, 'payee_id': USER, 'pay_method': 'revolut', 'repay_by': None, 'terms_version': 1,
                'pledge_text': 'Je m’engage à rembourser à Compte de démonstration, par Revolut, après la soirée, chaque consommation servie à mon nom.',
                'options': opts, 'items': items, 'staff': [], 'people': [], 'cancellations': [],
                'totals': {'served': 6, 'served_chf': 20, 'refunded_chf': 0},
                'stock_log': [{'at': '2030-11-14T21:00:00Z', 'actor': 'Léa', 'item': 'Coca', 'kind': 'restock', 'qty': 12, 'amount': None}]}

    def my_bar():
        free = opts['free_bar']
        return {'phase': 'open', 'eligible': True, 'manage': manage, 'serve': serve, 'closes_at': '2030-11-15T03:00:00Z', 'preorder_until': None,
                'options': opts, 'rights': RIGHTS if serve else None, 'pledged_current': False,
                'pledge_text': overview()['pledge_text'], 'pledge_version': 1,
                'payee': {'id': USER, 'name': 'Compte de démonstration', 'method': 'revolut', 'repay_by': None, 'iban': None, 'holder': None, 'link': None},
                'qr': {'token': 'ab' * 32, 'code': 'K7M2QX'}, 'balance': 0, 'pending_total': 0, 'refund_declared': 0,
                'mine': {'glasses': 2, 'chf': 8},
                'items': [guest_item(BIERE, 'Bière blonde', 0 if free else 4, 'bieres', detail='33 cl', available=3 if opts['show_stock'] else None),
                          guest_item(VODKA, 'Vodka Red Bull', 0 if free else 6, 'cocktails', unavailable=True),
                          guest_item(COCA, 'Coca', 0 if free else 2, 'softs')],
                'served': [], 'cancelled': [], 'pledges': []}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        name = request.url.rsplit('/', 1)[-1].split('?')[0]
        args = json.loads(request.post_data or '{}')
        calls.append((name, args))
        if name == 'bar_save_settings':
            opts.update({k: v for k, v in args['settings'].items() if k in opts})
            body = overview()
        elif name == 'bar_overview':
            body = overview()
        elif name == 'my_bar' or name == 'bar_order' or name == 'bar_pledge':
            body = my_bar()
        elif name == 'bar_save_item':
            body = {'id': args['item'].get('id') or BIERE, 'overbooked': 0, 'name': args['item']['name']}
        elif name == 'bar_staff_items':
            body = {'rights': RIGHTS, 'items': items}
        elif name == 'bar_item_action':
            target = next(i for i in items if i['id'] == args['item'])
            if args['action'] == 'remaining':
                target.update(left=args['amount'])
            elif args['action'] in ('unavailable', 'available'):
                target.update(unavailable=args['action'] == 'unavailable')
            body = target
        elif name == 'bar_scan':
            body = {'result': 'ok', 'member': LEA, 'name': 'Léa', 'avatar_url': None, 'pledged_at': '2030-11-14T20:00:00Z', 'balance': 4,
                    'pending': [], 'pledged_current': True, 'free': opts['free_bar'], 'counter': opts['counter_serve'] or not opts['guest_orders'],
                    'rights': RIGHTS, 'menu': [{'item': COCA, 'name': 'Coca', 'emoji': None, 'detail': None, 'category': 'softs', 'price_chf': 2,
                                                'age_min': 0, 'unavailable': False, 'available': 6}]}
        elif name == 'bar_serve':
            body = {'serve_id': 'c0000000-0000-4000-8000-000000000001', 'total': 4, 'balance_before': 4, 'balance': 8, 'lines': []}
        else:
            body = None
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=CORS)

    page.route(re.compile(r'/rest/v1/rpc/(my_bar|bar_\w+)'), handle)
    return calls


def open_bar(browser, origin, path, **backend):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='fr-CH')
    page = context.new_page()
    errors: list = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page)
    calls = bar_backend(page, **backend)
    page.goto(f'{origin}/events/sign-in', wait_until='domcontentloaded')
    login(page)
    page.wait_for_timeout(1500)
    page.goto(f'{origin}/events/event/{EVENT}/bar{path}', wait_until='domcontentloaded')
    return context, page, calls, errors


def sent(calls, name):
    return [args for n, args in calls if n == name]


def test_the_organizer_sets_the_bar_options_with_one_sentence_each(browser, origin):
    context, page, calls, errors = open_bar(browser, origin, '/manage')
    try:
        page.get_by_role('tab', name='Options').click()
        pw.expect(page.get_by_text('Options du bar', exact=True)).to_be_visible(timeout=15000)
        for label in ('Les invités commandent dans l’app', 'Service au comptoir sans commande', 'Montrer aux invités combien il en reste',
                      'Bar offert', 'Ajuster les quantités', 'Marquer un article indisponible', 'Changer les prix',
                      'Ajouter ou modifier des articles'):
            pw.expect(page.get_by_role('switch', name=label, exact=True)).to_be_visible()
        page.get_by_role('switch', name='Les invités commandent dans l’app', exact=True).click()
        page.wait_for_timeout(500)
        assert sent(calls, 'bar_save_settings')[-1]['settings'] == {'guest_orders': False, 'counter_serve': True}
        page.get_by_label('Verres au plus').fill('6')
        page.get_by_role('button', name='Enregistrer les limites').click()
        page.wait_for_timeout(500)
        assert sent(calls, 'bar_save_settings')[-1]['settings'] == {'limit_glasses': 6, 'limit_chf': None}
        page.get_by_role('switch', name='Bar offert', exact=True).click()
        page.wait_for_timeout(500)
        assert sent(calls, 'bar_save_settings')[-1]['settings'] == {'free_bar': True}
        pw.expect(page.get_by_text('Les verres sont à 0 CHF', exact=False)).to_be_visible()
        page.get_by_role('tab', name='Direct').click()
        pw.expect(page.get_by_text('Léa · Coca : +12 en réassort', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        context.close()


def test_an_item_gets_a_category_a_detail_a_per_person_maximum_and_can_be_unavailable(browser, origin):
    context, page, calls, errors = open_bar(browser, origin, '/manage')
    try:
        page.get_by_role('button', name='Modifier Bière blonde').click()
        page.get_by_role('button', name='Cocktails', exact=True).click()
        page.get_by_label('Précision', exact=True).fill('50 cl')
        page.get_by_label('Maximum par personne pour la soirée').fill('3')
        page.get_by_role('switch', name='Indisponible pour l’instant').click()
        page.get_by_role('button', name='Enregistrer', exact=True).click()
        page.wait_for_timeout(500)
        saved = sent(calls, 'bar_save_item')[-1]['item']
        assert {k: saved[k] for k in ('category', 'detail', 'max_per_person', 'unavailable')} == \
            {'category': 'cocktails', 'detail': '50 cl', 'max_per_person': 3, 'unavailable': True}
        assert not errors, errors
    finally:
        context.close()


def test_the_guest_menu_follows_the_options(browser, origin):
    context, page, calls, errors = open_bar(browser, origin, '', options={'limit_glasses': 6}, manage=False, serve=False)
    try:
        pw.expect(page.get_by_text('La carte', exact=True)).to_be_visible(timeout=15000)
        for group in ('SOFTS', 'BIÈRES', 'COCKTAILS'):
            pw.expect(page.get_by_text(group, exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Indisponible pour l’instant', exact=True)).to_be_visible()
        assert page.get_by_role('button', name='Ajouter : Vodka Red Bull').count() == 0
        pw.expect(page.get_by_text('Il en reste 3', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Limite de la soirée : 6 verres par personne (tu en es à 2 verres).', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('4 CHF', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        context.close()


def test_a_free_bar_has_no_price_and_no_pledge(browser, origin):
    context, page, calls, errors = open_bar(browser, origin, '', options={'free_bar': True}, manage=False, serve=False)
    try:
        pw.expect(page.get_by_text('BAR OFFERT', exact=True)).to_be_visible(timeout=15000)
        assert page.get_by_text(re.compile(r'\d CHF$')).count() == 0
        page.get_by_role('button', name='Ajouter : Coca').click()
        page.get_by_role('button', name='Commander', exact=True).click()
        pw.expect(page.get_by_text('Ta commande', exact=True)).to_be_visible()
        assert page.get_by_role('checkbox').count() == 0
        page.get_by_role('button', name='Valider la commande').click()
        page.wait_for_timeout(500)
        order = sent(calls, 'bar_order')[-1]
        assert order['pledge_text'] is None and order['pledge_version'] is None and order['lines'] == [{'item': COCA, 'qty': 1}]
        assert not errors, errors
    finally:
        context.close()


def test_counter_only_the_menu_is_read_only_and_the_pledge_is_accepted_once(browser, origin):
    context, page, calls, errors = open_bar(browser, origin, '', options={'guest_orders': False, 'counter_serve': True},
                                            manage=False, serve=False)
    try:
        pw.expect(page.get_by_text('Commande au comptoir : montre ton QR au barman, il te sert directement.', exact=True)).to_be_visible(timeout=15000)
        assert page.get_by_role('button', name=re.compile('^Ajouter : ')).count() == 0
        pw.expect(page.get_by_role('button', name='J’accepte l’engagement')).to_be_disabled()
        page.get_by_role('checkbox').click()
        page.get_by_role('button', name='J’accepte l’engagement').click()
        page.wait_for_timeout(500)
        assert sent(calls, 'bar_pledge')[-1]['pledge_version'] == 1
        assert not errors, errors
    finally:
        context.close()


def test_the_barman_counts_what_is_left_marks_unavailable_and_serves_without_order(browser, origin):
    context, page, calls, errors = open_bar(browser, origin, '/scan', options={'counter_serve': True}, manage=False, serve=True)
    try:
        page.get_by_role('button', name='Ouvrir la carte et le stock').click()
        page.get_by_role('button', name='Il en reste : Coca').click()
        page.get_by_label('Il en reste · Coca').fill('5')
        page.get_by_role('button', name='OK', exact=True).click()
        pw.expect(page.get_by_text('Coca : il en reste 5.', exact=True)).to_be_visible(timeout=10000)
        assert sent(calls, 'bar_item_action')[-1] == {'e': EVENT, 'item': COCA, 'action': 'remaining', 'amount': 5}
        page.get_by_role('button', name='Indisponible : Bière blonde').click()
        page.wait_for_timeout(500)
        assert sent(calls, 'bar_item_action')[-1]['action'] == 'unavailable'
        page.get_by_label('Code du QR').fill('K7M2QX')
        page.get_by_role('button', name='Valider', exact=True).click()
        pw.expect(page.get_by_text('Servir sans commande :', exact=True)).to_be_visible(timeout=10000)
        page.get_by_role('button', name='Ajouter : Coca (sans commande)').click()
        page.get_by_role('button', name='Ajouter : Coca (sans commande)').click()
        page.get_by_role('button', name='Servir 2 articles · 4 CHF').click()
        pw.expect(page.get_by_text('Servi à Léa', exact=True)).to_be_visible(timeout=10000)
        assert sent(calls, 'bar_serve')[-1]['lines'] == [{'item': COCA, 'qty': 0, 'extra': 2}]
        assert not errors, errors
    finally:
        context.close()
