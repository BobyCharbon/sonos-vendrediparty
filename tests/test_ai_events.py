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
         "start": NEXT_WEEK, "end": "", "place_query": "Rue du Lac 12, Vevey", "place_name": "Chez Léa", "place_broad": "", "address_complete": True, "price_chf": 0,
         "max_participants": 12, "category": "Soirée", "audience": "Ski", "invitees": ["Tom"], "not_understood": [],
         "pot": True, "bring": ["Salade", "Vin"],
         "summary": "Raclette chez Léa samedi prochain à 20 h"}


class Resp:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def json(self):
        return self.body


class FakeAccounts:
    def __init__(self, perms=("ai.use", "events.create", "events.publish_direct")):
        self.perms, self.calls, self.in_vip = set(perms), [], True

    def _uid(self, token):
        return "u1"

    def _perms(self, token):
        return self.perms

    def link(self, token):
        return {"name": "Léa"}

    def groups(self, token):
        # Foot : créé par la personne mais elle n'en fait pas partie (jamais proposé, sauf à un admin).
        return {"groups": [{"id": "g-vip", "name": "Vendredi Party", "system": True, "inside": self.in_vip},
                           {"id": "g-ski", "name": "Ski", "system": False, "inside": True},
                           {"id": "g-foot", "name": "Foot", "system": False, "inside": False}],
                "people": [{"id": "p-tom", "name": "Tom"}, {"id": "p-lea", "name": "Léa"}]}

    def _get(self, method, path, token, json=None, headers=None):
        self.calls.append((method, path, json))
        if path.startswith("/rest/v1/categories"):
            return Resp(200, [{"id": "c-soiree", "name": "Soirée"}, {"id": "c-sport", "name": "Sport"}])
        if path.startswith("/rest/v1/tags"):
            return Resp(200, [{"id": "t-fondue", "name": "fondue"}])
        if method == "POST" and path.startswith("/rest/v1/polls"):
            return Resp(201, [{"id": "poll1"}])
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
    assert schema["properties"]["audience"]["enum"] == ["Vendredi Party", "Ski", ev.ONLY_INVITEES, "Public (lien)"]
    assert schema["properties"]["invitees"]["items"]["enum"] == ["Tom", "Léa"] and d["invitees"] == ["Tom"]
    assert "Léa" in client.calls[0]["system"] and client.calls[0]["model"] == ev.MODEL
    assert "Soirée" in schema["properties"]["category"]["enum"]
    entry = a.ai.usage.items[0]
    assert entry["feature"] == "event" and entry["model"] == "claude-opus-5-5" and "invite le groupe Ski" in entry["said"]
    assert entry["cost_usd"] == pytest.approx((900 * 4 + 300 * 20) / 1e6)


def test_missing_date_or_title_always_comes_back_as_a_question(tmp_path):
    a, _, _ = make(tmp_path, {**READY, "status": "ready", "start": "", "title": ""})
    d = a.draft("ok", ["On se fait un truc"], None)
    assert d["status"] == "needs_info" and len(d["questions"]) == 2


def test_a_past_date_is_never_kept(tmp_path):
    a, _, _ = make(tmp_path, {**READY, "start": "2020-01-01T20:00"})
    assert a.draft("ok", ["Raclette le 1er janvier 2020"], None)["start"] == ""


def test_answers_follow_the_previous_draft_as_a_conversation(tmp_path):
    a, _, client = make(tmp_path)
    a.draft("ok", ["Raclette chez Léa", "samedi à 20h"], {"title": "Raclette chez Léa", "questions": ["Quand ?"]})
    roles = [m["role"] for m in client.calls[0]["messages"]]
    assert roles == ["user", "assistant", "user"] and client.calls[0]["messages"][2]["content"] == "samedi à 20h"
    assert "Quand ?" in client.calls[0]["messages"][1]["content"]


def test_named_people_are_invited_and_only_them_when_asked(tmp_path):
    a, accounts, _ = make(tmp_path)
    a.create("ok", {**READY, "audience": ev.ONLY_INVITEES, "invitees": ["Tom", "Léa", "Inconnu"]}, None)
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    invites = next(j for m, p, j in accounts.calls if p == "/rest/v1/event_invites")
    assert row["visibility"] == "invited" and [i["user_id"] for i in invites] == ["p-tom", "p-lea"]
    assert not any(p == "/rest/v1/event_groups" for _, p, _ in accounts.calls)
    with pytest.raises(AccountError, match="qui inviter"):
        a.create("ok", {**READY, "audience": ev.ONLY_INVITEES, "invitees": []}, None)


