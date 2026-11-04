"""Billet d'un événement dans Apple Wallet : .pkpass signé, droits de la route, 503 sans certificats, mises à jour
(PassKit Web Service) et push APNs simulé.

La signature réelle est vérifiée avec les vrais certificats (dossier WALLET_TEST_DIR, par défaut ~/sb-work/wallet,
jamais dans le dépôt) contre la chaîne Apple (racine « Apple Root CA » du trousseau macOS) : test sauté ailleurs."""
import hashlib
import io
import json
import os
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main, wallet as wl, wallet_push
from app.wallet_tickets import WalletTickets

EVENT = "32f18a3b-827f-4123-8cf4-33de06c9a51c"
ME = "5b0c7e1e-1d3a-4c8e-9a51-6f2f4b9d0a11"
SERIAL = f"{EVENT}.{ME}"
TOKEN_HEX = "ab" * 32
PASS_AUTH = "cd" * 32
PUSH = "0f" * 32
DEVICE = "a1b2c3d4e5f6"
UPDATED = "2030-11-14T19:30:00.123456+00:00"
REAL = Path(os.environ.get("WALLET_TEST_DIR") or Path.home() / "sb-work/wallet")
EVENT_ROW = {"id": EVENT, "title": "Vendredi Party", "starts_at": "2030-11-14T19:00:00+00:00", "ends_at": "2030-11-15T01:00:00+00:00",
             "all_day": False, "location_name": "Chez Boby", "location_address": "Rue du Lac 1, 1200 Genève",
             "location_url": "https://maps.apple.com/?ll=46.2044,6.1432&q=Chez%20Boby", "status": "published"}
TICKET = {"token": TOKEN_HEX, "code": "K7M2QX", "plus_ones": 2, "checked_in_at": None, "paid": False, "price_chf": 20}


def payload(valid=True, **ticket):
    """Réponse de wallet_pass_issue / wallet_pass_by_token (migration 20261103160000)."""
    return {"serial": SERIAL, "user_id": ME, "auth_token": PASS_AUTH, "updated_at": UPDATED, "valid": valid,
            "holder": "Léa", "event": EVENT_ROW, "ticket": {**TICKET, **ticket}}


def fake_signer_dir(folder: Path) -> Path:
    """Certificats jetables (autosignés) au format des vrais : clé PEM, certificats DER."""
    def cert(name: str, key, issuer_key, issuer_name: str):
        now = datetime.now(timezone.utc)
        return (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)])).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
                .not_valid_after(now + timedelta(days=30)).sign(issuer_key, hashes.SHA256()))
    root_key, pass_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "pass.key").write_bytes(pass_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                               serialization.NoEncryption()))
    (folder / "pass.cer").write_bytes(cert("Pass Type ID: test", pass_key, root_key, "WWDR test").public_bytes(serialization.Encoding.DER))
    (folder / "wwdr_g4.cer").write_bytes(cert("WWDR test", root_key, root_key, "WWDR test").public_bytes(serialization.Encoding.DER))
    return folder


