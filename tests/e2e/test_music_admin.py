"""Pilotage de la musique dans l'onglet Musique de l'app (compte admin), sans passer par /admin.
Pas de vraies enceintes en test : les réponses du serveur pour la soirée en cours sont simulées
(état, recherche, ajout, file) ; on vérifie les vrais boutons de l'onglet et ce qu'ils envoient."""
import json
import time

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
            "guest_pin": "4821", "guest_url": "https://partytest.bobycharbon.ch/",
            "guests": [{"guest_id": "g-online-0001", "name": "Zoé", "via": ["music", "games"], "last_seen": time.time(), "joined_at": 0, "active_at": 0},
                       {"guest_id": "g-gone-00001", "name": "Parti", "via": ["music"], "last_seen": 0, "joined_at": 0, "active_at": 0}]}


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
        expect(admin.locator('[data-ma="queue"]')).not_to_contain_text("Troisième")  # playlist réduite par défaut
        admin.locator('[data-ma-act="queueAll"]').tap()
        expect(admin.locator('[data-ma="queue"]')).to_contain_text("Troisième")
        expect(admin.locator('[data-ma="requests"]')).to_contain_text("Léa")
        expect(admin.locator('[data-ma="top"]')).to_contain_text("Apéro")

        # Code et QR des invités : repliés (pas de place perdue), le code reste visible dans le titre.
        expect(admin.locator('[data-ma="access"] summary')).to_contain_text("4821")
        expect(admin.locator('[data-ma="qr"]')).to_be_hidden()
        admin.locator('[data-ma="access"] summary').tap()
        expect(admin.locator('[data-ma="qr"]')).to_be_visible()
        expect(admin.locator('[data-ma="guestUrl"]')).to_have_text("https://partytest.bobycharbon.ch/?pin=4821")
        # Sous le QR : les invités connectés en ce moment (pas ceux partis), aussi comptés dans le titre.
        expect(admin.locator('[data-ma="online"]')).to_contain_text("Zoé")
        expect(admin.locator('[data-ma="online"]')).not_to_contain_text("Parti")
        expect(admin.locator('[data-ma="access"] summary')).to_contain_text("👥 1")
        # Mêmes actions que dans Réglages, directement sur un invité connecté.
        admin.locator('[data-ma="online"] [data-pa-guest="kick"][data-g="g-online-0001"]').tap()
        expect(boss.page.locator("#toast")).to_contain_text("Invité déconnecté")
        assert ("kick", {"guest_id": "g-online-0001"}) in sent
        expect(admin.locator('[data-ma="online"] [data-pa-guest="ban"]')).to_be_visible()
        # Enceintes : repliées par défaut, dépliées d'un toucher.
        expect(admin.locator('[data-ma="speakersBody"]')).to_be_hidden()
        admin.locator('[data-ma-act="speakersFold"]').tap()
        expect(admin.locator('[data-ma="speakers"]')).to_contain_text("Salon")
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


def people_state(read=False, ban=None, name="Léa"):
    return {**live_state(), "messages": [{"id": "m1", "name": "Léa", "text": "Tu peux mettre du Daft Punk ?", "at": 1761120000, "read": read}],
            "guests": [{"guest_id": "guest-lea-0001", "name": name, "via": ["music"], "joined_at": 1761120000, "last_seen": 0, "active_at": 1761120000,
                        "total": 3, "queued": 1, "ban": ban}],
            "bans": [{"guest_id": "guest-old-0001", "name": "Ancien", "until": 0}]}


