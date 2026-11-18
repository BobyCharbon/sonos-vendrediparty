"""Conformité App Store du 16.11.2026 (bar et Discussions ouverts en production) : ce qui se vérifie sans la base.
Le reste (blocage signalé, tabac refusé, bar payant privé, CGU 2026-11-16) : tests/supabase_live/test_conformite_app_store_live.py."""
import plistlib
from pathlib import Path

from app import games, party_questions

ROOT = Path(__file__).resolve().parents[1]


def test_the_room_board_never_ranks_players_by_what_they_drank():
    room = {"rnames": {"a": "Ana", "b": "Bob", "c": "Cléo"}, "players": [], "rpts": {"a": 5, "b": 5},
            "rtally": {"a": {"drink": 0}, "b": {"drink": 9}, "c": {"drink": 30}}, "rhistory": [], "rvotes": {}}
    board = games.room_view(room, "a", None)["board"]
    assert [r["name"] for r in board] == ["Ana", "Bob", "Cléo"]  # points, puis nom : jamais les gorgées
    js = (ROOT / "app/static/games.js").read_text()
    assert "g-room-sips" not in js and ".filter((r) => r.pts)" in js


def test_no_question_rates_the_body_of_people_at_the_table():
    every = " ".join(q for v in vars(party_questions).values() if isinstance(v, list) for q in v if isinstance(q, str))
    for q in ("est le plus sexy au réveil", "a la tenue la plus sexy ce soir", "a le meilleur décolleté ou le meilleur torse"):
        assert q not in every


def test_terms_say_adults_only_and_that_party_never_touches_money_on_web_and_iphone():
    web = (ROOT / "web/events/src/lib/terms.ts").read_text()
    ios = (ROOT / "ios/Party/Settings/Moderation/TermsView.swift").read_text()
    for text in (web, ios):
        assert "18 novembre 2026" in text and "Réservé aux adultes" in text and "Paiements, billets et bar" in text
        assert "18 ans ou plus" in text and "Tabac et drogues sont interdits" in text
    assert "tu confirmes avoir 18 ans ou plus" in (ROOT / "web/events/src/components/TermsSheet.tsx").read_text()
    assert "tu confirmes avoir 18 ans ou plus" in (ROOT / "ios/Party/Settings/Moderation/ModerationSheets.swift").read_text()


def test_privacy_policy_and_manifest_cover_the_bar_and_voice_messages():
    for p in ("web/events/src/app/privacy.tsx", "ios/Party/Settings/Account/SignInView.swift"):
        text = (ROOT / p).read_text()
        assert "Bar de la soirée, seulement si l" in text and "6 mois après sa fermeture" in text and "18 novembre 2026" in text
    with open(ROOT / "ios/Party/PrivacyInfo.xcprivacy", "rb") as f:
        types = {e["NSPrivacyCollectedDataType"] for e in plistlib.load(f)["NSPrivacyCollectedDataTypes"]}
    assert {"NSPrivacyCollectedDataTypeAudioData", "NSPrivacyCollectedDataTypePurchaseHistory"} <= types


def test_blocked_people_are_masked_in_group_chats_on_web_and_iphone():
    assert "hidden.has(m.user_id) ? masked(m) : m" in (ROOT / "web/events/src/components/GroupChat.tsx").read_text()
    assert '"body": BLOCKED_TEXT, "photo_path": None, "audio_path": None' in (ROOT / "app/group_chats.py").read_text()
