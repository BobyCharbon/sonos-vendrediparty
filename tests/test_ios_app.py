"""App iOS native (ios/) : fichier des liens universels servi par le site, pour que les QR codes ouvrent l'app."""
from fastapi.testclient import TestClient

from app import main


def test_apple_app_site_association_lists_the_ios_app_for_every_path():
    client = TestClient(main.app)
    r = client.get("/.well-known/apple-app-site-association", follow_redirects=False)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    details = r.json()["applinks"]["details"]
    assert details == [{"appIDs": ["GS2B6GA9JA.ch.bobycharbon.party"], "components": [{"/": "/*"}]}]
