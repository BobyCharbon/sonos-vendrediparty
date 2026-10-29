"""Avis partagés entre le site de test et la production : une seule liste, gardée par la production
(app/feedback_remote.py côté test, /api/feedback-sync côté production)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.feedback import FeedbackBox
from app.feedback_remote import FeedbackRemote, FeedbackUnavailable
from tests.test_features import admin  # noqa: F401 (fixture)

SECRET = "s" * 40


@pytest.fixture
def prod(monkeypatch, tmp_path):
    """La production : sa liste locale, le secret partagé ; le « site de test » lui parle par HTTP."""
    box = FeedbackBox(tmp_path / "feedback.json")
    monkeypatch.setattr(main, "local_feedback", box)
    monkeypatch.setattr(main, "feedback", box)
    monkeypatch.setattr(main, "FEEDBACK_SYNC_SECRET", SECRET)
    return box, FeedbackRemote("http://testserver", SECRET, client=TestClient(main.app))


def test_the_test_site_reads_and_writes_the_production_list(prod):
    box, remote = prod
    item = remote.add("guest-test-0001", "Léa", "bug", "Le joystick est trop petit sur mon iPhone", {"tab": "games", "site": "Test"})
    assert box.all()[0]["id"] == item["id"] and box.all()[0]["context"]["site"] == "Test"
    assert remote.count_new() == 1 and remote.all()[0]["text"].startswith("Le joystick")
    remote.set_note(item["id"], "Agrandir le joystick à 96 px")
    finished = remote.update([item["id"]], "done", "Corrigé, merci !")
    assert finished[0]["id"] == item["id"] and box.get(item["id"])["status"] == "done"
    assert remote.mine("guest-test-0001")[0]["reply"] == "Corrigé, merci !"
    remote.mark_seen("guest-test-0001")
    assert not box.get(item["id"]).get("unseen")
    assert remote.count_new() == 0  # cache vidé par l'écriture : la pastille suit tout de suite


def test_the_old_test_site_feedback_is_poured_in_once(prod, tmp_path):
    box, remote = prod
    box.add("guest-prod-0001", "Tom", "idea", "Un mode équipe au Quiz, avec deux camps", {"site": "Prod"})
    old = FeedbackBox(tmp_path / "test-site.json")
    old.add("guest-test-0002", "Zoé", "idea", "Des thèmes de couleur pour le Quiz du vendredi", {})
    assert remote.absorb(old.items) == 1
    assert remote.absorb(old.items) == 0  # jamais en double
    assert [i["name"] for i in box.all()] == ["Zoé", "Tom"]


def test_wrong_secret_or_unknown_operation_is_refused(prod):
    _, remote = prod
    client = TestClient(main.app)
    assert client.post("/api/feedback-sync", json={"op": "all"}, headers={"X-Feedback-Sync": "faux"}).status_code == 403
    assert client.post("/api/feedback-sync", json={"op": "all"}).status_code == 403
    assert client.post("/api/feedback-sync", json={"op": "_save"}, headers={"X-Feedback-Sync": SECRET}).status_code == 400
    assert client.post("/api/feedback-sync", json={"op": "update", "args": {"x": 1}}, headers={"X-Feedback-Sync": SECRET}).status_code == 400
    with pytest.raises(FeedbackUnavailable):
        FeedbackRemote("http://testserver", "autre" * 10, client=client).all()


def test_sync_is_off_without_a_long_secret(monkeypatch, prod):
    monkeypatch.setattr(main, "FEEDBACK_SYNC_SECRET", "court")
    r = TestClient(main.app).post("/api/feedback-sync", json={"op": "all"}, headers={"X-Feedback-Sync": "court"})
    assert r.status_code == 403


def test_production_down_shows_a_clear_message_and_never_blocks_the_admin(admin, monkeypatch):  # noqa: F811
    def down(request):
        raise httpx.ConnectError("injoignable")
    remote = FeedbackRemote("http://prod.invalid", SECRET, client=httpx.Client(transport=httpx.MockTransport(down)))
    monkeypatch.setattr(main, "feedback", remote)
    r = admin.post("/api/feedback", json={"guest_id": "feedback-host-0001", "kind": "idea",
                                          "text": "Un mode équipe au Quiz, avec deux camps"})
    assert r.status_code == 503 and "indisponibles" in r.json()["detail"]
    assert admin.get("/api/admin/state").status_code == 200  # la pastille retombe à 0, l'admin reste utilisable


def test_prompt_names_the_site_the_feedback_came_from(prod, monkeypatch):
    box, _ = prod
    monkeypatch.setattr(main, "feedback_site", lambda: ("Prod", "https://party.example"))
    item = box.add("g-0001-xxxx", "Léa", "bug", "Le bouton Révéler ne marche pas du tout", {"site": "Test"})
    assert "Test" in main.feedback_prompt(item) and "party.example" not in main.feedback_prompt(item)
    mine = box.add("g-0002-xxxx", "Tom", "bug", "Le bouton Révéler ne marche pas du tout", {"site": "Prod"})
    assert "Prod (https://party.example)" in main.feedback_prompt(mine)
