from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def events_client(monkeypatch, tmp_path):
    root = tmp_path / "events-web"
    root.mkdir()
    (root / "index.html").write_text('<html><div id="root">Événements</div></html>')
    (root / "_expo").mkdir()
    (root / "_expo" / "entry-abc.js").write_text('console.log("events")')
    monkeypatch.setattr(main, "EVENTS_WEB", root)
    return TestClient(main.app)


def test_party_navigation_embeds_same_origin_events_without_changing_game_access(events_client):
    page = events_client.get("/")
    assert page.status_code == 200
    assert 'data-tab="events"' in page.text
    assert 'data-tab="music"' in page.text and 'data-tab="games"' in page.text
    assert 'title="Événements du groupe : connexion, événements et sondages"' in page.text
    assert 'frame.src = "/events" +' in page.text and 'data-tab="account"' in page.text
    assert 'bobycharbon.expo.app' not in page.text
    assert events_client.get("/api/state").status_code == 401


@pytest.mark.parametrize("path", ["/events/", "/events/sign-in", "/events/event/64d0880c-5379-42f8-8166-e259d25c7e7b", "/events/settings/subscriptions"])
def test_events_client_routes_return_local_entry_and_prevent_external_framing(events_client, path):
    result = events_client.get(path)
    assert result.status_code == 200 and 'id="root"' in result.text
    assert result.headers['content-security-policy'] == "frame-ancestors 'self'"
    assert result.headers['cache-control'] == 'no-store'


def test_events_assets_are_cacheable_but_missing_files_do_not_return_html(events_client):
    result = events_client.get("/events/_expo/entry-abc.js")
    assert result.status_code == 200
    assert "immutable" in result.headers['cache-control']
    assert 'javascript' in result.headers['content-type']
    for path in ["/events/_expo/missing.js", "/events/package.json", "/events/.env"]:
        assert events_client.get(path).status_code == 404


def test_events_cannot_read_files_outside_build_directory(events_client, tmp_path):
    (tmp_path / "private.txt").write_text("private-data")
    (main.EVENTS_WEB / "outside.txt").symlink_to(tmp_path / "private.txt")
    assert events_client.get("/events/outside.txt").status_code == 404
    assert events_client.get("/events/%2e%2e/private.txt").status_code == 404


def test_missing_events_build_is_explicitly_unavailable(events_client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path / "missing")
    assert events_client.get("/events/").status_code == 503


def test_calendar_file_opens_in_ios_and_android_calendars(events_client):
    result = events_client.get("/api/calendar.ics", params={
        "uid": "64d0880c-5379-42f8-8166-e259d25c7e7b", "title": "Karaoké, chez Marc ; 20 h",
        "start": "2026-10-23T18:30:00.000Z", "end": "2026-10-23T21:30:00.000Z",
        "location": "Chez Marc, Rue du Lac 12", "description": "Ligne 1\nLigne 2 " + "é" * 120,
        "url": "https://party.example/events/event/64d0880c-5379-42f8-8166-e259d25c7e7b",
    })
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("text/calendar")
    assert result.headers["content-disposition"] == 'attachment; filename="karaoke-chez-marc-20-h.ics"'
    body = result.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "DTSTART:20261023T183000Z\r\n" in body and "DTEND:20261023T213000Z\r\n" in body
    assert "SUMMARY:Karaoké\\, chez Marc \\; 20 h\r\n" in body
    assert "UID:64d0880c-5379-42f8-8166-e259d25c7e7b@vendredi-party" in body
    assert "TRIGGER:-PT2H" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))


@pytest.mark.parametrize("params", [
    {"uid": "pas-un-uuid", "title": "Sortie", "start": "2026-10-23T18:30:00Z"},
    {"uid": "64d0880c-5379-42f8-8166-e259d25c7e7b", "title": " ", "start": "2026-10-23T18:30:00Z"},
    {"uid": "64d0880c-5379-42f8-8166-e259d25c7e7b", "title": "Sortie", "start": "demain"},
    {"uid": "64d0880c-5379-42f8-8166-e259d25c7e7b", "title": "Sortie", "start": "2026-10-23T18:30:00"},
])
def test_calendar_file_rejects_invalid_fields(events_client, params):
    assert events_client.get("/api/calendar.ics", params=params).status_code == 400


