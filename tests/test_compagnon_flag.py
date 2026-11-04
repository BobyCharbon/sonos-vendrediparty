"""Compagnon (Zicou) en bêta (décision de l'admin, 04.11.2026) : allumé sur le site de test, éteint en production,
sans dépendre d'une branche (app/features.py). Éteint : ses routes répondent 404, rien ne se calcule, la page ne
l'affiche nulle part."""
import pytest
from fastapi.testclient import TestClient
from starlette.responses import Response

from app import features, main

SOON = "Zicou arrive bientôt."   # jamais « Compagnon » dans un texte visible (décision du 04.11.2026)


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setenv("COMPAGNON_ENABLED", "0")
    return TestClient(main.app)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("COMPAGNON_ENABLED", "1")
    return TestClient(main.app)


# ── Le drapeau ──

@pytest.mark.parametrize("value, expected", [("1", True), ("0", False)])
def test_the_variable_decides_when_it_is_set(monkeypatch, value, expected):
    for url in ("https://party.bobycharbon.ch", "https://partytest.bobycharbon.ch"):
        monkeypatch.setenv("PARTY_PUBLIC_URL", url)
        monkeypatch.setenv("COMPAGNON_ENABLED", value)
        assert features.compagnon_enabled() is expected


@pytest.mark.parametrize("url, expected", [
    ("https://partytest.bobycharbon.ch", True),
    ("https://partytest.bobycharbon.ch/", True),
    ("https://party.bobycharbon.ch", False),
    ("https://partytest.bobycharbon.ch.example.com", False),
    ("", False),   # adresse par défaut : la production
])
def test_without_the_variable_only_the_test_site_has_it(monkeypatch, url, expected):
    monkeypatch.delenv("COMPAGNON_ENABLED", raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", url)
    assert features.compagnon_enabled() is expected


def test_an_unknown_value_falls_back_to_the_site_address(monkeypatch):
    monkeypatch.setenv("COMPAGNON_ENABLED", "oui")
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://party.bobycharbon.ch")
    assert features.compagnon_enabled() is False


def test_the_apps_read_the_flag(off, on, monkeypatch):
    assert on.get("/api/features").json()["compagnon"] is True
    monkeypatch.setenv("COMPAGNON_ENABLED", "0")
    assert off.get("/api/features").json()["compagnon"] is False


# ── Éteint : aucune route ──

@pytest.mark.parametrize("path", ["/api/pet/me", "/api/pet/status", "/api/pet/act", "/api/pet/game", "/api/pet/friends",
                                  "/api/pet/friend", "/api/pet/gift", "/api/pet/collection", "/api/pet/coll",
                                  "/api/pet/reactions", "/api/pet/reactions/prefs"])
def test_every_pet_route_answers_404_when_off(off, path):
    r = off.post(path, json={"token": "x" * 40, "guest_id": "acct-" + "1" * 40})
    assert r.status_code == 404 and r.json()["detail"] == SOON


@pytest.mark.parametrize("path", ["/api/tv/zicou", "/api/pet/certificats/cle", "/api/pet/verifier?code=AB",
                                  "/zicou/certificat", "/static/pet/pet.js"])
def test_tv_dance_floor_certificates_and_scripts_answer_404_when_off(off, path):
    r = off.get(path)
    assert r.status_code == 404 and r.json()["detail"] == SOON


def test_routes_still_answer_when_on(on):
    assert on.post("/api/pet/reactions", json={"guest_id": "acct-" + "1" * 40}).status_code == 200
    assert on.get("/static/pet/pet.js").status_code == 200


# ── Éteint : rien ne se calcule ──

def test_no_reaction_is_computed_when_off(monkeypatch):
    calls = []
    monkeypatch.setattr(main.pet_party_log, "react", lambda *a: calls.append(a))
    monkeypatch.setenv("COMPAGNON_ENABLED", "0")
    main.zicou_react("acct-" + "1" * 40, "music", "t1")
    assert calls == []
    assert main.zicou_now(Response(), "acct-" + "1" * 40) == []
    monkeypatch.setenv("COMPAGNON_ENABLED", "1")
    main.zicou_react("acct-" + "1" * 40, "music", "t1")
    assert calls == [("acct-" + "1" * 40, "music", "t1")]


def test_no_reaction_call_bypasses_the_flag():
    """Fin de partie, file, Méninges : toutes passent par zicou_react (un seul endroit vérifie le drapeau)."""
    src = (main.STATIC.parent / "main.py").read_text()
    assert src.count("pet_party_log.react(") == 1
    assert src.count("zicou_react(") >= 4
    assert "compagnon_enabled() and soiree_zicous.due(uid)" in src   # /api/join/account : Apple TV


# ── Éteint : la page ne l'affiche pas ──

def test_the_page_has_no_trace_of_the_companion_when_off(off):
    html = off.get("/").text
    assert '<html data-compagnon="off"' in html
    for trace in ('data-tab="pet"', "/static/pet/", "zicouChip", "zicouFloat", 'id="petTab"', "<!-- compagnon -->"):
        assert trace not in html, trace
    assert 'data-tab="music"' in html and 'data-tab="games"' in html


def test_the_page_keeps_the_companion_when_on(on):
    html = on.get("/").text
    assert '<html data-compagnon' not in html
    for trace in ('data-tab="pet"', "/static/pet/pet.js", "zicouChip", 'id="petTab"'):
        assert trace in html, trace


def test_the_events_module_hides_companion_settings_when_off(monkeypatch, tmp_path):
    """Module Événements (Réglages › Compagnon, cadeaux Zicou, mesure de l'admin) : il lit <html data-compagnon>."""
    root = tmp_path / "events-web"
    root.mkdir()
    (root / "index.html").write_text('<html><div id="root"></div></html>')
    monkeypatch.setattr(main, "EVENTS_WEB", root)
    monkeypatch.setenv("COMPAGNON_ENABLED", "0")
    assert '<html data-compagnon="off"' in TestClient(main.app).get("/events/settings/notifications").text
    monkeypatch.setenv("COMPAGNON_ENABLED", "1")
    assert "data-compagnon" not in TestClient(main.app).get("/events/settings/notifications").text
    src = (main.STATIC.parents[1] / "web" / "events" / "src")
    assert "dataset.compagnon !== 'off'" in (src / "lib" / "features.ts").read_text()
    for screen in ("app/settings/notifications.tsx", "app/admin/index.tsx", "app/event/[id]/index.tsx",
                   "app/event/[id]/gifts.tsx"):
        assert "compagnonOn" in (src / screen).read_text(), screen
