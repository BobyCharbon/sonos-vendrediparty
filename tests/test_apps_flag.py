"""Agenda et Pronos gardés en test (décision de l'admin du 19.11) : allumés sur le site de test seulement, sauf
AGENDA_ENABLED / PRONOS_ENABLED. Éteints : leurs routes répondent 404, la page le dit au module (data-agenda="off",
data-pronos="off") et à l'app iPhone (/api/features), les confettis le sont aussi."""
import pytest
from fastapi.testclient import TestClient

from app import features, main


@pytest.fixture
def prod(monkeypatch):
    for name in ("AGENDA_ENABLED", "PRONOS_ENABLED", "PATATES_ENABLED"):
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
