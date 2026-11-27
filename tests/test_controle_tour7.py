"""Contrôle Apple, tour 7 (27.11) : prénoms de la Musique masqués dans l'app App Store, photos de profil effacées avant le
compte, accord IA qui cite « Modifier avec l'IA » (version 4)."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import account_auth, ai_feedback, main
from tests.test_features import admin  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"


def test_the_store_app_never_shows_who_asked_for_a_song_except_my_own():
    out = {"now": {"title": "A", "by": "Léa"}, "played": [{"title": "B", "by": "Noé"}],
           "upcoming": [{"title": "C", "by": "Léa", "rid": None}, {"title": "D", "by": "Moi", "rid": "r1"}]}
    hidden = main.music_without_names(out)
    assert hidden["now"]["by"] is None and hidden["played"][0]["by"] is None
    assert [t["by"] for t in hidden["upcoming"]] == [None, "Moi"]


def test_the_guest_state_of_the_store_app_hides_names_and_the_web_keeps_them(admin):  # noqa: F811
    main.store.session.played = [
        {"track_id": "p" * 22, "title": "Avant", "artist": "A", "art": "", "by": "Noé", "at": 0},
        {"track_id": "c" * 22, "title": "En cours", "artist": "A", "art": "", "by": "Noé", "at": 1},
    ]
    for ua, by in ((STORE_UA, None), ("Mozilla/5.0 (iPhone) Safari", "Noé")):
        guest = TestClient(main.app, headers={"user-agent": ua})
        guest.post("/api/join", json={"pin": main.store.session.guest_pin})
        guest.post("/api/hello", json={"guest_id": "guest-t7-1", "guest_name": "Zoé"})
        s = guest.get("/api/state?guest_id=guest-t7-1").json()
        assert [p["by"] for p in s["played"]] == [by], ua


class FakeAccounts:
    def __init__(self, delete_status=200, storage=(200,)):
        self.calls, self.delete_status, self.storage = [], delete_status, list(storage)

    def _uid(self, token):
        return "u1"

    def _get(self, method, path, token, **kw):
        self.calls.append((method, path))
        if path.startswith("/storage/"):
            status = self.storage.pop(0) if self.storage else 500
        else:
            status = self.delete_status if path.endswith("delete_my_account") else 200
        return type("R", (), {"status_code": status, "text": "last_admin" if status == 400 else "", "json": lambda self: []})()

    def forget(self, token):
        pass


def auth_with(acc, monkeypatch):
    auth = account_auth.AccountAuth.__new__(account_auth.AccountAuth)
    auth.accounts = acc
    monkeypatch.setattr(auth, "_own_photos", lambda uid, token: ["u1/a.jpg"])
    monkeypatch.setattr(account_auth.time, "sleep", lambda s: None)
    return auth


def test_profile_photos_leave_after_the_account_with_a_checked_retry(monkeypatch, caplog):
    deletes = lambda acc: [c for c in acc.calls if c[0] == "DELETE"]
    # Effacement refusé une fois : réessayé, puis réussi.
    acc = FakeAccounts(storage=(500, 200))
    auth_with(acc, monkeypatch).delete_account("t" * 30, "SUPPRIMER")
    paths = [c[1] for c in acc.calls]
    assert paths.index("/rest/v1/rpc/delete_my_account") < paths.index("/storage/v1/object/profile-photos")
    assert len(deletes(acc)) == 2
    # Toujours refusé : 3 essais, puis une trace dans le journal (jamais avalé en silence).
    acc = FakeAccounts(storage=(500, 500, 500))
    auth_with(acc, monkeypatch).delete_account("t" * 30, "SUPPRIMER")
    assert len(deletes(acc)) == 3 and "u1/ à vider" in caplog.text
    # Suppression refusée (dernier admin) : le compte reste, sa photo aussi.
    acc = FakeAccounts(delete_status=400)
    try:
        auth_with(acc, monkeypatch).delete_account("t" * 30, "SUPPRIMER")
    except account_auth.AccountError:
        pass
    assert deletes(acc) == []


def test_the_ai_consent_names_the_event_edit_everywhere_and_asks_again():
    assert ai_feedback.CONSENT_VERSION == 4
    for path in ("app/static/index.html", "ios/Party/Feedback/FeedbackAI.swift", "web/events/src/lib/aiConsent.ts"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "pour modifier un événement avec l" in text and "prix et infos de paiement" in text, path
