"""Bandeau « Active les notifications » en haut d'un événement (avis c77d117ab172 de l'admin, 13.11.2026), vrai navigateur
(Supabase simulé) : notifications éteintes → bandeau ; « Plus tard » le cache ; app iPhone (pont PartyNative simulé) :
« Activer » demande à iOS et le bandeau disparaît ; refusées → « Ouvrir les réglages »."""
import json
import os
from pathlib import Path

import pytest

from tests.test_event_participant_browser import event_row, open_event, rsvp
from tests.test_events_browser import DIST, USER, browser, events_origin  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SHOTS = Path(os.environ['NOTIFY_SHOTS']) if os.environ.get('NOTIFY_SHOTS') else None
TITLE = 'Ne rate rien de cet événement'


def native(status: str) -> str:
    """Pont de l'app iPhone (NativeBridge.swift) : status() puis enable() → « granted » (ou reste refusé)."""
    return """window.__enabled = 0; window.PartyNative = { platform: 'ios', push: {
      status: () => Promise.resolve({ status: window.__enabled ? 'granted' : '%s' }),
      enable: () => { window.__enabled = '%s' === 'denied' ? 0 : 1; window.__asked = true;
                      return Promise.resolve({ status: window.__enabled ? 'granted' : 'denied' }); },
      register: () => Promise.reject(new Error('non')) } };""" % (status, status)


def test_web_banner_offers_notifications_and_later_hides_it(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        # Jamais demandé (le Chromium des tests refuse d'office) : « Activer ».
        page.add_init_script("Object.defineProperty(Notification, 'permission', { get: () => 'default' });")
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Activer les notifications')).to_be_visible()
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / '01-bandeau-web.png'))
        # En haut : au-dessus du titre de l'événement.
        assert page.get_by_text(TITLE, exact=True).bounding_box()['y'] < page.get_by_role('heading', level=1).bounding_box()['y']
        page.get_by_role('button', name='Plus tard').click()
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_role('heading', level=1)).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)  # caché 24 h
    finally:
        context.close()


def test_iphone_app_enable_asks_ios_and_the_banner_goes_away(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.add_init_script(native('default'))
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Continuer', exact=True).click()
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0, timeout=5000)
        assert page.evaluate('window.__asked') is True
    finally:
        context.close()


def test_iphone_app_blocked_opens_the_settings(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.add_init_script(native('denied'))
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Tes notifications sont bloquées', exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Ouvrir les réglages').click()
        page.wait_for_timeout(300)
        assert page.evaluate('window.__asked') is True
    finally:
        context.close()


def test_already_on_no_banner(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    try:
        page.add_init_script(native('granted'))
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_role('heading', level=1)).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)
    finally:
        context.close()


def test_web_blocked_says_where_to_allow_them(browser, events_origin):  # noqa: F811
    context, page = open_event(browser, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))  # refusées par défaut
    try:
        pw.expect(page.get_by_text('Tes notifications sont bloquées', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('le cadenas à côté de l’adresse', exact=False)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Activer les notifications')).to_have_count(0)
    finally:
        context.close()


# « Activer » sur le web, pour de vrai : autorisation du navigateur, vrai service worker /sw.js inscrit sur la portée du
# module (/events/), appareil enregistré dans la base (register_web_push), puis plus de bandeau. Faux : Supabase et
# pushManager.subscribe (le Chromium des tests n'a pas de service push).
RPC = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
KEY = 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM'
ENDPOINT = 'https://fcm.googleapis.com/fcm/send/appareil-de-test'
SUBSCRIBE = """(() => {
  if (typeof PushManager === "undefined") return;
  const sub = { endpoint: "%s", toJSON: () => ({ endpoint: "%s", expirationTime: null,
    keys: { p256dh: "BA", auth: "AA" } }), unsubscribe: async () => true };
  PushManager.prototype.getSubscription = async () => (localStorage.getItem("fake_sub") ? sub : null);
  PushManager.prototype.subscribe = async (options) => {
    window.__serverKey = btoa(String.fromCharCode(...new Uint8Array(options.applicationServerKey)));
    localStorage.setItem("fake_sub", "1");
    return sub; };
})();""" % (ENDPOINT, ENDPOINT)


@pytest.fixture(scope='module')
def chromium(request):
    """Chromium complet sans fenêtre : le « headless shell » refuse toute permission de notification."""
    try:
        p, owned = request.getfixturevalue('playwright'), None
    except pytest.FixtureLookupError:
        p = owned = pw.sync_playwright().start()
    b = p.chromium.launch(channel='chromium')
    yield b
    b.close()
    if owned:
        owned.stop()


def test_web_enable_registers_this_browser_and_the_banner_goes_away(chromium, events_origin):  # noqa: F811
    context, page = open_event(chromium, events_origin, event_row(rsvps=[rsvp(USER, 'yes')]))
    registered, errors = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))

    def rpc(route):
        name = route.request.url.split('/rpc/')[1].split('?')[0]
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        if name == 'register_web_push':
            registered.append(json.loads(route.request.post_data))
        answers = {'get_web_push_public_key': KEY, 'register_web_push': None, 'web_push_device_status': bool(registered)}
        if name not in answers:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(answers[name]), headers=HEADERS)
    try:
        context.grant_permissions(['notifications'], origin=events_origin)
        page.add_init_script(SUBSCRIBE)
        page.route(RPC + '**', rpc)
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Activer les notifications').click()
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0, timeout=15000)
        [args] = registered
        assert args == {'device_subscription': {'endpoint': ENDPOINT, 'expirationTime': None, 'keys': {'p256dh': 'BA', 'auth': 'AA'}},
                        'device_origin': events_origin}
        scope = "navigator.serviceWorker.getRegistration('/events/').then((r) => r && new URL(r.scope).pathname)"
        assert page.evaluate(scope) == '/events/'
        assert page.evaluate("window.__serverKey") == page.evaluate(
            f"btoa(atob('{KEY}'.replace(/-/g, '+').replace(/_/g, '/') + '='))")
        # Fiche rouverte : cet appareil est inscrit, plus de bandeau.
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_role('heading', level=1)).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        pw.expect(page.get_by_text(TITLE, exact=True)).to_have_count(0)
        assert not errors, errors
    finally:
        context.close()
