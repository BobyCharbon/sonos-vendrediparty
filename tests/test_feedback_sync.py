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


def test_non_ascii_secret_is_refused_not_crashed(prod):
    # Avant : hmac.compare_digest(str, str) levait TypeError (500) sur un en-tête non-ASCII (« é » en latin-1).
    r = TestClient(main.app).post("/api/feedback-sync", json={"op": "all"},
                                  headers=[(b"X-Feedback-Sync", "é".encode("latin-1"))])
    assert r.status_code == 403


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


def test_priority_set_on_the_test_site_lands_in_the_production_list(prod):
    box, remote = prod
    item = remote.add("guest-test-0002", "Tom", "idea", "Ajouter une priorité aux avis depuis le site de test", {})
    remote.set_priority([item["id"]], "high")
    assert box.get(item["id"])["priority"] == "high"
    with pytest.raises(ValueError):
        remote.set_priority([item["id"]], "urgentissime")


def test_the_same_account_finds_its_feedback_on_both_sites(prod, monkeypatch):
    """22.11 : un avis envoyé en prod (appareil A) se retrouve sur le site de test (appareil B) avec le même numéro ;
    jamais celui d'un autre numéro, jamais le numéro lui-même dans l'avis."""
    box, remote = prod
    phones = {"tok-lea-prod": "+41 79 111 22 33", "tok-lea-test": "+41791112233", "tok-tom": "+41798887766"}
    monkeypatch.setattr(main.accounts, "profile", lambda token: {"phone": phones[token]})
    lea = main.feedback_owner("tok-lea-prod")
    assert lea and lea == main.feedback_owner("tok-lea-test") and lea != main.feedback_owner("tok-tom")
    assert main.feedback_owner("") == ""
    item = box.add("guest-prod-lea1", "Léa", "idea", "Un mode équipe au Quiz du vendredi", {"site": "Prod"}, owner=lea)
    assert "79" not in str(item.get("owner"))
    assert [i["id"] for i in remote.mine("guest-test-lea2", owner=main.feedback_owner("tok-lea-test"))] == [item["id"]]
    assert remote.mine("guest-test-lea2") == []  # sans compte : seulement les avis de l'appareil
    assert remote.mine("guest-test-tom1", owner=main.feedback_owner("tok-tom")) == []
    client = TestClient(main.app)
    got = client.get("/api/feedback", params={"guest_id": "guest-test-lea2"}, headers={"Authorization": "Bearer tok-lea-test"})
    assert [i["id"] for i in got.json()["mine"]] == [item["id"]]
    assert remote.edit_text("guest-test-lea2", item["id"], "Un mode équipe au Quiz, deux camps", owner=lea)
    assert box.get(item["id"])["text"].endswith("deux camps")


def test_an_older_production_still_answers_without_the_owner(prod, monkeypatch):
    """Prod pas encore à jour (elle ne connaît pas « owner ») : le site de test réessaie sans, rien ne casse."""
    box, remote = prod
    original = FeedbackBox.mine
    monkeypatch.setattr(FeedbackBox, "mine", lambda self, guest_id: original(self, guest_id))
    box.add("guest-test-0003", "Zoé", "idea", "Des thèmes de couleur pour le Quiz", {})
    assert len(remote.mine("guest-test-0003", owner="abc")) == 1
