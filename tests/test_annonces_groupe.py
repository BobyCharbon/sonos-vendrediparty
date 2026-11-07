"""Annonces d'événement aux groupes (décision de l'admin du 06.11.2026, migration 20261106220000) : ce qui se vérifie
sans base. Le comportement réel est testé sur la base de TEST (tests/supabase_live/test_annonces_groupe_live.py), dans
un navigateur (tests/test_annonces_groupe_browser.py) et par le banc des bots (phase « annonces »)."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from tests.test_notify_prefs import FakeAccounts

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261106220000_annonces_groupe.sql").read_text(encoding="utf-8")
APPLY = (ROOT / "supabase/prod/2026-11-06-annonces-groupe-apply.sql").read_text(encoding="utf-8")
ROLLBACK = (ROOT / "supabase/prod/2026-11-06-annonces-groupe-rollback.sql").read_text(encoding="utf-8")
WEB = ROOT / "web/events/src"
KINDS = ("announce_request", "announce_accepted", "announce_refused", "group_event_request", "group_event_accepted",
         "group_event_refused")


def test_the_three_new_switches_are_saved_from_the_native_settings(monkeypatch):
    monkeypatch.setattr(main, "accounts", FakeAccounts())
    client = TestClient(main.app)
    for key in ("announce_requests", "group_event_requests", "announce_results"):
        r = client.post("/api/account/notifications/update", json={"token": "ok", "patch": {key: False}})
        assert r.status_code == 200 and r.json()["prefs"][key] is False, key


def test_the_migration_is_additive_and_replayable():
    assert not re.search(r"\bdrop (table|column)\b", MIGRATION, re.I)
    code = "\n".join(line for line in MIGRATION.splitlines() if not line.lstrip().startswith("--"))
    for create in re.findall(r"\bcreate (?:or replace )?(\w+)", code, re.I):
        assert create.lower() in ("function", "table", "index", "policy", "trigger"), create
    assert "create table if not exists public.event_announcements" in MIGRATION
    assert all(t in MIGRATION for t in ("drop trigger if exists events_announce", "drop policy if exists"))
    assert "one_time_changes" in MIGRATION  # droit donné et existant repris une seule fois


def test_every_new_notification_follows_its_switch_on_every_channel():
    """Insertion (préférence lue avant queue_notification) ET envoi push / web push (private.web_push_allowed)."""
    for kind in KINDS:
        assert f"when ''{kind}'' then coalesce(prefs." in MIGRATION, kind  # web_push_allowed (send-push, send-web-push)
        assert f"''{kind}''" in MIGRATION.split("private.may_receive_push")[1], kind
    assert "np.announce_results" in MIGRATION and "np.announce_requests" in MIGRATION and "np.group_event_requests" in MIGRATION


def test_group_members_are_only_told_through_a_sent_announcement():
    should_invite = MIGRATION.split("create or replace function private.should_invite")[1].split("$$;")[0]
    assert "private.group_announced_to(ev.id, u)" in should_invite
    assert "ev.notify_on_publish and private.invited_in_person(ev.id, u)" in should_invite
    notify = MIGRATION.split("create or replace function public.notify_event_change")[1].split("end $$;")[0]
    assert "'new_event'" not in notify  # « Nouvel événement » aux Membres VIP : seulement par l'annonce (broadcast_new_event)


def test_first_answer_wins_and_auto_after_48_hours():
    answer = MIGRATION.split("create or replace function public.answer_announcement")[1].split("end $$;")[0]
    assert "for update" in answer and "r.status <> 'pending'" in answer and "'already', true" in answer
    auto = MIGRATION.split("create or replace function private.auto_accept_announcements")[1].split("end $$;")[0]
    assert "interval '48 hours'" in auto and "skip locked" in auto
    assert "cron.schedule('group-announcements-auto'" in MIGRATION


def test_prod_files_are_ready_but_separate():
    assert APPLY.startswith("-- PROD, annonces_groupe (20261106220000). À appliquer SEULEMENT après un « Ok prod »")
    assert "values ('20261106220000', 'annonces_groupe')" in APPLY and APPLY.count("begin;") == 1 and "commit;" in APPLY
    assert "delete from supabase_migrations.schema_migrations where version = '20261106220000'" in ROLLBACK
    assert "drop table if exists public.event_announcements" in ROLLBACK


def test_the_ai_never_turns_the_announcement_on():
    assert '"announce_group": False' in (ROOT / "app/ai_events.py").read_text(encoding="utf-8")


def test_screens_offer_the_switch_off_by_default_and_never_for_a_public_event():
    form = (WEB / "components/EventForm.tsx").read_text(encoding="utf-8")
    assert "announce_group: false," in form and "announce_group: hasGroupAudience(d.who) && d.announce_group" in form
    assert "return who.audience === 'invite' && (who.vip || who.group_ids.length > 0);" in form
    step = (WEB / "components/InviteStep.tsx").read_text(encoding="utf-8")
    # Deux interrupteurs indépendants, éteints par défaut ; jamais pour un public ni « sur invitation » (campagne 2, C1).
    assert "useState({ vip: false, group: false });" in step
    assert "(kind === 'vip' && announce.vip) || (kind === 'group' && announce.group)" in step
    lib = (WEB / "lib/groupAnnounce.ts").read_text(encoding="utf-8")
    assert "Ta demande sera envoyée à l’admin du groupe ; sans réponse sous 48 h, l’annonce part automatiquement." in lib


def test_every_switch_exists_on_the_web_and_on_the_iphone():
    web = (WEB / "app/settings/notifications.tsx").read_text(encoding="utf-8")
    ios = (ROOT / "ios/Party/Settings/NotificationSettingsView.swift").read_text(encoding="utf-8")
    for key, label in (("announce_requests", "Annonce à valider"), ("group_event_requests", "Événement à valider pour mon groupe"),
                       ("announce_results", "Réponse du groupe à mes demandes")):
        assert f"prefs.{key} !== false" in web and f'label="{label}"' in web, key
        assert f'eventToggle("{key}"' in ios and f'"{label}"' in ios, key
