"""Noms des contacts (avis f780431defe7) dans le vrai module Événements (navigateur, Supabase simulé) :
- app iPhone : le pont natif donne { compte : nom du contact } → « Nom du contact · pseudo » (participants, fiche) ;
- ailleurs (pas de pont) : le pseudo, rien d'autre ;
- fiche d'un membre : « Ajouter aux contacts » télécharge une vCard 3.0 valide et échappée, jamais sans numéro visible ;
  dans l'app, la fiche Contacts d'Apple (pont natif) au lieu du téléchargement.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json
import re

import pytest

from tests.test_event_tickets_browser import DIST, LEA, LEA_YES, MINE_YES, origin, shot, tickets_backend, with_rsvps  # noqa: F401
from tests.test_events_browser import browser, login, mock_services  # noqa: F401 (fixture browser)

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

CONTACT = 'Léa Martin'
RPC = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
BRIDGE = """window.PartyNative = { platform: 'ios', contacts: {
  names: () => Promise.resolve({ '%s': '%s' }),
  add: (p) => { (window.top.__added = window.top.__added || []).push(p); return Promise.resolve(true); } } };""" % (LEA, CONTACT)


def card(phone='41790000001', **extra):
    return {'id': LEA, 'display_name': 'Léa', 'avatar_url': None, 'role': 'member', 'root': False, 'me': False,
            'first_name': 'Léa;', 'last_name': 'Mar,tin', 'phone': phone, 'groups': ['Rando'], **extra}


def launch(browser, origin, native: bool, member=None):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, accept_downloads=True)
    page = context.new_page()
    if native:
        page.add_init_script(BRIDGE)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}])
    with_rsvps(page, [MINE_YES, LEA_YES])
    tickets_backend(page)
    if member is not None:
        page.route(RPC + 'member_card', lambda r: r.fulfill(status=204 if r.request.method == 'OPTIONS' else 200, headers=HEADERS,
                                                           content_type='application/json', body=json.dumps(member)))
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    return context, page, frame, errors


def open_member(page, frame):
    """Fiche de Léa : depuis « Qui vient ? » de l'événement (sa pastille ouvre son profil)."""
    frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    frame.get_by_role('button', name=re.compile(r'^Profil de (Léa|Léa Martin · Léa)')).first.click()


def test_in_the_app_participants_show_the_contact_name_then_the_pseudo(browser, origin):
    context, page, frame, errors = launch(browser, origin, native=True)
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        pw.expect(frame.get_by_text('Qui vient ?', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text(f'{CONTACT} · Léa', exact=False).first).to_be_visible(timeout=10000)
        frame.get_by_text(f'{CONTACT} · Léa', exact=False).first.scroll_into_view_if_needed()
        page.wait_for_timeout(800)  # fin des apparitions
        shot(page, 'contacts-participants')
        assert not errors
    finally:
        context.close()


def test_outside_the_app_the_pseudo_stays(browser, origin):
    context, page, frame, errors = launch(browser, origin, native=False)
    try:
        frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        pw.expect(frame.get_by_text('Qui vient ?', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(500)
        assert frame.get_by_text(CONTACT, exact=False).count() == 0
        pw.expect(frame.get_by_text('Léa', exact=False).first).to_be_visible()
        assert not errors
    finally:
        context.close()


def test_member_card_downloads_an_escaped_vcard(browser, origin, tmp_path):
    context, page, frame, errors = launch(browser, origin, native=False, member=card())
    try:
        open_member(page, frame)
        button = frame.get_by_text('Ajouter aux contacts', exact=True)
        pw.expect(button).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        shot(page, 'contacts-fiche-web')
        with page.expect_download() as got:
            button.click()
        path = tmp_path / 'lea.vcf'
        got.value.save_as(path)
        text = path.read_bytes().decode('utf-8')
        assert got.value.suggested_filename.endswith('.vcf')
        assert text.startswith('BEGIN:VCARD\r\nVERSION:3.0\r\n') and text.endswith('END:VCARD\r\n')
        assert 'N:Mar\\,tin;Léa\\;;;;\r\n' in text  # « Léa; » échappé, puis les 3 champs vides and 'FN:Léa\\; Mar\\,tin\r\n' in text
        assert 'NICKNAME:Léa\r\n' in text and 'TEL;TYPE=CELL:+41790000001\r\n' in text
        assert not errors
    finally:
        context.close()


def test_no_button_without_a_visible_number(browser, origin):
    context, page, frame, errors = launch(browser, origin, native=False, member=card(phone=None))
    try:
        open_member(page, frame)
        pw.expect(frame.get_by_text('ne montre pas son numéro', exact=False)).to_be_visible(timeout=15000)
        assert frame.get_by_text('Ajouter aux contacts', exact=True).count() == 0
        assert not errors
    finally:
        context.close()


def test_in_the_app_the_card_uses_the_contact_name_and_known_contacts_have_no_add_button(browser, origin):
    context, page, frame, errors = launch(browser, origin, native=True, member=card())
    try:
        open_member(page, frame)
        pw.expect(frame.get_by_text(CONTACT, exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('Léa · dans tes contacts', exact=True)).to_be_visible()
        assert frame.get_by_text('Ajouter aux contacts', exact=True).count() == 0  # déjà dans le répertoire
        page.wait_for_timeout(800)
        shot(page, 'contacts-fiche-app')
        assert not errors
    finally:
        context.close()


def test_in_the_app_adding_hands_the_card_to_apple_contacts(browser, origin):
    context, page, frame, errors = launch(browser, origin, native=True, member={**card(), 'id': LEA.replace('a11', 'b22')})
    try:
        open_member(page, frame)
        frame.get_by_text('Ajouter aux contacts', exact=True).click()
        page.wait_for_function('window.__added && window.__added.length === 1', timeout=10000)
        added = page.evaluate('window.__added[0]')
        assert added == {'phone': '+41790000001', 'firstName': 'Léa;', 'lastName': 'Mar,tin', 'nickname': 'Léa'}
        assert not errors
    finally:
        context.close()
