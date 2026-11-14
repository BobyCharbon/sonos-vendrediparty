"""Notifications iPhone contre un faux serveur APNs LOCAL qui parle vraiment HTTP/2 sur TLS (bibliothèque h2),
comme api.push.apple.com : le client du serveur Party (httpx, http2=True) est testé de bout en bout, sans Apple."""
import datetime
import ipaddress
import json
import socket
import ssl
import threading
import time

import pytest

h2_connection = pytest.importorskip("h2.connection")  # h2 est dans requirements.txt ; sans lui, http2=True échoue
import h2.config  # noqa: E402
import h2.events  # noqa: E402
import httpx  # noqa: E402
from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402

from app import apns as apns_mod  # noqa: E402
from app.push import Push  # noqa: E402

TOKEN = "ab" * 32


def self_signed(tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "apple.pem", tmp_path / "apple.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path


class FakeApple:
    """Faux api.push.apple.com : HTTP/2 seulement (ALPN h2), réponses programmées (statut, raison), requêtes notées."""

    def __init__(self, tmp_path, replies=()):
        self.replies, self.requests = list(replies), []
        self.cert, key = self_signed(tmp_path)
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls.load_cert_chain(self.cert, key)
        self.tls.set_alpn_protocols(["h2"])
        self.sock = socket.create_server(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, raw):
        try:
            conn = self.tls.wrap_socket(raw, server_side=True)
        except (ssl.SSLError, OSError):
            return
        assert conn.selected_alpn_protocol() == "h2"
        h2c = h2_connection.H2Connection(config=h2.config.H2Configuration(client_side=False, header_encoding="utf-8"))
        h2c.initiate_connection()
        conn.sendall(h2c.data_to_send())
        streams = {}
        while data := conn.recv(65535):
            for event in h2c.receive_data(data):
                if isinstance(event, h2.events.RequestReceived):
                    streams[event.stream_id] = {"headers": dict(event.headers), "body": b""}
                elif isinstance(event, h2.events.DataReceived):
                    streams[event.stream_id]["body"] += event.data
                    h2c.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                elif isinstance(event, h2.events.StreamEnded):
                    request = streams.pop(event.stream_id)
                    self.requests.append(request)
                    status, reason = self.replies.pop(0) if self.replies else (200, None)
                    body = json.dumps({"reason": reason}).encode() if reason else b""
                    h2c.send_headers(event.stream_id, [(":status", str(status)),
                                                       ("apns-id", request["headers"].get("apns-id", ""))],
                                     end_stream=not body)
                    if body:
                        h2c.send_data(event.stream_id, body, end_stream=True)
            conn.sendall(h2c.data_to_send())

    def apns(self, monkeypatch):
        url = f"https://127.0.0.1:{self.port}"
        monkeypatch.setattr(apns_mod, "HOSTS", {"production": url, "sandbox": url})
        monkeypatch.setattr(apns_mod, "RETRY_DELAYS", (0, 0))
        pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        client = httpx.Client(http2=True, timeout=5, verify=ssl.create_default_context(cafile=str(self.cert)))
        return apns_mod.Apns(pem, "KEY1234567", client=client)


def sub(environment="production", topic="ch.bobycharbon.party"):
    return {"endpoint": f"apns:{TOKEN}", "apns": {"token": TOKEN, "environment": environment, "topic": topic}}


def test_alert_reaches_apple_over_http2_with_all_its_headers(tmp_path, monkeypatch):
    apple = FakeApple(tmp_path)
    sender = apple.apns(monkeypatch)
    payload = {"title": "💬 Léa", "body": "On arrive !", "url": "/admin#settings", "tag": "message"}
    assert sender.send(sub(topic="ch.bobycharbon.party.beta"), payload) is True
    [req] = apple.requests
    h = req["headers"]
    assert h[":method"] == "POST" and h[":path"] == f"/3/device/{TOKEN}"
    assert h["apns-topic"] == "ch.bobycharbon.party.beta" and h["apns-push-type"] == "alert"
    assert h["apns-priority"] == "10" and int(h["apns-expiration"]) > time.time()
    assert h["authorization"].startswith("bearer ") and h["authorization"].count(".") == 2
    body = json.loads(req["body"])
    assert body == {"aps": {"alert": {"title": "💬 Léa", "body": "On arrive !"}, "sound": "default",
                            "thread-id": "message"}, "url": "/admin#settings"}


def test_busy_apple_then_ok_sends_once_with_the_same_id(tmp_path, monkeypatch):
    apple = FakeApple(tmp_path, [(503, "ServiceUnavailable"), (429, "TooManyRequests")])
    assert apple.apns(monkeypatch).send(sub(), {"title": "a", "body": "b"}) is True
    ids = {r["headers"]["apns-id"] for r in apple.requests}
    assert len(apple.requests) == 3 and len(ids) == 1
    assert apple.requests[0]["headers"]["apns-collapse-id"] == ids.pop()


@pytest.mark.parametrize("status, reason", [(410, "Unregistered"), (400, "BadDeviceToken")])
def test_gone_device_is_forgotten_through_push(tmp_path, monkeypatch, status, reason):
    apple = FakeApple(tmp_path, [(status, reason)])
    push = Push(tmp_path, "https://party.bobycharbon.ch", apns=apple.apns(monkeypatch))
    gone = []
    push.send([sub()], {"title": "a", "body": "b"}, on_gone=gone.append)
    end = time.time() + 5
    while time.time() < end and not gone:
        time.sleep(0.02)
    assert [g["endpoint"] for g in gone] == [f"apns:{TOKEN}"] and len(apple.requests) == 1


def test_live_activity_over_http2(tmp_path, monkeypatch):
    apple = FakeApple(tmp_path)
    target = {"token": TOKEN, "environment": "production", "topic": "ch.bobycharbon.party"}
    assert apple.apns(monkeypatch).send_live_activity(target, "end", {"dismissal-date": 1}, 10) is True
    h = apple.requests[0]["headers"]
    assert h["apns-topic"] == "ch.bobycharbon.party.push-type.liveactivity" and h["apns-push-type"] == "liveactivity"
