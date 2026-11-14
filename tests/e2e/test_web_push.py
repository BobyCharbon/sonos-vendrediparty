"""Notifications Web Push de bout en bout dans un vrai Chromium : vraie page, vrai service worker /sw.js, vrai serveur
Party, vrai chiffrement Web Push (pywebpush, clés VAPID du serveur), vraie notification affichée par le navigateur.

Deux faux, et seulement ceux-là :
- le service push (Google, Apple, Mozilla) est un service local : il vérifie la signature VAPID du serveur, déchiffre
  le message avec les clés de l'abonnement, puis le remet au service worker par le protocole DevTools
  (ServiceWorker.deliverPushMessage), comme le ferait le navigateur. Il répond 410 pour un abonnement expiré ;
- pushManager.subscribe : le Chromium des tests n'a pas de service push (le vrai renvoie une adresse que Google refuse
  par 410, essai du 14.11.2026). L'abonnement simulé a de vraies clés, détenues par le faux service push.
Le toucher d'une notification est simulé dans le service worker (aucun outil ne clique une notification système) :
ouvrir une fenêtre et la mettre au premier plan sont enregistrés, la navigation d'un onglet ouvert est réelle."""
import base64
import json
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import http_ece
import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from tests.e2e.helpers import ADMIN_PIN, ROOT, Server  # noqa: E402

