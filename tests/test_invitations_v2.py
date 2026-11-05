"""Invitations v2 (05.11.2026, bêta) côté Party : drapeau invites_v2_enabled (site de test seulement), page servie avec
<html data-invites="off"> en production, aperçu riche du lien /events/invite/<jeton> (WhatsApp, iMessage) lu sans
session et échappé ; migration additive et rejouable, fichier prod prêt (jamais appliqué ici)."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import event_invites, features, main
from tests.test_app_invites import TOKEN, fake

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261105200000_invitations_v2.sql"
CARD = {"inviter": "Ludo", "title": "Raclette & vinyles", "starts_at": "2026-11-14T20:00:00Z", "all_day": False,
        "location_name": "Chez Ludo", "cover_url": None}


@pytest.fixture
def page_dir(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>Party</title></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path)
    main._pages.clear()
    return tmp_path


# ── Le drapeau ──

@pytest.mark.parametrize("url, expected", [("https://partytest.bobycharbon.ch", True), ("https://party.bobycharbon.ch", False)])
def test_on_only_on_the_test_site_without_the_variable(monkeypatch, url, expected):
    monkeypatch.delenv("INVITES_V2_ENABLED", raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", url)
    assert features.invites_v2_enabled() is expected


def test_the_variable_decides_and_the_apps_read_it(monkeypatch):
    monkeypatch.setenv("INVITES_V2_ENABLED", "1")
    assert TestClient(main.app).get("/api/features").json()["invites_v2"] is True
    monkeypatch.setenv("INVITES_V2_ENABLED", "0")
    assert TestClient(main.app).get("/api/features").json()["invites_v2"] is False


def test_production_page_says_invites_off_and_test_site_does_not(monkeypatch, page_dir):
    monkeypatch.setenv("INVITES_V2_ENABLED", "0")
    assert '<html data-invites="off"' in TestClient(main.app).get("/events/").text
    assert 'data-invites="off"' in main.page("index.html").body.decode()
    monkeypatch.setenv("INVITES_V2_ENABLED", "1")
    assert "data-invites" not in TestClient(main.app).get("/events/").text
    assert "data-invites" not in main.page("index.html").body.decode()


# ── Aperçu riche du lien ──

def test_preview_is_read_without_session_and_never_counts_as_opened():
    acc, seen = fake({"invite_preview": CARD})
    assert event_invites.preview(acc, TOKEN) == CARD
    path, body, auth = seen[0]
    assert path == "/rest/v1/rpc/invite_preview" and json.loads(body) == {"token": TOKEN, "opened": False}
    assert "sb_publishable" in auth or auth.startswith("Bearer ")


def test_meta_says_who_invites_to_what_when_and_where_escaped():
    meta = event_invites.invite_meta({**CARD, "inviter": 'Lu"><script>x</script>'}, f"https://party.bobycharbon.ch/events/invite/{TOKEN}",
                                     "https://party.bobycharbon.ch")
    assert "<script>" not in meta
    assert 'property="og:title" content="Lu&quot;&gt;&lt;script&gt;x&lt;/script&gt; t&#x27;invite : Raclette &amp; vinyles"' in meta
    assert "sam. 14 nov. · 21:00 · Chez Ludo. Réponds en quelques secondes, sans installer d&#x27;app." in meta
    assert 'name="twitter:card" content="summary"' in meta and "icon-512.png" in meta


def test_meta_uses_the_event_poster_when_there_is_one_and_stays_generic_without_card():
    meta = event_invites.invite_meta({**CARD, "cover_url": "https://exemple.ch/affiche.jpg"}, "u", "https://party.bobycharbon.ch")
    assert 'property="og:image" content="https://exemple.ch/affiche.jpg"' in meta and "summary_large_image" in meta
    assert 'content="Tu es invité sur Party"' in event_invites.invite_meta(None, "u", "https://party.bobycharbon.ch")
    assert "javascript" not in event_invites.invite_meta({**CARD, "cover_url": "javascript:alert(1)"}, "u", "https://p.ch")


def test_invite_page_gets_the_preview_only_when_v2_is_on(monkeypatch, page_dir):
    acc, _ = fake({"invite_preview": CARD})
    monkeypatch.setattr(main, "accounts", acc)
    monkeypatch.setenv("INVITES_V2_ENABLED", "1")
    page = TestClient(main.app).get(f"/events/invite/{TOKEN}").text
    assert "Ludo t&#x27;invite : Raclette &amp; vinyles" in page
    assert f'property="og:url" content="https://party.bobycharbon.ch/events/invite/{TOKEN}"' in page
    monkeypatch.setenv("INVITES_V2_ENABLED", "0")
    assert "og:title" not in TestClient(main.app).get(f"/events/invite/{TOKEN}").text


def test_base_down_still_serves_the_page_with_a_generic_preview(monkeypatch, page_dir):
    acc, _ = fake(status=500)
    monkeypatch.setattr(main, "accounts", acc)
    monkeypatch.setenv("INVITES_V2_ENABLED", "1")
    r = TestClient(main.app).get(f"/events/invite/{TOKEN}")
    assert r.status_code == 200 and "Tu es invité sur Party" in r.text


@pytest.mark.parametrize("iso, all_day, expected", [
    ("2026-11-14T20:00:00Z", False, "sam. 14 nov. · 21:00"), ("2026-07-03T18:30:00+00:00", False, "ven. 3 juil. · 20:30"),
    ("2026-11-14T20:00:00Z", True, "sam. 14 nov."), (None, False, ""), ("pas une date", False, "")])
def test_short_date_in_swiss_time(iso, all_day, expected):
    assert event_invites.short_date(iso, all_day) == expected


# ── Base : migration additive, fichier prod prêt ──

def test_migration_is_additive_and_replayable():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert not re.search(r"\bdrop (table|column)\b", sql, re.IGNORECASE)
    assert "create table if not exists private.invite_link_arrivals" in sql
    assert "add column if not exists max_uses" in sql and "add column if not exists opened_at" in sql
    assert "add column if not exists invited_by" in sql and "add column if not exists link_token" in sql
    for fn in ("invite_preview", "accept_invite", "event_guest_list", "invite_people", "remove_invitee", "nudge_invitees",
               "nudge_invite_link", "create_event_invite"):
        assert f"create or replace function public.{fn}(" in sql, fn
    # Lisible sans compte : la carte seulement ; tout le reste demande une connexion.
    assert "grant execute on function public.invite_preview(uuid, boolean) to anon, authenticated" in sql
    assert re.search(r"revoke all on function public\.create_event_invite[^;]*from public, anon;", sql, re.S)
    # Une relance par jour et par personne ; jamais l'adresse exacte avant la réponse.
    assert "private.nudged_today(e, u, null) is not null then skipped" in sql
    assert "'location_address', case when arrived then ev.location_address end" in sql
    # Personne n'entre dans un groupe par un lien d'événement.
    assert "member_group_members (" not in sql.split("public.accept_invite")[1].split("$$;")[0]


def test_prod_files_are_ready_and_never_applied_here():
    prod = ROOT / "supabase/prod"
    apply = (prod / "2026-11-05-invitations-v2-apply.sql").read_text(encoding="utf-8")
    rollback = (prod / "2026-11-05-invitations-v2-rollback.sql").read_text(encoding="utf-8")
    assert apply.count("begin;") == 1 and "commit;" in apply and "values ('20261105200000'" in apply
    assert MIGRATION.read_text(encoding="utf-8").strip() in apply  # la même migration, mot pour mot
    assert "delete from supabase_migrations.schema_migrations where version = '20261105200000'" in rollback
    assert "drop function if exists public.accept_invite(uuid, text, text)" in rollback


def test_phone_invite_is_gone_with_v2_and_the_form_keeps_link_guests():
    picker = (ROOT / "web/events/src/components/AudiencePicker.tsx").read_text(encoding="utf-8")
    assert "invitesV2On ? (" in picker and "carte « Invités »" in picker
    form = (ROOT / "web/events/src/components/EventForm.tsx").read_text(encoding="utf-8")
    assert "staleInvites.not('user_id', 'in'" in form  # « venu par le lien » n'est plus effacé en enregistrant


def test_install_party_is_optional_and_never_rewarded():
    screen = (ROOT / "web/events/src/components/InviteCardScreen.tsx").read_text(encoding="utf-8")
    assert "Plus tard" in screen and "Installer Party" in screen
    for word in ("pièce", "bonus", "gagne", "zicou"):
        assert word not in screen.lower(), word
