"""Liens cliquables dans les textes d'un événement (avis 2c221fd8effc), dans le vrai module Événements (navigateur,
Supabase simulé) : description, infos de paiement et message de la discussion d'événement.
- une adresse web est un vrai lien <a> (nouvel onglet, rel noopener noreferrer) ;
- un numéro ou un e-mail ouvre la fenêtre principale (tel:/mailto:, jamais chargés dans l'iframe) ;
- javascript:, data: et le HTML écrit dans le texte restent du texte (rien d'injecté, aucun script exécuté) ;
- un lien de lieu (location_url) dangereux n'est jamais ouvert : on retombe sur la recherche Plans.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json
import re

import pytest

from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services  # noqa: F401 (fixtures)

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
TRAP = '<img src=x onerror="window.top.__pwned=1"><b>gras</b>'
DESCRIPTION = (f'Programme : https://exemple.ch/programme. Questions à ana@exemple.ch ou au 079 123 45 67. '
               f'Pas un lien : javascript:window.top.__pwned=2 ni data:text/html,x. {TRAP}')
PAYMENT = 'TWINT ou page de paiement www.paye.example/vendredi'
MESSAGE = 'Photos ici : https://photos.example/album, merci !'


def event_with_links(page):
    category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
    event = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': DESCRIPTION, 'created_by': USER,
             'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
             'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
             'location_address': 'Rue du Test 1, Genève', 'location_url': 'javascript:window.top.__pwned=3',
             'category_id': category['id'], 'category': category, 'event_tags': [], 'date_options': [], 'rsvps': [],
             'event_organizers': [], 'polls': [], 'bring_items': [], 'event_groups': [], 'author': {'display_name': 'Compte de démonstration'},
             'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None,
             'rsvp_deadline': None, 'forum_enabled': True, 'all_day': False, 'price_chf': 15, 'payment_info': PAYMENT, 'visibility': 'all'}
    message = {'id': '6a1f0c55-8a43-4c1b-9d2e-0b8f1d9c7e01', 'event_id': EVENT, 'user_id': USER, 'body': MESSAGE, 'reply_to': None,
               'mentions': [], 'pinned': False, 'created_at': '2026-11-03T18:00:00Z', 'deleted_at': None}

    def events(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        single = 'id=eq.' in route.request.url
        route.fulfill(status=200, content_type='application/json', body=json.dumps(event if single else [event]), headers=HEADERS)

    def messages(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        route.fulfill(status=200, content_type='application/json', body=json.dumps([message]), headers=HEADERS)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/events?**', events)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/messages?**', messages)


def open_event(browser, origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    # Pages externes ouvertes par les liens : servies vides (aucune requête réelle).
    context.route(re.compile(r'https://(exemple\.ch|maps\.apple\.com|photos\.example|www\.paye\.example)/.*'),
                  lambda r: r.fulfill(status=200, content_type='text/html', body='<title>externe</title>'))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: (errors.append(f'dialog {d.message}'), d.dismiss()))
    mock_services(page)
    event_with_links(page)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    pw.expect(frame.get_by_text('À propos', exact=True)).to_be_visible(timeout=15000)
    return context, page, frame, errors


def test_description_and_payment_links_are_real_safe_links(browser, events_origin):
    context, page, frame, errors = open_event(browser, events_origin)
    try:
        web = frame.locator('a[href="https://exemple.ch/programme"]')
        pw.expect(web).to_have_count(1)
        assert web.inner_text() == 'https://exemple.ch/programme'  # le point final reste du texte
        assert web.get_attribute('target') == '_blank' and set(web.get_attribute('rel').split()) >= {'noopener', 'noreferrer'}
        mail = frame.locator('a[href="mailto:ana@exemple.ch"]')
        phone = frame.locator('a[href="tel:0791234567"]')
        pw.expect(mail).to_have_count(1)
        pw.expect(phone).to_have_count(1)
        assert mail.get_attribute('target') == '_top' and phone.get_attribute('target') == '_top'
        pay = frame.locator('a[href="https://www.paye.example/vendredi"]')
        pw.expect(pay).to_have_count(1)
        assert pay.inner_text() == 'www.paye.example/vendredi'
        # Aucun lien dangereux, le HTML écrit reste du texte visible, rien ne s'exécute.
        hrefs = frame.locator('a[href]').evaluate_all('els => els.map(e => e.getAttribute("href"))')
        assert not [h for h in hrefs if re.match(r'\s*(javascript|data|vbscript):', h, re.I)]
        pw.expect(frame.get_by_text(TRAP, exact=False)).to_be_visible()
        assert frame.locator('img[src="x"]').count() == 0 and frame.locator('b', has_text='gras').count() == 0
        pw.expect(frame.get_by_text('javascript:window.top.__pwned=2', exact=False)).to_be_visible()
        # Le lien suit la couleur d'accent et reste souligné (lisible sur fond sombre).
        assert 'underline' in web.evaluate('e => getComputedStyle(e).textDecorationLine')
        # Un clic ouvre un nouvel onglet, la page Party reste en place.
        with context.expect_page() as opened:
            web.click()
        popup = opened.value
        assert popup.url.startswith('https://exemple.ch/programme') or popup.url == 'about:blank'
        popup.close()
        assert page.evaluate('window.__pwned') is None
        assert not errors
    finally:
        context.close()


def test_dangerous_place_link_falls_back_to_maps_search(browser, events_origin):
    context, page, frame, errors = open_event(browser, events_origin)
    try:
        with context.expect_page() as opened:
            frame.get_by_text('Itinéraire ›', exact=True).click()
        assert opened.value.url.startswith('https://maps.apple.com/')
        opened.value.close()
        assert page.evaluate('window.__pwned') is None
        assert not errors
    finally:
        context.close()


def test_event_chat_message_link_is_clickable(browser, events_origin):
    context, page, frame, errors = open_event(browser, events_origin)
    try:
        frame.get_by_text('Ouvrir ›', exact=True).click()
        link = frame.locator('a[href="https://photos.example/album"]')
        pw.expect(link).to_have_count(1, timeout=15000)
        assert link.inner_text() == 'https://photos.example/album'  # la virgule reste du texte
        assert link.get_attribute('target') == '_blank'
        assert not errors
    finally:
        context.close()
