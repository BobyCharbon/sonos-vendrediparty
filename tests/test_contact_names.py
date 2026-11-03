"""Noms des contacts (app iPhone) : seules des empreintes passent, réponse limitée à {user_id, hash}, rien n'est gardé."""
import hashlib
import hmac
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main
from app.contact_names import ContactNames

KEY = "ab" * 32
LEA = "11111111-1111-1111-1111-111111111111"


def digest(number: str) -> str:
    return hmac.new(KEY.encode(), number.encode(), hashlib.sha256).hexdigest()


def fake(status: int = 200, rows: list | None = None):
    seen = []

    def handler(request: httpx.Request):
        seen.append((request.url.path, request.content))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-me"})
        if request.url.path == "/rest/v1/rpc/contacts_key":
            return httpx.Response(200, json=KEY)
        if request.url.path == "/rest/v1/rpc/contacts_match":
            if status != 200:
                return httpx.Response(status, json={"message": "rate_limited: Trop de demandes, réessaie plus tard"})
            return httpx.Response(200, json=rows if rows is not None else [{"user_id": LEA, "hash": digest("+41790000001"), "phone": "41790000001"}])
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    return ContactNames(acc), seen


def test_key_comes_from_the_base_with_the_member_session():
    names, seen = fake()
    assert names.key("tok") == KEY
    assert ("/rest/v1/rpc/contacts_key", b"{}") in seen


def test_only_hashes_are_sent_deduplicated_and_the_answer_never_carries_a_number():
    names, seen = fake()
    h = digest("+41790000001")
    result = names.match("tok", [h, h.upper(), digest("+33612345678")])
    assert result == [{"user_id": LEA, "hash": h}]  # le champ « phone » de la base n'est jamais relayé
    body = json.loads(next(c for p, c in seen if p == "/rest/v1/rpc/contacts_match"))
    assert sorted(body["hashes"]) == sorted({h, digest("+33612345678")})
    assert "41790000001" not in json.dumps(body)


def test_a_match_that_was_not_asked_for_is_dropped():
    names, _ = fake(rows=[{"user_id": LEA, "hash": digest("+41790000009")}, {"user_id": "pas-un-uuid", "hash": digest("+1")}])
    assert names.match("tok", [digest("+41790000001")]) == []


def test_invalid_hashes_are_refused_before_reaching_the_base():
    names, seen = fake()
    for bad in (["+41790000001"], ["zz" * 32]):
        try:
            names.match("tok", bad)
            raise AssertionError("aurait dû être refusé")
        except accounts_mod.AccountError:
            pass
    assert not any(p == "/rest/v1/rpc/contacts_match" for p, _ in seen)


def test_routes_relay_and_map_the_rate_limit_to_429(monkeypatch):
    names, _ = fake()
    monkeypatch.setattr(main, "contact_names", names)
    client = TestClient(main.app)
    assert client.post("/api/account/contacts/key", json={"token": "tok"}).json() == {"key": KEY}
    h = digest("+41790000001")
    r = client.post("/api/account/contacts/match", json={"token": "tok", "hashes": [h]})
    assert r.status_code == 200 and r.json() == {"matches": [{"user_id": LEA, "hash": h}]}
    limited, _ = fake(status=400)
    monkeypatch.setattr(main, "contact_names", limited)
    assert client.post("/api/account/contacts/match", json={"token": "tok", "hashes": [h]}).status_code == 429


def test_too_many_hashes_are_refused_by_the_route():
    client = TestClient(main.app)
    r = client.post("/api/account/contacts/match", json={"token": "tok", "hashes": ["a" * 64] * 20001})
    assert r.status_code == 422
