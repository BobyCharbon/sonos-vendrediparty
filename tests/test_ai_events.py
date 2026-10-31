"""Créer un événement avec l'IA : brouillon (Claude simulé, aucun appel payant), questions quand il manque quelque
chose, dates passées refusées, puis création avec la session de la personne (base simulée)."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app import ai_events as ev
from app import assistant as ai
from app.accounts import AccountError

NEXT_WEEK = (datetime.now(ev.ZURICH) + timedelta(days=7)).strftime("%Y-%m-%dT20:00")
READY = {"status": "ready", "questions": [], "title": "Raclette chez Léa", "description": "Raclette, amène une salade.",
         "start": NEXT_WEEK, "end": "", "place_query": "Rue du Lac 12, Vevey", "place_name": "Chez Léa", "price_chf": 0,
         "max_participants": 12, "category": "Soirée", "audience": "Ski", "pot": True, "bring": ["Salade", "Vin"],
         "summary": "Raclette chez Léa samedi prochain à 20 h"}


class Resp:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def json(self):
        return self.body


class FakeAccounts:
    def __init__(self, perms=("ai.use", "events.create", "events.publish_direct")):
        self.perms, self.calls = set(perms), []

    def _uid(self, token):
        return "u1"

    def _perms(self, token):
        return self.perms

    def link(self, token):
        return {"name": "Léa"}

    def groups(self, token):
        return {"groups": [{"id": "g-vip", "name": "Vendredi Party", "system": True},
                           {"id": "g-ski", "name": "Ski", "system": False}]}

    def _get(self, method, path, token, json=None, headers=None):
        self.calls.append((method, path, json))
        if path.startswith("/rest/v1/categories"):
            return Resp(200, [{"id": "c-soiree", "name": "Soirée"}, {"id": "c-sport", "name": "Sport"}])
        if method == "POST" and path.startswith("/rest/v1/events"):
            return Resp(201, [{"id": "e1"}])
        return Resp(201 if method == "POST" else 204, None)


class FakeClient:
    def __init__(self, answer):
        self.answer, self.calls = answer, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason="end_turn", usage=SimpleNamespace(input_tokens=900, output_tokens=300),
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def make(tmp_path, answer=READY, perms=("ai.use", "events.create", "events.publish_direct")):
    accounts = FakeAccounts(perms)
    client = FakeClient(answer)
    base = ai.Assistant(accounts, ai.UsageLog(tmp_path / "ai.json"), lambda: client, 3.0, ("CHF",))
    return ev.EventAssistant(base, accounts), accounts, client


def test_a_description_becomes_a_ready_draft_with_the_user_groups_and_categories(tmp_path):
    a, _, client = make(tmp_path)
    d = a.draft("ok", ["Raclette chez Léa samedi prochain à 20h, invite le groupe Ski"], None)
    assert d["status"] == "ready" and d["title"] == "Raclette chez Léa" and d["audience"] == "Ski" and d["pot"]
    schema = client.calls[0]["output_config"]["format"]["schema"]
    assert schema["properties"]["audience"]["enum"] == ["Vendredi Party", "Ski", "Public (lien)"]
    assert "Soirée" in schema["properties"]["category"]["enum"] and client.calls[0]["model"] == ai.MODEL
    assert a.ai.usage.items[0]["feature"] == "event"


def test_missing_date_or_title_always_comes_back_as_a_question(tmp_path):
    a, _, _ = make(tmp_path, {**READY, "status": "ready", "start": "", "title": ""})
    d = a.draft("ok", ["On se fait un truc"], None)
    assert d["status"] == "needs_info" and len(d["questions"]) == 2


def test_a_past_date_is_never_kept(tmp_path):
    a, _, _ = make(tmp_path, {**READY, "start": "2020-01-01T20:00"})
    assert a.draft("ok", ["Raclette le 1er janvier 2020"], None)["start"] == ""


def test_answers_are_sent_with_the_previous_draft(tmp_path):
    a, _, client = make(tmp_path)
    a.draft("ok", ["Raclette chez Léa", "samedi à 20h"], {"title": "Raclette chez Léa"})
    said = client.calls[0]["messages"][0]["content"]
    assert "samedi à 20h" in said and "Brouillon actuel" in said


def test_confirmed_draft_creates_the_event_as_the_user_then_publishes_it(tmp_path):
    a, accounts, _ = make(tmp_path)
    out = a.create("ok", READY, {"name": "Chez Léa", "address": "Rue du Lac 12, 1800 Vevey",
                                 "url": "https://www.google.com/maps/search/?api=1&query=Rue+du+Lac+12"})
    assert out == {"id": "e1", "status": "published", "title": "Raclette chez Léa"}
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["status"] == "draft" and row["visibility"] == "invited" and row["category_id"] == "c-soiree"
    assert row["location_address"].startswith("Rue du Lac") and row["pot_enabled"] and row["max_participants"] == 12
    assert ("POST", "/rest/v1/event_groups", {"event_id": "e1", "group_id": "g-ski"}) in accounts.calls
    assert any(p == "/rest/v1/bring_items" for _, p, _ in accounts.calls)
    assert accounts.calls[-1] == ("PATCH", "/rest/v1/events?id=eq.e1", {"status": "published"})


def test_without_direct_publishing_the_event_is_proposed(tmp_path):
    a, accounts, _ = make(tmp_path, perms=("ai.use", "events.create"))
    assert a.create("ok", {**READY, "audience": "Vendredi Party"}, None)["status"] == "pending"
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["visibility"] == "all" and not any(p == "/rest/v1/event_groups" for _, p, _ in accounts.calls)


def test_rights_and_unsafe_links_are_checked(tmp_path):
    a, _, _ = make(tmp_path, perms=("events.create",))
    with pytest.raises(AccountError, match="pas activé"):
        a.draft("ok", ["Raclette"], None)
    a, _, _ = make(tmp_path, perms=("ai.use",))
    with pytest.raises(AccountError, match="créer"):
        a.create("ok", READY, None)
    a, accounts, _ = make(tmp_path)
    a.create("ok", READY, {"url": "javascript:alert(1)"})
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["location_url"] is None


def test_an_incomplete_draft_cannot_be_created(tmp_path):
    a, _, _ = make(tmp_path)
    with pytest.raises(AccountError, match="titre ou la date"):
        a.create("ok", {**READY, "start": ""}, None)
