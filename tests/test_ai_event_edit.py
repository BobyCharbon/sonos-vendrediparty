"""Modifier un événement publié avec l'IA (Claude et base simulés) : l'événement relu en brouillon, la liste des
changements, l'écriture limitée à ce qui change (réponses gardées), le message aux invités, et les droits."""
import json
from datetime import datetime, timedelta

import pytest

from app import ai_event_edit as edit
from app import ai_events as ev
from app.accounts import AccountError
from tests.test_ai_events import FakeAccounts, Resp, make

START = (datetime.now(ev.ZURICH) + timedelta(days=10)).replace(hour=20, minute=0, second=0, microsecond=0)
EVENT = {
    "id": "e1", "title": "Raclette chez Léa", "description": "Raclette.", "date_mode": "fixed",
    "starts_at": START.isoformat(), "ends_at": None, "location_name": "Chez Léa", "location_address": "Rue du Lac 12, Vevey",
    "location_url": "https://maps.example/x", "price_chf": None, "max_participants": 12, "visibility": "all",
    "public_link": False, "allow_plus_ones": True, "forum_enabled": True, "pot_enabled": False, "created_by": "u1",
    "category": {"name": "Soirée"}, "event_tags": [], "event_organizers": [], "event_groups": [], "date_options": [],
    "event_invites": [{"user_id": "p-tom", "via_group": False}],
    "polls": [{"id": "poll-old", "question": "Fondue ou raclette ?", "poll_options": [{"label": "Fondue"}, {"label": "Raclette"}]}],
    "bring_items": [{"id": "b-vin", "label": "Bouteilles de vin", "quantity": 10, "added_by": None, "sort": 0},
                    {"id": "b-salade", "label": "Salade", "quantity": None, "added_by": None, "sort": 1},
                    {"id": "b-guest", "label": "Chips", "quantity": None, "added_by": "p-tom", "sort": 2}],
}


class EventAccounts(FakeAccounts):
    def __init__(self, event=EVENT, **kw):
        super().__init__(**kw)
        self.event = event

    def _get(self, method, path, token, json=None, headers=None):
        if method == "GET" and path.startswith("/rest/v1/events?id=eq."):
            self.calls.append((method, path, json))
            return Resp(200, [self.event])
        if method == "PATCH" and path.startswith("/rest/v1/events"):
            self.calls.append((method, path, json))
            return Resp(200, [{"id": "e1"}])
        return super()._get(method, path, token, json, headers)


def editor(tmp_path, answer, **kw):
    a, _, client = make(tmp_path, answer)
    accounts = EventAccounts(**kw)
    a.accounts = a.ai.accounts = accounts
    return edit.EventEditor(a), accounts, client


def current(tmp_path):
    e, _, _ = editor(tmp_path, {})
    return e.load("ok", "e1")["draft"]


def test_the_published_event_comes_back_as_a_draft_with_its_lists(tmp_path):
    d = current(tmp_path)
    assert d["title"] == "Raclette chez Léa" and d["start"] == START.strftime("%Y-%m-%dT%H:%M")
    assert d["place_kind"] == "home" and d["place_query"] == "Rue du Lac 12, Vevey"
    assert d["bring"] == ["10 Bouteilles de vin", "Salade"]  # « Chips » ajouté par un invité n'est pas à l'organisateur
    assert d["invitees"] == ["Tom"] and d["polls"][0]["question"] == "Fondue ou raclette ?"


