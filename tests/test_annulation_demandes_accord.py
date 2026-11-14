"""Annulation et demandes d'accord (décision de l'admin, 14.11.2026) : la personne qui attend l'accord de l'organisateur
apprend l'annulation, une fois, avec l'interrupteur des annulations, sans lien vers un événement qu'elle ne voit pas.
Le refus de l'organisateur suit le même modèle (20261114201500). Recette réelle : test_notifications_recette_live.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261114220000_annulation_demandes_accord.sql").read_text(encoding="utf-8")
APPLY = (ROOT / "supabase/prod/2026-11-14-annulation-demandes-accord-apply.sql").read_text(encoding="utf-8")
ROLLBACK = (ROOT / "supabase/prod/2026-11-14-annulation-demandes-accord-rollback.sql").read_text(encoding="utf-8")
REFUS = (ROOT / "supabase/migrations/20261114201500_refus_accord_notifie.sql").read_text(encoding="utf-8")


def test_waiting_people_are_told_of_a_cancellation_once_without_a_link_to_the_event():
    sql = re.sub(r"--[^\n]*", "", MIGRATION)
    assert "old.status = 'published' and new.status = 'cancelled'" in sql
    assert "q.status = 'pending'" in sql and "np.event_changed" in sql and "event_mutes" in sql
    assert "queue_notification(u, 'event_changed', null, 'Événement annulé'" in sql  # sans event_id
    assert "'join_cancelled:' || new.id" in sql  # une seule fois par personne et par événement


def test_the_migration_is_additive_and_replayable():
    sql = re.sub(r"--[^\n]*", "", MIGRATION).lower()
    assert "create or replace function private.tell_waiting_of_cancel()" in sql
    assert "drop trigger if exists events_tell_waiting_of_cancel on public.events" in sql
    assert not re.search(r"\b(drop table|drop column|delete from|truncate)\b", sql)


def test_prod_files_apply_the_same_body_and_roll_back():
    body = MIGRATION.strip()
    assert body in APPLY and APPLY.startswith("-- PROD") and "begin;" in APPLY and APPLY.rstrip().endswith("commit;")
    assert "'20261114220000', 'annulation_demandes_accord'" in APPLY
    assert "drop trigger if exists events_tell_waiting_of_cancel" in ROLLBACK
    assert "where version = '20261114220000'" in ROLLBACK


def test_the_refusal_also_comes_without_a_link_to_the_event():
    assert "queue_notification(person, 'private_invite', null, ev.title" in REFUS
