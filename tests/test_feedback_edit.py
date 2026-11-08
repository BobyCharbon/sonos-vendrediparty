"""Retour de l'admin (08.11) : la personne qui a écrit un avis peut le modifier à tout moment (texte), avec une trace de
chaque modification (heure, ancien texte) ; personne d'autre ne le peut ; un avis fermé (terminé, pas retenu) ne bouge
plus ; la version la plus récente suit d'un site à l'autre."""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.feedback import FeedbackBox
from tests.test_feedback import GUEST, PLAIN, PLUS, account_rights, send  # noqa: F401 (fixture)

NEW_TEXT = "Un mode équipe au Quiz, avec deux camps et un score commun"


def edit(c, fid, text=NEW_TEXT, gid=GUEST, token=PLUS):
    return c.post("/api/feedback/edit", json={"guest_id": gid, "id": fid, "text": text, "token": token})


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "feedback", FeedbackBox(tmp_path / "feedback.json"))
    return TestClient(main.app)


def test_the_author_edits_the_text_and_every_change_is_traced(client):
    fid = send(client).json()["mine"][0]["id"]
    r = edit(client, fid)
    assert r.status_code == 200, r.text
    mine = r.json()["mine"][0]
    assert mine["text"] == NEW_TEXT and mine["edited_at"] > 0
    item = main.feedback.get(fid)
    assert item["text"] == NEW_TEXT
    assert item["edits"][-1]["before"] == "Un mode équipe au Quiz, avec deux camps" and item["edits"][-1]["at"] == mine["edited_at"]
    assert item["history"][-1]["field"] == "text" and item["history"][-1]["by"] == "author"
    assert edit(client, fid, text=NEW_TEXT + " !").status_code == 200
    assert len(main.feedback.get(fid)["edits"]) == 2


def test_nobody_else_edits_and_a_closed_or_too_short_one_is_refused(client):
    fid = send(client).json()["mine"][0]["id"]
    assert edit(client, fid, gid="feedback-other-0001").status_code == 404
    assert edit(client, fid, token=PLAIN).status_code == 403
    assert edit(client, fid, text="court").status_code == 400
    main.feedback.update([fid], "done")
    assert edit(client, fid).status_code == 409
    assert main.feedback.get(fid)["text"] == "Un mode équipe au Quiz, avec deux camps"


def test_the_latest_edit_follows_from_one_site_to_the_other(tmp_path):
    here, there = FeedbackBox(tmp_path / "a.json"), FeedbackBox(tmp_path / "b.json")
    item = here.add(GUEST, "Léa", "idea", "Un mode équipe au Quiz, avec deux camps", {})
    assert there.absorb([dict(item)]) == 1
    here.edit_text(GUEST, item["id"], NEW_TEXT)
    there.absorb([dict(here.get(item["id"]))])
    assert there.get(item["id"])["text"] == NEW_TEXT
    there.absorb([dict(item)])  # une ancienne version ne revient jamais par-dessus
    assert there.get(item["id"])["text"] == NEW_TEXT


def test_an_ai_title_does_not_stay_above_a_rewritten_text(tmp_path):
    """Agent « Cohérence » (08.11) : le titre de la version IA restait affiché en gros au-dessus du nouveau texte."""
    box = FeedbackBox(tmp_path / "f.json")
    item = box.add(GUEST, "Léa", "idea", "Un mode équipe au Quiz, avec deux camps",
                   {"ai": {"title": "Quiz en équipes", "kind": "idea", "area": "games"}})
    assert box.mine(GUEST)[0]["title"] == "Quiz en équipes"
    box.edit_text(GUEST, item["id"], NEW_TEXT)
    assert "title" not in box.mine(GUEST)[0]
    assert box.get(item["id"])["context"]["ai"]["area"] == "games"  # le classement de l'IA reste
