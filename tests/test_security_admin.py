"""Sécurité de l'admin (campagne du 14.11.2026) : chaque route admin refuse sans session, la déconnexion invalide
vraiment la session, le cookie est protégé, le code admin résiste à la force brute, un jeton de compte fermé n'est
plus reconnu."""
import re
import time

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import account_auth, accounts as accounts_mod, main
from app.security import Limiter


def _deps(dependant) -> set[str]:
    out = set()
    for d in dependant.dependencies:
        out.add(getattr(d.call, "__name__", ""))
        out |= _deps(d)
    return out


def admin_routes():
    """Toutes les routes de l'admin : /api/admin/* (sauf connexion / déconnexion) et celles qui exigent la session."""
    found = []
    for r in main.app.routes:
        if not isinstance(r, APIRoute):
            continue
        admin_path = r.path.startswith("/api/admin/") and r.path not in ("/api/admin/login", "/api/admin/logout")
        if admin_path or "require_admin" in _deps(r.dependant):
            found += [(m, r.path, r) for m in sorted(r.methods) if m != "HEAD"]
    return found


@pytest.fixture
def client():
    main.admin_limiter = Limiter(per_ip=3, ip_lock=15, global_max=30, global_window=900, global_lock=900, cooldown=True)
    return TestClient(main.app)


def test_every_admin_route_is_guarded_by_require_admin():
    routes = admin_routes()
    assert len(routes) > 40
    unguarded = [(m, p) for m, p, r in routes if "require_admin" not in _deps(r.dependant)]
    assert unguarded == []


@pytest.mark.parametrize("method,path", [(m, p) for m, p, _ in admin_routes()])
def test_admin_route_refuses_without_session_or_with_a_forged_cookie(client, method, path):
    url = re.sub(r"\{[^}]+\}", "x", path)
    if url.startswith("/api/tv/zicou") and not main.compagnon_enabled():
        pytest.skip("Zicou éteint : 404")
    body = {} if method in ("POST", "DELETE", "PUT") else None
    assert client.request(method, url, json=body).status_code == 401
    client.cookies.set("vp_admin", "0" * 64)
    assert client.request(method, url, json=body).status_code == 401
    client.cookies.set("vp_admin", "a1b2.0000")
    assert client.request(method, url, json=body).status_code == 401


def test_logout_really_ends_the_admin_session(client):
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    stolen = client.cookies.get("vp_admin")
    assert client.get("/api/admin/state").status_code == 200
    assert client.post("/api/admin/logout").status_code == 200
    thief = TestClient(main.app, cookies={"vp_admin": stolen})
    assert thief.get("/api/admin/state").status_code == 401  # un cookie copié avant la déconnexion ne vaut plus rien


def test_each_login_is_its_own_session(client):
    other = TestClient(main.app)
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    assert other.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    assert client.cookies.get("vp_admin") != other.cookies.get("vp_admin")
    client.post("/api/admin/logout")
    assert other.get("/api/admin/state").status_code == 200  # se déconnecter du téléphone ne déconnecte pas l'ordinateur


def test_admin_session_ends_after_thirty_days_even_if_the_cookie_is_kept(client, monkeypatch):
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    # Cookie gardé de force (sans date d'expiration côté navigateur) : seul le serveur peut y mettre fin.
    kept = TestClient(main.app, cookies={"vp_admin": client.cookies.get("vp_admin")})
    assert kept.get("/api/admin/state").status_code == 200
    later = time.time() + 31 * 86400
    monkeypatch.setattr(main.time, "time", lambda: later)
    assert kept.get("/api/admin/state").status_code == 401


def test_changing_the_admin_code_ends_every_session(client, monkeypatch):
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    monkeypatch.setattr(main, "ADMIN_PIN", "4242")
    assert client.get("/api/admin/state").status_code == 401


def test_admin_cookie_is_httponly_strict_and_secure_over_https():
    c = TestClient(main.app, base_url="https://party.test")
    main.admin_limiter = Limiter(per_ip=3, ip_lock=15, global_max=30, global_window=900, global_lock=900, cooldown=True)
    r = c.post("/api/admin/login", json={"pin": "9999"})
    cookie = r.headers["set-cookie"].lower()
    assert "vp_admin=" in cookie and "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie


def test_admin_code_brute_force_is_slowed_and_logged(client):
    before = len(main.journal.read(500, None))
    for pin in ("0000", "1111", "2222"):
        assert client.post("/api/admin/login", json={"pin": pin}).status_code == 401
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 429  # même le bon code attend
    entries = main.journal.read(500, None)
    assert len(entries) - before == 3 and all(e["action"] == "admin.login_failed" for e in entries[:3])


def test_cross_site_form_post_never_reaches_an_admin_action(client):
    # Un formulaire d'un autre site ne peut envoyer que du text/plain ou un formulaire : jamais traité comme du JSON.
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    pin = main.store.session.guest_pin
    r = client.post("/api/admin/pin", content='{"pin":"1234"}', headers={"content-type": "text/plain"})
    assert r.status_code == 422 and main.store.session.guest_pin == pin
    # Pas de CORS : un autre site ne lit aucune réponse.
    r = client.get("/api/notice", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_notice_routes_refuse_before_reading_the_body(client):
    # Annonce et maintenance : sans session, 401 (et non une erreur de saisie qui laisse deviner la route).
    assert client.post("/api/admin/notice", json={"kind": "info", "message": "x"}).status_code == 401
    assert client.post("/api/admin/notice", json={}).status_code == 401
    assert client.delete("/api/admin/notice").status_code == 401


def test_signed_out_account_token_is_no_longer_trusted_from_the_cache():
    """Déconnexion d'un compte : le jeton n'est plus reconnu par Party tout de suite (et non 5 min plus tard)."""
    alive = {"on": True}

    def handler(request: httpx.Request):
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u1"}) if alive["on"] else httpx.Response(403, json={"msg": "session_not_found"})
        if request.url.path == "/auth/v1/logout":
            alive["on"] = False
            return httpx.Response(204)
        return httpx.Response(204)

    acc = accounts_mod.Accounts(b"s", httpx.Client(transport=httpx.MockTransport(handler)))
    token = "t" * 40
    assert acc._uid(token) == "u1"
    account_auth.AccountAuth(acc).sign_out(token)
    with pytest.raises(accounts_mod.AccountError):
        acc._uid(token)
