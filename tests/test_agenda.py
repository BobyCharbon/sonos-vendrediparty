"""Agenda (17.11.2026) côté serveur, avec une base simulée : page publique /d/<jeton> (neutre 404 identique, en-têtes
noindex / no-referrer, aucune ressource externe), demande (champ piège, temps de saisie, motif d'un refus du filtre),
suivi /d/r/<secret>, relais iPhone limité aux fonctions de l'agenda, lecture des agendas .ics."""
import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import agenda, agenda_ics, main

TOKEN = "k7Qm2xV9aB3cD4eF5gH6iJ7k"
SECRET = "9fX2" + "a" * 28
PAGE = {"name": "Léa", "link_name": "Rendez-vous pro", "tz": "Europe/Zurich", "duration_min": 60, "horizon_days": 28,
        "rules": [{"days": [1, 2, 3, 4, 5], "from": "09:00", "to": "18:00"}], "from": "2026-11-18", "to": "2026-12-15",
        "slots": [["2026-11-23T08:00:00+00:00", "2026-11-23T09:00:00+00:00"],
                  ["2026-11-23T09:00:00+00:00", "2026-11-23T10:00:00+00:00"]],
        "booking": {"fields": {"first_name": "required", "last_name": "off", "email": "required", "phone": "off",
                               "message": "optional"}, "message_label": None, "pending_hours": 48, "full": False},
        "contact_email": "aide@exemple.ch"}


@pytest.fixture
def db(monkeypatch):
    calls, answers = [], {}

    def call(self, name, args, token=None):
        calls.append((name, args, token))
        answer = answers.get(name, (200, None))
        return answer(args) if callable(answer) else answer
    monkeypatch.setattr(agenda.Db, "call", call)
    return calls, answers


@pytest.fixture
def client():
    return TestClient(main.app)


def test_unknown_stopped_or_expired_links_all_get_the_same_neutral_page(db, client):
    _, answers = db
    answers["agenda_public_page"] = (200, None)
    bad = client.get("/d/court")
    unknown = client.get(f"/d/{TOKEN}")
    assert bad.status_code == unknown.status_code == 404
    strip = lambda t: re.sub(r'nonce-[^\'"]+|nonce="[^"]+"', "", t)  # noqa: E731
    assert strip(bad.text) == strip(unknown.text) and "Ce lien n’est plus actif" in unknown.text
    assert "Léa" not in unknown.text
    assert unknown.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert unknown.headers["referrer-policy"] == "no-referrer"


