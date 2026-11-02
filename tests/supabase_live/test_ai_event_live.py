"""Créer un événement avec l'IA, sur la VRAIE base de test (jamais la prod) : Claude simulé, mais l'écriture passe par
les vraies règles de la base avec la session d'un compte de test (événement, groupe invité, qui amène quoi, pot commun)."""
import httpx
import pytest

from app import accounts as accounts_mod, assistant as ai
from app import ai_events as ev
from tests.supabase_live.test_audiences_live import ADMIN
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.test_ai_events import READY


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    monkeypatch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    accounts = accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))
    who = Session(ADMIN)
    token = who.headers['Authorization'].removeprefix('Bearer ')
    base = ai.Assistant(accounts, ai.UsageLog(tmp_path / 'ai.json'), None, 3.0, ('CHF',))
    return ev.EventAssistant(base, accounts), token, who


def test_the_confirmed_draft_becomes_a_real_published_event(live):
    a, token, who = live
    options = a._options(token)
    draft = {**READY, "title": "Raclette IA (test)", "category": next(iter(options.categories), ""), "audience": "Vendredi Party",
             "invitees": [], "payment_info": "TWINT", "plus_ones": False,
             "polls": [{"question": "Tu prends quoi ?", "options": ["Raclette", "Autre plat"], "multiple": False,
                        "anonymous": False, "add_options": False}]}
    out = a.create(token, draft, {"name": "Chez Léa", "address": "Rue du Lac 12, 1800 Vevey",
                                  "url": "https://www.google.com/maps/search/?api=1&query=Rue%20du%20Lac%2012%20Vevey"})
    try:
        row = httpx.get(f"{TEST_URL}/rest/v1/events?id=eq.{out['id']}&select=status,title,location_address,pot_enabled,payment_info,allow_plus_ones,bring_items(label),polls(question,poll_options(label))",
                        headers=who.headers, timeout=30).json()[0]
        assert row["status"] == out["status"] == "published" and row["title"] == "Raclette IA (test)"
        assert row["location_address"].startswith("Rue du Lac") and row["pot_enabled"]
        assert sorted(b["label"] for b in row["bring_items"]) == ["Salade", "Vin"]
        assert row["payment_info"] == "TWINT" and row["allow_plus_ones"] is False and out["problems"] == []
        assert row["polls"][0]["question"] == "Tu prends quoi ?"
        assert sorted(o["label"] for o in row["polls"][0]["poll_options"]) == ["Autre plat", "Raclette"]
    finally:
        httpx.delete(f"{TEST_URL}/rest/v1/events?id=eq.{out['id']}", headers=who.headers, timeout=30)


def test_a_published_event_is_changed_by_voice_keeping_what_guests_already_said(live):
    from app.ai_event_edit import EventEditor
    a, token, who = live
    draft = {**READY, "title": "Raclette à modifier (test)", "audience": "Vendredi Party", "invitees": [],
             "category": "", "bring": ["10 bouteilles de vin", "Salade"],
             "polls": [{"question": "Fondue ?", "options": ["Oui", "Non"], "multiple": False, "anonymous": False, "add_options": False}]}
    eid = a.create(token, draft, {"name": "Chez Léa", "address": "Rue du Lac 12, 1800 Vevey", "url": ""})["id"]
    try:
        vin = who.get(f"bring_items?event_id=eq.{eid}&label=eq.Bouteilles%20de%20vin&select=id").json()[0]["id"]
        assert httpx.post(f"{TEST_URL}/rest/v1/bring_claims", headers=who.headers, timeout=30,
                          json={"item_id": vin, "user_id": who.uid, "quantity": 3}).status_code == 201
        editor = EventEditor(a)
        current = editor.load(token, eid)["draft"]
        assert current["bring"] == ["10 Bouteilles de vin", "Salade"]
        asked = {**current, "title": "Raclette modifiée (test)", "bring": ["15 Bouteilles de vin", "Dessert"], "polls": []}
        out = editor.save(token, eid, asked, None, announce=True)
        assert out["problems"] == [] and "Titre : Raclette modifiée (test)" in out["changes"]
        row = who.get(f"events?id=eq.{eid}&select=title,location_address,polls(id),messages(body),"
                      "bring_items(label,quantity,bring_claims(quantity))").json()[0]
        assert row["title"] == "Raclette modifiée (test)" and row["location_address"].startswith("Rue du Lac")
        items = {b["label"]: b for b in row["bring_items"]}
        assert set(items) == {"Bouteilles de vin", "Dessert"} and items["Bouteilles de vin"]["quantity"] == 15
        assert items["Bouteilles de vin"]["bring_claims"] == [{"quantity": 3}]  # la réponse déjà donnée reste
        assert row["polls"] == [] and row["messages"][0]["body"].startswith("✏️ Événement mis à jour")
    finally:
        httpx.delete(f"{TEST_URL}/rest/v1/events?id=eq.{eid}", headers=who.headers, timeout=30)