def test_admin_answers_messages_and_moderates_guests_from_settings(browser, server):
    boss = Phone(browser, server, "Boss")
    sent = []
    state = {"read": False, "ban": None, "name": "Léa"}

    def admin_api(route):
        path = route.request.url.split("/api/admin/", 1)[1].split("?")[0]
        body = json.loads(route.request.post_data or "{}")
        sent.append((path, body))
        if path == "messages":
            state["read"] = body["action"] == "read"
        if path == "ban":
            state["ban"] = {"until": 9999999999}
        if path == "rename":
            state["name"] = body["name"]
        return route.fulfill(json=people_state(**state))
    try:
        boss.page.goto("/")
        as_account_admin(boss)
        boss.page.route("**/api/admin/**", admin_api)
        # Réglages → « Invités, messages et notifications » (lien du module, vérifié dans test_events_web).
        boss.page.evaluate("showTab('host')")
        expect(boss.page.locator('#tabs button[data-tab="account"]')).to_have_attribute("aria-current", "page")
        assert boss.page.locator("#musicAdmin").is_hidden()  # plus dans l'onglet Musique
        people = boss.page.locator("#peopleAdmin")
        expect(people.locator('[data-pa="messages"]')).to_contain_text("Daft Punk")
        expect(boss.page.locator("#hostBadge")).to_have_text("1")  # message non lu : pastille sur Réglages
        expect(people.locator('[data-pa="bans"]')).to_contain_text("Ancien")
        # Notifications de l'hôte : les deux réglages de /admin sont là (abonnement réel impossible sans téléphone).
        expect(people.locator('[data-pa-notif="messages"]')).to_be_attached()
        expect(people.locator('[data-pa-notif="games"]')).to_be_attached()

        people.locator('[data-pa-reply="m1"]').fill("Ça arrive !")
        people.locator('[data-pa-reply-form="m1"] button').tap()
        expect(boss.page.locator("#toast")).to_contain_text("Réponse envoyée")
        assert ("messages/reply", {"id": "m1", "text": "Ça arrive !"}) in sent

        people.locator('[data-pa-act="readAll"]').tap()
        expect(boss.page.locator("#hostBadge")).to_be_hidden()

        people.locator('[data-pa-guest="ban10"]').tap()
        expect(people.locator('[data-pa="guests"]')).to_contain_text("bloqué")
        assert ("ban", {"guest_id": "guest-lea-0001", "minutes": 10}) in sent

        people.locator('[data-pa-guest="unban"][data-g="guest-old-0001"]').tap()
        assert ("unban", {"guest_id": "guest-old-0001"}) in sent
        boss.page.locator("[data-host-back]").tap()
        expect(boss.page.locator('section[data-view="host"]')).to_be_hidden()
        assert not boss.errors, boss.errors
    finally:
        boss.close()


def test_admin_sees_and_closes_games_from_the_games_tab(browser, server):
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Boss")
    try:
        code = guest.create("whoof")  # une vraie partie, créée par un invité
        boss.page.goto("/")
        boss.page.locator('#tabs button[data-tab="games"]').tap()
        assert boss.page.locator("#gamesAdmin").is_hidden()  # pas encore admin : rien
        as_account_admin(boss)
        block = boss.page.locator("#gamesAdmin")
        expect(block).to_contain_text("Parties en cours")
        expect(block).to_contain_text(code)
        expect(block).to_contain_text("Lea")
        block.locator(f'[data-ga-open="{code}"]').tap()
        expect(block.locator(f'[data-ga-close="{code}"]')).to_be_visible()
        boss.page.once("dialog", lambda d: d.accept())
        block.locator(f'[data-ga-close="{code}"]').tap()
        expect(boss.page.locator("#toast")).to_contain_text("Partie fermée")
        expect(block).to_be_hidden()  # plus aucune partie
        assert not boss.errors, boss.errors
    finally:
        guest.close(); boss.close()


def test_reducing_the_queue_hides_only_playlist_tracks(browser, server):
    """Réduire la file masque les titres de la playlist ; les demandes des invités restent visibles, à leur place."""
    boss = Phone(browser, server, "Boss")
    mixed = [{"pos": i + 2, "key": f"k{i}", "title": f"Titre {i}", "artist": "A", "art": "", "by": "Léa" if i in (1, 5) else None, "eta": 60 * i}
             for i in range(8)]
    try:
        boss.page.goto("/")
        as_account_admin(boss)
        boss.page.route("**/api/admin/**", lambda route: route.fulfill(json=live_state(mixed)))
        boss.page.locator('#tabs button[data-tab="music"]').tap()
        admin = boss.page.locator("#musicAdmin")
        queue = admin.locator('[data-ma="queue"] .track')
        expect(queue).to_have_count(2)  # réduite par défaut : seulement les demandes des invités
        expect(queue.first).to_contain_text("Titre 1")
        expect(queue.last).to_contain_text("Titre 5")
        more = admin.locator('[data-ma-act="queueAll"]')
        expect(more).to_have_text("🎵 Voir les 6 titres de la playlist")
        more.tap()
        expect(queue).to_have_count(8)
        expect(more).to_have_text("Masquer les titres de la playlist")
        # Le choix est gardé au rechargement ; le titre « File d'attente » bascule aussi.
        boss.page.reload()
        as_account_admin(boss)
        boss.page.locator('#tabs button[data-tab="music"]').tap()
        expect(queue).to_have_count(8)
        admin.locator('[data-ma-act="queueFold"]').tap()
        expect(queue).to_have_count(2)
        assert not boss.errors, boss.errors
    finally:
        boss.close()