class FakeBase:
    """Base Supabase simulée : fonctions Wallet de la migration, avec les vérifications de jeton côté base."""

    def __init__(self, issue=None, targets=(PUSH,)):
        self.issue = issue if issue is not None else payload()
        self.targets = list(targets)
        self.devices: dict[str, str] = {}
        self.seen: list[tuple] = []

    def handler(self, request: httpx.Request):
        body = json.loads(request.content) if request.content else {}
        auth = request.headers.get("authorization")
        path = request.url.path
        self.seen.append((request.method, path, auth, body))
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME}) if auth == "Bearer good" else httpx.Response(401, json={})
        name = path.removeprefix("/rest/v1/rpc/")
        if name == "wallet_pass_issue":
            if isinstance(self.issue, int):
                return httpx.Response(self.issue, json={"message": "Pas encore de billet pour cet événement : l'organisateur doit te le remettre."})
            return httpx.Response(200, json=self.issue)
        good = body.get("tok") == PASS_AUTH and body.get("serial") == SERIAL
        if name == "wallet_pass_by_token":
            return httpx.Response(200, json=self.issue if good else None)
        if name == "wallet_register":
            if not good:
                return httpx.Response(200, json="unauthorized")
            known = body["device"] in self.devices
            self.devices[body["device"]] = body["push"]
            return httpx.Response(200, json="exists" if known else "created")
        if name == "wallet_unregister":
            return httpx.Response(200, json=good and self.devices.pop(body["device"], None) is not None)
        if name == "wallet_updated_serials":
            since = body.get("since")
            fresh = body["device"] in self.devices and (since is None or datetime.fromisoformat(since) < datetime.fromisoformat(UPDATED))
            return httpx.Response(200, json={"serials": [SERIAL] if fresh else [], "last_updated": UPDATED})
        if name == "wallet_push_targets":
            if auth != "Bearer good":
                return httpx.Response(401, json={})
            if body.get("member") not in (None, ME):
                return httpx.Response(403, json={"message": "Seuls les organisateurs de l'événement préviennent les billets."})
            return httpx.Response(200, json=self.targets)
        return httpx.Response(404, json={})

    def accounts(self):
        return accounts_mod.Accounts(b"s" * 32, httpx.Client(transport=httpx.MockTransport(self.handler)))


class FakeApns:
    """Passerelle APNs simulée (un vrai push vers un iPhone ne se teste pas ici)."""

    def __init__(self, status=200):
        self.status = status
        self.requests: list[httpx.Request] = []

    def client(self):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(self.status, json={} if self.status == 200 else {"reason": "BadDeviceToken"})
        return httpx.Client(transport=httpx.MockTransport(handler))


def tickets_for(tmp_path, base: FakeBase, apns: FakeApns | None = None) -> WalletTickets:
    push = wallet_push.WalletPush((apns or FakeApns()).client())
    return WalletTickets(base.accounts(), fake_signer_dir(tmp_path / "w"), push=push)


def open_pass(data: bytes) -> tuple[dict, dict, zipfile.ZipFile]:
    z = zipfile.ZipFile(io.BytesIO(data))
    return json.loads(z.read("pass.json")), json.loads(z.read("manifest.json")), z


def fields(data: dict, group: str) -> dict:
    return {f["key"]: f["value"] for f in data["eventTicket"][group]}


# --- pass.json -----------------------------------------------------------------------------------------------

def test_pass_json_carries_the_ticket_and_the_exact_qr_of_the_app():
    data = wl.ticket_pass(origin="https://party.example", event=EVENT_ROW, user_id=ME, holder="Léa", ticket=TICKET,
                          auth_token=PASS_AUTH)
    assert data["passTypeIdentifier"] == "pass.ch.bobycharbon.party.ticket" and data["teamIdentifier"] == "GS2B6GA9JA"
    assert data["barcodes"][0] == {"format": "PKBarcodeFormatQR", "messageEncoding": "iso-8859-1", "altText": "K7M 2QX",
                                   "message": f"https://party.example/?tab=events&event={EVENT}&ticket={TOKEN_HEX}"}
    assert data["eventTicket"]["primaryFields"][0]["value"] == "Vendredi Party"
    # 19:00 UTC en novembre = 20:00 à Zurich.
    assert fields(data, "secondaryFields") == {"date": "jeudi 14 novembre 2030", "time": "20:00", "place": "Chez Boby"}
    assert fields(data, "auxiliaryFields") == {"holder": "Léa", "plus": "+2", "pay": "À payer : 20 CHF", "arrival": "—"}
    assert data["relevantDate"] == "2030-11-14T19:00:00+00:00"
    assert data["expirationDate"].startswith("2030-11-16T01:00")
    assert data["locations"][0]["latitude"] == 46.2044 and data["locations"][0]["longitude"] == 6.1432
    assert data["sharingProhibited"] is True and "voided" not in data
    assert data["backgroundColor"] == "rgb(21, 16, 42)"
    # Mises à jour automatiques : adresse du service et jeton propre au pass.
    assert data["webServiceURL"] == "https://party.example/api/wallet/passkit" and data["authenticationToken"] == PASS_AUTH


