"""CGU exigées en prod (private.moderation_settings.terms_enforced, 06.11) : quand la base refuse une publication avec
« terms_required: … » (private.require_terms), le serveur répond 403 {"detail": <la phrase>, "code": "terms_required"}
pour que l'app ouvre la feuille des CGU puis relance l'action ; les autres refus de la base (content_refused,
blocked…) remontent avec leur phrase au lieu d'un message général. Bug de prod : « Oui, continuer » de l'assistant IA
renvoyait 400 « L'événement n'a pas pu être créé » sans dire pourquoi."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai_event_edit as edit
from app import main
from app.accounts import AccountError, TermsRequired, db_refusal
from app.group_admin import refusal
from tests.test_ai_events import READY, Resp, make

TERMS = "terms_required: accepte les conditions d'utilisation de Party pour publier (Réglages › Confidentialité)."
REFUSED = "content_refused: Événement non enregistré : le titre contient une insulte. Les règles de Party l'interdisent."
FALLBACK = "L'événement n'a pas pu être créé. Réessaie, ou crée-le à la main."


def response(status: int, message: str | None) -> httpx.Response:
    return httpx.Response(status, json={"code": "42501", "message": message} if message is not None else None)


def test_terms_required_from_the_base_becomes_terms_required_with_its_sentence():
    error = db_refusal(response(403, TERMS), FALLBACK)
    assert isinstance(error, TermsRequired) and error.code == "terms_required"
    assert str(error) == "Accepte les conditions d'utilisation de Party pour publier (Réglages › Confidentialité)."


def test_other_refusals_keep_their_sentence_and_failures_keep_the_general_message():
    refused = db_refusal(response(400, REFUSED), FALLBACK)
    assert type(refused) is AccountError and str(refused).startswith("Événement non enregistré : le titre contient une insulte")
    assert str(db_refusal(response(400, "new row violates row-level security policy"), FALLBACK)) == FALLBACK
    assert str(db_refusal(httpx.Response(500, text="boom"), FALLBACK)) == FALLBACK
    assert str(db_refusal(httpx.Response(400, text=""), FALLBACK)) == FALLBACK


def test_group_and_chat_refusals_raise_terms_required_too():
    assert isinstance(refusal(response(403, TERMS), "Le message n'a pas pu être envoyé."), TermsRequired)
    assert type(refusal(response(400, REFUSED), "x")) is AccountError


def refuse_events(accounts, message: str, status: int = 403):
    plain = accounts._get

    def _get(method, path, token, json=None, headers=None):
        if method in ("POST", "PATCH") and path.startswith("/rest/v1/events"):
            accounts.calls.append((method, path, json))
            return Resp(status, {"code": "42501", "message": message})
        return plain(method, path, token, json=json, headers=headers)
    accounts._get = _get


@pytest.mark.parametrize("step", ["save_draft", "create"])
def test_the_ai_assistant_says_the_terms_are_required(tmp_path, step):
    a, accounts, _ = make(tmp_path)
    refuse_events(accounts, TERMS)
    with pytest.raises(TermsRequired, match="Accepte les conditions d'utilisation"):
        getattr(a, step)("ok", READY, None)


def test_the_ai_assistant_says_why_the_base_refused_the_title(tmp_path):
    a, accounts, _ = make(tmp_path)
    refuse_events(accounts, REFUSED, 400)
    with pytest.raises(AccountError, match="le titre contient une insulte"):
        a.save_draft("ok", READY, None)


def test_the_ai_edit_says_why_the_base_refused_the_change(tmp_path, monkeypatch):
    a, accounts, _ = make(tmp_path)
    editor = edit.EventEditor(a)
    monkeypatch.setattr(editor, "_event", lambda token, eid: {"id": eid})
    monkeypatch.setattr(editor, "_check", lambda token, e: "u1")
    monkeypatch.setattr(edit, "kept", lambda e: None)
    monkeypatch.setattr(edit, "draft_of", lambda e, o: {})
    refuse_events(accounts, REFUSED, 400)
    with pytest.raises(AccountError, match="le titre contient une insulte"):
        editor.save("ok", "e1", READY, None, False)


class TermsAssistant:
    def save_draft(self, token, draft, place):
        raise TermsRequired("Accepte les conditions d'utilisation de Party pour publier (Réglages › Confidentialité).")

    create = save_draft


@pytest.mark.parametrize("route", ["/api/account/ai/event/draft/save", "/api/account/ai/event/create"])
def test_the_route_answers_403_with_the_terms_required_code(monkeypatch, route):
    monkeypatch.setattr(main, "event_assistant", TermsAssistant())
    r = TestClient(main.app).post(route, json={"token": "t", "draft": READY})
    assert r.status_code == 403
    assert r.json() == {"code": "terms_required",
                        "detail": "Accepte les conditions d'utilisation de Party pour publier (Réglages › Confidentialité)."}