def test_the_ai_gets_the_current_event_and_only_the_changes_are_listed(tmp_path):
    later = (START + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    asked = {**current(tmp_path), "start": later, "bring": ["15 Bouteilles de vin", "Salade", "Dessert"]}
    e, _, client = editor(tmp_path, asked)
    out = e.draft("ok", "e1", ["Décale d'une heure, 15 bouteilles et ajoute un dessert"])
    sent = client.calls[0]
    assert json.loads(sent["messages"][1]["content"])["title"] == "Raclette chez Léa"  # l'événement actuel
    assert "déjà publié" in sent["messages"][0]["content"] and "CHANGEMENTS" in sent["system"]
    assert out["changes"] == [f"Début : {later.replace('T', ' à ')}",
                              "Qui amène quoi : + 15 Bouteilles de vin, Dessert", "Qui amène quoi : − 10 Bouteilles de vin"]


def test_saving_keeps_answers_changes_only_what_moved_and_tells_the_guests(tmp_path):
    asked = {**current(tmp_path), "bring": ["15 Bouteilles de vin", "Dessert"], "polls": [],
             "invitees": ["Tom", "Léa"]}
    e, accounts, _ = editor(tmp_path, asked)
    out = e.save("ok", "e1", asked, None, announce=True)
    calls = [(m, p) for m, p, _ in accounts.calls]
    patch = next(body for m, p, body in accounts.calls if m == "PATCH" and p.startswith("/rest/v1/events"))
    assert "location_name" not in patch and "created_by" not in patch  # lieu inchangé, auteur intact
    assert next(b for m, p, b in accounts.calls if p == "/rest/v1/bring_items?id=eq.b-vin") == {"quantity": 15}
    assert ("DELETE", "/rest/v1/bring_items?id=eq.b-salade") in calls
    assert ("DELETE", "/rest/v1/bring_items?id=eq.b-guest") not in calls  # l'ajout d'un invité n'est jamais touché
    assert ("DELETE", "/rest/v1/polls?id=eq.poll-old") in calls
    message = next(b for m, p, b in accounts.calls if p == "/rest/v1/messages")
    assert message["body"].startswith("✏️ Événement mis à jour") and "Dessert" in message["body"]
    assert out["problems"] == []


def test_without_announce_nothing_is_posted_in_the_discussion(tmp_path):
    asked = {**current(tmp_path), "title": "Raclette géante"}
    e, accounts, _ = editor(tmp_path, asked)
    assert e.save("ok", "e1", asked, None, announce=False)["changes"] == ["Titre : Raclette géante"]
    assert not any(p == "/rest/v1/messages" for _, p, _ in accounts.calls)


def test_only_an_organizer_can_load_or_change_the_event(tmp_path):
    e, _, _ = editor(tmp_path, {}, event={**EVENT, "created_by": "someone-else"})
    for call in (lambda: e.load("ok", "e1"), lambda: e.save("ok", "e1", current(tmp_path), None, True)):
        with pytest.raises(AccountError, match="ne peux pas modifier"):
            call()


def test_editing_with_the_ai_never_touches_the_qr_tickets_option(tmp_path):
    """Billets QR activés par l'organisateur : une modification par l'IA ne les éteint ni ne les allume (colonne absente)."""
    asked = {**current(tmp_path), "title": "Raclette géante", "tickets_enabled": False}
    e, accounts, _ = editor(tmp_path, asked, event={**EVENT, "tickets_enabled": True})
    e.save("ok", "e1", asked, None, announce=False)
    patch = next(body for m, p, body in accounts.calls if m == "PATCH" and p.startswith("/rest/v1/events"))
    assert "tickets_enabled" not in patch and patch["title"] == "Raclette géante"
    assert current(tmp_path)["audience"] == ev.VIP_AUDIENCE  # un événement existant garde son public


def test_a_co_organizer_editing_with_the_ai_never_removes_himself(tmp_path):
    """Bug : un co-organisateur (pas le créateur) qui modifie avec l'IA se retirait lui-même des co-organisateurs (il
    n'est jamais dans la liste du brouillon) et perdait la main sur l'événement ; son invitation aussi."""
    event = {**EVENT, "created_by": "someone-else", "event_organizers": [{"user_id": "u1"}],
             "event_invites": [{"user_id": "p-tom", "via_group": False}, {"user_id": "u1", "via_group": False}]}
    e, _, _ = editor(tmp_path, {}, event=event)
    asked = {**e.load("ok", "e1")["draft"], "title": "Raclette géante"}
    e, accounts, _ = editor(tmp_path, asked, event=event)
    e.save("ok", "e1", asked, None, announce=False)
    dropped = [p for m, p, _ in accounts.calls if m == "DELETE"]
    assert not any("user_id=eq.u1" in p for p in dropped), dropped


def test_an_organizer_outside_vendredi_party_keeps_its_audience_when_editing(tmp_path):
    """Question de l'admin (06.11) : Vendredi Party n'est proposé qu'à ses membres ; un événement qui lui est déjà
    réservé le reste quand on le modifie (la visibilité ne change jamais sans qu'on le demande)."""
    e, accounts, client = editor(tmp_path, {**current(tmp_path), "title": "Raclette géante"})
    accounts.in_vip = False
    assert e.load("ok", "e1")["draft"]["audience"] == ev.VIP_AUDIENCE
    out = e.draft("ok", "e1", ["Appelle-la Raclette géante"])
    assert out["draft"]["audience"] == ev.VIP_AUDIENCE and not any(c.startswith("Invités :") for c in out["changes"])
    assert "Vendredi Party" in client.calls[-1]["output_config"]["format"]["schema"]["properties"]["audience"]["enum"]