def test_arrival_and_payment_show_on_the_pass_with_a_change_message():
    data = wl.ticket_pass(origin="https://p.ch", event=EVENT_ROW, user_id=ME, holder="Léa",
                          ticket={**TICKET, "checked_in_at": "2030-11-14T19:04:00+00:00", "paid": True})
    aux = {f["key"]: f for f in data["eventTicket"]["auxiliaryFields"]}
    assert aux["arrival"]["value"] == "✓ 20:04" and "%@" in aux["arrival"]["changeMessage"]
    assert aux["pay"]["value"] == "Payé ✓" and "%@" in aux["pay"]["changeMessage"]


def test_pass_without_https_origin_does_not_promise_updates():
    data = wl.ticket_pass(origin="http://127.0.0.1:8000", event=EVENT_ROW, user_id=ME, holder="Léa", ticket=TICKET, auth_token=PASS_AUTH)
    assert "webServiceURL" not in data and "authenticationToken" not in data


def test_a_pass_no_longer_valid_is_voided():
    data = wl.ticket_pass(origin="https://p.ch", event=EVENT_ROW, user_id=ME, holder="Léa", ticket=TICKET, valid=False)
    assert data["voided"] is True
    assert "barcodes" not in data  # billet retiré ou « Billets QR » éteints : plus de QR utilisable dans Cartes


def test_pass_without_date_or_coordinates_stays_valid():
    data = wl.ticket_pass(origin="https://p.ch", user_id=ME, holder="Léa", ticket={"token": TOKEN_HEX, "code": "K7M2QX"},
                          event={"id": EVENT, "title": "Apéro", "starts_at": None, "location_url": "https://example.com/lieu"})
    assert "relevantDate" not in data and "locations" not in data
    assert data["eventTicket"]["secondaryFields"] == []
    assert list(fields(data, "auxiliaryFields")) == ["holder", "arrival"]


@pytest.mark.parametrize("url, expected", [
    ("https://maps.apple.com/?ll=46.2,6.15", (46.2, 6.15)),
    ("https://www.google.com/maps/place/X/@46.2044,6.1432,17z", (46.2044, 6.1432)),
    ("https://maps.google.com/?q=46.5%2C-6.25", (46.5, -6.25)),
    ("https://maps.apple.com/?address=Rue%20du%20Lac", None),
    ("https://maps.apple.com/?ll=123.0,6.1", None),
    (None, None),
])
def test_coordinates_are_read_from_the_map_link(url, expected):
    assert wl.coordinates(url) == expected


# --- paquet et signature -------------------------------------------------------------------------------------

def test_package_has_manifest_hashes_and_a_detached_signature(tmp_path):
    signer = wl.Signer.from_dir(fake_signer_dir(tmp_path / "w"))
    data = wl.package({"formatVersion": 1}, wl.images(), signer)
    _, manifest, z = open_pass(data)
    names = set(z.namelist())
    assert names == {"pass.json", "manifest.json", "signature", *wl.IMAGE_NAMES}
    assert set(manifest) == names - {"manifest.json", "signature"}
    for name, digest in manifest.items():
        assert hashlib.sha1(z.read(name)).hexdigest() == digest
    assert z.read("manifest.json") not in z.read("signature")  # PKCS#7 détaché


def test_icons_have_the_wallet_sizes():
    from PIL import Image
    sizes = {name: Image.open(wl.ASSETS / name).size for name in wl.IMAGE_NAMES}
    assert sizes["icon.png"] == (29, 29) and sizes["icon@2x.png"] == (58, 58) and sizes["icon@3x.png"] == (87, 87)
    assert sizes["logo.png"] == (50, 50) and sizes["logo@3x.png"] == (150, 150)


def test_missing_or_broken_certificates_disable_the_wallet(tmp_path):
    assert wl.Signer.from_dir(tmp_path) is None
    folder = fake_signer_dir(tmp_path / "w")
    (folder / "pass.key").write_text("pas une clé")
    assert wl.Signer.from_dir(folder) is None


