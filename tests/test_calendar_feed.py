"""Agenda abonné d'un sondage de dates (retour de l'admin du 11.11.2026) : après « Valider mes dates », l'agenda de
la personne se met à jour tout seul. Sondage ouvert : ses dates « À confirmer » ; date fixée : la seule bonne ;
Non à la date retenue, annulé ou plus concerné : rien."""
from fastapi.testclient import TestClient

from app import calendar_feed, calendar_ics, main

EVENT = "81ea6cbd-4c95-4af0-98d3-68fc25c8b27d"
OPT1, OPT2 = "11111111-2222-4333-8444-555555555551", "11111111-2222-4333-8444-555555555552"
TOKEN = "a" * 36


def feed(**over) -> dict:
    base = {"event_id": EVENT, "title": "Paintball", "location": "Cobalt Project, Lutry", "status": "published",
            "date_mode": "poll", "starts_at": None, "ends_at": None, "active": True, "my_rsvp": None,
            "dates": [{"id": OPT1, "starts_at": "2027-01-16T13:00:00+00:00", "ends_at": None},
                      {"id": OPT2, "starts_at": "2027-01-17T13:00:00+00:00", "ends_at": None}]}
    return {**base, **over}


def entries(body: str) -> list[str]:
    return body.replace("\r\n ", "").split("BEGIN:VEVENT")[1:]


def test_open_poll_shows_my_dates_to_confirm_and_asks_to_be_refreshed():
    body = calendar_ics.build_feed(feed(), event_url="https://party.bobycharbon.ch/events/event/" + EVENT)
    assert "REFRESH-INTERVAL;VALUE=DURATION:PT1H" in body and "X-WR-CALNAME:Paintball · Vendredi Party" in body
    found = entries(body)
    assert len(found) == 2
    assert all("SUMMARY:À confirmer · Paintball" in e and "STATUS:TENTATIVE" in e for e in found)
    assert f"UID:{OPT1}@vendredi-party-agenda" in found[0] and "DTSTART:20270116T130000Z" in found[0]


def test_fixed_date_keeps_only_the_right_one_under_its_real_title():
    found = entries(calendar_ics.build_feed(feed(date_mode="fixed", starts_at="2027-01-17T13:00:00+00:00", my_rsvp="yes")))
    assert len(found) == 1
    assert "SUMMARY:Paintball" in found[0] and "STATUS:CONFIRMED" in found[0] and "TRIGGER:-PT2H" in found[0]
    assert "À confirmer" not in found[0]


def test_nothing_when_not_coming_cancelled_or_unknown():
    assert entries(calendar_ics.build_feed(feed(date_mode="fixed", starts_at="2027-01-17T13:00:00+00:00", my_rsvp="no"))) == []
    assert entries(calendar_ics.build_feed(feed(active=False))) == []
    assert entries(calendar_ics.build_feed(None)) == []
    assert "END:VCALENDAR" in calendar_ics.build_feed(None)


def test_endpoint_serves_the_calendar_and_never_empties_it_when_the_base_is_down(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setattr(calendar_feed, "read", lambda accounts, token: (feed(), True))
    ok = client.get(f"/api/calendar-feed/{TOKEN}.ics")
    assert ok.status_code == 200 and ok.headers["content-type"].startswith("text/calendar")
    assert len(entries(ok.text)) == 2 and f"/events/event/{EVENT}" in ok.text.replace("\r\n ", "")
    monkeypatch.setattr(calendar_feed, "read", lambda accounts, token: (None, False))
    assert client.get(f"/api/calendar-feed/{TOKEN}.ics").status_code == 503


def test_malformed_token_never_reaches_the_base():
    assert calendar_feed.read(None, "pas-un-jeton") == (None, True)  # type: ignore[arg-type]
    assert calendar_feed.read(None, "A" * 36) == (None, True)  # type: ignore[arg-type]
