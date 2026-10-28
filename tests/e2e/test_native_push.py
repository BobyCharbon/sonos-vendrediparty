"""App iOS native : les notifications passent par Apple (APNs) au lieu de Web Push, absent d'une WKWebView.
push.js garde la même interface pour les pages (supported, permission, current, subscribe, unsubscribe) ;
on simule le pont natif (window.PartyNative.push, NativeBridge.swift) et on capture ce que le site envoie."""
import json

import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import Server

TOKEN = "ab" * 32
NATIVE_PUSH = """
window.__nativeStatus = "default";
window.PartyNative = { platform: "ios", push: {
  register: async () => { window.__nativeStatus = "granted";
                          return { token: "%s", environment: "production", bundleId: "ch.bobycharbon.party" }; },
  status: async () => ({ status: window.__nativeStatus }),
} };
""" % TOKEN


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(base_url=server.url)
    ctx.add_init_script(NATIVE_PUSH)
    page = ctx.new_page()
    page.posted = []

    def capture(route):
        page.posted.append((route.request.url.split("/api/")[1], json.loads(route.request.post_data or "{}")))
        route.fulfill(status=200, content_type="application/json", body='{"ok": true}')

    page.route("**/api/push/subscribe", capture)
    page.route("**/api/push/unsubscribe", capture)
    page.goto("/")
    yield page
    ctx.close()


def test_native_app_supports_notifications_without_web_push(page):
    assert page.evaluate("Push.supported()")
    assert page.evaluate("Push.permission()") == "default"
    assert page.evaluate("Push.current('/')") is None


def test_subscribing_registers_the_device_with_apple_and_the_server(page):
    endpoint = page.evaluate("Push.subscribe('/', '/api/push/subscribe', { guest_id: 'g1' }).then((s) => s.endpoint)")
    assert endpoint == f"apns:{TOKEN}"
    [(path, body)] = page.posted
    assert path == "push/subscribe" and body["guest_id"] == "g1"
    assert body["subscription"] == {"endpoint": f"apns:{TOKEN}", "apns": {
        "token": TOKEN, "environment": "production", "topic": "ch.bobycharbon.party"}}
    assert page.evaluate("Push.permission()") == "granted"
    # Comme un abonnement Web Push : current() le retrouve et toJSON() le redonne tel quel.
    assert page.evaluate("Push.current('/').then((s) => s.toJSON().endpoint)") == f"apns:{TOKEN}"


def test_unsubscribing_forgets_the_device(page):
    page.evaluate("Push.subscribe('/', '/api/push/subscribe', { guest_id: 'g1' })")
    page.evaluate("Push.unsubscribe('/')")
    assert page.posted[-1] == ("push/unsubscribe", {"endpoint": f"apns:{TOKEN}"})
    assert page.evaluate("Push.current('/')") is None


def test_refusal_is_reported_like_on_the_web(page):
    page.evaluate("""() => { PartyNative.push.register = async () => { window.__nativeStatus = "denied";
                                                                    throw new Error("Notifications refusées"); }; }""")
    message = page.evaluate("Push.subscribe('/', '/api/push/subscribe', {}).then(() => '', (e) => e.message)")
    assert "refusées" in message
    assert page.evaluate("Push.permission()") == "denied"
    assert page.posted == []


def test_reopening_the_page_does_not_turn_my_choices_back_on(page):
    """Retour PartyTEST : les notifications coupées revenaient à chaque ouverture. La page réassocie l'appareil
    à l'invité à chaque arrivée : ce renvoi ne doit jamais rallumer « Mon titre passe » (keep_prefs)."""
    page.evaluate("Push.subscribe('/', '/api/push/subscribe', { guest_id: 'g1' })")
    page.posted.clear()
    page.evaluate("initNotifications()")
    page.wait_for_timeout(300)
    [(path, body)] = page.posted
    assert path == "push/subscribe" and body["keep_prefs"] is True