def apple_root(tmp_path) -> Path | None:
    keychain = "/System/Library/Keychains/SystemRootCertificates.keychain"
    if not Path(keychain).exists():
        return None
    out = subprocess.run(["security", "find-certificate", "-c", "Apple Root CA", "-a", "-p", keychain], capture_output=True, text=True)
    if out.returncode or "BEGIN CERTIFICATE" not in out.stdout:
        return None
    path = tmp_path / "apple_roots.pem"
    path.write_text(out.stdout)
    return path


REAL_FILES = pytest.mark.skipif(not all((REAL / f).is_file() for f in wl.FILES), reason="Certificats Wallet réels absents")


@REAL_FILES
def test_real_pass_signature_verifies_against_the_apple_chain(tmp_path):
    roots = apple_root(tmp_path)
    if not roots:
        pytest.skip("Racine Apple introuvable (trousseau macOS)")
    tickets = WalletTickets(FakeBase().accounts(), REAL, push=wallet_push.WalletPush(None))
    assert tickets.enabled
    data = tickets.build("good", EVENT, "https://party.bobycharbon.ch")
    _, manifest, z = open_pass(data)
    (tmp_path / "manifest.json").write_bytes(z.read("manifest.json"))
    (tmp_path / "signature").write_bytes(z.read("signature"))
    result = subprocess.run(["openssl", "smime", "-verify", "-binary", "-inform", "DER", "-in", str(tmp_path / "signature"),
                             "-content", str(tmp_path / "manifest.json"), "-CAfile", str(roots), "-purpose", "any",
                             "-out", os.devnull], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Verification successful" in result.stderr
    certs = subprocess.run(["openssl", "pkcs7", "-inform", "DER", "-in", str(tmp_path / "signature"), "-print_certs", "-noout"],
                           capture_output=True, text=True).stdout
    assert "pass.ch.bobycharbon.party.ticket" in certs and "G4" in certs
    assert set(manifest) >= {"pass.json", "icon.png", "logo.png"}


@REAL_FILES
def test_real_certificate_makes_a_tls_client_context_for_apns():
    signer = wl.Signer.from_dir(REAL)
    context = wallet_push.tls_context(REAL, signer)
    assert context.verify_mode.name == "CERT_REQUIRED"  # Apple vérifié, notre certificat présenté
    assert wallet_push.WalletPush.from_signer(REAL, signer).client is not None


# --- service : ajout ----------------------------------------------------------------------------------------

def test_build_uses_the_member_session_only(tmp_path):
    base = FakeBase()
    data = tickets_for(tmp_path, base).build("good", EVENT, "https://p.ch")
    pass_json, _, _ = open_pass(data)
    assert pass_json["serialNumber"] == SERIAL and pass_json["authenticationToken"] == PASS_AUTH
    assert fields(pass_json, "auxiliaryFields")["holder"] == "Léa"
    assert {auth for _, _, auth, _ in base.seen} == {"Bearer good"}
    assert ("POST", "/rest/v1/rpc/wallet_pass_issue", "Bearer good", {"e": EVENT}) in base.seen


@pytest.mark.parametrize("issue", [400, payload(valid=False)])
def test_no_pass_without_a_ticket(tmp_path, issue):
    with pytest.raises(wl.WalletError, match="remettre"):
        tickets_for(tmp_path, FakeBase(issue=issue)).build("good", EVENT, "https://p.ch")


@pytest.fixture
def base():
    return FakeBase()


@pytest.fixture
def apns():
    return FakeApns()


@pytest.fixture
def client(tmp_path, monkeypatch, base, apns):
    monkeypatch.setattr(main, "wallet", tickets_for(tmp_path, base, apns))
    return TestClient(main.app)


def test_route_prepares_then_downloads_the_pass(client):
    assert client.get("/api/wallet/status").json() == {"enabled": True}
    r = client.post("/api/wallet/ticket", json={"token": "good", "event_id": EVENT}, headers={"Origin": "https://test.party.ch"})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/api/wallet/pass/") and url.endswith(".pkpass")
    got = client.get(url)
    assert got.status_code == 200
    assert got.headers["content-type"] == "application/vnd.apple.pkpass"
    pass_json, _, _ = open_pass(got.content)
    assert pass_json["barcodes"][0]["message"] == f"https://test.party.ch/?tab=events&event={EVENT}&ticket={TOKEN_HEX}"
    assert pass_json["webServiceURL"] == "https://test.party.ch/api/wallet/passkit"


def test_route_falls_back_to_the_public_url_for_a_strange_origin(client):
    url = client.post("/api/wallet/ticket", json={"token": "good", "event_id": EVENT}, headers={"Origin": "javascript:alert(1)"}).json()["url"]
    pass_json, _, _ = open_pass(client.get(url).content)
    assert pass_json["barcodes"][0]["message"].startswith(main.PUBLIC_URL + "/?tab=events")


def test_route_refuses_a_bad_session_an_unknown_link_and_a_bad_event_id(client):
    assert client.post("/api/wallet/ticket", json={"token": "bad", "event_id": EVENT}).status_code == 401
    assert client.post("/api/wallet/ticket", json={"token": "good", "event_id": "../x"}).status_code == 422
    assert client.get("/api/wallet/pass/inconnu.pkpass").status_code == 404


def test_route_answers_404_when_the_member_has_no_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "wallet", tickets_for(tmp_path, FakeBase(issue=400)))
    r = TestClient(main.app).post("/api/wallet/ticket", json={"token": "good", "event_id": EVENT})
    assert r.status_code == 404 and "remettre" in r.json()["detail"]


