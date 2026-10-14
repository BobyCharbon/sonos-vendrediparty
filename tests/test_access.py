import pytest
from fastapi.testclient import TestClient

from app import main
from app.security import Limiter


@pytest.fixture
def client():
    main.guest_limiter = Limiter(per_ip=5, ip_lock=900, global_max=30, global_window=600, global_lock=600)
    return TestClient(main.app)


def test_guest_routes_require_pin(client):
    for path in ["/api/state", "/api/search?q=daft"]:
        assert client.get(path).status_code == 401
    assert client.post("/api/queue", json={"track_id": "x", "guest_id": "y", "guest_name": "z"}).status_code == 401
    assert client.get("/qr.svg").status_code == 401  # le QR contient le code : admin seulement


def test_join_with_pin_then_regenerate_logs_out(client):
    assert client.post("/api/join", json={"pin": "abcd"}).status_code == 401
    assert client.post("/api/join", json={"pin": main.store.session.guest_pin}).status_code == 200
    assert client.get("/api/state").status_code == 200

    main.store.regenerate_pin()
    assert client.get("/api/state").status_code == 401


def test_admin_sees_pin_and_qr_contains_it(client):
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    state = client.get("/api/admin/state").json()
    assert len(state["guest_pin"]) == 4 and state["guest_pin"].isdigit()
    # La page invités exige le code, même dans le navigateur de l'admin.
    assert client.get("/api/state").status_code == 401

    old = state["guest_pin"]
    assert client.post("/api/admin/pin").json()["guest_pin"] != old


def test_pin_bruteforce_is_locked(client):
    for _ in range(5):
        assert client.post("/api/join", json={"pin": "0000" if main.store.session.guest_pin != "0000" else "1111"}).status_code == 401
    # Même le bon code est refusé pendant le verrouillage.
    r = client.post("/api/join", json={"pin": main.store.session.guest_pin})
    assert r.status_code == 429


def test_global_lock_against_many_ips():
    lim = Limiter(per_ip=5, ip_lock=900, global_max=3, global_window=600, global_lock=600)
    for ip in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
        lim.fail(ip)
    assert lim.blocked("4.4.4.4") is not None
