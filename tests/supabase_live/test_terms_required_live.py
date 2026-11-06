"""CGU exigées (terms_enforced, allumé en prod le 06.11) sur la VRAIE base de TEST (jamais la prod) : l'étape 1 de
« Créer avec l'IA » (« Oui, continuer » → /api/account/ai/event/draft/save) passe par la vraie route du serveur et
les vraies règles de la base. Sans CGU acceptées : 403 {"code": "terms_required"} avec la phrase de la base, rien
d'écrit ; après accept_terms : le brouillon est créé. Le réglage et les acceptations du compte sont remis tels quels.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_terms_required_live.py -q"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, assistant as ai
from app import ai_events as ev
from app import main
from tests.supabase_live.test_audiences_live import ADMIN
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql
from tests.test_ai_events import READY

TITLE = "Samedi party CGU (test)"
PLACE = {"name": "Chez Boby", "address": "Rue du Lac 12, 1800 Vevey", "url": ""}


@pytest.fixture
def enforced(monkeypatch, tmp_path):
    """CGU exigées le temps du test, acceptations du compte retirées ; tout est remis à la fin, même en cas d'échec."""
    monkeypatch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    monkeypatch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    accounts = accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))
    who = Session(ADMIN)
    token = who.headers['Authorization'].removeprefix('Bearer ')
    base = ai.Assistant(accounts, ai.UsageLog(tmp_path / 'ai.json'), None, 3.0, ('CHF',))
    monkeypatch.setattr(main, 'event_assistant', ev.EventAssistant(base, accounts))
    was = sql("select terms_enforced from private.moderation_settings where id = 1")[0]['terms_enforced']
    kept = sql(f"select version, accepted_at from public.terms_acceptances where user_id = '{who.uid}'")
    try:
        sql(f"delete from public.terms_acceptances where user_id = '{who.uid}'")
        sql("update private.moderation_settings set terms_enforced = true where id = 1")
        yield TestClient(main.app), token, who
    finally:
        sql(f"update private.moderation_settings set terms_enforced = {'true' if was else 'false'} where id = 1")
        sql(f"delete from public.terms_acceptances where user_id = '{who.uid}'")
        for row in kept:
            sql(f"insert into public.terms_acceptances (user_id, version, accepted_at) values "
                f"('{who.uid}', '{row['version']}', '{row['accepted_at']}') on conflict do nothing")
        assert sql("select terms_enforced from private.moderation_settings where id = 1")[0]['terms_enforced'] is was
        httpx.delete(f"{TEST_URL}/rest/v1/events?title=eq.{TITLE}&created_by=eq.{who.uid}", headers=who.headers, timeout=30)


def test_oui_continuer_asks_for_the_terms_then_saves_the_draft_once_accepted(enforced):
    client, token, who = enforced
    draft = {**READY, "title": TITLE, "category": "", "audience": "", "invitees": [], "polls": []}
    r = client.post("/api/account/ai/event/draft/save", json={"token": token, "draft": draft, "place": PLACE})
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "terms_required"
    assert r.json()["detail"].startswith("Accepte les conditions d'utilisation de Party pour publier")
    assert who.get(f"events?title=eq.{TITLE}&select=id").json() == []  # rien d'écrit
    version = who.rpc('my_terms').json()['version']
    assert who.rpc('accept_terms', p_version=version).json()['accepted'] is True
    r = client.post("/api/account/ai/event/draft/save", json={"token": token, "draft": draft, "place": PLACE})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft" and r.json()["title"] == TITLE
    rows = who.get(f"events?id=eq.{r.json()['id']}&select=status,title").json()
    assert rows == [{"status": "draft", "title": TITLE}]