def test_route_answers_503_without_certificates(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "wallet", WalletTickets(FakeBase().accounts(), tmp_path / "vide"))
    c = TestClient(main.app)
    assert c.get("/api/wallet/status").json() == {"enabled": False}
    r = c.post("/api/wallet/ticket", json={"token": "good", "event_id": EVENT})
    assert r.status_code == 503 and r.json()["detail"] == "Wallet pas encore configuré"
    pk = f"/api/wallet/passkit/v1/passes/{wl.PASS_TYPE_ID}/{SERIAL}"
    assert c.get(pk, headers={"Authorization": f"ApplePass {PASS_AUTH}"}).status_code == 503


def test_download_link_expires(tmp_path, monkeypatch):
    tickets = tickets_for(tmp_path, FakeBase())
    link = tickets.prepare("good", EVENT, "https://p.ch")
    assert tickets.download(link)
    later = __import__("time").time() + 301
    monkeypatch.setattr("app.wallet_tickets.time.time", lambda: later)
    assert tickets.download(link) is None


# --- PassKit Web Service (l'iPhone, sans session) ------------------------------------------------------------

PK = "/api/wallet/passkit/v1"
REG = f"{PK}/devices/{DEVICE}/registrations/{wl.PASS_TYPE_ID}"
APPLE = {"Authorization": f"ApplePass {PASS_AUTH}"}


def test_device_registers_once_and_needs_the_pass_token(client, base):
    assert client.post(f"{REG}/{SERIAL}", json={"pushToken": PUSH}, headers=APPLE).status_code == 201
    assert client.post(f"{REG}/{SERIAL}", json={"pushToken": PUSH}, headers=APPLE).status_code == 200
    assert base.devices == {DEVICE: PUSH}
    bad = {"Authorization": "ApplePass " + "ee" * 32}
    assert client.post(f"{REG}/{SERIAL}", json={"pushToken": PUSH}, headers=bad).status_code == 401
    assert client.post(f"{REG}/{SERIAL}", json={"pushToken": PUSH}).status_code == 401
    assert client.post(f"{REG}/{SERIAL}", json={"pushToken": "pas hexa"}, headers=APPLE).status_code == 422
    # Les appels de l'iPhone se font sans session (clé publique seule), la base vérifie le jeton du pass.
    anon = [auth for _, path, auth, _ in base.seen if path.endswith("wallet_register")]
    assert anon and all(a is None for a in anon)


