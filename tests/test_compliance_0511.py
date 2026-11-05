"""Contrôle App Store du 05.11.2026 (audit final), points orange :
- O1 : plus de « cul sec » nulle part (Apple TV comprise) ;
- O2 : signaler un événement (type « event ») et filtre de contenu sur son titre et sa description ;
- O3 : textes de permission et d'écran fidèles à ce qui existe en production (micro, invitation, dictée) ;
- O6 : Casino et Blackjack masqués sur l'Apple TV de l'App Store, comme sur l'iPhone."""
import pathlib
import re

import pytest

from app import main, moderation_api
from app.accounts import AccountError
from app.ai_events import clean_event_text

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261105180000_signaler_evenement.sql"
PROD = ROOT / "supabase/prod"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# ── O1 ──
def test_no_bottoms_up_anywhere_in_the_apps():
    hits = [str(p.relative_to(ROOT)) for base in ("app", "ios", "web/events/src")
            for p in (ROOT / base).rglob("*") if p.is_file() and p.suffix in (".py", ".js", ".swift", ".ts", ".tsx", ".html")
            and "/build/" not in str(p) and "Tests/" not in str(p) and "cul sec" in p.read_text(encoding="utf-8", errors="ignore").lower()]
    assert hits == []
    assert 'detail: "Un shot (ou un verre d\'eau)"' in read("ios/PartyTV/Outcome.swift")


# ── O2 ──
def test_event_is_a_report_kind_everywhere():
    assert "event" in moderation_api.KINDS
    assert "| 'event'" in read("web/events/src/lib/moderation.ts")
    assert "event: 'Événement'" in read("web/events/src/app/admin/reports.tsx")
    assert '"event": "Événement"' in read("ios/Party/Settings/Moderation/ModerationModels.swift")


def test_event_page_and_public_link_offer_report():
    page = read("web/events/src/app/event/[id]/index.tsx")
    assert "Signaler cet événement" in page and "kind: 'event'" in page and "ev.created_by !== me.id" in page
    public = read("web/events/src/app/share/[id].tsx")
    assert "Signaler cet événement" in public and "kind: 'event'" in public and "SUPPORT_EMAIL" in public


def test_migration_is_additive_and_filters_title_and_description():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(r"target_kind in \([^)]*'event'", sql)
    assert "drop trigger if exists events_moderation" in sql
    assert "before insert or update of title, description on public.events" in sql
    assert "event_text_verdict(new.title, 'le titre')" in sql and "event_text_verdict(new.description, 'la description')" in sql
    assert not re.search(r"\bdrop (table|column)\b", sql, re.IGNORECASE)


def test_prod_files_are_ready():
    apply = (PROD / "2026-11-05-signaler-evenement-apply.sql").read_text(encoding="utf-8")
    rollback = (PROD / "2026-11-05-signaler-evenement-rollback.sql").read_text(encoding="utf-8")
    assert apply.count("begin;") == 1 and "commit;" in apply and "values ('20261105180000'" in apply
    assert "2026-11-04-moderation" in apply  # prérequis noté
    assert "delete from supabase_migrations.schema_migrations where version = '20261105180000'" in rollback
    assert "drop trigger if exists events_moderation" in rollback


def test_assistant_filters_event_texts_before_writing():
    assert clean_event_text("Soirée chez Léa", "le titre") == "Soirée chez Léa"
    assert clean_event_text("Soirée des connards", "le titre") == "Soirée des ••••••••"  # insulte d'un mot masquée
    assert clean_event_text("Infos : www.exemple.ch, 079 123 45 67", "la description").startswith("Infos")  # liens permis
    with pytest.raises(AccountError, match="Événement non enregistré : le titre contient des propos haineux"):
        clean_event_text("sale nègre", "le titre")


# ── O3 ──
def test_microphone_texts_describe_only_what_ships():
    # project.yml est la source (Info.plist est régénéré par xcodegen et n'est pas suivi par git).
    for path in [p for p in ("ios/project.yml", "ios/Party/Info.plist") if (ROOT / p).exists()]:
        text = read(path)
        mic = re.search(r"NSMicrophoneUsageDescription(</key>\s*<string>|: \")([^<\"]+)", text).group(2)
        assert "Discussions" not in mic and "jeux" not in mic and "dicter" in mic
        speech = re.search(r"NSSpeechRecognitionUsageDescription(</key>\s*<string>|: \")([^<\"]+)", text).group(2)
        assert "Apple" in speech


def test_invite_screen_mentions_group_chats_only_when_open():
    screen = read("web/events/src/components/AppJoinScreen.tsx")
    assert "discussionsOn ? 'Événements, discussions de groupe" in screen
    assert "'Événements, jeux et musique de la soirée'" in screen


def test_privacy_names_the_dictation_services():
    privacy = read("web/events/src/app/privacy.tsx")
    assert "faite par ton téléphone" not in privacy
    assert "service vocal de ton système" in privacy and "Apple (Dictée)" in privacy and "dictée vocale dans Chrome" in privacy


# ── O6 ──
def test_apple_tv_hides_the_same_games_as_the_iphone():
    views = read("ios/PartyTV/GameViews.swift")
    hidden = set(re.search(r'static let hidden: Set<String> = \[([^\]]*)\]', views).group(1).replace('"', "").replace(" ", "").split(","))
    assert hidden == set(main.STORE_HIDDEN_GAMES)
    assert "StoreGames.hides(game)" in views and 'hasSuffix(".beta")' in views
    assert "StoreGames.hides(g)" in read("ios/PartyTV/Outcome.swift")
    assert "StoreGames.name(" in read("ios/PartyTV/WatchScreen.swift") and "StoreGames.name(g)" in read("ios/PartyTV/Screens.swift")
