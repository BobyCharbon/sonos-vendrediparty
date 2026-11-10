"""Sondage de dates → toutes les dates proposées dans l'agenda en un toucher (avis 9ddbdea7fe8f du 10.11.2026).
Un seul fichier .ics avec une entrée par date : l'iPhone propose « Tout ajouter ». Chaque entrée commence par
« À confirmer · » et est marquée provisoire (STATUS:TENTATIVE) : on garde le créneau, rien n'est encore fixé."""
from fastapi.testclient import TestClient

from app import calendar_ics, main
from tests.test_events_browser import EVENT as EVENT_PAGE, browser, events_origin  # noqa: F401 (fixtures)

EVENT = "64d0880c-5379-42f8-8166-e259d25c7e7b"
OPT1, OPT2, OPT3 = ("11111111-2222-4333-8444-555555555551", "11111111-2222-4333-8444-555555555552",
                    "11111111-2222-4333-8444-555555555553")


def unfold(body: str) -> str:
    return body.replace("\r\n ", "")


def events(body: str) -> list[str]:
    return unfold(body).split("BEGIN:VEVENT")[1:]


def test_every_proposed_date_is_one_tentative_entry_marked_to_confirm():
    client = TestClient(main.app)
    result = client.get("/api/calendar-dates.ics", params=[
        ("uid", EVENT), ("title", "Paintball"), ("location", "Cobalt Project, Lutry"),
        ("url", "https://party.bobycharbon.ch/events/event/" + EVENT),
        ("d", f"{OPT1}|2026-12-04T19:00:00Z|"), ("d", f"{OPT2}|2026-12-11T19:00:00Z|2026-12-11T23:00:00Z"),
        ("d", f"{OPT3}|2026-12-18T19:00:00Z|"),
    ])
    assert result.status_code == 200, result.text
    assert result.headers["content-type"].startswith("text/calendar")
    entries = events(result.text)
    assert len(entries) == 3
    for opt, entry in zip((OPT1, OPT2, OPT3), entries):
        assert f"UID:{opt}@vendredi-party" in entry
        assert "SUMMARY:À confirmer · Paintball" in entry
        assert "STATUS:TENTATIVE" in entry
        assert "rien n'est encore fixé" in entry.replace("\\,", ",")
    assert "DTSTART:20261211T190000Z" in entries[1] and "DTEND:20261211T230000Z" in entries[1]
    assert "DTEND:20261204T220000Z" in entries[0]  # sans fin : 3 heures
    assert all(len(line.encode()) <= 75 for line in result.text.split("\r\n"))


def test_bad_or_too_many_dates_are_refused():
    client = TestClient(main.app)
    base = [("uid", EVENT), ("title", "Paintball")]
    assert client.get("/api/calendar-dates.ics", params=base).status_code == 400  # aucune date
    assert client.get("/api/calendar-dates.ics", params=base + [("d", "pas-une-date")]).status_code == 400
    many = [("d", f"{OPT1[:-2]}{i:02d}|2026-12-04T19:00:00Z|") for i in range(calendar_ics.MAX_DATES + 1)]
    assert client.get("/api/calendar-dates.ics", params=base + many).status_code == 400


def test_on_the_event_page_one_touch_sends_every_upcoming_date_to_the_calendar(browser, events_origin):  # noqa: F811
    from tests.test_event_participant_browser import event_row, open_event, pw
    ev = event_row(date_mode='poll', starts_at=None, max_participants=None, location_name='Cobalt Project', date_options=[
        {'id': OPT1, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-20T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
        {'id': OPT2, 'event_id': EVENT_PAGE, 'starts_at': '2030-11-27T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
        {'id': OPT3, 'event_id': EVENT_PAGE, 'starts_at': '2020-01-01T18:00:00Z', 'ends_at': None, 'proposed_by': None, 'date_votes': []},
    ])
    context, page = open_event(browser, events_origin, ev)
    try:
        button = page.get_by_role('button', name='Mettre les 2 dates dans mon agenda', exact=True)  # la date passée n'y est pas
        pw.expect(button).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Notées « À confirmer »', exact=False)).to_be_visible()
        with page.expect_download() as info:
            button.click()
        body = unfold(open(info.value.path(), encoding='utf-8').read())
        entries = events(body)
        assert [e.split('UID:')[1].split('@')[0] for e in entries] == [OPT1, OPT2]
        assert all('SUMMARY:À confirmer · Soirée de test participant' in e and 'LOCATION:Cobalt Project' in e for e in entries)
    finally:
        context.close()
