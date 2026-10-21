"""Régressions de robustesse : des entrées hostiles ne doivent plus provoquer de 500.

Ces cas étaient atteignables sans authentification sur un site exposé à Internet.
"""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.security import Limiter


@pytest.fixture
def client():
    # Repartir de limiteurs neufs : les autres tests peuvent avoir verrouillé des IP.
    main.admin_limiter = Limiter(per_ip=3, ip_lock=15, global_max=30, global_window=900, global_lock=900, cooldown=True)
    main.guest_limiter = Limiter(per_ip=5, ip_lock=900, global_max=30, global_window=600, global_lock=600)
    return TestClient(main.app)


def test_non_ascii_admin_pin_is_rejected_not_crashed(client):
    # Avant : hmac.compare_digest(str, str) levait TypeError (500) sur un caractère non-ASCII.
    r = client.post("/api/admin/login", json={"pin": "é"})
    assert r.status_code == 401


def test_non_ascii_guest_pin_is_rejected_not_crashed(client):
    r = client.post("/api/join", json={"pin": "é"})
    assert r.status_code == 401


def test_eq_handles_non_ascii_without_raising():
    # Cœur du correctif : la comparaison à temps constant ne doit jamais lever TypeError
    # sur une entrée non-ASCII (cookie vp_admin/vp_guest forgé reçu en octets bruts).
    # Le client de test httpx refuse d'émettre un tel cookie, d'où ce test direct.
    assert main._eq("é", "abc") is False
    assert main._eq("abc", "é") is False
    assert main._eq("héllo", "héllo") is True
    assert main._eq("", "") is True


def test_oversized_pin_body_is_rejected(client):
    # Champ borné (max_length) : un corps démesuré est refusé par la validation (422), pas bufferisé.
    assert client.post("/api/admin/login", json={"pin": "x" * 100_000}).status_code == 422


def test_events_path_with_nul_byte_is_404_not_500(client):
    # Path.resolve lève ValueError sur un octet nul ; on renvoie 404.
    assert client.get("/events/%00").status_code == 404


def test_roulette_names_flood_is_rejected(client):
    # DoS O(n²) de set_names : une liste démesurée est refusée par la validation du corps.
    client.post("/api/admin/login", json={"pin": "9999"})
    created = client.post("/api/games", json={"guest_id": "host-robust-1", "name": "Hôte", "type": "roulette"})
    assert created.status_code == 200
    code = created.json()["code"]
    r = client.post(f"/api/games/{code}", json={
        "guest_id": "host-robust-1", "action": "names", "names": ["n"] * 5000,
    })
    assert r.status_code == 422


def test_quiz_configure_with_non_string_theme_does_not_crash(client):
    client.post("/api/admin/login", json={"pin": "9999"})
    created = client.post("/api/games", json={"guest_id": "host-robust-2", "name": "Hôte", "type": "quiz"})
    assert created.status_code == 200
    code = created.json()["code"]
    # Un thème non-texte ([1]) ne doit plus lever TypeError (500) dans quiz.configure.
    r = client.post(f"/api/games/{code}", json={
        "guest_id": "host-robust-2", "action": "qset", "settings": {"themes": [[1], "inconnu"]},
    })
    assert r.status_code != 500