def test_confirmed_draft_creates_the_event_as_the_user_then_publishes_it(tmp_path):
    a, accounts, _ = make(tmp_path)
    out = a.create("ok", READY, {"name": "Chez Léa", "address": "Rue du Lac 12, 1800 Vevey",
                                 "url": "https://www.google.com/maps/search/?api=1&query=Rue+du+Lac+12"})
    assert out == {"id": "e1", "status": "published", "title": "Raclette chez Léa", "problems": []}
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
    with pytest.raises(AccountError, match="titre, la date"):
        a.create("ok", {**READY, "start": ""}, None)


FONDUE = {**READY, "title": "Fondue au Café de Collex", "audience": "Vendredi Party", "invitees": [], "bring": ["Dessert"],
          "polls": [{"question": "Tu prends quoi ?", "options": ["Fondue", "Autre plat"], "multiple": False,
                     "anonymous": False, "add_options": False}],
          "organizers": ["Léa"], "tags": ["fondue", "inconnu"], "payment_info": "TWINT", "plus_ones": False,
          "allow_maybe": False, "waitlist": False, "forum": False, "notify": False, "show_participants": False}


def test_every_form_field_is_written_polls_bring_and_options_included(tmp_path):
    a, accounts, _ = make(tmp_path)
    out = a.create("ok", FONDUE, None)
    assert out["problems"] == []
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert (row["payment_info"], row["allow_plus_ones"], row["allow_maybe"], row["waitlist_enabled"]) == ("TWINT", False, False, False)
    assert (row["forum_enabled"], row["notify_on_publish"], row["show_participants"]) == (False, False, False)
    poll = next(j for m, p, j in accounts.calls if p.startswith("/rest/v1/polls"))
    assert poll["question"] == "Tu prends quoi ?" and poll["event_id"] == "e1"
    options = next(j for m, p, j in accounts.calls if p == "/rest/v1/poll_options")
    assert [o["label"] for o in options] == ["Fondue", "Autre plat"] and options[0]["poll_id"] == "poll1"
    assert next(j for m, p, j in accounts.calls if p == "/rest/v1/event_organizers") == [{"event_id": "e1", "user_id": "p-lea"}]
    assert next(j for m, p, j in accounts.calls if p == "/rest/v1/event_tags") == [{"event_id": "e1", "tag_id": "t-fondue"}]
    assert next(j for m, p, j in accounts.calls if p == "/rest/v1/bring_items")[0]["label"] == "Dessert"


def test_a_date_poll_needs_two_dates_and_writes_them(tmp_path):
    a, accounts, _ = make(tmp_path)
    later = (datetime.now(ev.ZURICH) + timedelta(days=8)).strftime("%Y-%m-%dT19:00")
    poll = {**READY, "date_mode": "poll", "start": "", "date_options": [NEXT_WEEK]}
    with pytest.raises(AccountError, match="titre, la date"):
        a.create("ok", poll, None)
    a.create("ok", {**poll, "date_options": [NEXT_WEEK, later]}, None)
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["date_mode"] == "poll" and row["starts_at"] is None
    assert len(next(j for m, p, j in accounts.calls if p == "/rest/v1/date_options")) == 2


def test_defaults_match_the_web_form_when_nothing_is_said(tmp_path):
    d = ev.clean_draft({"title": "Ciné", "start": NEXT_WEEK, "place_query": "Pathé Flon, Lausanne", "address_complete": True},
                       datetime.now(ev.ZURICH),
                       {"categories": [], "tags": [], "audiences": ["Vendredi Party"], "people": []})
    assert d["status"] == "ready" and d["plus_ones"] and d["allow_maybe"] and d["waitlist"] and d["forum"] and d["notify"]
    assert d["polls"] == [] and d["date_mode"] == "fixed"


