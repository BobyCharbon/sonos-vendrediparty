"""Hoquet de la base ≠ refus (campagne 2, rapport 08 n° 5) : si my_permissions (ou la vérification de session) échoue
par une panne passagère, l'admin ne doit plus lire « L'assistant IA n'est pas activé pour ton compte » ni « Ta connexion
a expiré » : 503 « Réessaie dans un instant ». Un vrai refus reste un refus."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main
from app.accounts import AccountError, ServiceUnavailable

TOKEN = "tok-" + "x" * 40


def accounts(perms_status: int = 200, perms=None, user_status: int = 200):
    def handler(request: httpx.Request):
        if request.url.path == "/auth/v1/user":
            return httpx.Response(user_status, json={"id": "u-me"} if user_status == 200 else {"message": "x"})
        if request.url.path.endswith("/my_permissions"):
            return httpx.Response(perms_status, json=perms if perms_status == 200 else {"message": "timeout"})
        if request.url.path == "/rest/v1/notification_prefs":
            return httpx.Response(200, json=[{"user_id": "u-me"}])
        return httpx.Response(200, json=[])
    return accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("status", [500, 503, 504, 429])
def test_a_base_hiccup_on_permissions_is_not_an_empty_list(status):
    with pytest.raises(ServiceUnavailable, match="Réessaie dans un instant"):
        accounts(perms_status=status)._perms("tok")


def test_permissions_still_read_normally_and_service_unavailable_is_an_account_error():
    assert accounts(perms=["ai.use"])._perms("tok") == {"ai.use"}
    assert accounts(perms=[])._perms("tok") == set()
    assert issubclass(ServiceUnavailable, AccountError)


def test_auth_down_is_not_an_expired_session_but_a_bad_token_still_is():
    with pytest.raises(ServiceUnavailable):
        accounts(user_status=503)._uid("tok-a")
    with pytest.raises(AccountError, match="Ta connexion a expiré") as e:
        accounts(user_status=401)._uid("tok-b")
    assert not isinstance(e.value, ServiceUnavailable)


def test_network_failure_is_service_unavailable():
    def boom(request):
        raise httpx.ConnectTimeout("lent")
    acc = accounts_mod.Accounts(b"s", httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(ServiceUnavailable):
        acc._uid("tok")


def test_ai_routes_answer_503_retry_on_a_hiccup_and_403_on_a_real_refusal(monkeypatch):
    monkeypatch.setattr(main.assistant, "accounts", accounts(perms_status=504))
    client = TestClient(main.app)
    r = client.post("/api/account/ai/status", json={"token": TOKEN})
    assert r.status_code == 503 and "Réessaie dans un instant" in r.json()["detail"]
    monkeypatch.setattr(main.assistant, "accounts", accounts(perms=[]))
    r = client.post("/api/account/ai/status", json={"token": TOKEN})
    assert r.status_code == 200 and r.json()["allowed"] is False


def test_notification_settings_say_retry_on_a_hiccup_not_signed_out(monkeypatch):
    monkeypatch.setattr(main, "accounts", accounts(perms_status=503))
    r = TestClient(main.app).post("/api/account/notifications", json={"token": TOKEN})
    assert r.status_code == 503 and "Réessaie dans un instant" in r.json()["detail"]
