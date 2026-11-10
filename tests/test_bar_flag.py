"""Bar de la soirée (maquettes v6 du 10.11, en construction) : drapeau bar_enabled — allumé sur le site de test seulement
sans variable, BAR_ENABLED ("1" / "0") décide sinon ; la page sert <html data-bar="off"> quand il est éteint (lu par le
module Événements) et /api/features le dit aux apps natives. Rien du bar n'apparaît en production tant que l'admin n'a pas
validé la recette et donné son « Ok prod »."""
import pytest
from fastapi.testclient import TestClient

from app import features, main


@pytest.fixture
def page_dir(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>Party</title></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path)
    main._pages.clear()
    yield tmp_path
    main._pages.clear()


@pytest.mark.parametrize("url, expected", [("https://partytest.bobycharbon.ch", True), ("https://party.bobycharbon.ch", False)])
def test_the_bar_is_on_only_on_the_test_site_without_the_variable(monkeypatch, url, expected):
    monkeypatch.delenv("BAR_ENABLED", raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", url)
    assert features.bar_enabled() is expected


def test_the_variable_decides_and_the_native_apps_read_it(monkeypatch):
    monkeypatch.setenv("BAR_ENABLED", "1")
    assert TestClient(main.app).get("/api/features").json()["bar"] is True
    monkeypatch.setenv("BAR_ENABLED", "0")
    assert TestClient(main.app).get("/api/features").json()["bar"] is False


def test_the_events_page_says_bar_off_in_production_and_not_on_the_test_site(monkeypatch, page_dir):
    client = TestClient(main.app)
    monkeypatch.setenv("BAR_ENABLED", "0")
    main._pages.clear()
    assert 'data-bar="off"' in client.get("/events/").text
    monkeypatch.setenv("BAR_ENABLED", "1")
    main._pages.clear()
    assert 'data-bar="off"' not in client.get("/events/").text
