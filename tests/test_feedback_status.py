"""Statuts des retours gérés par l'admin (depuis l'app ou /admin) et ce que l'invité en voit :
envoyé → 🔧 en cours de correction → ✅ terminé (ou « pas retenu » avec un mot), avec notification et pastille."""
from fastapi.testclient import TestClient

from app import main
from app.feedback import FeedbackBox
from tests.test_features import admin, snap  # noqa: F401 (fixture)

GUEST = "feedback-guest-0003"


def setup(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(main, "feedback", FeedbackBox(tmp_path / "feedback.json"))
    monkeypatch.setattr(main, "notify_guest", lambda gid, payload, kind: sent.append((gid, payload)))
    main.feedback.add(GUEST, "Léa", "idea", "Un mode équipe au Quiz", {})
    return sent, main.feedback.all()[0]["id"]


def mine(c=None):
    return (c or TestClient(main.app)).get("/api/feedback", params={"guest_id": GUEST}).json()["mine"][0]


def act(admin, fid, action, **kw):  # noqa: F811
    return admin.post("/api/admin/feedback", json={"ids": [fid], "action": action, **kw})


def test_in_progress_is_shown_to_the_guest(admin, monkeypatch, tmp_path):  # noqa: F811
    sent, fid = setup(monkeypatch, tmp_path)
    assert mine()["status"] == "new"
    assert act(admin, fid, "progress").json()["items"][0]["status"] == "progress"
    assert mine()["status"] == "progress" and not mine()["unseen"] and sent == []
    assert admin.get("/api/admin/state").json()["feedback_new"] == 0  # pris en main : plus « à traiter »


def test_done_notifies_the_guest_and_lights_the_badge_until_seen(admin, monkeypatch, tmp_path):  # noqa: F811
    sent, fid = setup(monkeypatch, tmp_path)
    act(admin, fid, "done", reply="Ajouté au Quiz, merci !")
    m = mine()
    assert m["status"] == "done" and m["reply"] == "Ajouté au Quiz, merci !" and m["unseen"] is True
    assert [gid for gid, _ in sent] == [GUEST] and "terminé" in sent[0][1]["title"].lower()
    assert sent[0][1]["url"] == "/?tab=feedback"
    act(admin, fid, "done")  # déjà terminé : pas de deuxième notification
    assert len(sent) == 1
    TestClient(main.app).post("/api/feedback/seen", json={"guest_id": GUEST})
    assert mine()["unseen"] is False


def test_declined_needs_a_word_for_the_guest(admin, monkeypatch, tmp_path):  # noqa: F811
    sent, fid = setup(monkeypatch, tmp_path)
    assert act(admin, fid, "declined").status_code == 400
    act(admin, fid, "declined", reply="Pas prévu pour l'instant, mais on garde l'idée.")
    m = mine()
    assert m["status"] == "declined" and m["reply"].startswith("Pas prévu") and m["unseen"] is True
    assert len(sent) == 1


def test_claude_steps_look_like_in_progress_to_the_guest(admin, monkeypatch, tmp_path):  # noqa: F811
    _, fid = setup(monkeypatch, tmp_path)
    for status in ("sent", "verify"):
        main.feedback._edit(fid, status=status)
        assert mine()["status"] == "progress"  # interne (Claude, vérification) : « en cours » pour l'invité
    assert "note" not in mine() and "claude" not in mine()


def test_guest_sees_no_internal_fields_and_others_cannot_mark_seen(admin, monkeypatch, tmp_path):  # noqa: F811
    _, fid = setup(monkeypatch, tmp_path)
    act(admin, fid, "note", note="Instructions internes pour Claude")
    act(admin, fid, "done", reply="Fait.")
    assert set(mine()) == {"id", "at", "kind", "text", "status", "reply", "unseen"}
    TestClient(main.app).post("/api/feedback/seen", json={"guest_id": "feedback-other-0009"})
    assert mine()["unseen"] is True
    assert TestClient(main.app).post("/api/admin/feedback", json={"ids": [fid], "action": "progress"}).status_code == 401


def test_admin_can_put_an_item_in_progress_to_verify_by_hand(admin, monkeypatch, tmp_path):  # noqa: F811
    sent, fid = setup(monkeypatch, tmp_path)
    act(admin, fid, "progress")
    item = act(admin, fid, "verify").json()["items"][0]
    assert item["status"] == "verify"
    assert mine()["status"] == "progress" and sent == []  # l'invité voit toujours « en cours de correction »
    assert admin.get("/api/admin/state").json()["feedback_new"] == 1  # à vérifier : la pastille de l'admin s'allume
    act(admin, fid, "done")
    assert mine()["status"] == "done" and len(sent) == 1