def test_a_failed_poll_is_reported_without_losing_the_event(tmp_path):
    a, accounts, _ = make(tmp_path)
    original = accounts._get

    def broken(method, path, token, json=None, headers=None):
        if path.startswith("/rest/v1/polls"):
            accounts.calls.append((method, path, json))
            return Resp(403, {"message": "refusé"})
        return original(method, path, token, json=json, headers=headers)

    accounts._get = broken
    out = a.create("ok", FONDUE, None)
    assert out["status"] == "published" and out["problems"] == ["le sondage « Tu prends quoi ? »"]


def test_chez_moi_without_a_full_address_always_asks_for_it(tmp_path):
    a, _, _ = make(tmp_path, {**READY, "place_query": "Lutry", "place_name": "Chez Boby", "address_complete": False,
                              "status": "ready", "questions": []})
    d = a.draft("ok", ["Mon anniversaire chez moi samedi à 19h"], None)
    assert d["status"] == "needs_info" and any("adresse complète" in q for q in d["questions"])
    with pytest.raises(AccountError):
        a.create("ok", {**READY, "address_complete": False}, None)


def test_a_party_at_home_is_searched_as_an_address_and_keeps_its_name(tmp_path):
    home = {**READY, "place_kind": "home", "place_query": "420 Route des Rosselets, 01170 Ségny, France",
            "place_name": "Chez Boby", "place_broad": "bar, Ségny"}
    a, accounts, client = make(tmp_path, home)
    d = a.draft("ok", ["Soirée chez moi samedi, 420 route des roselets 01170 Segny France"], None)
    assert d["place_kind"] == "home" and d["place_broad"] == ""  # jamais de recherche large de commerces
    assert "place_kind" in client.calls[0]["output_config"]["format"]["schema"]["required"]
    a.create("ok", d, {"name": "420 Route des Rosselets", "address": "420 Route des Rosselets, 01170 Ségny, France",
                       "url": "https://www.google.com/maps/search/?api=1&query=420"})
    row = next(body for method, path, body in accounts.calls if method == "POST" and path.startswith("/rest/v1/events"))
    assert row["location_name"] == "Chez Boby"
    assert row["location_address"] == "420 Route des Rosselets, 01170 Ségny, France"


def test_an_old_draft_without_place_kind_is_a_venue(tmp_path):
    a, _, _ = make(tmp_path, {k: v for k, v in READY.items() if k != "place_kind"})
    assert a.draft("ok", ["Raclette"], None)["place_kind"] == "venue"


def test_a_quantity_said_to_the_ai_is_shared_between_guests(tmp_path):
    assert ev.bring_row("15 bouteilles de vin") == {"label": "Bouteilles de vin", "quantity": 15}
    assert ev.bring_row("3x paquets de chips") == {"label": "Paquets de chips", "quantity": 3}
    assert ev.bring_row("Salade") == {"label": "Salade", "quantity": None}
    assert ev.bring_row("1 gâteau") == {"label": "1 gâteau", "quantity": None}  # un seul : quelqu'un le prend en entier
    a, accounts, _ = make(tmp_path, {**READY, "bring": ["15 bouteilles de vin", "Salade"]})
    a.create("ok", a.draft("ok", ["Raclette, 15 bouteilles de vin et une salade"], None), {"name": "x", "address": "y"})
    rows = next(body for method, path, body in accounts.calls if method == "POST" and path == "/rest/v1/bring_items")
    assert [(r["label"], r.get("quantity")) for r in rows] == [("Bouteilles de vin", 15), ("Salade", None)]


def test_every_bring_row_has_the_same_fields_so_the_batch_insert_is_accepted(tmp_path):
    rows = [ev.bring_row(t) for t in ("15 bouteilles de vin", "Salade")]
    assert {frozenset(r) for r in rows} == {frozenset({"label", "quantity"})}


def test_a_malformed_draft_from_the_app_is_cleaned_never_a_crash(tmp_path):
    a, accounts, _ = make(tmp_path)
    for bad in ({"polls": ["x"]}, {"bring": 5}, {"tags": {"a": 1}}, {"invitees": [None, {"x": 1}]}):
        d = ev.clean_draft({**READY, **bad}, ev.datetime.now(ev.ZURICH), {"categories": [], "tags": [], "audiences": ["Ski"],
                                                                          "people": ["Tom"]})
        assert isinstance(d["polls"], list) and isinstance(d["bring"], list)


