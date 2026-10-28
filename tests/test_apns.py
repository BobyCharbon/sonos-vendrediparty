"""Notifications natives de l'app iOS (APNs) : abonnements « apns: », envoi HTTP/2 à Apple, appareils disparus."""
import base64
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import apns as apns_mod
from app.push import Push, valid_subscription

TOKEN = "a" * 64


def apns_sub(token=TOKEN, environment="production", topic="ch.bobycharbon.party"):
    return {"endpoint": f"apns:{token}", "apns": {"token": token, "environment": environment, "topic": topic}}


def test_native_subscriptions_are_validated():
    assert valid_subscription(apns_sub())
    assert valid_subscription(apns_sub(environment="sandbox", topic="ch.bobycharbon.party.beta"))
    assert not valid_subscription(apns_sub(token="xyz"))                         # pas un jeton d'appareil
    assert not valid_subscription(apns_sub(environment="staging"))
    assert not valid_subscription(apns_sub(topic="com.autre.app"))                # une autre app
    assert not valid_subscription({**apns_sub(), "endpoint": "apns:" + "b" * 64})  # adresse ≠ jeton


@pytest.fixture
def key_pem():
    key = ec.generate_private_key(ec.SECP256R1())
    return key, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode()


def make_apns(key_pem, handler):
    _, pem = key_pem
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return apns_mod.Apns(pem, key_id="KEY1234567", team_id="GS2B6GA9JA", client=client)


def test_alert_is_sent_to_the_right_apple_server_with_the_app_topic(key_pem):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200)

    sender = make_apns(key_pem, handler)
    payload = {"title": "🎶 Ton titre passe !", "body": "Titre · Artiste", "url": "/", "tag": "track"}
    assert sender.send(apns_sub(environment="sandbox", topic="ch.bobycharbon.party.beta"), payload) is True
    [req] = seen
    assert str(req.url) == f"https://api.sandbox.push.apple.com/3/device/{TOKEN}"
    assert req.headers["apns-topic"] == "ch.bobycharbon.party.beta"
    assert req.headers["apns-push-type"] == "alert"
    body = json.loads(req.content)
    assert body["aps"]["alert"] == {"title": "🎶 Ton titre passe !", "body": "Titre · Artiste"}
    assert body["aps"]["thread-id"] == "track" and body["url"] == "/"


def test_provider_token_is_a_signed_es256_jwt_reused_between_sends(key_pem):
    tokens = []

    def handler(request):
        tokens.append(request.headers["authorization"].removeprefix("bearer "))
        return httpx.Response(200)

    sender = make_apns(key_pem, handler)
    sender.send(apns_sub(), {"title": "a", "body": "b"})
    sender.send(apns_sub(), {"title": "c", "body": "d"})
    assert tokens[0] == tokens[1]  # Apple refuse qu'on renouvelle le jeton à chaque envoi
    header, claims, signature = tokens[0].split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)
    assert json.loads(base64.urlsafe_b64decode(pad(header))) == {"alg": "ES256", "kid": "KEY1234567"}
    claims = json.loads(base64.urlsafe_b64decode(pad(claims)))
    assert claims["iss"] == "GS2B6GA9JA" and abs(claims["iat"] - time.time()) < 60
    assert len(base64.urlsafe_b64decode(pad(signature))) == 64  # r ‖ s, pas de DER


@pytest.mark.parametrize("status, reason", [(410, "Unregistered"), (400, "BadDeviceToken"), (400, "DeviceTokenNotForTopic")])
def test_uninstalled_or_foreign_devices_are_reported_gone(key_pem, status, reason):
    sender = make_apns(key_pem, lambda request: httpx.Response(status, json={"reason": reason}))
    assert sender.send(apns_sub(), {"title": "a", "body": "b"}) is False


def test_other_apple_errors_keep_the_device(key_pem):
    sender = make_apns(key_pem, lambda request: httpx.Response(429, json={"reason": "TooManyRequests"}))
    assert sender.send(apns_sub(), {"title": "a", "body": "b"}) is True


def test_from_env_needs_the_key_and_its_id(key_pem):
    _, pem = key_pem
    assert apns_mod.Apns.from_env({}) is None
    assert apns_mod.Apns.from_env({"APNS_KEY_P8": pem}) is None
    sender = apns_mod.Apns.from_env({"APNS_KEY_P8": pem, "APNS_KEY_ID": "KEY1234567"})
    assert sender is not None and sender.team_id == "GS2B6GA9JA"


class FakeApns:
    def __init__(self, alive=True):
        self.sent, self.alive = [], alive

    def send(self, sub, payload):
        self.sent.append((sub["apns"]["token"], payload["title"]))
        return self.alive


def wait_for(predicate, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end and not predicate():
        time.sleep(0.01)
    return predicate()


def test_push_routes_native_subscriptions_to_apns_and_forgets_gone_devices(tmp_path, monkeypatch):
    webpush_calls = []
    monkeypatch.setattr("app.push.webpush", lambda sub, *a, **k: webpush_calls.append(sub["endpoint"]))
    fake = FakeApns(alive=False)
    push = Push(tmp_path, "https://party.bobycharbon.ch", apns=fake)
    gone = []
    web_sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/x", "keys": {"p256dh": "k", "auth": "a"}}
    push.send([apns_sub(), web_sub], {"title": "Hello", "body": "!"}, on_gone=gone.append)
    assert wait_for(lambda: fake.sent and webpush_calls and gone)
    assert fake.sent == [(TOKEN, "Hello")] and webpush_calls == [web_sub["endpoint"]]
    assert [g["endpoint"] for g in gone] == [f"apns:{TOKEN}"]


def test_native_subscriptions_are_kept_when_apns_is_not_configured(tmp_path):
    push = Push(tmp_path, "https://party.bobycharbon.ch", apns=None)
    gone = []
    push.send([apns_sub()], {"title": "Hello", "body": "!"}, on_gone=gone.append)
    time.sleep(0.1)
    assert gone == []


def test_key_pasted_on_one_line_or_with_escaped_newlines_still_loads():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.apns import Apns
    pem_text = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    body = "".join(pem_text.splitlines()[1:-1])
    for variant in (pem_text, pem_text.replace("\n", " "), pem_text.replace("\n", "\\n"), body):
        assert Apns(variant, "KEY1234567").key_id == "KEY1234567"


def test_a_badly_pasted_key_never_stops_the_site():
    from app.apns import Apns
    assert Apns.from_env({"APNS_KEY_P8": "pas une clé", "APNS_KEY_ID": "KEY1234567"}) is None


def test_live_activity_update_goes_to_the_liveactivity_topic():
    import json as _json

    import httpx
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.apns import Apns
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200)

    key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    a = Apns(key, "KEY1234567", client=httpx.Client(transport=httpx.MockTransport(handler)))
    target = {"token": "ab" * 32, "environment": "production", "topic": "ch.bobycharbon.party.beta"}
    assert a.send_live_activity(target, "update", {"content-state": {"ahead": 1}}, 5)
    r = seen[0]
    assert r.url.path == "/3/device/" + "ab" * 32
    assert r.headers["apns-topic"] == "ch.bobycharbon.party.beta.push-type.liveactivity"
    assert r.headers["apns-push-type"] == "liveactivity" and r.headers["apns-priority"] == "5"
    body = _json.loads(r.content)["aps"]
    assert body["event"] == "update" and body["content-state"] == {"ahead": 1} and body["timestamp"] > 0
