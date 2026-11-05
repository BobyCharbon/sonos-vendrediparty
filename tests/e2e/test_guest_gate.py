"""Compte progressivement obligatoire (vrai navigateur) : Léa, invitée sans compte, voit « Garde tes scores » après sa
1re partie, peut encore jouer jusqu'à la limite réglée par l'admin, puis une nouvelle partie lui demande un compte ;
« Créer mon compte » ouvre la connexion et, une fois le compte relié, elle revient directement dans la partie."""
import httpx
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, FakeSupabase, Phone, Server, sign_in, wait_state  # noqa: E402

HOST = "acct-" + "2" * 40  # l'animateur a un compte : ses parties ne comptent pas


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    errors = s.errors()
    s.stop()
    supabase.stop()
    assert not errors, errors[-3000:]


def admin(server) -> httpx.Client:
    c = httpx.Client(base_url=server.url, timeout=10)
    assert c.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200
    return c


def host_game(server) -> str:
    r = httpx.post(f"{server.url}/api/games", json={"type": "tmc", "guest_id": HOST, "name": "Boby"}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def host_act(server, code, action):
    r = httpx.post(f"{server.url}/api/games/{code}", json={"guest_id": HOST, "name": "Boby", "action": action}, timeout=10)
    assert r.status_code == 200, r.text


def test_soft_message_then_account_required_then_back_in_the_game(browser, server):
    a = admin(server)
    assert a.post("/api/admin/guest-gate", json={"games": 2, "tracks": 2}).status_code == 200
    a.close()
    lea = Phone(browser, server, "Lea")
    try:
        # 1re partie : jouée jusqu'au bout, puis le message doux (non bloquant).
        first = host_game(server)
        lea.join(first)
        wait_state(lea, lambda s: bool(s.get("me")))
        host_act(server, first, "start")
        host_act(server, first, "finish")
        soft = lea.page.locator('#gateModal [data-gate="soft"]')
        expect(soft).to_be_visible(timeout=8000)
        expect(soft).to_contain_text("juste ton numéro")
        soft.locator("[data-gate-later]").click()
        expect(lea.page.locator("#gateModal")).to_be_hidden()

        # 2e partie : encore permise.
        second = host_game(server)
        lea.join(second)
        assert wait_state(lea, lambda s: bool(s.get("me")))["gate"]["played"] == 2

        # 3e partie : compte requis, écran clair, Léa n'est pas inscrite.
        third = host_game(server)
        lea.page.goto(f"/?game={third}")
        gate = lea.page.locator('#gateModal [data-gate="games"]')
        expect(gate).to_be_visible(timeout=8000)
        expect(gate).to_contain_text("2 parties en invité")
        assert not lea.state().get("me")

        # « Créer mon compte » : Réglages › Se connecter, puis le compte relié la ramène dans la partie.
        gate.locator("[data-gate-create]").click()
        expect(lea.page.locator("body")).to_have_attribute("data-tab", "account")
        sign_in(lea, "jeton-de-test-guest-plus-0001")
        lea.page.wait_for_function("localStorage.getItem('vp_guest').startsWith('acct-')")
        expect(lea.page.locator("body")).to_have_attribute("data-tab", "games", timeout=8000)
        account = lea.page.evaluate("localStorage.getItem('vp_guest')")
        lea.page.wait_for_function(
            """([code, gid]) => fetch(`/api/games/${code}?guest_id=${gid}`).then((r) => r.json()).then((s) => !!s.me)""",
            arg=[third, account], timeout=8000)
        assert lea.errors == []
    finally:
        lea.close()


def test_music_shows_the_guest_limit_and_the_account_screen(browser, server):
    lea = Phone(browser, server, "Lea")
    try:
        lea.page.goto("/")
        # État de la soirée tel que /api/state l'envoie (une vraie soirée demande des enceintes Sonos) ;
        # le serveur, lui, est testé dans tests/test_guest_gate.py.
        lea.page.evaluate("GuestGate.music({ used: 1, limit: 3, left: 2 })")
        note = lea.page.locator("#guestTracks")
        expect(note).to_contain_text("encore 2 titres")
        lea.page.evaluate("GuestGate.music({ used: 3, limit: 3, left: 0 })")
        expect(note).to_contain_text("Tu as proposé tes 3 titres")
        lea.page.evaluate("""GuestGate.refused({ detail: { account_required: "music", limit: 3, used: 3, left: 0,
          message: "Tu as proposé tes 3 titres" } })""")
        sheet = lea.page.locator('#gateModal [data-gate="music"]')
        expect(sheet).to_be_visible()
        sheet.locator("[data-gate-create]").click()
        expect(lea.page.locator("body")).to_have_attribute("data-tab", "account")
        assert lea.errors == []
    finally:
        lea.close()