def test_calendar_file_defaults_to_three_hours_and_drops_unsafe_links(events_client):
    body = events_client.get("/api/calendar.ics", params={
        "uid": "64d0880c-5379-42f8-8166-e259d25c7e7b", "title": "Sortie", "start": "2026-10-23T20:30:00+02:00",
        "end": "2026-10-23T10:00:00+02:00", "url": "javascript:alert(1)"}).text
    assert "DTSTART:20261023T183000Z" in body and "DTEND:20261023T213000Z" in body
    assert "javascript" not in body


def test_events_are_beta_only_in_production(events_client, monkeypatch):
    """Production (EVENTS_ENABLED=0) : « Bientôt » sauf pour les bêta-testeurs ; le module reste servi pour le compte Party."""
    monkeypatch.setattr(main, "EVENTS_ENABLED", False)
    monkeypatch.setattr(main, "_pages", {})
    for path in ("/", "/admin"):
        page = events_client.get(path)
        assert page.status_code == 200 and '<html data-events="beta"' in page.text
    for path in ("/events/", "/events/admin"):
        module = events_client.get(path)
        assert module.status_code == 200 and '<html data-events="beta"' in module.text
    monkeypatch.setattr(main, "_pages", {})  # les pages suivantes retrouvent l'onglet actif


def test_members_can_add_what_they_bring_and_organizer_items_are_labelled():
    root = Path(__file__).resolve().parent.parent
    sql = (root / "supabase/migrations/20261022090000_bring_items_by_members.sql").read_text(encoding="utf-8")
    assert "add column if not exists added_by" in sql and "for insert" in sql and "can_participate(event_id)" in sql
    # Garde : hors organisateur / admin, une mise à jour ne change que claimed_by (sinon on pourrait renommer
    # l'objet d'un autre, ou s'en déclarer l'auteur pour le supprimer).
    guard = sql[sql.index("function public.guard_bring_item()"):]
    assert "before update on public.bring_items" in guard
    for col in ("event_id", "label", "sort", "added_by"):
        assert f"new.{col} := old.{col};" in guard
    assert "new.claimed_by" not in guard
    assert "added_by = auth.uid() and claimed_by = auth.uid()" in sql  # on n'ajoute qu'en son nom
    ui = (root / "web/events/src/components/EventSections.tsx").read_text(encoding="utf-8")
    assert "Demandé par l’organisateur" in ui and "it.added_by ? null" in ui and "Ce que j’amène" in ui


def test_events_shell_lets_android_scroll_by_dragging_over_cards():
    root = Path(__file__).resolve().parent.parent
    shell = (root / "web/events/scripts/postbuild.mjs").read_text(encoding="utf-8")
    # Retour #10 (Android) : aucune règle de défilement sur « * », sinon le doigt posé sur une carte ne fait plus
    # défiler la liste ; vérifié en vrai navigateur par test_android_finger_on_an_event_card_scrolls_the_list.
    star_rules = [r for r in shell.split("}") if r.strip().startswith("*{")]
    assert star_rules and not any("overscroll-behavior" in r or "touch-action" in r for r in star_rules)
    assert "overscroll-behavior:none" in shell  # le rebond reste bloqué au niveau de la page


def test_settings_open_the_party_page_for_guests_messages_and_notifications():
    """Réglages (admin) : « Invités, messages et notifications » ouvre la page de Party ; /admin reste en secours."""
    root = Path(__file__).resolve().parent.parent
    ui = (root / "web/events/src/components/Settings.tsx").read_text(encoding="utf-8")
    assert "openPartyTab('host')" in ui and "Invités, messages et notifications" in ui
    assert "Admin de la soirée" in ui
    page = (root / "app/static/index.html").read_text(encoding="utf-8")
    assert '"feedback", "music", "games", "events", "chats", "host", "stats"].includes(event.data.tab)' in page
    # Tout compte : « Mes stats de jeu » ouvre la page de Party (un onglet par jeu, Purify Test pour commencer).
    assert "openPartyTab('stats')" in ui and "Mes stats de jeu" in ui