def test_without_saying_for_whom_the_event_is_public_with_a_public_link(tmp_path):
    """Demande de l'admin (4.11) : rien de dit sur le public → public + lien public (plus le groupe Vendredi Party)."""
    d = ev.clean_draft({"title": "Ciné", "start": NEXT_WEEK, "place_query": "Pathé Flon, Lausanne", "address_complete": True},
                       datetime.now(ev.ZURICH),
                       {"categories": [], "tags": [], "audiences": ["Vendredi Party", ev.PUBLIC_AUDIENCE], "people": []})
    assert d["audience"] == ev.PUBLIC_AUDIENCE
    a, accounts, _ = make(tmp_path)
    a.create("ok", {k: v for k, v in READY.items() if k not in ("audience", "invitees")}, None)
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["visibility"] == "all" and row["public_link"] is True
    assert "Si elle n'en parle pas : « {public} »" in ev.SYSTEM


def test_the_ai_never_turns_qr_tickets_on(tmp_path):
    """Billets QR : l'organisateur les active lui-même ; ni le schéma, ni le brouillon, ni l'événement écrit n'en parlent."""
    schema = ev.schema({"categories": [], "tags": [], "audiences": ["Vendredi Party"], "people": []})
    assert not any("ticket" in k or "billet" in k for k in schema["properties"])
    d = ev.clean_draft({**READY, "tickets_enabled": True, "tickets": True}, datetime.now(ev.ZURICH),
                       {"categories": ["Soirée"], "tags": [], "audiences": ["Ski"], "people": ["Tom"]})
    assert "tickets_enabled" not in d and "tickets" not in d
    a, accounts, _ = make(tmp_path)
    a.create("ok", {**READY, "tickets_enabled": True}, None)
    writes = [j for m, p, j in accounts.calls if p.startswith("/rest/v1/events") and isinstance(j, dict)]
    assert writes and all("tickets_enabled" not in j for j in writes)
    assert "Billets QR : tu ne les actives JAMAIS" in ev.SYSTEM


# ── Deux étapes (demande de l'admin, 06.11) : la soirée, puis les invités choisis par la personne ──

def test_the_prompt_never_asks_whom_to_invite_and_never_invents_guests(tmp_path):
    a, _, client = make(tmp_path)
    a.draft("ok", ["Raclette chez Léa samedi à 20h"], None)
    system = client.calls[0]["system"]
    assert "tu ne demandes JAMAIS qui inviter" in system and "tu n'inventes aucun invité" in system
    assert "ni\nsur qui inviter" in system and "tu ne les invites pas toi-même" in system


def test_a_question_about_whom_to_invite_is_dropped(tmp_path):
    a, _, _ = make(tmp_path, {**READY, "status": "needs_info", "questions": ["Qui veux-tu inviter ?", "Tu invites le groupe ?"]})
    d = a.draft("ok", ["Raclette chez Léa samedi à 20h"], None)
    assert d["questions"] == [] and d["status"] == "ready"


def test_step_two_saves_a_draft_without_inviting_anyone_and_proposes_the_named_people(tmp_path):
    a, accounts, _ = make(tmp_path)
    out = a.save_draft("ok", {**READY, "audience": ev.ONLY_INVITEES, "invitees": ["Tom", "Léa", "Inconnu"]}, None)
    # Léa est la personne connectée (FakeAccounts.link) mais pas u1 : seule une personne qui n'est pas soi est proposée.
    assert out == {"id": "e1", "status": "draft", "title": "Raclette chez Léa", "problems": [],
                   "suggested": [{"id": "p-tom", "name": "Tom"}, {"id": "p-lea", "name": "Léa"}],
                   "preset": {"audience": "invite", "group_ids": []}}
    assert not any(p == "/rest/v1/event_invites" for _, p, _ in accounts.calls)
    assert not any(m == "PATCH" and "status" in (j or {}) for m, _, j in accounts.calls)  # jamais publié par l'IA : étape 2
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    # Visibilité choisie à l'étape 2 : en attendant, le défaut (public + lien public).
    assert row["status"] == "draft" and row["visibility"] == "all" and row["public_link"] is True


