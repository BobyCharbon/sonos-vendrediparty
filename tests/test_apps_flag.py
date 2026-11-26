"""Agenda et Pronos gardés en test (décision de l'admin du 19.11) : allumés sur le site de test seulement, sauf
AGENDA_ENABLED / PRONOS_ENABLED. Éteints : leurs routes répondent 404, la page le dit au module (data-agenda="off",
data-pronos="off") et à l'app iPhone (/api/features), les confettis le sont aussi."""
import pytest
from fastapi.testclient import TestClient

from app import features, main


@pytest.fixture
def prod(monkeypatch):
    for name in ("AGENDA_ENABLED", "PRONOS_ENABLED", "PATATES_ENABLED", "SOUVENIRS_ENABLED", "COVERS_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://party.bobycharbon.ch")
    main._pages.clear()
    yield TestClient(main.app)
    main._pages.clear()


def test_agenda_and_pronos_are_off_in_production(prod):
    assert not features.agenda_enabled() and not features.pronos_enabled()
    flags = prod.get("/api/features").json()
    assert flags["agenda"] is False and flags["pronos"] is False and flags["patates"] is False
    for path in ("/d/" + "a" * 24, "/agenda/ludo/soiree", "/prono/" + "a" * 24):
        assert prod.get(path).status_code == 404, path
    for path in ("/api/account/agenda/rpc", "/api/account/pronos/rpc"):
        assert prod.post(path, json={"token": "x" * 30, "fn": "x"}).status_code == 404, path
    page = prod.get("/").text
    assert 'data-agenda="off"' in page and 'data-pronos="off"' in page


def test_patates_stay_off_while_pronos_are_off(prod, monkeypatch):
    monkeypatch.setenv("PATATES_ENABLED", "1")
    assert prod.get("/api/features").json()["patates"] is False


@pytest.mark.parametrize("name", ["AGENDA_ENABLED", "PRONOS_ENABLED"])
def test_the_test_site_keeps_them_on(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://partytest.bobycharbon.ch")
    main._pages.clear()
    try:
        flags = TestClient(main.app).get("/api/features").json()
        assert flags["agenda"] is True and flags["pronos"] is True
        assert 'data-agenda="off"' not in TestClient(main.app).get("/").text
    finally:
        main._pages.clear()


STORE_UA = {"User-Agent": "Mozilla/5.0 (iPhone) PartyStore/1.0"}
SOUVENIR_ROUTES = [("post", "/api/account/souvenirs/rpc", {"token": "x" * 30, "fn": "souvenir_counter", "args": {}}),
                   ("post", "/api/account/souvenirs/links", {"token": "x" * 30, "paths": []}),
                   ("get", "/api/souvenirs/file/" + "a" * 40, None)]
COVER_ROUTES = [("post", "/api/account/event-cover/" + n, {"token": "x" * 30, "event_id": "0" * 36})
                for n in ("suggest", "official", "poster", "remove")]


def call(client, method, path, body, headers=None):
    return client.get(path, headers=headers) if method == "get" else client.post(path, json=body, headers=headers)


def test_souvenirs_and_covers_are_off_in_production(prod):
    """Contrôle Apple du 26.11 : Souvenirs et couverture gardés en test ; la page le dit au module (data-souvenirs,
    data-covers), /api/features à l'app iPhone, leurs routes répondent 404."""
    assert not features.souvenirs_enabled() and not features.covers_enabled()
    flags = prod.get("/api/features").json()
    assert flags["souvenirs"] is False and flags["covers"] is False
    for method, path, body in SOUVENIR_ROUTES + COVER_ROUTES:
        assert call(prod, method, path, body).status_code == 404, path
    page = prod.get("/").text
    assert 'data-souvenirs="off"' in page and 'data-covers="off"' in page


@pytest.mark.parametrize("name", ["SOUVENIRS_ENABLED", "COVERS_ENABLED"])
def test_the_test_site_keeps_souvenirs_and_covers_on(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://partytest.bobycharbon.ch")
    main._pages.clear()
    try:
        client = TestClient(main.app)
        flags = client.get("/api/features").json()
        assert flags["souvenirs"] is True and flags["covers"] is True
        page = client.get("/").text
        assert 'data-souvenirs="off"' not in page and 'data-covers="off"' not in page
    finally:
        main._pages.clear()


def test_the_app_store_app_never_gets_souvenirs_nor_covers(monkeypatch):
    """Allumés sur le serveur (site de test ou variable), l'app App Store ne les reçoit jamais."""
    monkeypatch.setenv("SOUVENIRS_ENABLED", "1")
    monkeypatch.setenv("COVERS_ENABLED", "1")
    main._pages.clear()
    try:
        client = TestClient(main.app)
        flags = client.get("/api/features", headers=STORE_UA).json()
        assert flags["souvenirs"] is False and flags["covers"] is False
        for method, path, body in SOUVENIR_ROUTES + COVER_ROUTES:
            assert call(client, method, path, body, STORE_UA).status_code == 404, path
        page = client.get("/", headers=STORE_UA).text
        assert 'data-souvenirs="off"' in page and 'data-covers="off"' in page
        assert client.get("/api/features").json()["souvenirs"] is True  # le navigateur, lui, les garde
    finally:
        main._pages.clear()
