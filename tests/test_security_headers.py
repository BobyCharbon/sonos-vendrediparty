"""En-têtes de sécurité (campagne du 14.11.2026) : la page Party, l'admin, les fichiers et l'API ne se laissent pas
mettre en cadre par un autre site (vol de clics sur l'admin), ni deviner leur type ; HSTS seulement en HTTPS.
Le module Événements reste dans le cadre de Party (même origine : frame-ancestors 'self')."""
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.mark.parametrize("path", ["/", "/admin", "/tv", "/static/style.css", "/static/games.js", "/api/features", "/api/notice"])
def test_every_page_file_and_api_answer_carries_the_security_headers(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    csp = r.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in csp and "object-src 'none'" in csp and "base-uri 'self'" in csp
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_hsts_only_over_https(client):
    assert "strict-transport-security" not in client.get("/").headers
    behind_proxy = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert behind_proxy.headers["strict-transport-security"] == main.HSTS
    assert "includeSubDomains" not in main.HSTS
