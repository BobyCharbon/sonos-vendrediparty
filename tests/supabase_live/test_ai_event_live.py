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
    categories, audiences = a._options(token)
    draft = {**READY, "title": "Raclette IA (test)", "category": next(iter(categories), ""), "audience": "Vendredi Party"}
    out = a.create(token, draft, {"name": "Chez Léa", "address": "Rue du Lac 12, 1800 Vevey",
                                  "url": "https://www.google.com/maps/search/?api=1&query=Rue%20du%20Lac%2012%20Vevey"})
    try:
        row = httpx.get(f"{TEST_URL}/rest/v1/events?id=eq.{out['id']}&select=status,title,location_address,pot_enabled,bring_items(label)",
                        headers=who.headers, timeout=30).json()[0]
        assert row["status"] == out["status"] == "published" and row["title"] == "Raclette IA (test)"
        assert row["location_address"].startswith("Rue du Lac") and row["pot_enabled"]
        assert sorted(b["label"] for b in row["bring_items"]) == ["Salade", "Vin"]
    finally:
        httpx.delete(f"{TEST_URL}/rest/v1/events?id=eq.{out['id']}", headers=who.headers, timeout=30)