EVENT = "32f18a3b-827f-4123-8cf4-33de06c9a51c"
FCM = "https://fcm.googleapis.com"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class FakePushService:
    """Service push local : un appareil = une paire de clés ; garde chaque message reçu, déchiffré."""

    def __init__(self):
        self.devices, self.received, self.gone, self.errors, self.vapid_keys = {}, [], set(), [], []
        svc = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                device = self.path.rsplit("/", 1)[-1]
                status = 410 if device in svc.gone else 201
                try:
                    if status == 201:
                        svc.check_vapid(self.headers.get("Authorization", ""))
                        assert self.headers.get("Content-Encoding") == "aes128gcm"
                        key, auth = svc.devices[device]
                        plain = http_ece.decrypt(body, private_key=key, auth_secret=auth, version="aes128gcm")
                        svc.received.append((device, json.loads(plain)))
                    else:
                        svc.received.append((device, None))
                except Exception as e:  # un message illisible = un bug du serveur
                    svc.errors.append(repr(e))
                    status = 400
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def check_vapid(self, header: str):
        token, key = re.fullmatch(r"vapid t=([^,]+),\s*k=(\S+)", header).groups()
        head, claims, sig = token.split(".")
        raw = unb64(sig)
        signature = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64(key)).verify(
            signature, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
        claims = json.loads(unb64(claims))
        assert claims["aud"] == FCM and claims["exp"] > time.time(), claims
        self.vapid_keys.append(key)

    def new_device(self) -> dict:
        device, key, auth = secrets.token_hex(12), ec.generate_private_key(ec.SECP256R1()), secrets.token_bytes(16)
        self.devices[device] = (key, auth)
        point = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return {"endpoint": f"{FCM}/fcm/send/{device}", "keys": {"p256dh": b64(point), "auth": b64(auth)}}

    def wait(self, count: int, timeout: float = 10) -> list:
        end = time.monotonic() + timeout
        while len(self.received) < count and time.monotonic() < end:
            time.sleep(0.05)
        assert not self.errors, self.errors
        assert len(self.received) >= count, f"{len(self.received)} message(s) reçu(s), {count} attendu(s)"
        return self.received

    def stop(self):
        self.http.shutdown()


class PushServer(Server):
    """Serveur Party (réglages de la prod) dont les envois vers fcm.googleapis.com partent au faux service push."""

    def __init__(self, fake: FakePushService):
        self.fake_url = fake.url
        super().__init__(compagnon=False)

    def _launch(self):
        shim = ("import requests\n_post = requests.post\n"
                f"requests.post = lambda url, *a, **k: _post(url.replace({FCM!r}, {self.fake_url!r}), *a, **k)\n"
                f"import uvicorn\nuvicorn.run('app.main:app', port={self.port}, log_level='warning')\n")
        self.proc = subprocess.Popen([sys.executable, "-c", shim], cwd=ROOT, env=self._env, stdout=self.log,
                                     stderr=subprocess.STDOUT)
        for _ in range(600):
            try:
                if httpx.get(self.url + "/", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.1)
        raise RuntimeError("Le serveur de test n'a pas démarré")


# pushManager simulé, un abonnement par portée (« / », « /admin », « /events/ »), gardé dans le localStorage.
STUB = """(() => {
  if (typeof ServiceWorkerRegistration === "undefined") return;  // about:blank
  const DEVICES = %s;
  const scopes = new WeakMap();
  const d = Object.getOwnPropertyDescriptor(ServiceWorkerRegistration.prototype, "pushManager");
  Object.defineProperty(ServiceWorkerRegistration.prototype, "pushManager", { configurable: true, get() {
    const pm = d.get.call(this); scopes.set(pm, new URL(this.scope).pathname); return pm; } });
  const key = (pm) => "fake_push:" + scopes.get(pm);
  const make = (pm, data) => ({ endpoint: data.endpoint, expirationTime: null,
    toJSON: () => ({ endpoint: data.endpoint, expirationTime: null, keys: data.keys }),
    unsubscribe: async () => { localStorage.removeItem(key(pm)); return true; } });
  PushManager.prototype.getSubscription = async function () {
    const raw = localStorage.getItem(key(this)); return raw ? make(this, JSON.parse(raw)) : null; };
  PushManager.prototype.subscribe = async function (options) {
    const data = { ...DEVICES[scopes.get(this)], userVisibleOnly: options.userVisibleOnly,
      serverKey: btoa(String.fromCharCode(...new Uint8Array(options.applicationServerKey)))
        .replace(/[+]/g, "-").replace(/[/]/g, "_").replace(/=+$/, "") };
    localStorage.setItem(key(this), JSON.stringify(data)); return make(this, data); };
})();"""

STATE = {"active": True, "room": "Salon", "state": "PAUSED_PLAYBACK", "name": "Léa", "now": None, "upcoming": [],
         "upcoming_total": 0, "played": [], "messages": [], "source": "sonos", "queue_editable": True}


class Device:
    """Un navigateur (un téléphone) : pages, service workers et notifications affichées."""

    def __init__(self, browser, server: PushServer, fake: FakePushService):
        self.server, self.fake = server, fake
        self.subs = {scope: fake.new_device() for scope in ("/", "/admin", "/events/")}
        self.scope_of = {sub["endpoint"].rsplit("/", 1)[-1]: scope for scope, sub in self.subs.items()}
        self.ctx = browser.new_context(base_url=server.url, permissions=["notifications"], locale="fr-CH")
        self.ctx.add_init_script(STUB % json.dumps(self.subs))
        self.ctx.add_init_script("if (location.protocol === 'http:') localStorage.setItem('vp_install_dismissed', '1')")
        self.page = self.ctx.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.cdp = self.ctx.new_cdp_session(self.page)
        self.registrations = {}
        self.cdp.on("ServiceWorker.workerRegistrationUpdated", lambda e: self.registrations.update(
            {r["scopeURL"]: r["registrationId"] for r in e["registrations"] if not r["isDeleted"]}))
        self.cdp.send("ServiceWorker.enable")
        self.delivered = 0

    def deliver(self):
        """Ce que le service push a reçu pour CE navigateur arrive à son service worker."""
        for device, payload in self.fake.received[self.delivered:]:
            self.delivered += 1
            if device not in self.scope_of or payload is None:
                continue
            self.push_raw(self.scope_of[device], payload)

    def push_raw(self, scope: str, payload: dict):
        """Message déjà déchiffré remis au service worker (forme de supabase/functions/send-web-push)."""
        worker, end = self.worker(scope), time.monotonic() + 5
        while worker.evaluate("self.registration.active?.state") != "activated" and time.monotonic() < end:
            time.sleep(0.05)
        while self.server.url + scope not in self.registrations and time.monotonic() < end:
            time.sleep(0.05)
        self.cdp.send("ServiceWorker.deliverPushMessage", {
            "origin": self.server.url, "registrationId": self.registrations[self.server.url + scope],
            "data": json.dumps(payload)})

    def notifications(self, scope: str, count: int = 1) -> list:
        js = """async () => (await self.registration.getNotifications())
                  .map((n) => ({ title: n.title, body: n.body, icon: n.icon, tag: n.tag, data: n.data,
                                 silent: n.silent, renotify: n.renotify }))"""
        worker, end = self.worker(scope), time.monotonic() + 8
        while True:
            shown = worker.evaluate(js)
            if len(shown) >= count or time.monotonic() > end:
                return shown
            time.sleep(0.1)

    def worker(self, scope: str):
        for _ in range(50):
            for w in self.ctx.service_workers:
                if w.evaluate("self.registration.scope") == self.server.url + scope:
                    return w
            time.sleep(0.1)
        raise AssertionError(f"pas de service worker pour {scope}")

    def click(self, scope: str) -> list:
        """Toucher la notification : ce que fait le service worker (fenêtre ouverte, mise au premier plan)."""
        return self.worker(scope).evaluate("""async () => {
          const calls = [];
          self.clients.openWindow = async (url) => { calls.push(["open", url]); return null; };
          WindowClient.prototype.focus = async function () { calls.push(["focus", new URL(this.url).pathname]); return this; };
          const navigate = WindowClient.prototype.navigate;
          WindowClient.prototype.navigate = async function (url) {
            try { return await navigate.call(this, url); } catch (e) { calls.push(["navigate refused"]); throw e; } };
          const [n] = await self.registration.getNotifications();
          const ev = new NotificationEvent("notificationclick", { notification: n });
          let done = Promise.resolve();
          Object.defineProperty(ev, "waitUntil", { value: (p) => { done = p; } });
          self.dispatchEvent(ev);
          await done;
          return calls;
        }""")

    def close(self):
        self.ctx.close()


@pytest.fixture(scope="module")
def fake():
    svc = FakePushService()
    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def server(fake):
    s = PushServer(fake)
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture(scope="module")
def chromium(playwright):
    # Chromium complet sans fenêtre (le « headless shell » refuse toute permission de notification).
    b = playwright.chromium.launch(channel="chromium")
    yield b
    b.close()


@pytest.fixture
def device(chromium, server, fake):
    d = Device(chromium, server, fake)
    yield d
    d.close()
    assert not d.errors, d.errors


def admin_client(server) -> httpx.Client:
    c = httpx.Client(base_url=server.url, timeout=10)
    c.post("/api/admin/login", json={"pin": ADMIN_PIN}).raise_for_status()
    return c


def open_guest(d: Device, gid: str):
    """Invité entré avec le code de la soirée, onglet Musique ; l'état Sonos est simulé (pas d'enceinte en test)."""
    pin = admin_client(d.server).get("/api/admin/state").json()["guest_pin"]
    d.ctx.request.post(f"{d.server.url}/api/join", data={"pin": pin})
    d.ctx.add_init_script(f"if (location.protocol === 'http:') {{ localStorage.setItem('vp_guest', '{gid}'); "
                          "localStorage.setItem('vp_name', 'Léa'); }")
    d.page.route("**/api/state*", lambda r: r.fulfill(json=STATE))
    d.page.route("**/api/hello", lambda r: r.fulfill(json={}))
    d.page.goto("/?tab=music")
    expect(d.page.locator("#notifBox")).to_be_visible()


def subscribe_guest(d: Device):
    """« Me prévenir quand mon titre passe » (onglet Musique), jusqu'à la fin de l'abonnement."""
    d.page.locator("#notifToggle").click(force=True)
    expect(d.page.locator("#notifToggle")).to_be_checked()
    expect(d.page.locator("#notifToggle")).to_be_enabled()


def finish_feedback(server, gid: str, reply: str):
    admin = admin_client(server)
    item = admin.post("/api/admin/feedback/new", json={"kind": "idea", "text": "Une idée assez longue pour être claire",
                                                       "guest_id": gid, "name": "Léa"}).json()["item"]
    admin.post("/api/admin/feedback", json={"ids": [item["id"]], "action": "done", "reply": reply}).raise_for_status()


def test_guest_subscribes_and_his_answer_arrives_on_the_phone(device, fake):
    gid = "e2e-push-lea-" + secrets.token_hex(4)
    open_guest(device, gid)
    subscribe_guest(device)
    # L'abonnement utilise la clé VAPID du serveur ; le serveur l'a enregistré pour cet invité.
    key = device.page.request.get("/api/push/key").json()["key"]
    assert device.page.evaluate("JSON.parse(localStorage.getItem('fake_push:/')).serverKey") == key
    assert device.page.evaluate("JSON.parse(localStorage.getItem('fake_push:/')).userVisibleOnly") is True
    assert device.page.request.get(f"/api/notify?guest_id={gid}").json() == {
        "prefs": {"track": True, "feedback": True}, "subscribed": True}

    before = len(fake.received)
    finish_feedback(device.server, gid, "C'est en place, merci !")
    [(_, payload)] = fake.wait(before + 1)[before:]
    assert fake.vapid_keys[-1] == key
    device.deliver()
    [shown] = device.notifications("/")
    assert shown["title"] == "✅ Ton retour est terminé" and shown["body"] == "C'est en place, merci !"
    assert shown["icon"].endswith("/static/icon-192.png?v=3")
    assert shown["data"] == {"url": "/?tab=feedback"} and shown["silent"] is False

    # Toucher : la page déjà ouverte est reprise (pas de 2e fenêtre) et va sur « Ton avis ».
    assert device.click("/") == [["focus", "/"]]
    expect(device.page).to_have_url(re.compile(r"/$"))  # l'adresse est nettoyée une fois l'onglet ouvert

    # Interrupteur « Réponse à mes avis » coupé : plus rien ne part vers le téléphone.
    device.page.request.post("/api/notify", data={"guest_id": gid, "kind": "feedback", "on": False})
    finish_feedback(device.server, gid, "Deuxième réponse")
    time.sleep(1.5)
    assert len(fake.received) == before + 1


def test_track_notification_opens_the_music_tab(device):
    """« Ton titre passe » ouvre Musique (l'app s'ouvre d'habitude sur Événements, avis du 13.11)."""
    gid = "e2e-push-tom-" + secrets.token_hex(4)
    open_guest(device, gid)
    subscribe_guest(device)
    device.page.locator('#tabs [data-tab="events"]').click()
    device.push_raw("/", {"title": "🎶 Ton titre passe !", "body": "Mon titre · Moi", "url": "/?tab=music",
                          "tag": "now-playing"})
    [shown] = device.notifications("/")
    assert shown["renotify"] is True and shown["tag"] == "now-playing"
    assert device.click("/") == [["focus", "/"]]
    expect(device.page.locator("body")).to_have_attribute("data-tab", "music", timeout=30000)  # page rechargée
    # Party fermée : le toucher ouvre Party sur Musique.
    device.page.goto("about:blank")
    device.push_raw("/", {"title": "🎶 Ton titre passe !", "body": "Mon titre · Moi", "url": "/?tab=music",
                          "tag": "now-playing"})
    device.notifications("/")
    assert device.click("/") == [["open", device.server.url + "/?tab=music"]]


def test_new_account_notification_opens_the_account_tab(device):
    """« Nouveau compte » (data.url /?tab=account, campagne du 14.11) ouvre l'onglet du compte, pas Événements."""
    gid = "e2e-push-signup-" + secrets.token_hex(4)
    open_guest(device, gid)
    subscribe_guest(device)
    device.page.locator('#tabs [data-tab="events"]').click()
    device.push_raw("/", {"title": "👋 Nouveau compte", "body": "Léa vient de créer son compte.", "url": "/?tab=account",
                          "tag": "party-event-signup"})
    device.notifications("/")
    assert device.click("/") == [["focus", "/"]]
    expect(device.page.locator("body")).to_have_attribute("data-tab", "account", timeout=30000)


def test_expired_subscription_is_forgotten(device, fake):
    gid = "e2e-push-max-" + secrets.token_hex(4)
    open_guest(device, gid)
    subscribe_guest(device)
    fake.gone.add(device.subs["/"]["endpoint"].rsplit("/", 1)[-1])
    before = len(fake.received)
    finish_feedback(device.server, gid, "Fait")
    fake.wait(before + 1)
    end = time.monotonic() + 5
    while device.page.request.get(f"/api/notify?guest_id={gid}").json()["subscribed"] and time.monotonic() < end:
        time.sleep(0.1)
    assert device.page.request.get(f"/api/notify?guest_id={gid}").json()["subscribed"] is False


def test_host_hears_about_new_games_only_when_switched_on(device, fake):
    device.ctx.request.post(f"{device.server.url}/api/admin/login", data={"pin": ADMIN_PIN})
    device.page.goto("/admin#settings")
    toggle = device.page.locator("#notifGamesToggle")
    expect(device.page.locator("#notifGamesBox")).not_to_have_class(re.compile("hidden"))
    toggle.evaluate("t => t.click()")
    expect(toggle).to_be_checked()
    expect(toggle).to_be_enabled()

    before = len(fake.received)
    r = httpx.post(f"{device.server.url}/api/games", json={"guest_id": "e2e-push-host", "name": "Zoé", "type": "likely"})
    assert r.status_code == 200, r.text
    [(_, payload)] = fake.wait(before + 1)[before:]
    device.deliver()
    [shown] = device.notifications("/admin")
    assert shown["title"] == "🎮 Qui est le plus… ?" and shown["body"].startswith("Zoé lance une partie · code ")
    assert shown["data"] == {"url": "/admin#games"}
    # Admin ouvert sur Réglages : le toucher le reprend et l'ouvre sur Jeux.
    assert device.click("/admin") == [["focus", "/admin"]]
    expect(device.page).to_have_url(re.compile(r"/admin#games$"))

    toggle.evaluate("t => t.click()")
    expect(toggle).not_to_be_checked()
    expect(toggle).to_be_enabled()
    httpx.post(f"{device.server.url}/api/games", json={"guest_id": "e2e-push-host2", "name": "Zoé", "type": "likely"})
    time.sleep(1.5)
    assert len(fake.received) == before + 1


def events_payload(silent=False) -> dict:
    """Message d'un événement tel que l'envoie supabase/functions/send-web-push."""
    return {"title": "Date choisie", "body": "Soirée raclette : le vendredi 20 novembre à 19 h",
            "tag": "party-event-0f6c2b1e-5d1a-4a4e-9a51-0c2a8f1b7d10", "silent": silent,
            "url": f"https://partytest.bobycharbon.ch/?tab=events&event={EVENT}"}


def test_event_notification_reuses_the_open_party_page(device):
    """Abonnement du module Événements (portée « /events/ », lib/push.ts) : la page Party ouverte (« / ») n'est pas
    contrôlée par ce service worker ; le toucher doit pourtant la reprendre et ouvrir la fiche, pas ouvrir un 2e Party."""
    device.page.goto("/")
    device.page.evaluate("navigator.serviceWorker.register('/sw.js', { scope: '/events/' })")
    device.worker("/events/")
    payload = events_payload()
    payload["url"] = payload["url"].replace("https://partytest.bobycharbon.ch", device.server.url)
    device.push_raw("/events/", payload)
    [shown] = device.notifications("/events/")
    assert shown["title"] == "Date choisie" and shown["renotify"] is False and shown["silent"] is False
    # Ce service worker ne contrôle pas la page : navigate() est refusé, la page ouvre l'adresse elle-même.
    assert device.click("/events/") == [["navigate refused"], ["focus", "/"]]
    expect(device.page).to_have_url(re.compile(rf"/\?tab=events&event={EVENT}$"), timeout=30000)
    expect(device.page.locator("body")).to_have_attribute("data-tab", "events", timeout=30000)


def test_event_notification_during_the_moon_is_silent_and_never_leaves_party(device):
    device.page.goto("about:blank")
    device.page.goto("/")
    device.page.evaluate("navigator.serviceWorker.register('/sw.js', { scope: '/events/' })")
    device.worker("/events/")
    device.page.goto("about:blank")
    device.push_raw("/events/", events_payload(silent=True))  # adresse d'un autre site que celui-ci
    [shown] = device.notifications("/events/")
    assert shown["silent"] is True
    # L'adresse vient d'une autre origine (base partagée prod/test) : on reste chez soi, jamais ailleurs.
    assert device.click("/events/") == [["open", device.server.url + "/"]]
