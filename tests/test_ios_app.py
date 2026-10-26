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
