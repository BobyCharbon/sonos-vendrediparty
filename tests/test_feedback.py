"""Onglet « Ton avis » : les invités envoient idées et bugs, l'admin les traite ; rien ne se perd entre deux soirées."""
from fastapi.testclient import TestClient

from app import main
from app.feedback import FeedbackBox
from tests.test_features import admin, snap  # noqa: F401 (fixture)

GUEST = "feedback-guest-0001"


def send(c, text="Un mode équipe au Quiz, avec deux camps", kind="idea", gid=GUEST, **context):
    return c.post("/api/feedback", json={"guest_id": gid, "name": "Léa", "kind": kind, "text": text, "context": context})


def test_guest_sends_without_party_code_and_sees_own_messages(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "feedback", FeedbackBox(tmp_path / "feedback.json"))
    c = TestClient(main.app)
    r = send(c, game="heist", tab="games", secret="x" * 99)
    assert r.status_code == 200 and r.json()["mine"][0]["text"] == "Un mode équipe au Quiz, avec deux camps"
    item = main.feedback.all()[0]
    assert item["context"] == {"game": "heist", "tab": "games"} and item["status"] == "new"  # contexte filtré
    assert c.get("/api/feedback", params={"guest_id": GUEST}).json()["mine"][0]["status"] == "new"
    assert c.get("/api/feedback", params={"guest_id": "feedback-other-0001"}).json()["mine"] == []


def test_native_app_request_is_accepted(monkeypatch, tmp_path):
    # App iOS (ios/Party/Feedback, PartyAPI.sendFeedback) : prénom parfois vide, contexte « tab » seul,
    # en-tête de l'app ; puis « vu » quand l'onglet natif s'affiche.
    monkeypatch.setattr(main, "feedback", FeedbackBox(tmp_path / "feedback.json"))
    c = TestClient(main.app, headers={"X-Party-Native": "ios"})
    r = c.post("/api/feedback", json={"guest_id": GUEST, "name": "", "kind": "bug", "text": "Le quiz se fige après la 3e question",
                                      "context": {"tab": "games"}})
    assert r.status_code == 200
    [mine] = r.json()["mine"]
    assert set(mine) == {"id", "at", "kind", "text", "status", "reply", "unseen"}  # décodé par FeedbackItem
    assert main.feedback.all()[0]["name"] == "Anonyme" and main.feedback.all()[0]["context"] == {"tab": "games"}
    assert c.post("/api/feedback/seen", json={"guest_id": GUEST}).status_code == 200


def test_validation_minimum_30_characters_and_no_sending_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "feedback", FeedbackBox(tmp_path / "feedback.json"))
    c = TestClient(main.app)
    assert send(c, text="  ").status_code == 400
    assert send(c, kind="spam").status_code == 400
    short = send(c, text="Ajouter un mode équipe au Quiz")  # exactement 30 caractères : accepté
    assert short.status_code == 200
    r = send(c, text="Ajouter   un mode équipe au Qu")  # 28 caractères une fois les espaces nettoyés
    assert r.status_code == 400 and "30 caractères" in r.json()["detail"]
    # Plusieurs avis à la suite : plus de délai ni de plafond par jour.
    for i in range(12):
        assert send(c, text=f"Idée numéro {i} : un mode équipe au Quiz").status_code == 200
    assert len(main.feedback.all()) == 13


def test_admin_lists_marks_done_and_deletes_and_it_persists(admin, monkeypatch, tmp_path):  # noqa: F811
    path = tmp_path / "feedback.json"
    monkeypatch.setattr(main, "feedback", FeedbackBox(path))
    assert TestClient(main.app).get("/api/admin/feedback").status_code == 401  # réservé à l'admin
    send(admin, kind="bug", text="Le laser ne marche pas sur iPhone")
    assert admin.get("/api/admin/state").json()["feedback_new"] == 1
    items = admin.get("/api/admin/feedback").json()["items"]
    fid = items[0]["id"]
    assert items[0]["kind"] == "bug"
    r = admin.post("/api/admin/feedback", json={"ids": [fid], "action": "done"}).json()
    assert r["items"][0]["status"] == "done" and main.feedback.count_new() == 0
    assert FeedbackBox(path).all()[0]["status"] == "done"  # relu depuis le fichier : survit à un redémarrage
    assert admin.post("/api/admin/feedback", json={"ids": [fid], "action": "hack"}).status_code == 400
    admin.post("/api/admin/feedback", json={"ids": [fid], "action": "delete"})
    assert FeedbackBox(path).all() == []