def test_updated_passes_list_then_the_latest_pass(client):
    client.post(f"{REG}/{SERIAL}", json={"pushToken": PUSH}, headers=APPLE)
    listing = client.get(REG)
    assert listing.status_code == 200 and listing.json()["serialNumbers"] == [SERIAL]
    tag = listing.json()["lastUpdated"]
    assert tag.isdigit()
    assert client.get(REG, params={"passesUpdatedSince": tag}).status_code == 204  # rien de neuf depuis
    assert client.get(f"{PK}/devices/inconnu/registrations/{wl.PASS_TYPE_ID}").status_code == 204
    got = client.get(f"{PK}/passes/{wl.PASS_TYPE_ID}/{SERIAL}", headers=APPLE)
    assert got.status_code == 200 and got.headers["content-type"] == "application/vnd.apple.pkpass"
    assert got.headers["last-modified"] == format_datetime(datetime.fromisoformat(UPDATED), usegmt=True)
    pass_json, _, _ = open_pass(got.content)
    assert pass_json["serialNumber"] == SERIAL
    assert pass_json["webServiceURL"] == "https://testserver/api/wallet/passkit"
    # Toujours le pass entier : deux changements dans la même seconde ne se perdent pas.
    again = client.get(f"{PK}/passes/{wl.PASS_TYPE_ID}/{SERIAL}", headers={**APPLE, "If-Modified-Since": got.headers["last-modified"]})
    assert again.status_code == 200
    assert client.get(f"{PK}/passes/{wl.PASS_TYPE_ID}/{SERIAL}", headers={"Authorization": "ApplePass " + "ee" * 32}).status_code == 401


def test_device_unregisters(client, base):
    client.post(f"{REG}/{SERIAL}", json={"pushToken": PUSH}, headers=APPLE)
    assert client.delete(f"{REG}/{SERIAL}", headers=APPLE).status_code == 200
    assert base.devices == {}
    assert client.delete(f"{REG}/{SERIAL}", headers={"Authorization": "ApplePass " + "ee" * 32}).status_code == 401


def test_wallet_logs_are_accepted(client):
    assert client.post(f"{PK}/log", json={"logs": ["Web service error"]}).status_code == 200


# --- push après un changement --------------------------------------------------------------------------------

def test_notify_sends_an_empty_push_to_the_pass_topic(client, apns, base):
    r = client.post("/api/wallet/notify", json={"token": "good", "event_id": EVENT, "member": ME})
    assert r.status_code == 200 and r.json() == {"devices": 1}
    assert len(apns.requests) == 1
    sent = apns.requests[0]
    assert str(sent.url) == f"https://api.push.apple.com/3/device/{PUSH}"
    assert sent.headers["apns-topic"] == "pass.ch.bobycharbon.party.ticket" and sent.content == b"{}"
    assert ("POST", "/rest/v1/rpc/wallet_push_targets", "Bearer good", {"e": EVENT, "member": ME}) in base.seen


def test_notify_is_refused_when_the_base_refuses(client, apns):
    assert client.post("/api/wallet/notify", json={"token": "bad", "event_id": EVENT}).status_code == 401
    other = "11111111-1111-1111-1111-111111111111"
    assert client.post("/api/wallet/notify", json={"token": "good", "event_id": EVENT, "member": other}).status_code == 403
    assert apns.requests == []


def test_gone_devices_are_not_counted_and_no_client_sends_nothing():
    assert wallet_push.WalletPush(FakeApns(status=410).client()).send([PUSH]) == 0
    assert wallet_push.WalletPush(FakeApns().client()).send([PUSH, PUSH]) == 1  # doublons envoyés une fois
    assert wallet_push.WalletPush(None).send([PUSH]) == 0


def test_ai_event_edit_pushes_the_event_passes(client, apns, monkeypatch):
    monkeypatch.setattr(main.event_editor, "save", lambda *a: {"id": EVENT, "title": "X", "changes": ["date"], "problems": []})
    r = client.post("/api/account/ai/event/edit/save", json={"token": "good", "event_id": EVENT, "draft": {}})
    assert r.status_code == 200 and len(apns.requests) == 1
