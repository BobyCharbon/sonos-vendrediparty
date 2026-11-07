"""« Ajouter à mon agenda » (campagne 2, rapport 04 bug 13) : un lieu + adresse de plus de 300 caractères (ou une
longue description) donnait une erreur 422 au lieu du fichier. Le fichier se crée toujours : le texte est tronqué."""
from fastapi.testclient import TestClient

from app import main

EVENT = "64d0880c-5379-42f8-8166-e259d25c7e7b"


def unfold(body: str) -> str:
    return body.replace("\r\n ", "")


def test_a_long_location_and_description_are_truncated_instead_of_refused():
    client = TestClient(main.app)
    location = "Salle des fêtes, " + "Rue très longue " * 40  # ~660 caractères (lieu + adresse)
    result = client.get("/api/calendar.ics", params={
        "uid": EVENT, "title": "Soirée " + "x" * 400, "start": "2026-11-20T19:00:00Z",
        "location": location, "description": "Programme " * 600,
    })
    assert result.status_code == 200, result.text
    lines = unfold(result.text).split("\r\n")
    loc = next(line for line in lines if line.startswith("LOCATION:"))
    unescaped = loc.removeprefix("LOCATION:").replace("\\,", ",")
    assert unescaped.startswith("Salle des fêtes, Rue très longue") and len(unescaped) == 300
    summary = next(line for line in lines if line.startswith("SUMMARY:"))
    assert len(summary) <= len("SUMMARY:") + 200
    assert all(len(line.encode()) <= 75 for line in result.text.split("\r\n"))


def test_an_absurdly_long_field_is_still_refused():
    client = TestClient(main.app)
    result = client.get("/api/calendar.ics", params={"uid": EVENT, "title": "Soirée", "start": "2026-11-20T19:00:00Z",
                                                     "location": "x" * 5000})
    assert result.status_code == 422
