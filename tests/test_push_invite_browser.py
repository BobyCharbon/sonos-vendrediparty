"""Notifications proposées à qui a installé Party en app web (retour de l'admin du 11.11.2026) : des amis l'ont mise sur
l'écran d'accueil (Safari iPhone, Android) sans jamais activer les notifications. Une petite fenêtre le propose en
arrivant dans les Événements, jamais dans les autres onglets (Réglages partage pourtant le même cadre), jamais dans un
simple navigateur. « Plus tard » : pas avant une semaine. Vrai module construit, Supabase simulé."""
import json

import pytest

from tests.test_events_browser import DIST, browser, events_origin, login, mock_services  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')

TITLE = 'Ne rate aucune soirée'
# App web sur l'écran d'accueil ; la demande du système est simulée (réponse dans window.__answer).
INSTALLED = """
const realMatch = window.matchMedia.bind(window);
window.matchMedia = (q) => q.includes('display-mode: standalone')
  ? { matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} } : realMatch(q);
window.__asked = 0;
let state = 'default';
Object.defineProperty(Notification, 'permission', { get: () => state, configurable: true });
Notification.requestPermission = () => { window.__asked += 1; state = window.__answer || 'denied'; return Promise.resolve(state); };
"""


def open_party(browser, origin, installed=True, memory=None):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    if installed:
        context.add_init_script(INSTALLED)
    if memory is not None:
        context.add_init_script(f"localStorage.setItem('vp_push_invite', {json.dumps(json.dumps(memory))})")
    page = context.new_page()
    mock_services(page)
    page.goto(origin, wait_until='domcontentloaded')
    return context, page, page.frame_locator('#eventsFrame')


def to_events_and_sign_in(page, frame):
    page.locator('#tabs [data-tab="events"]').click()
    login(frame)
    pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)


def test_installed_web_app_proposes_notifications_in_events_and_later_waits_a_week(browser, events_origin):
    context, page, frame = open_party(browser, events_origin)
    try:
        to_events_and_sign_in(page, frame)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_be_visible(timeout=10000)
        pw.expect(frame.get_by_role('button', name='Activer les notifications', exact=True)).to_be_visible()
        frame.get_by_role('button', name='Plus tard', exact=True).click()
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)
        memory = json.loads(page.evaluate("localStorage.getItem('vp_push_invite')"))
        assert memory['asks'] == 1 and memory['last'] > 0
        page.reload(wait_until='domcontentloaded')
        page.locator('#tabs [data-tab="events"]').click()
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)  # pas avant une semaine
    finally:
        context.close()


def test_activate_asks_the_system_and_a_refusal_is_explained_then_never_asked_again(browser, events_origin):
    context, page, frame = open_party(browser, events_origin)
    try:
        to_events_and_sign_in(page, frame)
        frame.get_by_role('button', name='Activer les notifications', exact=True).click(timeout=10000)
        pw.expect(frame.get_by_text('Notifications non autorisées', exact=False)).to_be_visible(timeout=10000)
        assert frame.locator('body').evaluate('() => window.__asked') == 1
        frame.get_by_role('button', name='Plus tard', exact=True).click()
        page.reload(wait_until='domcontentloaded')
        page.locator('#tabs [data-tab="events"]').click()
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)
    finally:
        context.close()


def test_never_in_settings_only_once_on_the_events_tab(browser, events_origin):
    """Réglages s'affiche dans le même cadre que les Événements : la fenêtre attend l'onglet Événements."""
    context, page, frame = open_party(browser, events_origin)
    try:
        page.locator('#tabs [data-tab="account"]').click()
        login(frame)
        pw.expect(frame.get_by_role('button', name='Recevoir un code par SMS')).to_have_count(0, timeout=15000)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)
        page.locator('#tabs [data-tab="events"]').click()
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_be_visible(timeout=10000)
    finally:
        context.close()


def test_a_plain_browser_is_never_asked(browser, events_origin):
    context, page, frame = open_party(browser, events_origin, installed=False)
    try:
        to_events_and_sign_in(page, frame)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)
    finally:
        context.close()


def test_three_later_and_it_stops_for_good(browser, events_origin):
    context, page, frame = open_party(browser, events_origin, memory={'asks': 3, 'last': 1})
    try:
        to_events_and_sign_in(page, frame)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)
    finally:
        context.close()


def test_the_native_iphone_app_keeps_its_own_notifications(browser, events_origin):
    """App iPhone (PartyNative) : ses notifications sont natives, la fenêtre web ne s'y affiche jamais."""
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    context.add_init_script(INSTALLED + "window.PartyNative = { tabs: { update() {} } };")
    page = context.new_page()
    mock_services(page)
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        frame = page.frame_locator('#eventsFrame')
        page.evaluate("PartyTabs.select('events')")  # barre d'onglets native de l'app
        login(frame)
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(2500)
        pw.expect(frame.get_by_text(TITLE, exact=True)).to_have_count(0)
    finally:
        context.close()
