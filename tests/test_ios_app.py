"""Apps iOS natives (ios/) : fichier des liens universels servi par le site, pour que les QR codes ouvrent l'app.

Le site principal ouvre VendrediParty (ch.bobycharbon.party), le site de test VendrediPartyBETA (….beta)."""
from fastapi.testclient import TestClient

from app import main


def app_ids(monkeypatch, public_url):
    if public_url is None:
        monkeypatch.delenv("PARTY_PUBLIC_URL", raising=False)
    else:
        monkeypatch.setenv("PARTY_PUBLIC_URL", public_url)
    r = TestClient(main.app).get("/.well-known/apple-app-site-association", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    details = r.json()["applinks"]["details"]
    assert [d["components"] for d in details] == [[{"/": "/*"}]]
    return details[0]["appIDs"]


def test_main_site_opens_the_app_store_app(monkeypatch):
    assert app_ids(monkeypatch, None) == ["GS2B6GA9JA.ch.bobycharbon.party"]
    assert app_ids(monkeypatch, "https://party.bobycharbon.ch") == ["GS2B6GA9JA.ch.bobycharbon.party"]


def test_test_site_opens_the_beta_app(monkeypatch):
    assert app_ids(monkeypatch, "https://partytest.bobycharbon.ch/") == ["GS2B6GA9JA.ch.bobycharbon.party.beta"]


# ── Pas de zoom : l'app doit se sentir native, pas comme un site web ──
_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
NO_ZOOM = "maximum-scale=1, user-scalable=no"


def test_every_page_forbids_zooming():
    for page in ("app/static/index.html", "app/static/admin.html", "app/static/tv.html", "web/events/scripts/postbuild.mjs"):
        assert NO_ZOOM in (_ROOT / page).read_text(encoding="utf-8"), page


def test_pinch_and_double_tap_zoom_are_blocked_in_the_page():
    js = (_ROOT / "app/static/ios-app.js").read_text(encoding="utf-8")
    assert '"gesturestart"' in js and "preventDefault" in js
    css = (_ROOT / "app/static/style.css").read_text(encoding="utf-8")
    assert "touch-action: manipulation" in css


def test_native_app_web_view_cannot_zoom():
    swift = (_ROOT / "ios/Party/PartyWebView.swift").read_text(encoding="utf-8")
    assert "maximumZoomScale = 1" in swift and "viewForZooming" in swift


# ── Android (android/) : Digital Asset Links, pour que l'app s'ouvre sans barre d'adresse ──
def asset_links(monkeypatch, public_url):
    monkeypatch.setenv("PARTY_PUBLIC_URL", public_url)
    r = TestClient(main.app).get("/.well-known/assetlinks.json", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    [statement] = r.json()
    assert statement["relation"] == ["delegate_permission/common.handle_all_urls"]
    assert statement["target"]["namespace"] == "android_app"
    assert main.ANDROID_UPLOAD_KEY_SHA256 in statement["target"]["sha256_cert_fingerprints"]
    return statement["target"]["package_name"]


def test_main_site_declares_the_play_store_app(monkeypatch):
    assert asset_links(monkeypatch, "https://party.bobycharbon.ch") == "ch.bobycharbon.party"


def test_test_site_declares_the_android_beta_app(monkeypatch):
    assert asset_links(monkeypatch, "https://partytest.bobycharbon.ch") == "ch.bobycharbon.party.beta"