def test_the_public_page_is_self_contained_and_never_indexed(db, client):
    calls, answers = db
    answers["agenda_public_page"] = (200, PAGE)
    r = client.get(f"/d/{TOKEN}", headers={"user-agent": "Mozilla/5.0"})
    assert r.status_code == 200
    page = r.text
    assert "Prendre rendez-vous avec" in page and "Rendez-vous pro" in page and "Voir en liste" in page
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in page and 'name="referrer" content="no-referrer"' in page
    assert not re.search(r'<(script|link|img)[^>]+(src|href)=', page)                 # aucune ressource externe
    assert "fonts.googleapis" not in page and "@import" not in page
    csp = r.headers["content-security-policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "Responsable : Vendredi Party (Suisse)" in page and "aide@exemple.ch" in page     # notice, contact des réglages
    assert "type=\"checkbox\"" not in page                                             # aucune case de consentement
    assert 'name="site"' in page                                                        # champ piège
    assert "obligatoire pour ce rendez-vous" in page and 'name="phone"' not in page     # champs choisis seulement
    assert "Disponible de 9 h – 10 h" in page                                           # sans JavaScript : la liste
    assert calls[-1][:2] == ("agenda_public_page", {"t": TOKEN, "count_view": True})
    og = re.search(r'property="og:image" content="([^"]+)"', page).group(1)
    assert og == f"{main.configured_public_url()}/d/{TOKEN}/apercu.png"                 # adresse depuis PARTY_PUBLIC_URL


def test_link_preview_robots_do_not_count_a_view(db, client):
    calls, answers = db
    answers["agenda_public_page"] = (200, PAGE)
    client.get(f"/d/{TOKEN}", headers={"user-agent": "WhatsApp/2.23"})
    assert calls[-1][1]["count_view"] is False
    png = client.get(f"/d/{TOKEN}/apercu.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"


def test_a_request_needs_a_human_and_the_trap_field_empty(db, client):
    calls, answers = db
    body = {"starts_at": "2026-11-23T08:00:00+00:00", "answers": {"first_name": "Marc", "email": "m@x.ch"}}
    assert client.post(f"/d/{TOKEN}/demande", json={**body, "elapsed": 1}).status_code == 400
    assert client.post(f"/d/{TOKEN}/demande", json={**body, "elapsed": 9, "site": "spam"}).status_code == 400
    assert not [c for c in calls if c[0] == "agenda_booking_request"]
    answers["agenda_booking_request"] = (200, {"secret": SECRET, "status": "pending"})
    r = client.post(f"/d/{TOKEN}/demande", json={**body, "elapsed": 9, "answers": {**body["answers"], "evil": "x"}})
    assert r.json() == {"ok": True, "url": f"/d/r/{SECRET}", "status": "pending"}
    sent = calls[-1][1]
    assert sent["t"] == TOKEN and sent["ip"] and set(sent["answers"]) == {"first_name", "email"}
    assert "duration" not in sent  # ancienne page : la durée par défaut du lien
    # Plusieurs durées (17.11) : la durée choisie par la personne part avec la demande ; hors bornes : refusée ici.
    client.post(f"/d/{TOKEN}/demande", json={**body, "elapsed": 9, "duration": 90})
    assert calls[-1][1]["duration"] == 90
    assert client.post(f"/d/{TOKEN}/demande", json={**body, "elapsed": 9, "duration": 5}).status_code == 422


def test_a_filtered_text_says_why_what_did_not_leave_and_whom_to_ask(db, client):
    _, answers = db
    answers["agenda_public_page"] = (200, PAGE)
    answers["agenda_booking_request"] = (400, {"message": "content_refused: Message refusé : il contient un lien, et les liens "
                                                          "ne sont pas acceptés ici. Retirez-le puis envoyez de nouveau. Rien n'a été transmis."})
    r = client.post(f"/d/{TOKEN}/demande", json={"starts_at": "2026-11-23T08:00:00+00:00", "elapsed": 9,
                                                 "answers": {"first_name": "Marc", "message": "www.x.ch"}})
    j = r.json()
    assert r.status_code == 400 and j["field"] == "message" and j["title"] == "Message refusé"
    assert j["message"].startswith("Il contient un lien") and "Rien n’a été transmis à Léa." in j["message"]
    assert "aide@exemple.ch" in j["message"]
    answers["agenda_booking_request"] = (409, {"message": "slot_taken: Ce créneau n'est plus libre. Choisissez-en un autre."})
    assert client.post(f"/d/{TOKEN}/demande", json={"starts_at": "2026-11-23T08:00:00+00:00", "elapsed": 9}).json()["code"] == "slot_taken"


@pytest.mark.parametrize("status,words", [("pending", ["Demande envoyée", "Annuler la demande", "Effacer mes données", "Copier le lien"]),
                                          ("accepted", ["Rendez-vous confirmé", "Ajouter à mon agenda", "Annuler le rendez-vous"]),
                                          ("refused", ["Léa ne peut pas ce jour-là", "Voir d’autres créneaux"]),
                                          ("expired", ["Léa ne peut pas ce jour-là"])])
def test_the_follow_page_tells_where_the_request_stands(db, client, status, words):
    _, answers = db
    answers["agenda_booking_status"] = (200, {
        "status": status, "starts_at": "2026-11-23T09:00:00+00:00", "ends_at": "2026-11-23T10:00:00+00:00",
        "expires_at": "2026-11-19T09:00:00+00:00", "name": "Léa", "link_path": f"/d/{TOKEN}",
        "can_cancel": status in ("pending", "accepted"), "contact_email": None,
        "answers": {"first_name": "Marc", "email": "m@x.ch"} if status in ("pending", "accepted") else None})
    r = client.get(f"/d/r/{SECRET}")
    assert r.status_code == 200 and r.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    for w in words:
        assert w in r.text, w
    assert "Lundi 23 novembre" in r.text and "10 h – 11 h" in r.text
    assert (f"{main.configured_public_url()}/d/r/{SECRET}" in r.text) == (status in ("pending", "accepted"))


def test_cancel_and_erase_go_through_the_secret_link(db, client):
    calls, answers = db
    answers["agenda_booking_status"] = (200, None)
    r = client.post(f"/d/r/{SECRET}/effacer", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/d/r/{SECRET}"
    assert calls[-1][:2] == ("agenda_booking_erase", {"secret": SECRET})
    client.post(f"/d/r/{SECRET}/annuler", follow_redirects=False)
    assert calls[-1][0] == "agenda_booking_cancel"
    gone = client.get(f"/d/r/{SECRET}")
    assert gone.status_code == 404 and "Cette demande n’existe plus" in gone.text


def test_an_accepted_appointment_downloads_as_ics(db, client):
    _, answers = db
    answers["agenda_booking_status"] = (200, {"status": "accepted", "starts_at": "2026-11-23T09:00:00+00:00",
                                              "ends_at": "2026-11-23T10:00:00+00:00", "name": "Léa"})
    r = client.get(f"/d/r/{SECRET}/rendez-vous.ics")
    assert r.status_code == 200 and "SUMMARY:Rendez-vous avec Léa" in r.text and "DTSTART:20261123T090000Z" in r.text


def test_the_iphone_relay_only_reaches_agenda_functions(db, client):
    calls, answers = db
    assert client.post("/api/account/agenda/rpc", json={"token": "t", "fn": "delete_my_account"}).status_code == 404
    answers["agenda_badge"] = (200, {"pending": 1})
    r = client.post("/api/account/agenda/rpc", json={"token": "jwt", "fn": "agenda_badge", "args": {}})
    assert r.json()["result"] == {"pending": 1} and calls[-1] == ("agenda_badge", {}, "jwt")
    # Pastille de l'app iPhone : l'adresse du temps réel pour écouter le signal user:<id> (et seulement pour agenda_badge).
    assert r.json()["realtime"]["url"].startswith("wss://") and r.json()["realtime"]["url"].endswith("/realtime/v1/websocket")
    answers["agenda_sharing"] = (200, {"groups": []})
    assert client.post("/api/account/agenda/rpc", json={"token": "jwt", "fn": "agenda_sharing"}).json() == {"result": {"groups": []}}
    answers["agenda_link_save"] = (400, {"message": "profile_incomplete: Complète ton profil (prénom, nom, surnom) pour créer un lien."})
    r = client.post("/api/account/agenda/rpc", json={"token": "jwt", "fn": "agenda_link_save", "args": {"link": {}}})
    assert r.status_code == 403 and r.json()["code"] == "profile_incomplete"


ICS = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:weekly@x\r
DTSTART;TZID=Europe/Zurich:20261102T183000\r
DTEND;TZID=Europe/Zurich:20261102T200000\r
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=6\r
EXDATE;TZID=Europe/Zurich:20261104T183000\r
SUMMARY:Badminton\\, club\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:weekly@x\r
RECURRENCE-ID;TZID=Europe/Zurich:20261109T183000\r
DTSTART;TZID=Europe/Zurich:20261109T190000\r
DTEND;TZID=Europe/Zurich:20261109T203000\r
SUMMARY:Badminton (déplacé)\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:day@x\r
DTSTART;VALUE=DATE:20261110\r
DTEND;VALUE=DATE:20261111\r
SUMMARY:Congé\r
TRANSP:TRANSPARENT\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:gone@x\r
DTSTART:20261105T100000Z\r
DTEND:20261105T110000Z\r
STATUS:CANCELLED\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_an_ics_calendar_is_read_with_its_repeats_exceptions_and_moves():
    f = datetime(2026, 11, 1, tzinfo=timezone.utc)
    t = datetime(2026, 11, 30, tzinfo=timezone.utc)
    evs = agenda_ics.events_between(ICS, f, t)
    badminton = [(e["title"], e["starts_at"]) for e in evs if e["uid"] == "weekly@x"]
    assert badminton == [("Badminton, club", "2026-11-02T17:30:00+00:00"),       # 4.11 exclu, 9.11 déplacé
                         ("Badminton (déplacé)", "2026-11-09T18:00:00+00:00"),
                         ("Badminton, club", "2026-11-11T17:30:00+00:00"),
                         ("Badminton, club", "2026-11-16T17:30:00+00:00"),
                         ("Badminton, club", "2026-11-18T17:30:00+00:00")]
    day = next(e for e in evs if e["uid"] == "day@x")
    assert day["all_day"] and day["busy"] is False and day["starts_at"] == "2026-11-09T23:00:00+00:00"
    assert not [e for e in evs if e["uid"] == "gone@x"]


def test_an_ics_link_must_be_public_https():
    assert agenda_ics.normalize_url("webcal://p01-caldav.icloud.com/x.ics") == "https://p01-caldav.icloud.com/x.ics"
    for bad in ("http://example.com/a.ics", "file:///etc/passwd", "ftp://x"):
        with pytest.raises(agenda_ics.IcsError):
            agenda_ics.normalize_url(bad)
    with pytest.raises(agenda_ics.IcsError):
        agenda_ics.fetch("https://127.0.0.1/a.ics")
    with pytest.raises(agenda_ics.IcsError):
        agenda_ics.fetch("https://localhost/a.ics")


def test_a_readable_address_serves_the_same_page_without_showing_the_token(db, client):
    """Adresse lisible (17.11) : /agenda/<nom>/<lien> → même page, demande et signalement ; le jeton n'apparaît jamais ;
    inconnue, arrêtée ou mal écrite : la même page neutre."""
    calls, answers = db
    answers["agenda_resolve"] = lambda args: (200, TOKEN if (args["handle"], args["slug"]) == ("ludovic", "semaine") else None)
    answers["agenda_public_page"] = (200, PAGE)
    r = client.get("/agenda/Ludovic/semaine", headers={"user-agent": "Mozilla/5.0"})
    assert r.status_code == 200 and "Prendre rendez-vous avec" in r.text
    assert TOKEN not in r.text and "/agenda/ludovic/semaine/apercu.png" in r.text
    assert ("agenda_public_page", {"t": TOKEN, "count_view": True}) in [c[:2] for c in calls]
    for bad in ("/agenda/ludovic/autre", "/agenda/inconnu/semaine", "/agenda/l%20v/semaine"):
        assert client.get(bad).status_code == 404
    answers["agenda_booking_request"] = (200, {"secret": SECRET, "status": "pending"})
    sent = client.post("/agenda/ludovic/semaine/demande", json={"starts_at": "2026-11-23T08:00:00Z", "answers": {"first_name": "Marc"},
                                                                 "site": "", "elapsed": 9})
    assert sent.json()["url"] == f"/d/r/{SECRET}"
    assert client.post("/agenda/ludovic/autre/demande", json={"starts_at": "2026-11-23T08:00:00Z", "answers": {}, "site": "", "elapsed": 9}).status_code == 404
    assert client.get("/agenda/ludovic/semaine/apercu.png").headers["content-type"] == "image/png"
    assert "agenda_handle_set" in agenda.RELAY and "agenda_link_set_slug" in agenda.RELAY