def test_step_two_draft_keeps_the_group_options_and_lists_but_not_qr_tickets(tmp_path):
    a, accounts, _ = make(tmp_path, {**READY, "tickets_enabled": True})
    d = a.draft("ok", ["Raclette, billets QR"], None)
    out = a.save_draft("ok", {**d, "tickets_enabled": True}, None)
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert "tickets_enabled" not in row and out["status"] == "draft"
    # Le groupe dit à l'IA n'est qu'un pré-réglage de l'étape 2 : rien n'est écrit avant que la personne confirme.
    assert not any(p == "/rest/v1/event_groups" for _, p, _ in accounts.calls)
    assert out["preset"] == {"audience": "group", "group_ids": ["g-ski"]} and row["public_link"] is True
    assert any(p == "/rest/v1/bring_items" for _, p, _ in accounts.calls)


def test_step_two_draft_needs_no_named_guest_even_for_invitees_only(tmp_path):
    a, _, _ = make(tmp_path, perms=("ai.use", "events.create"))
    out = a.save_draft("ok", {**READY, "audience": ev.ONLY_INVITEES, "invitees": []}, None)
    assert out["status"] == "draft" and out["suggested"] == []


def test_step_two_draft_checks_rights_moderation_and_completeness(tmp_path):
    a, _, _ = make(tmp_path, perms=("ai.use",))
    with pytest.raises(AccountError, match="créer"):
        a.save_draft("ok", READY, None)
    a, _, _ = make(tmp_path)
    with pytest.raises(AccountError, match="titre"):
        a.save_draft("ok", {**READY, "title": ""}, None)


def test_the_ai_never_asks_who_sees_the_event_and_what_is_said_is_only_a_preset(tmp_path):
    """Retour de l'admin (06.11) : la visibilité se choisit à l'étape 2, jamais à l'étape 1."""
    assert "tu ne poses JAMAIS de question sur\n  la visibilité" in ev.SYSTEM and "pré-réglage" in ev.SYSTEM
    asks = ["Pour qui est l'événement ?", "Public ou privé ?", "Qui peut le voir ?", "Le rendre visible à tous ?",
            "À quelle heure ?"]
    a, _, _ = make(tmp_path, {**READY, "status": "needs_info", "questions": asks})
    assert a.draft("ok", ["Raclette"], None)["questions"] == ["À quelle heure ?"]
    assert ev.preset("public") == {"audience": "public", "group_ids": []}
    assert ev.preset(None) == {"audience": "vip", "group_ids": []}
    a, _, _ = make(tmp_path)
    assert a.save_draft("ok", {**READY, "audience": ev.PUBLIC_AUDIENCE}, None)["preset"]["audience"] == "public"
    assert a.save_draft("ok", {**READY, "audience": "Vendredi Party"}, None)["preset"]["audience"] == "vip"


def test_the_ai_only_offers_the_groups_the_person_is_in_vendredi_party_included(tmp_path):
    """Question de l'admin (06.11) : un groupe (Vendredi Party compris) seulement si on en fait partie ; un admin
    (events.manage_all) garde tous ses groupes. La base le garantit aussi (migration 20261106090000)."""
    a, accounts, client = make(tmp_path)
    a.draft("ok", ["Raclette"], None)
    assert client.calls[-1]["output_config"]["format"]["schema"]["properties"]["audience"]["enum"] == \
        ["Vendredi Party", "Ski", ev.ONLY_INVITEES, ev.PUBLIC_AUDIENCE]
    accounts.in_vip = False
    a.draft("ok", ["Raclette"], None)
    assert client.calls[-1]["output_config"]["format"]["schema"]["properties"]["audience"]["enum"] == \
        ["Ski", ev.ONLY_INVITEES, ev.PUBLIC_AUDIENCE]
    # Dit à l'IA quand même (ou venu de l'app) : jamais retenu, le public par défaut le remplace.
    assert a.save_draft("ok", {**READY, "audience": "Vendredi Party"}, None)["preset"]["audience"] == "public"
    assert a.save_draft("ok", {**READY, "audience": "Foot"}, None)["preset"]["audience"] == "public"
    accounts.perms.add("events.manage_all")
    a.draft("ok", ["Raclette"], None)
    assert client.calls[-1]["output_config"]["format"]["schema"]["properties"]["audience"]["enum"] == \
        ["Vendredi Party", "Ski", "Foot", ev.ONLY_INVITEES, ev.PUBLIC_AUDIENCE]


