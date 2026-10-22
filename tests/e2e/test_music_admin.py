"""Pilotage de la musique dans l'onglet Musique de l'app (compte admin), sans passer par /admin.
Pas de vraies enceintes en test : les réponses du serveur pour la soirée en cours sont simulées
(état, recherche, ajout, file) ; on vérifie les vrais boutons de l'onglet et ce qu'ils envoient."""
import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, Phone, Server  # noqa: E402

TRACK = {"title": "Titre en cours", "artist": "Artiste", "art": "", "by": "Léa"}
QUEUE = [{"pos": 2, "key": "k2", "title": "Deuxième", "artist": "A2", "art": "", "by": "Léa", "eta": 120},
         {"pos": 3, "key": "k3", "title": "Troisième", "artist": "A3", "art": "", "by": None, "eta": 300}]


def live_state(queue=QUEUE):
    return {"active": True, "source": "sonos", "mode": "next", "room_name": "Salon", "sonos_error": None,
            "sonos": {"state": "PLAYING", "now": TRACK, "volume": 30, "from_queue": True}, "queue": queue,
            "requests": [{"id": "r1", "title": "Deuxième", "artist": "A2", "image": "", "guest_name": "Léa", "added_at": 1761120000, "status": "queued"}],
            "top_playlists": [{"id": "spotify:playlist:abc", "title": "Apéro"}], "spotify_account": {"connected": False},
            "guest_pin": "4821", "guest_url": "https://partytest.bobycharbon.ch/"}


@pytest.fixture
def server():
    s = Server()
    yield s
    s.stop()


def as_account_admin(phone):
    """Compte Party admin connecté (session admin + compte admin) ; la vérification Supabase est testée ailleurs."""
    phone.page.request.post(f"{phone.server.url}/api/admin/login", data={"pin": ADMIN_PIN})
    phone.page.evaluate("account = { name: 'Boss', admin: true }; adminSession = true; fbSyncRole();")


def test_admin_starts_the_party_from_the_music_tab_and_guests_keep_their_page(browser, server):
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Boss")
    try:
        guest.page.goto("/")
        guest.page.locator('#tabs button[data-tab="music"]').tap()
        assert guest.page.locator("#musicAdmin").is_hidden()  # un invité garde sa page Musique

        boss.page.goto("/")
        as_account_admin(boss)
        boss.page.locator('#tabs button[data-tab="music"]').tap()
        admin = boss.page.locator("#musicAdmin")
        expect(admin.get_by_role("button", name="🎉 Démarrer la soirée")).to_be_visible()
        expect(admin.get_by_text("Party maison")).to_be_visible()
        # Party maison = file Sonos native : pas de compte Spotify à connecter, mode d'insertion au choix.
        expect(admin.get_by_text("depuis l'app Sonos")).to_be_visible()
        expect(admin.locator('[data-ma="spotifyStart"]')).to_be_hidden()
        expect(admin.locator('[data-ma="setup"] [data-ma-mode="fair"]')).to_be_visible()
        assert boss.page.locator("#pin").is_hidden() and boss.page.locator("#closed").is_hidden()
        admin.locator('[data-ma-src="spotify"]').tap()  # extérieur : pas de mode d'insertion (Spotify gère)
        expect(admin.locator('[data-ma="srcSpotify"]')).to_be_visible()
        expect(admin.locator('[data-ma="setup"] [data-ma="modes"]')).to_be_hidden()
        expect(admin.locator('[data-ma="spotifyStart"]')).to_be_visible()
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()


def test_admin_drives_the_live_party_from_the_music_tab(browser, server):
    boss = Phone(browser, server, "Boss")
    sent = []
    state = {"queue": list(QUEUE)}

    def admin_api(route):
        path = route.request.url.split("/api/admin/", 1)[1].split("?")[0]
        body = json.loads(route.request.post_data or "{}")
        sent.append((path, body))
        if path == "search":
            return route.fulfill(json=[{"id": "t9", "title": "Nouveau son", "artist": "A9", "image": ""}])
        if path == "queue" and body.get("action") == "remove":
            state["queue"] = [t for t in state["queue"] if t["key"] != body["key"]]
            return route.fulfill(json={**live_state(state["queue"]), "undo": "u1"})
        if path == "speakers":
            return route.fulfill(json=[{"uid": "s1", "name": "Salon", "in_group": True, "coordinator": True, "volume": 30}])
        return route.fulfill(json=live_state(state["queue"]))
    try:
        boss.page.goto("/")
        as_account_admin(boss)
        boss.page.route("**/api/admin/**", admin_api)
        boss.page.locator('#tabs button[data-tab="music"]').tap()
        admin = boss.page.locator("#musicAdmin")
        expect(admin.locator('[data-ma="now"]')).to_contain_text("Titre en cours")
        expect(admin.locator('[data-ma="queue"]')).to_contain_text("Troisième")
        expect(admin.locator('[data-ma="requests"]')).to_contain_text("Léa")
        expect(admin.locator('[data-ma="top"]')).to_contain_text("Apéro")

        # Code et QR des invités : repliés (pas de place perdue), le code reste visible dans le titre.
        expect(admin.locator('[data-ma="access"] summary')).to_contain_text("4821")
        expect(admin.locator('[data-ma="qr"]')).to_be_hidden()
        admin.locator('[data-ma="access"] summary').tap()
        expect(admin.locator('[data-ma="qr"]')).to_be_visible()
        expect(admin.locator('[data-ma="guestUrl"]')).to_have_text("https://partytest.bobycharbon.ch/?pin=4821")
        boss.page.once("dialog", lambda d: d.accept())
        admin.locator('[data-ma="pinCustom"]').fill("12a4")
        expect(admin.locator('[data-ma="pinCustom"]')).to_have_value("124")  # chiffres seulement
        admin.locator('[data-ma="pinCustom"]').fill("1234")
        admin.locator('[data-ma="pinForm"] button').tap()
        assert ("pin", {"pin": "1234"}) in sent

        # Retirer un titre de la file : il disparaît, avec « Annuler » dans le message.
        admin.locator('[data-ma-q="remove"][data-key="k3"]').tap()
        expect(admin.locator('[data-ma="queue"]')).not_to_contain_text("Troisième")
        expect(boss.page.locator("#toast")).to_contain_text("Titre retiré")
        expect(boss.page.locator("#toast button")).to_have_text("Annuler")

        # Ajouter un titre : recherche, puis ⏫ « jouer ensuite ».
        admin.locator('[data-ma="addQ"]').fill("nouveau")
        admin.locator('[data-ma-add="next"]').tap()
        expect(boss.page.locator("#toast")).to_contain_text("passera juste après")
        assert ("add", {"track_id": "t9", "where": "next", "force": False}) in sent

        # Pause et mode d'insertion.
        admin.locator('[data-ma-act="playpause"]').tap()
        admin.locator('[data-ma="live"] [data-ma-mode="fair"]').tap()
        assert ("playback", {"action": "pause"}) in sent and ("mode", {"mode": "fair"}) in sent
        assert not boss.errors, boss.errors
    finally:
        boss.close()
