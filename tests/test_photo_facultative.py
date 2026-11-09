"""Photo de profil facultative (décision de l'admin du 09.11.2026, Apple 5.1.1) : prénom, nom et surnom suffisent
pour voir les événements, demander à rejoindre et être accepté ; une photo donnée doit rester un fichier du membre."""
import pathlib
import re

from app import group_admin

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261109020000_photo_profil_facultative.sql"


def test_a_profile_without_photo_is_complete_for_the_group_admin():
    # Arrange
    profile = {"first_name": "Léa", "last_name": "M", "display_name": "Léa", "avatar_url": None}

    # Act / Assert
    assert group_admin.complete(profile)
    assert not group_admin.complete({**profile, "last_name": " "})


def test_the_web_module_does_not_require_a_photo():
    source = (ROOT / "web/events/src/lib/profile.ts").read_text()
    body = source[source.index("export function hasCompleteIdentity"):]
    assert "avatar_url" not in body.split("}")[0]


def test_the_ios_profile_rules_do_not_require_a_photo():
    source = (ROOT / "ios/Party/Settings/NotificationModels.swift").read_text()
    rule = re.search(r"static func isComplete\(([^)]*)\)", source)
    assert rule and "hasPhoto" not in rule.group(1)


def test_the_migration_drops_the_photo_from_every_identity_check_but_keeps_validating_a_given_photo():
    sql = MIGRATION.read_text()
    for fn in ("public.request_join", "public.guard_profile", "private.identity_complete"):
        assert f"create or replace function {fn}" in sql
    assert "coalesce(me.avatar_url, '') = ''" not in sql
    assert "btrim(p.avatar_url)" not in sql
    assert "profile_photo_invalid" in sql and "(storage.foldername(o.name))[1] = new.id::text" in sql


def test_no_visible_text_still_calls_the_photo_mandatory():
    places = [*(ROOT / "web/events/src").rglob("*.ts*"), *(ROOT / "ios/Party").rglob("*.swift"), *(ROOT / "app").glob("*.py")]
    offenders = [p.name for p in places
                 if re.search(r"son surnom et sa photo\.|surnom et photo (à compléter|obligatoires)|surnom ou photo|Obligatoire : pour que le groupe", p.read_text())]
    assert offenders == []