def test_a_public_event_never_announces_itself_but_a_group_event_still_does(tmp_path):
    """Décision de l'admin (06.11) : public → jamais de notification de publication (sinon spam), même si l'IA a
    compris « préviens tout le monde ». Le brouillon de l'étape 2 garde le réglage : la base décide à la publication
    (un brouillon public passé à un groupe à l'étape 2 prévient bien son groupe)."""
    a, accounts, _ = make(tmp_path)
    a.create("ok", {**READY, "audience": "Public (lien)", "notify": True}, None)
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["public_link"] and row["notify_on_publish"] is False
    a, accounts, _ = make(tmp_path)
    a.create("ok", {**READY, "audience": "Ski", "notify": True}, None)
    row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
    assert row["notify_on_publish"] is True


def test_the_ai_never_announces_to_a_group_by_itself(tmp_path):
    """Annonces de groupe (06.11) : l'IA n'allume jamais « Prévenir le groupe », même si elle a compris « préviens le
    groupe » ; la personne le choisit à l'étape 2 et la base fait valider la demande."""
    for audience in ("Ski", "Public (lien)"):
        a, accounts, _ = make(tmp_path)
        a.create("ok", {**READY, "audience": audience, "notify": True}, None)
        row = next(j for m, p, j in accounts.calls if m == "POST" and p.startswith("/rest/v1/events"))
        assert row["announce_group"] is False


def test_step_two_draft_keeps_the_named_people_with_the_draft_without_inviting_them(tmp_path):
    """Retour de l'admin (06.11) : les personnes citées à l'IA restent avec le brouillon (events.ai_suggested), pour être
    cochées d'avance quand l'étape 2 est rouverte depuis la fiche ; jamais une invitation."""
    a, accounts, _ = make(tmp_path)
    a.save_draft("ok", {**READY, "invitees": ["Tom", "Léa"]}, None)
    kept = [j for m, p, j in accounts.calls if m == "PATCH" and p == "/rest/v1/events?id=eq.e1"]
    assert kept == [{"ai_suggested": ["p-tom", "p-lea"]}]
    assert not any(p.startswith("/rest/v1/event_invites") for _, p, _ in accounts.calls)


def test_a_base_without_the_column_still_saves_the_draft(tmp_path):
    a, accounts, _ = make(tmp_path)
    plain = accounts._get
    accounts._get = lambda method, path, token, json=None, headers=None: (
        Resp(400, {"code": "PGRST204", "message": "Could not find the 'ai_suggested' column"})
        if method == "PATCH" and isinstance(json, dict) and "ai_suggested" in json else plain(method, path, token, json=json, headers=headers))
    out = a.save_draft("ok", {**READY, "invitees": ["Tom"]}, None)
    assert out["id"] == "e1" and out["problems"] == []


def test_without_named_people_nothing_more_is_written(tmp_path):
    a, accounts, _ = make(tmp_path)
    a.save_draft("ok", {**READY, "invitees": []}, None)
    assert not any(m == "PATCH" for m, _, _ in accounts.calls)


def test_poll_dates_said_without_an_hour_ask_for_the_hour_not_for_dates_again():
    """Retour de l'admin (08.11) : « le 14 ou le 21 » sans heure → les dates étaient jetées et l'IA redemandait les dates
    en boucle : impossible de créer un sondage. On demande l'heure, une seule fois ; avec l'heure, c'est prêt."""
    now = datetime.now(ev.ZURICH)
    day = lambda n: (now + timedelta(days=n)).strftime("%Y-%m-%d")  # noqa: E731
    choices = {"categories": [], "tags": [], "audiences": [], "people": []}
    base = {"title": "Raclette", "date_mode": "poll", "place_query": "Rue du Rhône 1, 1950 Sion", "address_complete": True}
    d = ev.clean_draft({**base, "date_options": [day(8), day(15)]}, now, choices)
    assert d["status"] == "needs_info" and d["questions"] == ["À quelle heure pour les dates proposées ?"]
    d = ev.clean_draft({**base, "date_options": [f"{day(8)} 19:00", f"{day(15)}T19:30"]}, now, choices)  # espace ou « T »
    assert d["status"] == "ready" and d["date_options"] == [f"{day(8)}T19:00", f"{day(15)}T19:30"]
