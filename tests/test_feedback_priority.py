"""Retours : l'admin donne une priorité (haute, moyenne, basse) et trie par priorité."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import feedback, main


def test_priority_is_set_cleared_and_validated(tmp_path: Path):
    box = feedback.FeedbackBox(tmp_path / "fb.json")
    a = box.add("guest-prio-00001", "Léa", "idea", "Un beer pong", {})
    box.set_priority([a["id"]], "high")
    assert box.get(a["id"])["priority"] == "high"
    box.set_priority([a["id"]], "")
    assert box.get(a["id"])["priority"] == ""
    try:
        box.set_priority([a["id"]], "urgent")
        raise AssertionError("priorité inconnue acceptée")
    except ValueError:
        pass


def test_admin_api_sets_priority_and_guests_never_see_it():
    c = TestClient(main.app)
    assert c.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    item = main.feedback.add("guest-prio-00002", "Tom", "bug", "Les dés vont trop vite", {})
    r = c.post("/api/admin/feedback", json={"ids": [item["id"]], "action": "priority", "priority": "medium"})
    assert r.status_code == 200 and next(i for i in r.json()["items"] if i["id"] == item["id"])["priority"] == "medium"
    assert c.post("/api/admin/feedback", json={"ids": [item["id"]], "action": "priority", "priority": "x"}).status_code == 400
    assert "priority" not in main.feedback.mine("guest-prio-00002")[0]
    main.feedback.update([item["id"]], "delete")
